"""
Plano A Intelligence Hub
Análise automatizada de faturas das operadoras de saúde.
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from io import BytesIO
from datetime import datetime

from modules.base_loader       import carregar_base, filtrar_convenio
from modules.pdf_parser        import parsear_pdf
from modules.invoice_processor import carregar_fatura
from modules.validator         import cruzar, resumo_por_locacao, resumo_geral
from modules.report_generator  import gerar_excel


# ── configurações da página ──────────────────────────────────────────────────
# (configuração deve vir antes de qualquer outro st.*)

st.set_page_config(
    page_title="Plano A — Intelligence Hub",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Autenticação ─────────────────────────────────────────────────────────────
def _check_senha():
    """Tela de login simples. Senha definida nos Secrets do Streamlit Cloud."""
    senha_correta = st.secrets.get("APP_PASSWORD", "planoa2026")
    if "autenticado" not in st.session_state:
        st.session_state["autenticado"] = False

    if not st.session_state["autenticado"]:
        st.markdown("""
        <div style='max-width:380px;margin:80px auto;text-align:center;'>
            <h2 style='color:#0D2B6B;'>🏥 Plano A Intelligence Hub</h2>
            <p style='color:#555;'>Acesso restrito — insira a senha para continuar</p>
        </div>
        """, unsafe_allow_html=True)

        col_c, col_m, col_c2 = st.columns([1, 2, 1])
        with col_m:
            senha = st.text_input("Senha", type="password", key="senha_input")
            if st.button("Entrar", type="primary", use_container_width=True):
                if senha == senha_correta:
                    st.session_state["autenticado"] = True
                    st.rerun()
                else:
                    st.error("Senha incorreta.")
        st.stop()

_check_senha()

# ── CSS Plano A ───────────────────────────────────────────────────────────────
st.markdown("""
<style>
    .main { background-color: #F8FBFF; }
    .stMetric { background: white; border-radius: 10px; padding: 10px;
                border-left: 4px solid #0D2B6B; box-shadow: 2px 2px 6px rgba(0,0,0,0.08); }
    .block-container { padding-top: 1.5rem; }
    h1, h2, h3 { color: #0D2B6B; }
    .alerta { background: #FADBD8; border-radius: 8px; padding: 10px;
              border-left: 4px solid #E74C3C; margin: 6px 0; }
    .ok     { background: #D5F5E3; border-radius: 8px; padding: 10px;
              border-left: 4px solid #27AE60; margin: 6px 0; }
</style>
""", unsafe_allow_html=True)


# ── cabeçalho ─────────────────────────────────────────────────────────────────
col_logo, col_title = st.columns([1, 6])
with col_logo:
    st.markdown("### 🏥")
with col_title:
    st.markdown("## Plano A — Intelligence Hub")
    st.caption("Análise automatizada de faturas · SELECT e SALV SAÚDE")

st.divider()


# ════════════════════════════════════════════════════════════════════════════
# SIDEBAR — UPLOAD DOS ARQUIVOS
# ════════════════════════════════════════════════════════════════════════════
with st.sidebar:
    st.image("https://via.placeholder.com/200x60/0D2B6B/FFFFFF?text=Plano+A", use_container_width=True)
    st.markdown("### 📂 Carregar Arquivos")

    mes_ref = st.text_input("Mês de referência (ex: Abril/2026)", value="")

    st.markdown("---")
    st.markdown("**Base Plano A (dinâmica)**")
    base_file = st.file_uploader("📋 Base (.xlsx)", type=["xlsx"], key="base")

    st.markdown("---")
    st.markdown("**SELECT**")
    sel_excel = st.file_uploader("📊 Fatura Excel (.xlsx)", type=["xlsx"], key="sel_xls")
    sel_pdf   = st.file_uploader("📄 Fatura PDF (.pdf)",   type=["pdf"],  key="sel_pdf")

    st.markdown("---")
    st.markdown("**SALV SAÚDE**")
    sal_excel = st.file_uploader("📊 Fatura Excel (.xlsx)", type=["xlsx"], key="sal_xls")
    sal_pdf   = st.file_uploader("📄 Fatura PDF (.pdf)",   type=["pdf"],  key="sal_pdf")

    st.markdown("---")
    processar = st.button("⚡ PROCESSAR FATURAS", type="primary", use_container_width=True)

    st.markdown("---")
    st.caption("Plano A Administradora · v1.0\nDesenv. Patrick Rodrigues & Diego Nobre")


# ════════════════════════════════════════════════════════════════════════════
# ESTADO DE SESSÃO
# ════════════════════════════════════════════════════════════════════════════
if "resultado" not in st.session_state:
    st.session_state["resultado"] = None


# ════════════════════════════════════════════════════════════════════════════
# PROCESSAMENTO
# ════════════════════════════════════════════════════════════════════════════
def _bytes(f):
    """Lê o file-uploader e devolve BytesIO resetado."""
    data = f.read()
    f.seek(0)
    return BytesIO(data)


if processar:
    if not base_file:
        st.error("⚠️ Por favor, carregue a Base Plano A antes de processar.")
        st.stop()

    erros = []
    if not sel_excel: erros.append("Fatura Excel da SELECT")
    if not sel_pdf:   erros.append("PDF da SELECT")
    if not sal_excel: erros.append("Fatura Excel da SALV")
    if not sal_pdf:   erros.append("PDF da SALV")
    if erros:
        st.warning(f"⚠️ Arquivos ausentes: {', '.join(erros)}. Processando apenas os disponíveis.")

    with st.spinner("Carregando base Plano A…"):
        base = carregar_base(_bytes(base_file))

    resultado = {}

    # ---- SELECT ----
    if sel_excel and sel_pdf:
        with st.spinner("Processando SELECT…"):
            pdf_data  = parsear_pdf(_bytes(sel_pdf), "SELECT")
            fatura_sel = carregar_fatura(_bytes(sel_excel), "SELECT", pdf_data["locacoes"])
            df_sel, div_sel = cruzar(fatura_sel, filtrar_convenio(base, "SELECT"))
            resultado["select"] = {
                "df":          df_sel,
                "divergencias": div_sel,
                "resumo":      resumo_geral(df_sel),
                "por_locacao": resumo_por_locacao(df_sel),
                "totais_pdf":  pdf_data["totais_pdf"],
            }
    else:
        resultado["select"] = None

    # ---- SALV ----
    if sal_excel and sal_pdf:
        with st.spinner("Processando SALV SAÚDE…"):
            pdf_data  = parsear_pdf(_bytes(sal_pdf), "SALV")
            fatura_sal = carregar_fatura(_bytes(sal_excel), "SALV", pdf_data["locacoes"])
            df_sal, div_sal = cruzar(fatura_sal, filtrar_convenio(base, "SALV"))
            resultado["salv"] = {
                "df":          df_sal,
                "divergencias": div_sal,
                "resumo":      resumo_geral(df_sal),
                "por_locacao": resumo_por_locacao(df_sal),
                "totais_pdf":  pdf_data["totais_pdf"],
            }
    else:
        resultado["salv"] = None

    resultado["mes_ref"] = mes_ref
    st.session_state["resultado"] = resultado
    st.success("✅ Processamento concluído!")


# ════════════════════════════════════════════════════════════════════════════
# EXIBIÇÃO DOS RESULTADOS
# ════════════════════════════════════════════════════════════════════════════
res = st.session_state.get("resultado")

if res is None:
    st.info("👈 Carregue os arquivos e clique em **PROCESSAR FATURAS** para começar.")
    st.markdown("""
    #### Como usar:
    1. Faça upload da **Base Plano A** (planilha dinâmica)
    2. Carregue a **fatura Excel + PDF** da SELECT
    3. Carregue a **fatura Excel + PDF** da SALV SAÚDE
    4. Clique em **PROCESSAR FATURAS**
    5. Visualize os resultados e baixe o relatório Excel completo
    """)
    st.stop()


# ── Tabs principais ───────────────────────────────────────────────────────────
tab_ceo, tab_sel, tab_sal, tab_div, tab_export = st.tabs([
    "📊 Dashboard CEO",
    "🔵 SELECT",
    "🟢 SALV SAÚDE",
    "⚠️ Divergências",
    "📥 Exportar Excel",
])


# ============================================================================
# TAB 1 — DASHBOARD CEO
# ============================================================================
with tab_ceo:
    st.subheader(f"Visão Executiva Consolidada · {res.get('mes_ref','')}")

    r_sel = res["select"]["resumo"]  if res.get("select") else {}
    r_sal = res["salv"]["resumo"]    if res.get("salv")   else {}

    def _s(d, k): return d.get(k, 0) or 0

    total_geral    = _s(r_sel,"total_fatura")    + _s(r_sal,"total_fatura")
    vidas_cobradas = _s(r_sel,"vidas_cobradas")  + _s(r_sal,"vidas_cobradas")
    vidas_inat     = _s(r_sel,"vidas_inativas")  + _s(r_sal,"vidas_inativas")
    nao_enc        = _s(r_sel,"nao_encontrados") + _s(r_sal,"nao_encontrados")
    total_div      = (len(res["select"]["divergencias"]) if res.get("select") else 0) + \
                     (len(res["salv"]["divergencias"])   if res.get("salv")   else 0)

    # KPIs principais
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("💰 Total Geral da Fatura",   f"R$ {total_geral:,.2f}")
    c2.metric("👥 Vidas Cobradas",          f"{vidas_cobradas:,}")
    c3.metric("⚠️ Vidas Inativas/Susp.",    f"{vidas_inat:,}",
              delta=f"R$ {_s(r_sel,'total_fatura') * (_s(r_sel,'vidas_inativas')/_s(r_sel,'vidas_cobradas') if _s(r_sel,'vidas_cobradas') else 0):.0f} risco" if vidas_inat else None,
              delta_color="inverse")
    c4.metric("❓ Não na Base",             f"{nao_enc:,}", delta_color="inverse")
    c5.metric("🔍 Divergências",            f"{total_div:,}", delta_color="inverse")

    st.divider()

    # Comparativo SELECT x SALV
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### Por Operadora")
        data_ops = {
            "Operadora":       ["SELECT",                  "SALV SAÚDE"],
            "Total (R$)":      [_s(r_sel,"total_fatura"),  _s(r_sal,"total_fatura")],
            "Mensalidade":     [_s(r_sel,"total_mensalid"),_s(r_sal,"total_mensalid")],
            "Pro Rata":        [_s(r_sel,"total_prorrata"),_s(r_sal,"total_prorrata")],
            "Coparticipação":  [_s(r_sel,"total_copat"),   _s(r_sal,"total_copat")],
            "Vidas":           [_s(r_sel,"vidas_cobradas"),_s(r_sal,"vidas_cobradas")],
            "Inativos":        [_s(r_sel,"vidas_inativas"),_s(r_sal,"vidas_inativas")],
        }
        st.dataframe(
            pd.DataFrame(data_ops).style.format({
                "Total (R$)": "R$ {:,.2f}",
                "Mensalidade": "R$ {:,.2f}",
                "Pro Rata": "R$ {:,.2f}",
                "Coparticipação": "R$ {:,.2f}",
            }),
            hide_index=True, use_container_width=True
        )

    with col2:
        st.markdown("#### Composição do Total Geral")
        labels = ["Mensalidade", "Pro Rata", "Coparticipação", "Outros"]
        values = [
            _s(r_sel,"total_mensalid") + _s(r_sal,"total_mensalid"),
            _s(r_sel,"total_prorrata") + _s(r_sal,"total_prorrata"),
            _s(r_sel,"total_copat")    + _s(r_sal,"total_copat"),
            _s(r_sel,"total_outros")   + _s(r_sal,"total_outros"),
        ]
        values = [v for v in values if v > 0]
        labels = [l for l, v in zip(labels, [
            _s(r_sel,"total_mensalid")+_s(r_sal,"total_mensalid"),
            _s(r_sel,"total_prorrata")+_s(r_sal,"total_prorrata"),
            _s(r_sel,"total_copat")+_s(r_sal,"total_copat"),
            _s(r_sel,"total_outros")+_s(r_sal,"total_outros"),
        ]) if v > 0]

        if any(v > 0 for v in values):
            fig = go.Figure(data=[go.Pie(
                labels=labels, values=values, hole=0.45,
                marker_colors=["#0D2B6B","#2874A6","#5DADE2","#AED6F1"],
                textinfo="label+percent", textfont_size=12,
            )])
            fig.update_layout(
                margin=dict(t=0, b=0, l=0, r=0),
                legend=dict(orientation="h", yanchor="bottom", y=-0.2),
                height=280
            )
            st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # Top locações por valor
    st.markdown("#### Top Locações por Valor Total")
    dfs = []
    if res.get("select"):
        d = res["select"]["por_locacao"].copy()
        d["Operadora"] = "SELECT"
        dfs.append(d)
    if res.get("salv"):
        d = res["salv"]["por_locacao"].copy()
        d["Operadora"] = "SALV"
        dfs.append(d)

    if dfs:
        df_all_loc = pd.concat(dfs, ignore_index=True)
        df_top = df_all_loc.sort_values("total_locacao", ascending=False).head(15)

        fig2 = px.bar(
            df_top, x="total_locacao", y="Locação",
            color="Operadora", orientation="h",
            color_discrete_map={"SELECT": "#0D2B6B", "SALV": "#27AE60"},
            labels={"total_locacao": "Valor Total (R$)", "Locação": ""},
            height=420,
        )
        fig2.update_layout(
            margin=dict(t=10, b=0, l=0, r=0),
            legend=dict(orientation="h", yanchor="bottom", y=-0.15),
            yaxis=dict(categoryorder="total ascending"),
            xaxis_tickprefix="R$ ",
        )
        st.plotly_chart(fig2, use_container_width=True)

    # Alertas
    if vidas_inat > 0 or nao_enc > 0:
        st.markdown("#### 🔴 Alertas Prioritários")
        if vidas_inat > 0:
            st.markdown(f'<div class="alerta">🚨 <b>{vidas_inat} vidas inativas/suspensas</b> estão sendo cobradas nas faturas. Verificar imediatamente para contestação.</div>', unsafe_allow_html=True)
        if nao_enc > 0:
            st.markdown(f'<div class="alerta">❓ <b>{nao_enc} beneficiários</b> não encontrados na base Plano A. Podem ser inclusões não registradas.</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="ok">✅ Nenhum alerta crítico identificado nesta fatura.</div>', unsafe_allow_html=True)


# ============================================================================
# TAB 2 — SELECT
# ============================================================================
def _render_operadora(tab, res_op, nome):
    if res_op is None:
        tab.info(f"Nenhuma fatura da {nome} foi carregada.")
        return

    r = res_op["resumo"]
    df = res_op["df"]
    por_loc = res_op["por_locacao"]
    divs = res_op["divergencias"]

    def _s(k): return r.get(k, 0) or 0

    tab.markdown(f"### {nome} — Análise da Fatura")

    c1, c2, c3, c4 = tab.columns(4)
    c1.metric("💰 Total Fatura",          f"R$ {_s('total_fatura'):,.2f}")
    c2.metric("👥 Vidas Cobradas",         f"{_s('vidas_cobradas'):,}")
    c3.metric("⚠️ Inativas/Suspensas",    f"{_s('vidas_inativas'):,}", delta_color="inverse")
    c4.metric("🔍 Divergências",           f"{len(divs):,}", delta_color="inverse")

    tab.divider()

    col_a, col_b = tab.columns([3, 2])

    with col_a:
        tab.markdown("#### Por Locação")
        cols_show = ["Locação","qtd_vidas","vidas_ativas","vidas_inativas",
                     "MENSALIDADE","PRO_RATA","COPARTICIPACAO","total_locacao"]
        cols_exist = [c for c in cols_show if c in por_loc.columns]
        tab.dataframe(
            por_loc[cols_exist].style.format({
                "MENSALIDADE": "R$ {:,.2f}",
                "PRO_RATA": "R$ {:,.2f}",
                "COPARTICIPACAO": "R$ {:,.2f}",
                "total_locacao": "R$ {:,.2f}",
            }),
            hide_index=True, use_container_width=True, height=350
        )

    with col_b:
        tab.markdown("#### Por Tipo de Cobrança")
        tipo_grp = df.groupby("tipo_cobranca")["valor"].sum().reset_index()
        tipo_grp.columns = ["Tipo", "Valor (R$)"]
        fig = px.bar(tipo_grp, x="Tipo", y="Valor (R$)",
                     color="Tipo", text_auto=".2s",
                     color_discrete_sequence=["#0D2B6B","#2874A6","#5DADE2","#AED6F1"])
        fig.update_layout(showlegend=False, margin=dict(t=10, b=0), height=280)
        tab.plotly_chart(fig, use_container_width=True)

    tab.divider()
    tab.markdown("#### Detalhamento (amostra — 500 linhas)")
    col_view = ["nome_ben_fat","cpf_ben","locacao_pdf","entidade","tipo_cobranca",
                "valor","valor_net","status_ben","categoria"]
    col_ex = [c for c in col_view if c in df.columns]
    tab.dataframe(df[col_ex].head(500), hide_index=True, use_container_width=True)


with tab_sel:
    _render_operadora(tab_sel, res.get("select"), "SELECT")

with tab_sal:
    _render_operadora(tab_sal, res.get("salv"), "SALV SAÚDE")


# ============================================================================
# TAB 3 — DIVERGÊNCIAS
# ============================================================================
with tab_div:
    st.subheader("⚠️ Divergências para Contestação")

    div_sel = res["select"]["divergencias"] if res.get("select") else pd.DataFrame()
    div_sal = res["salv"]["divergencias"]   if res.get("salv")   else pd.DataFrame()
    df_all_div = pd.concat([div_sel, div_sal], ignore_index=True)

    if df_all_div.empty:
        st.success("✅ Nenhuma divergência encontrada!")
    else:
        st.error(f"🔴 {len(df_all_div)} divergências encontradas")

        # Filtros
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            ops = ["Todas"] + sorted(df_all_div["Operadora"].dropna().unique().tolist())
            op_filter = st.selectbox("Operadora", ops)
        with col_f2:
            campos = ["Todos"] + sorted(df_all_div["Campo"].dropna().unique().tolist())
            campo_filter = st.selectbox("Tipo de Divergência", campos)

        df_show = df_all_div.copy()
        if op_filter != "Todas":
            df_show = df_show[df_show["Operadora"] == op_filter]
        if campo_filter != "Todos":
            df_show = df_show[df_show["Campo"] == campo_filter]

        st.dataframe(df_show, hide_index=True, use_container_width=True)

        col_m1, col_m2 = st.columns(2)
        with col_m1:
            fig_campo = px.bar(
                df_all_div.groupby("Campo").size().reset_index(name="Qtd"),
                x="Campo", y="Qtd", title="Divergências por Tipo",
                color="Campo"
            )
            fig_campo.update_layout(showlegend=False, margin=dict(t=30, b=0), height=250)
            st.plotly_chart(fig_campo, use_container_width=True)

        with col_m2:
            fig_op = px.pie(
                df_all_div.groupby("Operadora").size().reset_index(name="Qtd"),
                names="Operadora", values="Qtd",
                title="Divergências por Operadora",
                color_discrete_map={"SELECT": "#0D2B6B", "SALV SAUDE": "#27AE60"}
            )
            fig_op.update_layout(margin=dict(t=30, b=0), height=250)
            st.plotly_chart(fig_op, use_container_width=True)


# ============================================================================
# TAB 4 — EXPORTAR
# ============================================================================
with tab_export:
    st.subheader("📥 Exportar Relatório Excel")
    st.markdown("""
    O relatório inclui:
    - **RESUMO CEO** — Visão executiva consolidada com KPIs
    - **SELECT_POR_LOCACAO** — Agrupado por locação/associação
    - **SALV_POR_LOCACAO** — Agrupado por locação/associação
    - **SELECT_DETALHADO** — Linha a linha com status e divergências
    - **SALV_DETALHADO** — Linha a linha com status e divergências
    - **DIVERGENCIAS** — Lista para contestação junto às operadoras
    - **COPARTICIPACAO** — Valores para cobrar no sistema Plano A
    """)

    st.divider()

    df_sel_exp = res["select"]["df"]          if res.get("select") else pd.DataFrame()
    df_sal_exp = res["salv"]["df"]            if res.get("salv")   else pd.DataFrame()
    rs_exp     = res["select"]["resumo"]      if res.get("select") else {}
    ra_exp     = res["salv"]["resumo"]        if res.get("salv")   else {}
    rl_sel     = res["select"]["por_locacao"] if res.get("select") else pd.DataFrame()
    rl_sal     = res["salv"]["por_locacao"]   if res.get("salv")   else pd.DataFrame()
    div_sel_ex = res["select"]["divergencias"] if res.get("select") else pd.DataFrame()
    div_sal_ex = res["salv"]["divergencias"]   if res.get("salv")   else pd.DataFrame()
    mes        = res.get("mes_ref", datetime.now().strftime("%B/%Y"))

    with st.spinner("Gerando relatório Excel…"):
        excel_bytes = gerar_excel(
            df_sel_exp, df_sal_exp,
            rs_exp, ra_exp,
            rl_sel, rl_sal,
            div_sel_ex, div_sal_ex,
            mes_ref=mes
        )

    nome_arquivo = f"PlanoA_Analise_{mes.replace('/','_').replace(' ','_') or datetime.now().strftime('%Y%m')}.xlsx"
    st.download_button(
        label="⬇️  BAIXAR RELATÓRIO EXCEL COMPLETO",
        data=excel_bytes,
        file_name=nome_arquivo,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        type="primary",
        use_container_width=True,
    )

    st.caption(f"Arquivo: {nome_arquivo}")

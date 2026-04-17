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
import base64
from pathlib import Path

from modules.base_loader       import carregar_base, filtrar_convenio
from modules.pdf_parser        import parsear_pdf
from modules.invoice_processor import carregar_fatura, carregar_fatura_salv_csv
from modules.validator         import cruzar, resumo_por_locacao, resumo_geral
from modules.report_generator  import gerar_excel


# ── Configuração da página ────────────────────────────────────────────────────
st.set_page_config(
    page_title="Plano A — Intelligence Hub",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ── Helpers visuais ───────────────────────────────────────────────────────────
def _img_base64(path: str) -> str:
    try:
        data = Path(path).read_bytes()
        return base64.b64encode(data).decode()
    except Exception:
        return ""

LOGO_B64 = _img_base64("assets/logo.png")
LOGO_HTML = f'<img src="data:image/png;base64,{LOGO_B64}" style="height:56px;">' if LOGO_B64 else ""


# ── CSS Global ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
/* ---------- reset & fundo ---------- */
.main { background: #F0F4FA; }
.block-container { padding: 1.2rem 2rem 2rem 2rem; }

/* ---------- barra superior customizada ---------- */
.topbar {
    display: flex; align-items: center; gap: 20px;
    background: linear-gradient(135deg, #0D2B6B 0%, #1A4A9C 100%);
    border-radius: 14px; padding: 18px 28px; margin-bottom: 24px;
    box-shadow: 0 4px 20px rgba(13,43,107,0.25);
}
.topbar-text h1 {
    margin: 0; font-size: 1.55rem; font-weight: 700;
    color: #ffffff; letter-spacing: 0.3px;
}
.topbar-text p {
    margin: 0; font-size: 0.82rem; color: #A9C4F0; letter-spacing: 0.5px;
}

/* ---------- card de KPI ---------- */
.kpi-card {
    background: white; border-radius: 12px;
    padding: 18px 20px; margin-bottom: 8px;
    border-left: 5px solid #0D2B6B;
    box-shadow: 0 2px 12px rgba(0,0,0,0.07);
    transition: transform 0.15s;
}
.kpi-card:hover { transform: translateY(-2px); }
.kpi-card.alert { border-left-color: #E74C3C; }
.kpi-card.warn  { border-left-color: #F39C12; }
.kpi-card.ok    { border-left-color: #27AE60; }
.kpi-label { font-size: 0.75rem; color: #7F8C8D; text-transform: uppercase;
             letter-spacing: 0.8px; margin-bottom: 4px; }
.kpi-value { font-size: 1.6rem; font-weight: 700; color: #0D2B6B; line-height: 1.1; }
.kpi-sub   { font-size: 0.75rem; color: #95A5A6; margin-top: 3px; }

/* ---------- seção / subtítulo ---------- */
.section-title {
    font-size: 0.9rem; font-weight: 700; color: #0D2B6B;
    text-transform: uppercase; letter-spacing: 1px;
    border-bottom: 2px solid #D6EAF8; padding-bottom: 6px;
    margin: 20px 0 12px 0;
}

/* ---------- badge operadora ---------- */
.badge-sel { background:#0D2B6B; color:white; border-radius:20px;
             padding:3px 12px; font-size:0.75rem; font-weight:600; }
.badge-sal { background:#27AE60; color:white; border-radius:20px;
             padding:3px 12px; font-size:0.75rem; font-weight:600; }

/* ---------- alerta / ok ---------- */
.alerta-box {
    background:#FDF2F2; border:1px solid #F5B7B1; border-radius:10px;
    padding:12px 16px; margin:6px 0; display:flex; align-items:center; gap:10px;
}
.ok-box {
    background:#F0FBF4; border:1px solid #A9DFBF; border-radius:10px;
    padding:12px 16px; margin:6px 0; display:flex; align-items:center; gap:10px;
}

/* ---------- sidebar ---------- */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0D2B6B 0%, #1A3A7A 100%);
}
[data-testid="stSidebar"] * { color: #D6EAF8 !important; }
[data-testid="stSidebar"] .stButton button {
    background: linear-gradient(135deg, #2ECC71, #27AE60) !important;
    color: white !important; border-radius: 8px !important;
    font-weight: 700 !important; border: none !important;
    box-shadow: 0 3px 10px rgba(39,174,96,0.4) !important;
}
[data-testid="stSidebar"] label { color: #A9C4F0 !important; font-size:0.8rem !important; }
[data-testid="stSidebar"] .stFileUploader {
    background: rgba(255,255,255,0.08) !important;
    border-radius: 8px !important; padding: 6px !important;
}
[data-testid="stSidebar"] .stTextInput input {
    background: rgba(255,255,255,0.12) !important;
    border: 1px solid rgba(255,255,255,0.2) !important;
    color: white !important; border-radius: 6px !important;
}

/* ---------- tabs ---------- */
.stTabs [data-baseweb="tab-list"] {
    background: white; border-radius: 10px;
    padding: 4px; gap: 2px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.06);
}
.stTabs [data-baseweb="tab"] {
    border-radius: 8px !important; font-weight: 600;
    padding: 8px 18px !important; color: #5D6D7E !important;
}
.stTabs [aria-selected="true"] {
    background: linear-gradient(135deg,#0D2B6B,#1A4A9C) !important;
    color: white !important;
}

/* ---------- dataframe ---------- */
[data-testid="stDataFrame"] { border-radius: 10px; overflow: hidden; }

/* ---------- tela de login ---------- */
.login-card {
    max-width: 420px; margin: 60px auto;
    background: white; border-radius: 20px;
    padding: 48px 40px; text-align: center;
    box-shadow: 0 8px 40px rgba(13,43,107,0.15);
}
.login-card h2 { color: #0D2B6B; margin: 16px 0 6px 0; font-size: 1.4rem; }
.login-card p  { color: #7F8C8D; font-size: 0.88rem; margin-bottom: 28px; }
</style>
""", unsafe_allow_html=True)


# ── Autenticação ──────────────────────────────────────────────────────────────
def _check_senha():
    senha_correta = st.secrets.get("APP_PASSWORD", "planoa2026")
    if "autenticado" not in st.session_state:
        st.session_state["autenticado"] = False

    if not st.session_state["autenticado"]:
        col_l, col_m, col_r = st.columns([1, 1.4, 1])
        with col_m:
            st.markdown(f"""
            <div class="login-card">
                <div style="display:flex;justify-content:center;margin-bottom:8px;">
                    {LOGO_HTML}
                </div>
                <h2>Intelligence Hub</h2>
                <p>Acesso restrito — insira a senha para continuar</p>
            </div>
            """, unsafe_allow_html=True)
            senha = st.text_input("Senha de acesso", type="password",
                                  placeholder="••••••••••", label_visibility="collapsed")
            if st.button("Entrar", type="primary", use_container_width=True):
                if senha == senha_correta:
                    st.session_state["autenticado"] = True
                    st.rerun()
                else:
                    st.error("Senha incorreta. Tente novamente.")
        st.stop()

_check_senha()


# ── Barra superior ────────────────────────────────────────────────────────────
st.markdown(f"""
<div class="topbar">
    <div>{LOGO_HTML}</div>
    <div class="topbar-text">
        <h1>Intelligence Hub</h1>
        <p>ANÁLISE AUTOMATIZADA DE FATURAS · SELECT &amp; SALV SAÚDE</p>
    </div>
</div>
""", unsafe_allow_html=True)


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(f"""
    <div style="text-align:center;padding:12px 0 20px 0;">
        {LOGO_HTML}
        <div style="color:#A9C4F0;font-size:0.72rem;margin-top:8px;letter-spacing:1px;">
            INTELLIGENCE HUB
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown('<div style="border-top:1px solid rgba(255,255,255,0.1);margin-bottom:16px;"></div>', unsafe_allow_html=True)

    mes_ref = st.text_input("Mês de referência", placeholder="Ex: Abril/2026", value="")

    st.markdown('<p style="font-size:0.8rem;font-weight:700;margin:12px 0 6px 0;">BASE PLANO A</p>', unsafe_allow_html=True)
    base_file = st.file_uploader("Base dinâmica (.xlsx)", type=["xlsx"], key="base", label_visibility="collapsed")

    st.markdown('<p style="font-size:0.8rem;font-weight:700;margin:12px 0 6px 0;">SELECT</p>', unsafe_allow_html=True)
    sel_excel = st.file_uploader("Fatura Excel", type=["xlsx"], key="sel_xls", label_visibility="collapsed")
    sel_pdf   = st.file_uploader("Fatura PDF",   type=["pdf"],  key="sel_pdf", label_visibility="collapsed")

    st.markdown('<p style="font-size:0.8rem;font-weight:700;margin:12px 0 6px 0;">SALV SAÚDE</p>', unsafe_allow_html=True)
    sal_csvs  = st.file_uploader("Faturas CSV (selecione todos os arquivos)", type=["csv"], key="sal_csv", label_visibility="collapsed", accept_multiple_files=True)
    sal_pdf   = st.file_uploader("Fatura PDF (opcional)",   type=["pdf"],  key="sal_pdf", label_visibility="collapsed")

    st.markdown('<div style="margin:20px 0 8px 0;"></div>', unsafe_allow_html=True)
    processar = st.button("⚡  PROCESSAR FATURAS", type="primary", use_container_width=True)

    st.markdown('<div style="border-top:1px solid rgba(255,255,255,0.1);margin-top:20px;padding-top:12px;"></div>', unsafe_allow_html=True)
    st.markdown('<p style="font-size:0.68rem;color:#7F8C8D;text-align:center;">Patrick Rodrigues · Diego Nobre<br>Plano A Administradora · v1.0</p>', unsafe_allow_html=True)


# ── Helpers de UI ─────────────────────────────────────────────────────────────
def kpi(label, value, sub="", tipo="normal"):
    css = {"alert": "alert", "warn": "warn", "ok": "ok"}.get(tipo, "")
    st.markdown(f"""
    <div class="kpi-card {css}">
        <div class="kpi-label">{label}</div>
        <div class="kpi-value">{value}</div>
        {"<div class='kpi-sub'>"+sub+"</div>" if sub else ""}
    </div>""", unsafe_allow_html=True)

def section(title):
    st.markdown(f'<div class="section-title">{title}</div>', unsafe_allow_html=True)


# ── Estado da sessão ──────────────────────────────────────────────────────────
if "resultado" not in st.session_state:
    st.session_state["resultado"] = None


# ── Processamento ─────────────────────────────────────────────────────────────
def _bytes(f):
    data = f.read(); f.seek(0); return BytesIO(data)

if processar:
    if not base_file:
        st.error("⚠️ Carregue a Base Plano A antes de processar.")
        st.stop()

    with st.spinner("Carregando base Plano A…"):
        base = carregar_base(_bytes(base_file))

    resultado = {}

    if sel_excel and sel_pdf:
        with st.spinner("Processando SELECT…"):
            pdf_data   = parsear_pdf(_bytes(sel_pdf), "SELECT")
            fatura_sel = carregar_fatura(_bytes(sel_excel), "SELECT", pdf_data["locacoes"])
            df_sel, div_sel = cruzar(fatura_sel, filtrar_convenio(base, "SELECT"))
            resultado["select"] = {
                "df": df_sel, "divergencias": div_sel,
                "resumo": resumo_geral(df_sel),
                "por_locacao": resumo_por_locacao(df_sel),
                "totais_pdf": pdf_data["totais_pdf"],
            }
    else:
        resultado["select"] = None

    if sal_csvs:
        with st.spinner("Processando SALV SAÚDE…"):
            fatura_sal = carregar_fatura_salv_csv([_bytes(f) for f in sal_csvs])
            if fatura_sal.empty:
                st.warning("⚠️ Nenhuma linha válida encontrada nos CSVs da SALV. "
                           "Verifique se o arquivo está no formato correto "
                           "(separador ';', colunas: NOME BENEFICIÁRIO, CPF, VALOR MENSALIDADE…)")
                resultado["salv"] = None
            else:
                df_sal, div_sal = cruzar(fatura_sal, filtrar_convenio(base, "SALV"))
                resultado["salv"] = {
                    "df": df_sal, "divergencias": div_sal,
                    "resumo": resumo_geral(df_sal),
                    "por_locacao": resumo_por_locacao(df_sal),
                    "totais_pdf": {},
                }
    else:
        resultado["salv"] = None

    resultado["mes_ref"] = mes_ref
    st.session_state["resultado"] = resultado
    st.success("✅ Processamento concluído! Navegue pelas abas abaixo.")
    st.balloons()


# ── Tela inicial (sem dados) ──────────────────────────────────────────────────
res = st.session_state.get("resultado")

if res is None:
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("""
        <div class="kpi-card" style="border-left-color:#2ECC71;">
            <div class="kpi-label">PASSO 1</div>
            <div style="font-size:1.8rem;">📋</div>
            <div style="font-weight:600;color:#0D2B6B;margin-top:6px;">Base Plano A</div>
            <div class="kpi-sub">Carregue sua planilha dinâmica de beneficiários</div>
        </div>""", unsafe_allow_html=True)
    with col2:
        st.markdown("""
        <div class="kpi-card" style="border-left-color:#2874A6;">
            <div class="kpi-label">PASSO 2</div>
            <div style="font-size:1.8rem;">📄</div>
            <div style="font-weight:600;color:#0D2B6B;margin-top:6px;">Faturas SELECT e SALV</div>
            <div class="kpi-sub">SELECT: Excel + PDF · SALV: CSVs</div>
        </div>""", unsafe_allow_html=True)
    with col3:
        st.markdown("""
        <div class="kpi-card" style="border-left-color:#8E44AD;">
            <div class="kpi-label">PASSO 3</div>
            <div style="font-size:1.8rem;">⚡</div>
            <div style="font-weight:600;color:#0D2B6B;margin-top:6px;">Processar e Exportar</div>
            <div class="kpi-sub">Relatório Excel completo em segundos</div>
        </div>""", unsafe_allow_html=True)
    st.stop()


# ══════════════════════════════════════════════════════════════════════════════
# TABS
# ══════════════════════════════════════════════════════════════════════════════
tab_ceo, tab_sel, tab_sal, tab_div, tab_export = st.tabs([
    "📊  Dashboard CEO",
    "🔵  SELECT",
    "🟢  SALV SAÚDE",
    "⚠️  Divergências",
    "📥  Exportar Excel",
])


# ── TAB CEO ───────────────────────────────────────────────────────────────────
with tab_ceo:
    r_sel = res["select"]["resumo"] if res.get("select") else {}
    r_sal = res["salv"]["resumo"]   if res.get("salv")   else {}
    def _s(d, k): return d.get(k, 0) or 0

    total_geral    = _s(r_sel,"total_fatura")    + _s(r_sal,"total_fatura")
    vidas_cobradas = _s(r_sel,"vidas_cobradas")  + _s(r_sal,"vidas_cobradas")
    vidas_inat     = _s(r_sel,"vidas_inativas")  + _s(r_sal,"vidas_inativas")
    nao_enc        = _s(r_sel,"nao_encontrados") + _s(r_sal,"nao_encontrados")
    total_div      = (len(res["select"]["divergencias"]) if res.get("select") else 0) + \
                     (len(res["salv"]["divergencias"])   if res.get("salv")   else 0)

    mes_label = res.get("mes_ref","") or datetime.now().strftime("%B/%Y")
    section(f"KPIs CONSOLIDADOS · {mes_label.upper()}")

    c1, c2, c3, c4, c5 = st.columns(5)
    with c1: kpi("Total da Fatura", f"R$ {total_geral:,.2f}", "SELECT + SALV")
    with c2: kpi("Vidas Cobradas",  f"{vidas_cobradas:,}", "CPFs únicos na fatura")
    with c3: kpi("Vidas Inativas",  f"{vidas_inat:,}",
                 "cobradas indevidamente", "alert" if vidas_inat else "ok")
    with c4: kpi("Não na Base",     f"{nao_enc:,}",
                 "sem registro Plano A", "alert" if nao_enc else "ok")
    with c5: kpi("Divergências",    f"{total_div:,}",
                 "para contestação", "warn" if total_div else "ok")

    st.markdown("<br>", unsafe_allow_html=True)
    col_esq, col_dir = st.columns([3, 2])

    with col_esq:
        section("COMPARATIVO POR OPERADORA")
        data_ops = pd.DataFrame({
            "Operadora":      ["SELECT", "SALV SAÚDE"],
            "Total (R$)":     [_s(r_sel,"total_fatura"),   _s(r_sal,"total_fatura")],
            "Mensalidade":    [_s(r_sel,"total_mensalid"),  _s(r_sal,"total_mensalid")],
            "Pro Rata":       [_s(r_sel,"total_prorrata"),  _s(r_sal,"total_prorrata")],
            "Coparticipação": [_s(r_sel,"total_copat"),     _s(r_sal,"total_copat")],
            "Vidas":          [_s(r_sel,"vidas_cobradas"),  _s(r_sal,"vidas_cobradas")],
            "Inativas":       [_s(r_sel,"vidas_inativas"),  _s(r_sal,"vidas_inativas")],
        })
        st.dataframe(
            data_ops.style
                .format({"Total (R$)":"R$ {:,.2f}","Mensalidade":"R$ {:,.2f}",
                         "Pro Rata":"R$ {:,.2f}","Coparticipação":"R$ {:,.2f}"})
                .apply(lambda x: ["background:#FDF2F2" if v > 0 else "" for v in x]
                       if x.name == "Inativas" else [""]*len(x), axis=0),
            hide_index=True, use_container_width=True
        )

        section("TOP LOCAÇÕES POR VALOR")
        dfs = []
        if res.get("select"):
            d = res["select"]["por_locacao"].copy(); d["Operadora"] = "SELECT"; dfs.append(d)
        if res.get("salv"):
            d = res["salv"]["por_locacao"].copy();   d["Operadora"] = "SALV";   dfs.append(d)
        if dfs:
            df_top = pd.concat(dfs).sort_values("total_locacao", ascending=False).head(12)
            fig = px.bar(
                df_top, x="total_locacao", y="Locação", color="Operadora",
                orientation="h", text_auto=".2s",
                color_discrete_map={"SELECT":"#0D2B6B","SALV":"#27AE60"},
                labels={"total_locacao":"Valor Total (R$)","Locação":""},
                height=380,
            )
            fig.update_traces(textfont_size=10)
            fig.update_layout(
                plot_bgcolor="white", paper_bgcolor="white",
                margin=dict(t=0,b=0,l=0,r=10),
                yaxis=dict(categoryorder="total ascending", tickfont_size=10),
                xaxis_tickprefix="R$ ", legend=dict(orientation="h",y=-0.12),
                font=dict(family="Arial"),
            )
            st.plotly_chart(fig, use_container_width=True)

    with col_dir:
        section("COMPOSIÇÃO DO TOTAL")
        labels = ["Mensalidade","Pro Rata","Coparticipação","Outros"]
        values = [
            _s(r_sel,"total_mensalid")+_s(r_sal,"total_mensalid"),
            _s(r_sel,"total_prorrata")+_s(r_sal,"total_prorrata"),
            _s(r_sel,"total_copat")   +_s(r_sal,"total_copat"),
            _s(r_sel,"total_outros")  +_s(r_sal,"total_outros"),
        ]
        pairs = [(l,v) for l,v in zip(labels,values) if v > 0]
        if pairs:
            fig2 = go.Figure(go.Pie(
                labels=[p[0] for p in pairs],
                values=[p[1] for p in pairs],
                hole=0.55,
                marker_colors=["#0D2B6B","#2874A6","#5DADE2","#AED6F1"],
                textinfo="label+percent", textfont_size=11,
                hovertemplate="<b>%{label}</b><br>R$ %{value:,.2f}<extra></extra>",
            ))
            fig2.add_annotation(
                text=f"R$ {total_geral:,.0f}", x=0.5, y=0.5,
                font=dict(size=13, color="#0D2B6B", family="Arial Black"),
                showarrow=False
            )
            fig2.update_layout(
                plot_bgcolor="white", paper_bgcolor="white",
                margin=dict(t=0,b=30,l=0,r=0), height=270,
                legend=dict(orientation="h",y=-0.15,font_size=11),
                showlegend=True,
            )
            st.plotly_chart(fig2, use_container_width=True)

        section("SAÚDE DA FATURA")
        pct_ok = (vidas_cobradas - vidas_inat - nao_enc) / vidas_cobradas * 100 if vidas_cobradas else 100
        fig3 = go.Figure(go.Indicator(
            mode="gauge+number",
            value=round(pct_ok, 1),
            number={"suffix":"%","font":{"size":32,"color":"#0D2B6B"}},
            gauge={
                "axis":{"range":[0,100],"tickfont":{"size":10}},
                "bar":{"color":"#0D2B6B"},
                "steps":[
                    {"range":[0,60], "color":"#FADBD8"},
                    {"range":[60,85],"color":"#FEF9E7"},
                    {"range":[85,100],"color":"#D5F5E3"},
                ],
                "threshold":{"line":{"color":"#27AE60","width":3},"value":95},
            },
            title={"text":"Vidas sem pendências","font":{"size":12,"color":"#7F8C8D"}},
        ))
        fig3.update_layout(margin=dict(t=30,b=0,l=20,r=20), height=210,
                           paper_bgcolor="white")
        st.plotly_chart(fig3, use_container_width=True)

        section("ALERTAS")
        if vidas_inat > 0:
            st.markdown(f'<div class="alerta-box">🚨 <b>{vidas_inat} vidas inativas</b> cobradas indevidamente</div>', unsafe_allow_html=True)
        if nao_enc > 0:
            st.markdown(f'<div class="alerta-box">❓ <b>{nao_enc} beneficiários</b> não encontrados na base</div>', unsafe_allow_html=True)
        if vidas_inat == 0 and nao_enc == 0:
            st.markdown('<div class="ok-box">✅ <b>Nenhum alerta crítico</b> nesta fatura</div>', unsafe_allow_html=True)


# ── TAB OPERADORA (SELECT / SALV) ─────────────────────────────────────────────
def _render_operadora(tab, res_op, nome, cor):
    if res_op is None:
        tab.info(f"Nenhuma fatura da {nome} foi carregada.")
        return

    r   = res_op["resumo"]
    df  = res_op["df"]
    loc = res_op["por_locacao"]
    div = res_op["divergencias"]
    def _s(k): return r.get(k,0) or 0

    badge = f'<span class="badge-sel">{nome}</span>' if "SELECT" in nome else f'<span class="badge-sal">{nome}</span>'
    tab.markdown(f'<div style="margin-bottom:12px;">{badge}</div>', unsafe_allow_html=True)

    c1,c2,c3,c4 = tab.columns(4)
    with c1: kpi("Total da Fatura",    f"R$ {_s('total_fatura'):,.2f}")
    with c2: kpi("Vidas Cobradas",     f"{_s('vidas_cobradas'):,}")
    with c3: kpi("Inativas/Suspensas", f"{_s('vidas_inativas'):,}", tipo="alert" if _s('vidas_inativas') else "ok")
    with c4: kpi("Divergências",       f"{len(div):,}", tipo="warn" if div.__len__() else "ok")

    tab.markdown("<br>", unsafe_allow_html=True)
    col_a, col_b = tab.columns([3,2])

    with col_a:
        section("POR LOCAÇÃO")
        cols_show = ["Locação","qtd_vidas","vidas_ativas","vidas_inativas",
                     "MENSALIDADE","PRO_RATA","COPARTICIPACAO","total_locacao"]
        cols_ex = [c for c in cols_show if c in loc.columns]
        tab.dataframe(
            loc[cols_ex].style.format({
                "MENSALIDADE":"R$ {:,.2f}","PRO_RATA":"R$ {:,.2f}",
                "COPARTICIPACAO":"R$ {:,.2f}","total_locacao":"R$ {:,.2f}",
            }),
            hide_index=True, use_container_width=True, height=320
        )

    with col_b:
        section("POR TIPO DE COBRANÇA")
        tipo_grp = df.groupby("tipo_cobranca")["valor"].sum().reset_index()
        tipo_grp.columns = ["Tipo","Valor (R$)"]
        fig = px.bar(
            tipo_grp, x="Tipo", y="Valor (R$)", text_auto=".2s",
            color="Tipo",
            color_discrete_sequence=[cor,"#2874A6","#5DADE2","#AED6F1"],
            height=260,
        )
        fig.update_layout(showlegend=False, margin=dict(t=0,b=0),
                          plot_bgcolor="white", paper_bgcolor="white",
                          yaxis_tickprefix="R$ ")
        tab.plotly_chart(fig, use_container_width=True)

    section("DETALHAMENTO (primeiros 500 registros)")
    cols_view = ["nome_ben_fat","cpf_ben","locacao_pdf","entidade",
                 "tipo_cobranca","valor","valor_net","status_ben","categoria"]
    cols_ex2 = [c for c in cols_view if c in df.columns]
    tab.dataframe(df[cols_ex2].head(500), hide_index=True, use_container_width=True, height=300)


with tab_sel: _render_operadora(tab_sel, res.get("select"), "SELECT",    "#0D2B6B")
with tab_sal: _render_operadora(tab_sal, res.get("salv"),   "SALV SAÚDE","#27AE60")


# ── TAB DIVERGÊNCIAS ──────────────────────────────────────────────────────────
with tab_div:
    section("DIVERGÊNCIAS PARA CONTESTAÇÃO")
    div_sel = res["select"]["divergencias"] if res.get("select") else pd.DataFrame()
    div_sal = res["salv"]["divergencias"]   if res.get("salv")   else pd.DataFrame()
    df_all_div = pd.concat([div_sel, div_sal], ignore_index=True)

    if df_all_div.empty:
        st.markdown('<div class="ok-box">✅ <b>Nenhuma divergência encontrada!</b> Fatura validada com sucesso.</div>', unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="alerta-box">🔴 <b>{len(df_all_div)} divergências</b> encontradas — verifique e conteste junto às operadoras</div>', unsafe_allow_html=True)

        col_f1, col_f2, col_f3 = st.columns(3)
        with col_f1:
            ops = ["Todas"] + sorted(df_all_div["Operadora"].dropna().unique().tolist())
            op_f = st.selectbox("Operadora", ops)
        with col_f2:
            campos = ["Todos"] + sorted(df_all_div["Campo"].dropna().unique().tolist())
            campo_f = st.selectbox("Tipo", campos)
        with col_f3:
            st.markdown("<br>", unsafe_allow_html=True)
            st.metric("Total filtrado", len(df_all_div))

        df_show = df_all_div.copy()
        if op_f    != "Todas": df_show = df_show[df_show["Operadora"] == op_f]
        if campo_f != "Todos": df_show = df_show[df_show["Campo"]     == campo_f]
        st.dataframe(df_show, hide_index=True, use_container_width=True, height=380)

        col_g1, col_g2 = st.columns(2)
        with col_g1:
            fig_t = px.bar(
                df_all_div.groupby("Campo").size().reset_index(name="Qtd"),
                x="Campo", y="Qtd", title="Por Tipo", color="Campo",
                color_discrete_sequence=["#E74C3C","#F39C12","#3498DB","#9B59B6"],
            )
            fig_t.update_layout(showlegend=False, margin=dict(t=30,b=0),
                                 plot_bgcolor="white", paper_bgcolor="white", height=240)
            st.plotly_chart(fig_t, use_container_width=True)
        with col_g2:
            fig_o = px.pie(
                df_all_div.groupby("Operadora").size().reset_index(name="Qtd"),
                names="Operadora", values="Qtd", title="Por Operadora",
                color_discrete_map={"SELECT":"#0D2B6B","SALV SAUDE":"#27AE60"},
                hole=0.4,
            )
            fig_o.update_layout(margin=dict(t=30,b=0), paper_bgcolor="white", height=240)
            st.plotly_chart(fig_o, use_container_width=True)


# ── TAB EXPORTAR ──────────────────────────────────────────────────────────────
with tab_export:
    section("EXPORTAR RELATÓRIO EXCEL COMPLETO")

    col_info, col_btn = st.columns([3,1])
    with col_info:
        st.markdown("""
        <div class="kpi-card" style="border-left-color:#8E44AD;">
        O relatório contém <b>7 abas</b> prontas para o time financeiro e CEO:
        <ul style="margin:8px 0 0 0;color:#5D6D7E;font-size:0.88rem;line-height:1.8;">
            <li>📊 <b>RESUMO CEO</b> — KPIs, totais e alertas consolidados</li>
            <li>🔵 <b>SELECT_POR_LOCAÇÃO</b> — vidas, valores e status por associação</li>
            <li>🟢 <b>SALV_POR_LOCAÇÃO</b> — vidas, valores e status por associação</li>
            <li>📋 <b>SELECT_DETALHADO</b> — linha a linha com cruzamento da base</li>
            <li>📋 <b>SALV_DETALHADO</b> — linha a linha com cruzamento da base</li>
            <li>⚠️ <b>DIVERGÊNCIAS</b> — lista completa para contestação</li>
            <li>💊 <b>COPARTICIPAÇÃO</b> — valores para cobrar no sistema</li>
        </ul>
        </div>
        """, unsafe_allow_html=True)

    df_s = res["select"]["df"]          if res.get("select") else pd.DataFrame()
    df_a = res["salv"]["df"]            if res.get("salv")   else pd.DataFrame()
    rs   = res["select"]["resumo"]      if res.get("select") else {}
    ra   = res["salv"]["resumo"]        if res.get("salv")   else {}
    rl_s = res["select"]["por_locacao"] if res.get("select") else pd.DataFrame()
    rl_a = res["salv"]["por_locacao"]   if res.get("salv")   else pd.DataFrame()
    ds   = res["select"]["divergencias"] if res.get("select") else pd.DataFrame()
    da   = res["salv"]["divergencias"]   if res.get("salv")   else pd.DataFrame()
    mes  = res.get("mes_ref","") or datetime.now().strftime("%B/%Y")

    with st.spinner("Preparando relatório…"):
        excel_bytes = gerar_excel(df_s, df_a, rs, ra, rl_s, rl_a, ds, da, mes_ref=mes)

    nome = f"PlanoA_Analise_{mes.replace('/','_').replace(' ','_')}.xlsx"

    with col_btn:
        st.markdown("<br><br>", unsafe_allow_html=True)
        st.download_button(
            label="⬇️  BAIXAR EXCEL",
            data=excel_bytes,
            file_name=nome,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary",
            use_container_width=True,
        )
        st.caption(nome)

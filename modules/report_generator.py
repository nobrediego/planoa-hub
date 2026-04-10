"""
Gera o relatório Excel consolidado para o time financeiro e CEO.

Abas:
  1. RESUMO_CEO          — visão executiva consolidada
  2. SELECT_POR_LOCACAO  — agrupado por locação (SELECT)
  3. SALV_POR_LOCACAO    — agrupado por locação (SALV)
  4. SELECT_DETALHADO    — linha a linha SELECT (com status, NET, flags)
  5. SALV_DETALHADO      — linha a linha SALV
  6. DIVERGENCIAS        — lista completa de erros/alertas para contestação
  7. COPARTICIPACAO      — itens de copart. para cobrar no sistema Plano A
"""

import io
import pandas as pd
from datetime import datetime


# ---- paleta de cores Plano A -------------------------------------------
COR_AZUL_ESCURO = "#0D2B6B"
COR_AZUL_MED    = "#1A5276"
COR_AZUL_CLARO  = "#D6EAF8"
COR_VERDE       = "#D5F5E3"
COR_VERMELHO    = "#FADBD8"
COR_AMARELO     = "#FEF9E7"
COR_BRANCO      = "#FFFFFF"
COR_CINZA       = "#F2F3F4"


def _header_fmt(wb):
    return wb.add_format({
        "bold": True, "font_color": COR_BRANCO, "bg_color": COR_AZUL_ESCURO,
        "border": 1, "align": "center", "valign": "vcenter",
        "font_size": 10, "text_wrap": True
    })


def _subheader_fmt(wb):
    return wb.add_format({
        "bold": True, "font_color": COR_AZUL_ESCURO, "bg_color": COR_AZUL_CLARO,
        "border": 1, "align": "center"
    })


def _money_fmt(wb):
    return wb.add_format({"num_format": "R$ #,##0.00", "border": 1})


def _int_fmt(wb):
    return wb.add_format({"num_format": "#,##0", "border": 1, "align": "center"})


def _normal_fmt(wb):
    return wb.add_format({"border": 1, "font_size": 9})


def _red_fmt(wb):
    return wb.add_format({"bg_color": COR_VERMELHO, "border": 1, "font_size": 9})


def _green_fmt(wb):
    return wb.add_format({"bg_color": COR_VERDE, "border": 1, "font_size": 9})


def _yellow_fmt(wb):
    return wb.add_format({"bg_color": COR_AMARELO, "border": 1, "font_size": 9})


def _titulo_fmt(wb):
    return wb.add_format({
        "bold": True, "font_size": 14, "font_color": COR_AZUL_ESCURO,
        "valign": "vcenter"
    })


def _escrever_df(ws, df, wb, row_start=1):
    """Escreve DataFrame na worksheet a partir da linha row_start (0-indexed)."""
    hfmt = _header_fmt(wb)
    nfmt = _normal_fmt(wb)
    mfmt = _money_fmt(wb)
    ifmt = _int_fmt(wb)

    # cabeçalho
    for col_num, col_name in enumerate(df.columns):
        ws.write(row_start, col_num, col_name, hfmt)

    # linhas
    row_num = row_start  # valor padrão caso df esteja vazio
    for row_num, row in enumerate(df.itertuples(index=False), start=row_start + 1):
        for col_num, value in enumerate(row):
            col_name = df.columns[col_num]
            is_money = any(k in col_name.upper() for k in ["VALOR","TOTAL","MENSALIDADE","PRO_RATA","COPAT","NET"])
            is_int   = any(k in col_name.upper() for k in ["QTD","VIDAS","QTDE"])
            fmt = mfmt if is_money else (ifmt if is_int else nfmt)
            ws.write(row_num, col_num, value, fmt)

    return row_num + 1  # próxima linha disponível


def _aba_resumo_ceo(wb, resumo_select: dict, resumo_salv: dict,
                     div_select: pd.DataFrame, div_salv: pd.DataFrame,
                     mes_ref: str):
    ws = wb.add_worksheet("RESUMO CEO")
    ws.set_column(0, 0, 35)
    ws.set_column(1, 3, 18)

    tfmt  = _titulo_fmt(wb)
    hfmt  = _header_fmt(wb)
    mfmt  = _money_fmt(wb)
    ifmt  = _int_fmt(wb)
    sfmt  = _subheader_fmt(wb)

    bold_azul = wb.add_format({"bold": True, "font_color": COR_AZUL_ESCURO, "font_size": 10})
    gerado = wb.add_format({"italic": True, "font_color": "#7F8C8D", "font_size": 8})

    ws.merge_range("A1:D1", f"PLANO A — ANÁLISE DE FATURAS | {mes_ref}", tfmt)
    ws.write("A2", f"Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M')}", gerado)

    # Totais por operadora
    row = 3
    ws.merge_range(row, 0, row, 3, "RESUMO FINANCEIRO POR OPERADORA", sfmt)
    row += 1

    headers = ["Indicador", "SELECT", "SALV SAÚDE", "TOTAL GERAL"]
    for c, h in enumerate(headers):
        ws.write(row, c, h, hfmt)
    row += 1

    def _soma(r_sel, r_sal, key):
        s = r_sel.get(key, 0) or 0
        a = r_sal.get(key, 0) or 0
        return s, a, s + a

    metricas = [
        ("Total da Fatura (R$)",        "total_fatura",    mfmt),
        ("  Mensalidade (R$)",           "total_mensalid",  mfmt),
        ("  Pro Rata (R$)",              "total_prorrata",  mfmt),
        ("  Coparticipação (R$)",        "total_copat",     mfmt),
        ("  Outros (R$)",                "total_outros",    mfmt),
        ("Vidas Cobradas na Fatura",     "vidas_cobradas",  ifmt),
        ("  Vidas Ativas (base)",        "vidas_ativas",    ifmt),
        ("  Vidas Inativas/Susp cobradas","vidas_inativas", ifmt),
        ("  Não encontrados na base",    "nao_encontrados", ifmt),
    ]

    rfmt_label = wb.add_format({"bold": True, "border": 1, "bg_color": COR_CINZA})
    for label, key, fmt in metricas:
        s, a, t = _soma(resumo_select, resumo_salv, key)
        is_alerta = key in ("vidas_inativas", "nao_encontrados") and t > 0
        row_fmt = _red_fmt(wb) if is_alerta else fmt
        ws.write(row, 0, label, rfmt_label)
        ws.write(row, 1, s,     row_fmt)
        ws.write(row, 2, a,     row_fmt)
        ws.write(row, 3, t,     row_fmt)
        row += 1

    row += 1

    # Divergências
    ws.merge_range(row, 0, row, 3, "DIVERGÊNCIAS ENCONTRADAS", sfmt)
    row += 1

    total_div = len(div_select) + len(div_salv)
    ws.write(row, 0, "Total de divergências", bold_azul)
    ws.write(row, 1, len(div_select), ifmt)
    ws.write(row, 2, len(div_salv),   ifmt)
    ws.write(row, 3, total_div,        ifmt)
    row += 1

    if not div_select.empty:
        tipos_sel = div_select["Campo"].value_counts()
        for tipo, qtd in tipos_sel.items():
            ws.write(row, 0, f"  SELECT — {tipo}", _normal_fmt(wb))
            ws.write(row, 1, qtd, ifmt)
            row += 1

    if not div_salv.empty:
        tipos_sal = div_salv["Campo"].value_counts()
        for tipo, qtd in tipos_sal.items():
            ws.write(row, 0, f"  SALV — {tipo}", _normal_fmt(wb))
            ws.write(row, 2, qtd, ifmt)
            row += 1

    row += 1
    ws.write(row, 0, "* Ver abas DIVERGENCIAS e *_POR_LOCACAO para detalhes",
             wb.add_format({"italic": True, "font_color": "#E74C3C"}))

    ws.set_zoom(90)


def _aba_por_locacao(wb, df_resumo: pd.DataFrame, nome_aba: str):
    ws = wb.add_worksheet(nome_aba)
    ws.set_column(0, 0, 60)
    ws.set_column(1, 15, 16)

    tfmt = _titulo_fmt(wb)
    ws.merge_range("A1:K1", f"{nome_aba.replace('_', ' ')} — Análise por Locação", tfmt)
    _escrever_df(ws, df_resumo, wb, row_start=2)
    ws.freeze_panes(3, 1)
    ws.autofilter(2, 0, 2 + len(df_resumo), len(df_resumo.columns) - 1)


def _aba_detalhado(wb, df: pd.DataFrame, nome_aba: str):
    colunas = [
        "operadora","locacao_pdf","entidade","nome_ben_fat","cpf_ben",
        "categoria","tipo_cobranca","plano","dt_nascimento","dt_inclusao",
        "valor","valor_net","status_ben","nome_contratante","grupo_contratual",
        "faixa","prestador","descricao_item","dt_procedimento"
    ]
    colunas_existentes = [c for c in colunas if c in df.columns]
    df_out = df[colunas_existentes].copy()
    df_out.columns = [c.replace("_"," ").title() for c in colunas_existentes]

    ws = wb.add_worksheet(nome_aba)
    ws.set_column(0, 0, 12)
    ws.set_column(1, 2, 55)
    ws.set_column(3, 3, 30)
    ws.set_column(4, 20, 16)

    tfmt = _titulo_fmt(wb)
    ws.merge_range("A1:S1", f"{nome_aba.replace('_',' ')} — Detalhamento Completo", tfmt)

    hfmt  = _header_fmt(wb)
    nfmt  = _normal_fmt(wb)
    mfmt  = _money_fmt(wb)
    rfmt  = _red_fmt(wb)
    gfmt  = _green_fmt(wb)

    for col_num, col_name in enumerate(df_out.columns):
        ws.write(2, col_num, col_name, hfmt)

    for row_num, row in enumerate(df_out.itertuples(index=False), start=3):
        status_val = str(getattr(row, "Status Ben", "")).upper() if "Status Ben" in df_out.columns else ""
        for col_num, value in enumerate(row):
            col_name = df_out.columns[col_num]
            is_money = any(k in col_name.upper() for k in ["VALOR","NET"])
            fmt = mfmt if is_money else nfmt
            if "Status Ben" in col_name and status_val in ("INATIVO","SUSPENSO","NÃO ENCONTRADO NA BASE"):
                fmt = rfmt
            elif "Status Ben" in col_name and status_val == "ATIVO":
                fmt = gfmt

            if isinstance(value, float) and pd.isna(value):
                value = ""
            elif hasattr(value, "isoformat"):
                value = value.strftime("%d/%m/%Y") if not pd.isna(value) else ""
            ws.write(row_num, col_num, value, fmt)

    ws.freeze_panes(3, 0)
    ws.autofilter(2, 0, 2 + len(df_out), len(df_out.columns) - 1)
    ws.set_zoom(85)


def _aba_divergencias(wb, div_select: pd.DataFrame, div_salv: pd.DataFrame):
    ws = wb.add_worksheet("DIVERGENCIAS")
    ws.set_column(0, 1, 20)
    ws.set_column(2, 2, 12)
    ws.set_column(3, 4, 45)
    ws.set_column(5, 5, 35)
    ws.set_column(6, 7, 16)

    tfmt = _titulo_fmt(wb)
    ws.merge_range("A1:I1", "DIVERGÊNCIAS — Lista para Contestação junto às Operadoras", tfmt)

    df_all = pd.concat([div_select, div_salv], ignore_index=True) if not (div_select.empty and div_salv.empty) else pd.DataFrame()

    if df_all.empty:
        ws.write(2, 0, "Nenhuma divergência encontrada.", wb.add_format({"bold": True, "font_color": "#27AE60"}))
        return

    df_all["Valor fatura"] = pd.to_numeric(df_all["Valor fatura"], errors="coerce")
    df_all["Valor base (NET)"] = pd.to_numeric(df_all["Valor base (NET)"], errors="coerce")

    hfmt = _header_fmt(wb)
    rfmt = _red_fmt(wb)
    yfmt = _yellow_fmt(wb)
    nfmt = _normal_fmt(wb)
    mfmt = _money_fmt(wb)

    for col_num, col_name in enumerate(df_all.columns):
        ws.write(2, col_num, col_name, hfmt)

    campos_criticos = {"Status", "CPF"}
    for row_num, row in enumerate(df_all.itertuples(index=False), start=3):
        campo = str(getattr(row, "Campo", ""))
        fmt_row = rfmt if campo in campos_criticos else yfmt
        for col_num, value in enumerate(row):
            col_name = df_all.columns[col_num]
            is_money = "Valor" in col_name
            fmt = mfmt if is_money else fmt_row
            if isinstance(value, float) and pd.isna(value):
                value = ""
            ws.write(row_num, col_num, value, fmt)

    ws.freeze_panes(3, 0)
    ws.autofilter(2, 0, 2 + len(df_all), len(df_all.columns) - 1)


def _aba_coparticipacao(wb, df_select: pd.DataFrame, df_salv: pd.DataFrame):
    ws = wb.add_worksheet("COPARTICIPACAO")
    ws.set_column(0, 0, 12)
    ws.set_column(1, 2, 35)
    ws.set_column(3, 8, 18)

    tfmt = _titulo_fmt(wb)
    ws.merge_range("A1:H1", "COPARTICIPAÇÃO — Valores para Cobrar no Sistema Plano A", tfmt)

    copat_sel = df_select[df_select["tipo_cobranca"] == "COPARTICIPACAO"].copy() if not df_select.empty else pd.DataFrame()
    copat_sal = df_salv[df_salv["tipo_cobranca"] == "COPARTICIPACAO"].copy() if not df_salv.empty else pd.DataFrame()
    df_all = pd.concat([copat_sel, copat_sal], ignore_index=True)

    if df_all.empty:
        ws.write(2, 0, "Nenhum item de coparticipação nesta fatura.")
        return

    df_out = df_all[["operadora","cpf_ben","nome_ben_fat","entidade","plano",
                      "dt_procedimento","prestador","descricao_item","valor"]].copy()
    df_out.columns = ["Operadora","CPF","Beneficiário","Locação","Plano",
                      "Data Procedimento","Prestador","Descrição","Valor (R$)"]

    hfmt = _header_fmt(wb)
    mfmt = _money_fmt(wb)
    nfmt = _normal_fmt(wb)

    for col_num, col_name in enumerate(df_out.columns):
        ws.write(2, col_num, col_name, hfmt)

    for row_num, row in enumerate(df_out.itertuples(index=False), start=3):
        for col_num, value in enumerate(row):
            col_name = df_out.columns[col_num]
            fmt = mfmt if "Valor" in col_name else nfmt
            if isinstance(value, float) and pd.isna(value):
                value = ""
            elif hasattr(value, "isoformat"):
                try:
                    value = value.strftime("%d/%m/%Y")
                except Exception:
                    value = str(value)
            ws.write(row_num, col_num, value, fmt)

    # Total
    total = df_out["Valor (R$)"].sum()
    ultimo = 3 + len(df_out)
    tfmt2 = wb.add_format({"bold": True, "bg_color": COR_AZUL_CLARO, "border": 1, "num_format": "R$ #,##0.00"})
    ws.write(ultimo, len(df_out.columns) - 2, "TOTAL", wb.add_format({"bold": True, "border": 1}))
    ws.write(ultimo, len(df_out.columns) - 1, total, tfmt2)

    ws.autofilter(2, 0, 2 + len(df_out), len(df_out.columns) - 1)


# ---- Ponto de entrada -----------------------------------------------

def gerar_excel(
    df_select: pd.DataFrame,
    df_salv: pd.DataFrame,
    resumo_select: dict,
    resumo_salv: dict,
    res_loc_select: pd.DataFrame,
    res_loc_salv: pd.DataFrame,
    div_select: pd.DataFrame,
    div_salv: pd.DataFrame,
    mes_ref: str = "",
) -> bytes:
    """
    Gera o workbook e devolve os bytes para download.
    """
    output = io.BytesIO()

    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        wb = writer.book

        _aba_resumo_ceo(wb, resumo_select, resumo_salv, div_select, div_salv, mes_ref)
        _aba_por_locacao(wb, res_loc_select, "SELECT_POR_LOCACAO")
        _aba_por_locacao(wb, res_loc_salv,   "SALV_POR_LOCACAO")
        _aba_detalhado(wb, df_select, "SELECT_DETALHADO")
        _aba_detalhado(wb, df_salv,   "SALV_DETALHADO")
        _aba_divergencias(wb, div_select, div_salv)
        _aba_coparticipacao(wb, df_select, df_salv)

    output.seek(0)
    return output.read()

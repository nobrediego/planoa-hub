"""
Processa as planilhas Excel das operadoras (faturas).

Colunas do Excel (índice):
  0  = Contrato
  1  = Matricula      (CPF titular para SELECT; igual ao CPF para SALV titulares)
  2  = Código         (código interno — chave do PDF SALV)
  3  = Beneficiário   (nome)
  4  = CPF            (CPF individual do beneficiário)
  5  = Titular
  6  = CPF Titular
  7  = Plano
  8  = Categoria      (Titular / Dependente)
  9  = Data de nascimento
  10 = Idade
  11 = Data Inclusão
  12 = Tipo           (MENSALIDADE / PRO_RATA / ACRESCIMO/DESCONTO / COPARTICIPACAO_SINTETICA …)
  13 = Conta/Guia
  14 = Data
  15 = Prestador
  16 = Código do item
  17 = Descrição do item
  18 = Valor
  19 = Valor subsidio
"""

import pandas as pd
import re
from io import BytesIO


def _parse_br_valor(valor) -> float:
    """Converte valor em formato BR ('1.234,56' ou '381,92' ou '0') para float."""
    if pd.isna(valor) or str(valor).strip() in ("", "nan"):
        return 0.0
    if isinstance(valor, (int, float)):
        return float(valor)
    s = str(valor).strip()
    # Ponto = separador de milhar; vírgula = decimal (padrão BR)
    s = s.replace(".", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return 0.0


def _normalizar_cpf(valor) -> str:
    if pd.isna(valor):
        return ""
    # float→int para eliminar o ".0" que vira dígito extra
    if isinstance(valor, float):
        valor = int(valor)
    s = re.sub(r"[^\d]", "", str(valor))
    # CPF sempre 11 dígitos; se vier com 12+ é artefato, pega os 11 corretos
    s = s[:11] if len(s) > 11 else s.zfill(11)
    return s


def _normalizar_tipo(tipo: str) -> str:
    t = str(tipo).strip().upper()
    if "MENSALIDADE" in t:
        return "MENSALIDADE"
    if "PRO" in t and "RATA" in t:
        return "PRO_RATA"
    if "COPARTICIPACAO" in t or "COPART" in t:
        return "COPARTICIPACAO"
    if "ACRESCIMO" in t or "DESCONTO" in t:
        return "ACRESCIMO_DESCONTO"
    return t


def carregar_fatura(arquivo, operadora: str, mapa_locacao: dict) -> pd.DataFrame:
    """
    Lê o Excel da fatura e devolve DataFrame enriquecido com locação do PDF.

    mapa_locacao : {matricula_str → locacao_str}  (saída do pdf_parser)
    operadora    : "SELECT" ou "SALV"
    """
    df_raw = pd.read_excel(arquivo, sheet_name=0, header=0)
    df_raw.columns = range(len(df_raw.columns))

    df = pd.DataFrame()
    df["operadora"]       = operadora.upper()
    df["matricula_fat"]   = df_raw[1].astype(str).str.strip()
    df["codigo_fat"]      = df_raw[2].astype(str).str.strip()   # chave PDF SALV
    df["nome_ben_fat"]    = df_raw[3].astype(str).str.strip()
    df["cpf_ben"]         = df_raw[4].apply(_normalizar_cpf)
    df["cpf_titular"]     = df_raw[6].apply(_normalizar_cpf)
    df["plano"]           = df_raw[7].astype(str).str.strip()
    df["categoria"]       = df_raw[8].astype(str).str.strip()
    df["dt_nascimento"]   = pd.to_datetime(df_raw[9], errors="coerce")
    df["dt_inclusao"]     = pd.to_datetime(df_raw[11], errors="coerce")
    df["tipo_cobranca"]   = df_raw[12].apply(lambda x: _normalizar_tipo(x))
    df["dt_procedimento"] = pd.to_datetime(df_raw[14], errors="coerce")
    df["prestador"]       = df_raw[15].astype(str).str.strip()
    df["descricao_item"]  = df_raw[17].astype(str).str.strip()
    df["valor"]           = pd.to_numeric(df_raw[18], errors="coerce").fillna(0)

    # Para SELECT: chave do PDF = matricula_fat (que é o CPF titular)
    # Para SALV  : chave do PDF = codigo_fat
    if operadora.upper() == "SELECT":
        chave_pdf = df["matricula_fat"]
    else:
        chave_pdf = df["codigo_fat"]

    df["locacao_pdf"] = chave_pdf.map(mapa_locacao).fillna("SEM LOCAÇÃO")

    # Remove linhas sem CPF ou sem valor
    df = df[df["cpf_ben"].str.len() >= 11].copy()
    df = df.reset_index(drop=True)

    return df


def carregar_fatura_salv_csv(arquivos) -> pd.DataFrame:
    """
    Lê 1 ou mais CSVs da SALV (novo formato a partir de Abril/2026) e devolve
    DataFrame no mesmo formato que carregar_fatura() retorna.

    Colunas do CSV (separador ';', encoding utf-8-sig):
      NOME BENEFICIÁRIO | CATEGORIA | MATRICULA | COMPETÊNCIA | CPF |
      VALOR MENSALIDADE | ACRESCIMO/DESCONTO | VALOR UTILIZAÇÃO | TOTAL |
      TOTAL FAMÍLIA | NUMERO DO CONTRATO | LOCAÇÃO | PROCEDIMENTOS

    Cada linha do CSV é expandida em até 3 linhas no DataFrame de saída:
      - MENSALIDADE       (VALOR MENSALIDADE)
      - COPARTICIPACAO    (VALOR UTILIZAÇÃO, se > 0)
      - ACRESCIMO_DESCONTO (ACRESCIMO/DESCONTO, se != 0)
    """
    if not isinstance(arquivos, list):
        arquivos = [arquivos]

    frames = []
    for arq in arquivos:
        try:
            source = BytesIO(arq.read()) if hasattr(arq, "read") else arq
            df_raw = pd.read_csv(source, sep=";", encoding="utf-8-sig", dtype=str)
            frames.append(df_raw)
        except Exception:
            pass

    _empty_cols = [
        "operadora","matricula_fat","codigo_fat","nome_ben_fat","cpf_ben",
        "cpf_titular","plano","categoria","dt_nascimento","dt_inclusao",
        "dt_procedimento","prestador","descricao_item","locacao_pdf",
        "tipo_cobranca","valor",
    ]
    if not frames:
        return pd.DataFrame(columns=_empty_cols)

    df_raw = pd.concat(frames, ignore_index=True)
    df_raw.columns = [c.strip().upper() for c in df_raw.columns]

    rows = []
    for _, r in df_raw.iterrows():
        nome      = str(r.get("NOME BENEFICIÁRIO", "")).strip()
        categoria = str(r.get("CATEGORIA", "")).strip()
        matricula = str(r.get("MATRICULA", "")).strip()
        cpf_str   = str(r.get("CPF", "")).strip()
        locacao   = str(r.get("LOCAÇÃO", "")).strip()
        contrato  = str(r.get("NUMERO DO CONTRATO", "")).strip()
        procedimentos = str(r.get("PROCEDIMENTOS", "")).strip()

        if not locacao or locacao in ("nan", ""):
            locacao = "SEM LOCAÇÃO"

        cpf_ben = _normalizar_cpf(cpf_str)
        if not cpf_ben or len(cpf_ben) < 11:
            continue

        # Para dependentes, MATRICULA = CPF do titular
        mat_limpa = re.sub(r"[^\d]", "", matricula)
        if categoria.lower() == "titular" or not mat_limpa:
            cpf_tit = cpf_ben
        else:
            mat_norm = mat_limpa[:11].zfill(11)
            cpf_tit = mat_norm if len(mat_norm) == 11 else cpf_ben

        v_mens  = _parse_br_valor(r.get("VALOR MENSALIDADE", 0))
        v_copat = _parse_br_valor(r.get("VALOR UTILIZAÇÃO", 0))
        v_acrd  = _parse_br_valor(r.get("ACRESCIMO/DESCONTO", 0))

        base = {
            "operadora":       "SALV",
            "matricula_fat":   matricula,
            "codigo_fat":      matricula,
            "nome_ben_fat":    nome,
            "cpf_ben":         cpf_ben,
            "cpf_titular":     cpf_tit,
            "plano":           contrato,
            "categoria":       categoria,
            "dt_nascimento":   pd.NaT,
            "dt_inclusao":     pd.NaT,
            "dt_procedimento": pd.NaT,
            "prestador":       "",
            "descricao_item":  procedimentos,
            "locacao_pdf":     locacao,
        }

        if v_mens != 0:
            rows.append({**base, "tipo_cobranca": "MENSALIDADE", "valor": v_mens})
        if v_copat != 0:
            rows.append({**base, "tipo_cobranca": "COPARTICIPACAO", "valor": v_copat})
        if v_acrd != 0:
            rows.append({**base, "tipo_cobranca": "ACRESCIMO_DESCONTO", "valor": v_acrd})
        # Garante que a vida apareça mesmo sem valores
        if v_mens == 0 and v_copat == 0 and v_acrd == 0:
            rows.append({**base, "tipo_cobranca": "MENSALIDADE", "valor": 0.0})

    if not rows:
        return pd.DataFrame(columns=_empty_cols)

    return pd.DataFrame(rows).reset_index(drop=True)

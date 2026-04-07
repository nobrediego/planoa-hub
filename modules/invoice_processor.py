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

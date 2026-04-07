"""
Carrega e processa a base de beneficiários da Plano A.
Colunas-chave (índices da planilha, header nas linhas 0-1):
  col 7  = Valor Net
  col 8  = Status Ben.   (ATIVO / INATIVO / SUSPENSO)
  col 17 = Convênio      (SELECT, SALV SAUDE, …)
  col 20 = Entidade      (locação / associação)
  col 32 = Matrícula beneficiário
  col 33 = Nome beneficiário
  col 38 = Tipo          (TITULAR / DEPENDENTE)
  col 40 = CPF/CNPJ beneficiário
  col 23 = Nome contratante
  col 24 = CPF/CNPJ contratante
"""

import pandas as pd
import re


def _normalizar_cpf(valor) -> str:
    """Remove formatação e retorna só os 11 dígitos do CPF."""
    if pd.isna(valor):
        return ""
    s = re.sub(r"[^\d]", "", str(valor))
    return s.zfill(11) if len(s) <= 11 else s


def carregar_base(arquivo) -> pd.DataFrame:
    """
    Lê a planilha 'Table' e devolve um DataFrame limpo.
    Aceita caminho (str) ou objeto file-like (upload do Streamlit).
    """
    df_raw = pd.read_excel(arquivo, sheet_name="Table", header=None, skiprows=2)

    df = pd.DataFrame()
    df["convenio"]        = df_raw[17].astype(str).str.strip()
    df["entidade"]        = df_raw[20].fillna("SEM ENTIDADE").astype(str).str.strip()
    df["status_ben"]      = df_raw[8].astype(str).str.strip().str.upper()
    df["valor_net"]       = pd.to_numeric(df_raw[7], errors="coerce").fillna(0)
    df["matricula_base"]  = df_raw[32].astype(str).str.strip()
    df["nome_ben"]        = df_raw[33].astype(str).str.strip()
    df["tipo_ben"]        = df_raw[38].astype(str).str.strip().str.upper()
    df["cpf_ben_raw"]     = df_raw[40].astype(str)
    df["cpf_ben"]         = df["cpf_ben_raw"].apply(_normalizar_cpf)
    df["nome_contratante"] = df_raw[23].astype(str).str.strip()
    df["cpf_contratante"]  = df_raw[24].apply(_normalizar_cpf)
    df["grupo_contratual"] = df_raw[2].astype(str).str.strip()
    df["dt_status_ben"]    = pd.to_datetime(df_raw[9], errors="coerce")
    df["dt_vigencia"]      = pd.to_datetime(df_raw[12], errors="coerce")
    df["dt_inativacao"]    = pd.to_datetime(df_raw[14], errors="coerce")
    df["faixa"]            = df_raw[44].astype(str).str.strip()

    # Remove linhas sem CPF válido
    df = df[df["cpf_ben"].str.len() >= 11].copy()
    df = df.reset_index(drop=True)

    return df


def filtrar_convenio(base: pd.DataFrame, convenio: str) -> pd.DataFrame:
    """Retorna apenas as linhas do convênio solicitado (SELECT ou SALV SAUDE)."""
    mask = base["convenio"].str.contains(convenio, case=False, na=False)
    return base[mask].copy()

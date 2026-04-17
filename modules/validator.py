"""
Motor de validação: cruza a fatura com a base Plano A.

Tabela de coparticipação vigente (por contrato):
  Consulta eletiva agendada   : R$ 30,00 / procedimento
  Urgência / Emergência       : R$ 45,00 / procedimento
  Exame simples               : R$  5,00 / procedimento
  Exame alta complexidade     : 30 %  → teto R$ 70,00 / procedimento
  Limitador mensal            : R$ 250,00 / beneficiário (exceto terapias)
  Terapias                    : 30 %  → teto R$ 45,00 / sessão (sem limitador mensal)
"""

import pandas as pd

LIMITE_MENSAL_COPAT = 250.0   # R$ por beneficiário (exceto terapias)


def _flag(row, campo: str, mensagem: str, divergencias: list):
    divergencias.append({
        "CPF": row.get("cpf_ben", ""),
        "Nome": row.get("nome_ben_fat", ""),
        "Operadora": row.get("operadora", ""),
        "Tipo cobrança": row.get("tipo_cobranca", ""),
        "Locação (PDF)": row.get("locacao_pdf", ""),
        "Campo": campo,
        "Divergência": mensagem,
        "Valor fatura": row.get("valor", 0),
        "Valor base (NET)": row.get("valor_net", 0),
    })


def cruzar(fatura: pd.DataFrame, base: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Junta fatura com base via CPF beneficiário.
    Retorna (df_cruzado, df_divergencias).
    """
    _div_cols = ["CPF","Nome","Operadora","Tipo cobrança","Locação (PDF)",
                 "Campo","Divergência","Valor fatura","Valor base (NET)"]
    if fatura.empty or "cpf_ben" not in fatura.columns:
        return fatura, pd.DataFrame(columns=_div_cols)

    _cols = ["cpf_ben","convenio","entidade","status_ben","valor_net","tipo_ben",
             "nome_contratante","grupo_contratual","faixa","dt_inativacao"]
    base_sel = base.drop_duplicates("cpf_ben")[_cols]

    # Merge
    df = fatura.copy()
    df = df.merge(base_sel, on="cpf_ben", how="left")

    # Preenche quando não encontrado na base
    df["status_ben"]     = df["status_ben"].fillna("NÃO ENCONTRADO NA BASE")
    df["valor_net"]      = df["valor_net"].fillna(0)
    df["entidade"]       = df["entidade"].fillna("NÃO ENCONTRADO NA BASE")
    df["convenio"]       = df["convenio"].fillna("NÃO ENCONTRADO NA BASE")
    df["nome_contratante"] = df["nome_contratante"].fillna("")
    df["grupo_contratual"] = df["grupo_contratual"].fillna("")
    df["faixa"]          = df["faixa"].fillna("")

    divergencias = []

    for _, row in df.iterrows():
        r = row.to_dict()

        # 1. Beneficiário não encontrado na base
        if row["status_ben"] == "NÃO ENCONTRADO NA BASE":
            _flag(r, "CPF", "CPF não encontrado na base Plano A", divergencias)
            continue

        # 2. Beneficiário inativo/suspenso sendo cobrado
        if row["status_ben"] in ("INATIVO", "SUSPENSO"):
            _flag(r, "Status", f"Beneficiário {row['status_ben']} sendo cobrado", divergencias)

        # 3. Divergência de valor NET (somente mensalidade)
        if row["tipo_cobranca"] == "MENSALIDADE" and row["valor_net"] > 0:
            diff = abs(row["valor"] - row["valor_net"])
            if diff > 0.05:  # tolerância de R$ 0,05
                _flag(r, "Valor NET",
                      f"Valor fatura R$ {row['valor']:.2f} ≠ NET R$ {row['valor_net']:.2f} "
                      f"(diff R$ {diff:.2f})", divergencias)

        # 4. Coparticipação acima do limite mensal (agrupado depois por CPF/mês)
        # — validação individual por linha aqui é simplificada
        if row["tipo_cobranca"] == "COPARTICIPACAO" and row["valor"] > LIMITE_MENSAL_COPAT:
            _flag(r, "Coparticipação",
                  f"Valor R$ {row['valor']:.2f} acima do limite mensal R$ {LIMITE_MENSAL_COPAT:.2f}",
                  divergencias)

    # Validação de limite mensal de coparticipação agregado por CPF
    copat_df = df[df["tipo_cobranca"] == "COPARTICIPACAO"].copy()
    if not copat_df.empty:
        total_copat = copat_df.groupby("cpf_ben")["valor"].sum().reset_index()
        total_copat.columns = ["cpf_ben", "total_copat"]
        acima = total_copat[total_copat["total_copat"] > LIMITE_MENSAL_COPAT]
        for _, row in acima.iterrows():
            nome = df.loc[df["cpf_ben"] == row["cpf_ben"], "nome_ben_fat"].iloc[0] if not df[df["cpf_ben"] == row["cpf_ben"]].empty else ""
            divergencias.append({
                "CPF": row["cpf_ben"],
                "Nome": nome,
                "Operadora": "",
                "Tipo cobrança": "COPARTICIPACAO",
                "Locação (PDF)": "",
                "Campo": "Limite mensal copart.",
                "Divergência": f"Total copart. R$ {row['total_copat']:.2f} > limite R$ {LIMITE_MENSAL_COPAT:.2f}",
                "Valor fatura": row["total_copat"],
                "Valor base (NET)": 0,
            })

    df_div = pd.DataFrame(divergencias) if divergencias else pd.DataFrame(
        columns=["CPF","Nome","Operadora","Tipo cobrança","Locação (PDF)",
                 "Campo","Divergência","Valor fatura","Valor base (NET)"]
    )

    return df, df_div


def resumo_por_locacao(df: pd.DataFrame) -> pd.DataFrame:
    """
    Agrega valores por locação (usando entidade da base quando disponível,
    senão a locação do PDF).
    """
    df2 = df.copy()
    # Prioriza entidade da base; se não achou, usa o que veio do PDF
    df2["locacao_final"] = df2["entidade"].replace("NÃO ENCONTRADO NA BASE", pd.NA)
    df2["locacao_final"] = df2["locacao_final"].fillna(df2["locacao_pdf"])
    df2["locacao_final"] = df2["locacao_final"].fillna("SEM LOCAÇÃO")

    pivot = df2.pivot_table(
        index=["locacao_final"],
        columns="tipo_cobranca",
        values="valor",
        aggfunc="sum",
        fill_value=0
    ).reset_index()
    pivot.columns.name = None

    # Garante colunas mínimas
    for col in ["MENSALIDADE", "PRO_RATA", "COPARTICIPACAO", "ACRESCIMO_DESCONTO"]:
        if col not in pivot.columns:
            pivot[col] = 0.0

    # Qtde de vidas (CPFs únicos) por locação
    vidas = df2.groupby("locacao_final")["cpf_ben"].nunique().reset_index()
    vidas.columns = ["locacao_final", "qtd_vidas"]

    # Ativos vs Inativos
    ativos   = df2[df2["status_ben"] == "ATIVO"].groupby("locacao_final")["cpf_ben"].nunique().reset_index()
    ativos.columns = ["locacao_final", "vidas_ativas"]
    inativos = df2[df2["status_ben"].isin(["INATIVO","SUSPENSO"])].groupby("locacao_final")["cpf_ben"].nunique().reset_index()
    inativos.columns = ["locacao_final", "vidas_inativas"]
    nao_enc  = df2[df2["status_ben"] == "NÃO ENCONTRADO NA BASE"].groupby("locacao_final")["cpf_ben"].nunique().reset_index()
    nao_enc.columns  = ["locacao_final", "nao_encontrados"]

    pivot = pivot.merge(vidas,   on="locacao_final", how="left")
    pivot = pivot.merge(ativos,  on="locacao_final", how="left")
    pivot = pivot.merge(inativos,on="locacao_final", how="left")
    pivot = pivot.merge(nao_enc, on="locacao_final", how="left")

    for c in ["qtd_vidas","vidas_ativas","vidas_inativas","nao_encontrados"]:
        pivot[c] = pivot[c].fillna(0).astype(int)

    pivot["total_locacao"] = (pivot["MENSALIDADE"] + pivot.get("PRO_RATA", 0)
                              + pivot.get("COPARTICIPACAO", 0)
                              + pivot.get("ACRESCIMO_DESCONTO", 0))

    pivot = pivot.rename(columns={"locacao_final": "Locação"})
    pivot = pivot.sort_values("total_locacao", ascending=False).reset_index(drop=True)

    return pivot


def resumo_geral(df: pd.DataFrame) -> dict:
    """Retorna métricas consolidadas para o dashboard."""
    total_fatura   = df["valor"].sum()
    total_mensalid = df[df["tipo_cobranca"] == "MENSALIDADE"]["valor"].sum()
    total_prorrata = df[df["tipo_cobranca"] == "PRO_RATA"]["valor"].sum()
    total_copat    = df[df["tipo_cobranca"] == "COPARTICIPACAO"]["valor"].sum()
    total_outros   = df[~df["tipo_cobranca"].isin(["MENSALIDADE","PRO_RATA","COPARTICIPACAO"])]["valor"].sum()
    vidas_cobradas = df["cpf_ben"].nunique()
    vidas_ativas   = df[df["status_ben"] == "ATIVO"]["cpf_ben"].nunique()
    vidas_inativas = df[df["status_ben"].isin(["INATIVO","SUSPENSO"])]["cpf_ben"].nunique()
    nao_enc        = df[df["status_ben"] == "NÃO ENCONTRADO NA BASE"]["cpf_ben"].nunique()

    return {
        "total_fatura":    total_fatura,
        "total_mensalid":  total_mensalid,
        "total_prorrata":  total_prorrata,
        "total_copat":     total_copat,
        "total_outros":    total_outros,
        "vidas_cobradas":  vidas_cobradas,
        "vidas_ativas":    vidas_ativas,
        "vidas_inativas":  vidas_inativas,
        "nao_encontrados": nao_enc,
    }

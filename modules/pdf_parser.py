"""
Extrai mapeamento {matricula → locação} dos PDFs das operadoras.

SELECT PDF  : matrícula = CPF titular (11 dígitos)
SALV PDF    : matrícula = Código interno (6-9 dígitos)

Padrão do PDF (ambas operadoras):
  - Linha beneficiário : MATRICULA NOME PLANO TIPO NASCIMENTO IDADE INCLUSÃO VALOR
  - Linha locação      : Locação: CODIGO - NOME COMPLETO
  - Coparticipação SALV: bloco COPARTICIPACAO / Codigo Nome Valor / Total: X

Retorna:
  dict com duas chaves:
    "locacoes"     : {matricula_str → locacao_nome}
    "totais_pdf"   : {locacao_nome → {"mensalidade": float, "coparticipacao": float, "total": float}}
"""

import re
import pdfplumber
from io import BytesIO


# ---------- padrões regex -----------------------------------------------
_RE_LOCACAO  = re.compile(r'Loca[çc]ão:\s+(.+)', re.IGNORECASE)
_RE_BEN_SEL  = re.compile(
    r'^(\d{10,11})\s+.+?\s+(500\.\d{2})\s+(Titular|Dependente|Agregado)\s+\d{2}/\d{2}/\d{4}\s+\d+\s+\d{2}/\d{2}/\d{4}\s+([\d.,]+)\s*$'
)
_RE_BEN_SALV = re.compile(
    r'^(\d{6,9})\s+.+?\s+(\d{3})\s+(Titular|Dependente|Agregado)\s+\d{2}/\d{2}/\d{4}\s+\d+\s+\d{2}/\d{2}/\d{4}\s+([\d.,]+)\s*$'
)
_RE_COPAT_VAL = re.compile(r'^(\d{6,11})\s+.+?\s+([\d.,]+)\s*$')
_RE_TOTAL_LOC = re.compile(r'Total da loca[çc]ão:\s+([\d.,]+)', re.IGNORECASE)
_RE_TOTAL_GP  = re.compile(r'^Total\s*\(=\):\s*([\d.,]+)', re.IGNORECASE)


def _br_float(s: str) -> float:
    """Converte '1.234,56' → 1234.56"""
    return float(s.replace(".", "").replace(",", "."))


def _extract_lines(pdf_file) -> list[str]:
    """Lê todas as páginas e devolve lista de linhas (texto limpo)."""
    lines = []
    with pdfplumber.open(pdf_file) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            for line in text.split("\n"):
                stripped = line.strip()
                if stripped:
                    lines.append(stripped)
    return lines


def _parse(lines: list[str], operadora: str) -> dict:
    """Processa as linhas e devolve o dict de resultado."""
    locacao_atual = "SEM LOCAÇÃO"
    locacoes: dict[str, str] = {}          # matricula → locacao
    totais: dict[str, dict] = {}           # locacao → {mens, copat, total_loc}
    em_copat = False                        # dentro do bloco COPARTICIPACAO (SALV)

    re_ben = _RE_BEN_SEL if operadora == "SELECT" else _RE_BEN_SALV

    def _init_total(loc):
        if loc not in totais:
            totais[loc] = {"mensalidade": 0.0, "coparticipacao": 0.0, "total_locacao": 0.0}

    for line in lines:
        # ---- Locação --------------------------------------------------
        m = _RE_LOCACAO.match(line)
        if m:
            locacao_atual = m.group(1).strip()
            _init_total(locacao_atual)
            em_copat = False
            continue

        # ---- Total da locação ----------------------------------------
        m = _RE_TOTAL_LOC.search(line)
        if m:
            _init_total(locacao_atual)
            totais[locacao_atual]["total_locacao"] = _br_float(m.group(1))
            continue

        # ---- Bloco coparticipação (SALV) ------------------------------
        if line.upper() == "COPARTICIPACAO":
            em_copat = True
            continue
        if em_copat and line.startswith("Codigo"):
            continue
        if em_copat and line.startswith("Total:"):
            em_copat = False
            continue

        if em_copat:
            m = _RE_COPAT_VAL.match(line)
            if m:
                _init_total(locacao_atual)
                totais[locacao_atual]["coparticipacao"] += _br_float(m.group(2))
            continue

        # ---- Linha de beneficiário ------------------------------------
        m = re_ben.match(line)
        if m:
            matricula = m.group(1)
            valor     = _br_float(m.group(4))
            locacoes[matricula] = locacao_atual
            _init_total(locacao_atual)
            totais[locacao_atual]["mensalidade"] += valor
            continue

    return {"locacoes": locacoes, "totais_pdf": totais}


def parsear_pdf(pdf_file, operadora: str) -> dict:
    """
    Ponto de entrada principal.
    pdf_file : caminho (str) ou BytesIO
    operadora: "SELECT" ou "SALV"
    """
    if isinstance(pdf_file, (str, bytes)):
        source = pdf_file
    else:
        source = BytesIO(pdf_file.read())

    lines = _extract_lines(source)
    return _parse(lines, operadora.upper())

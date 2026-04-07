# Plano A Intelligence Hub — Guia para o Claude

## Sobre o Projeto
Sistema web de análise automatizada de faturas de operadoras de saúde para a
**Plano A Administradora de Planos de Saúde** (Porto Velho - RO).

**Responsáveis:** Patrick Rodrigues e Diego Nobre
**Stack:** Python 3.14 · Streamlit · Pandas · pdfplumber · XlsxWriter · Plotly

---

## Estrutura de Arquivos

```
planoa-hub/
├── app.py                      ← Streamlit UI principal
├── assets/logo.png             ← Logo oficial Plano A
├── modules/
│   ├── base_loader.py          ← Carrega base dinâmica de beneficiários
│   ├── pdf_parser.py           ← Extrai locação dos PDFs das operadoras
│   ├── invoice_processor.py    ← Processa Excel das faturas
│   ├── validator.py            ← Cruza fatura × base, detecta divergências
│   └── report_generator.py     ← Gera relatório Excel com 7 abas
├── .streamlit/
│   ├── config.toml             ← Tema e configurações do Streamlit
│   └── secrets.toml            ← Senha local (NÃO vai ao GitHub)
├── requirements.txt
└── CLAUDE.md                   ← Este arquivo
```

---

## Operadoras e Regras de Negócio

### SELECT e SALV SAÚDE (principais — com portal)
Ambas enviam **Excel** (tem CPF, sem locação) + **PDF** (tem locação, sem CPF).

**Chave de ligação PDF ↔ Excel:**
- SELECT: `PDF matrícula = CPF titular = coluna Matricula do Excel`
- SALV: `PDF matrícula = Código interno = coluna Código do Excel`

**Chave de ligação fatura ↔ base Plano A:**
- `CPF individual (col 4 do Excel da fatura) = CPF/CNPJ beneficiário (col 40 da base)`

**Modalidades:** Coletivo por Adesão (PF) e PME (PJ)

### Rede Total e Sabin Sinai
Ainda sem portal, poucas vidas — não são gargalos por ora.

---

## Base Plano A (Contrato Att 07.04.xlsx)

Planilha dinâmica com cabeçalho em 2 linhas (skiprows=2). Colunas-chave:

| Índice | Campo           | Uso                          |
|--------|-----------------|------------------------------|
| 7      | Valor Net       | Valor negociado com operadora|
| 8      | Status Ben.     | ATIVO / INATIVO / SUSPENSO   |
| 17     | Convênio        | SELECT / SALV SAUDE / …      |
| 20     | Entidade        | Locação / Associação         |
| 33     | Nome beneficiário|                             |
| 38     | Tipo            | TITULAR / DEPENDENTE         |
| 40     | CPF/CNPJ ben.   | Chave de cruzamento          |

---

## Tabela de Coparticipação Vigente

| Procedimento                    | Valor         | Teto          |
|---------------------------------|---------------|---------------|
| Consulta eletiva (agendada)     | R$ 30,00      | —             |
| Urgência / Emergência           | R$ 45,00      | —             |
| Exame simples                   | R$ 5,00       | —             |
| Exame alta complexidade         | 30%           | R$ 70,00      |
| Terapias                        | 30%           | R$ 45,00/sessão|
| **Limitador mensal/beneficiário**| —            | **R$ 250,00** |

*Terapias não têm limitador mensal.*

---

## Design System

### Cores
```
Primária:      #0D2B6B  (azul escuro — identidade Plano A)
Secundária:    #1A4A9C  (azul médio)
Acento claro:  #D6EAF8
Sucesso:       #27AE60
Alerta:        #E74C3C
Atenção:       #F39C12
Fundo:         #F0F4FA
```

### Componentes padrão
- **Cards KPI:** fundo branco, borda esquerda colorida (5px), sombra suave, hover com translateY
- **Sidebar:** gradiente azul escuro `#0D2B6B → #1A3A7A`, texto em `#D6EAF8`
- **Barra superior:** gradiente `#0D2B6B → #1A4A9C`, logo à esquerda
- **Tabs:** fundo branco, tab ativa com gradiente azul, bordas arredondadas
- **Títulos de seção:** uppercase, `letter-spacing: 1px`, borda inferior azul claro
- **Alertas:** fundo `#FDF2F2`, borda `#F5B7B1`
- **Sucesso:** fundo `#F0FBF4`, borda `#A9DFBF`

### Princípios UX
- Sidebar escura contrasta com conteúdo claro — nunca inverter
- KPIs sempre em linha horizontal (máx. 5 colunas)
- Gráficos de pizza com valor total anotado no centro
- Velocímetro (gauge) para % de saúde/conformidade
- Barras horizontais para rankings de locação
- `st.balloons()` ao concluir processamento (feedback positivo)

---

## Resultados de Referência (Abril/2026)

| Operadora   | Total Fatura     | Vidas | Inativas | Divergências |
|-------------|------------------|-------|----------|--------------|
| SELECT      | R$ 343.164,17    | 1.673 | 147      | 1.135        |
| SALV SAÚDE  | R$ 230.618,38    | 691   | 59       | 141          |
| **TOTAL**   | **R$ 573.782,55**| 2.364 | 206      | 1.276        |

*Use como referência para validar se o processamento está correto.*

---

## Deploy

- **Repositório:** https://github.com/nobrediego/planoa-hub
- **Plataforma:** Streamlit Cloud (share.streamlit.io)
- **Senha do app:** configurada nos Secrets do Streamlit Cloud (`APP_PASSWORD`)
- **Senha local:** `.streamlit/secrets.toml` (não sobe ao GitHub — está no .gitignore)

---

## Próximas Melhorias Planejadas

- [ ] Histórico mensal — comparar evolução mês a mês
- [ ] Incluir Rede Total e Sabin Sinai quando tiverem portal
- [ ] Exportar divergências em e-mail automático para as operadoras
- [ ] Gráfico de linha com evolução do total da fatura por mês
- [ ] Filtro por status na aba de detalhamento

---

## Como Rodar Localmente

```bash
cd C:\Users\Diego\Documents\planoa-hub
python -m streamlit run app.py
```

Ou clique em `iniciar.bat`.

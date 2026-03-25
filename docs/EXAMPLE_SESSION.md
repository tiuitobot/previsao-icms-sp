# Example Implantation Session

A condensed transcript of a real pipeline creation: investment analysis report for Brazil 2026.

## Phase 1: Interview

**Implantador:** "Me descreva o que você precisa — qual problema quer resolver?"

**User:** "Quero um relatório com as melhores opções de investimento no Brasil em 2026. Renda fixa, variável, fundos. Com dados reais, não opinião do ChatGPT."

**Implantador identifies:**
- Domain: `financeiro.investimentos`
- Problem: Investment analysis with real data
- Output: Technical report (HTML + PDF)
- Key requirement: "dados reais, não opinião" → deterministic data fetching is critical

**Implantador searches catalog:**
```bash
python3 scripts/build_catalog.py --search "financeiro.investimentos"
# → Found: renda_fixa_data, renda_variavel_data, fundos_data, macro_data
```

**Implantador launches research scouts:**
- API scout → Found: BCB SGS (Selic, IPCA), Tesouro Transparente, CVM (fundos), yfinance (B3)
- Library scout → Found: python-bcb, yfinance, pandas
- Methodology scout → Found: standard asset allocation frameworks, Sharpe ratio, carry analysis

## Phase 2: Data Investigation

| Source | Type | API/Method | Worker |
|---|---|---|---|
| Selic, IPCA, câmbio | API | BCB SGS | `macro_data` (exists in library) |
| Tesouro Direto rates | API | Tesouro Transparente CSV | `renda_fixa_data` (exists) |
| Ibovespa, setores | API | yfinance | `renda_variavel_data` (exists) |
| Fundos CVM | API | CVM open data | `fundos_data` (exists) |

**Result:** All 4 data workers already exist in the library. Zero new ingestion scripts needed.

## Phase 3: Output Design

- Type: Technical/academic report → `academic_report.html.j2`
- Format: HTML + PDF
- Language: Portuguese
- Size: Extenso (~20 pages)

## Phase 3.5: Product Summary

> "Antes de começar, confirmo:
> - **O que faz:** Analisa investimentos no Brasil e gera relatório com recomendações
> - **Dados:** APIs reais (BCB, Tesouro, CVM, B3) — zero web search
> - **Modelo:** GPT-4.1 para análise, validação cruzada automática
> - **Resultado:** Relatório HTML+PDF, ~20 páginas, estilo acadêmico
> - **Custo:** ~R$1.50 por execução
> - **Como usar:** `./run.sh` ou `./run.sh 'foco em renda fixa'` (dinâmico)"

**User confirms.**

## Phase 4: Architecture

```
Wave 0 (parallel):
  [deterministic] macro_data          → BCB SGS API
  [deterministic] renda_fixa_data     → Tesouro Transparente
  [deterministic] renda_variavel_data → yfinance
  [deterministic] fundos_data         → CVM open data

Wave 1 (parallel):
  [llm] macro_strategist    → analyze macro scenario
  [llm] asset_analyst       → analyze each asset class
  [llm] intl_comparisons    → compare with international markets

Wave 2:
  [deterministic] cross_validate → check LLM numbers against source data

Wave 3:
  [llm] portfolio_strategist → recommend allocation

Wave 4:
  [llm] report_writer → compile final report for template

Wave 5 (parallel):
  [deterministic] html_renderer → academic_report.html.j2
  [deterministic] pdf_renderer  → weasyprint
```

**12 steps total: 6 deterministic ($0) + 5 LLM (~$0.25 total) + 1 PDF ($0)**

## Resulting DAG

```
macro_data ─────────┐
renda_fixa_data ────┤
renda_variavel_data ┤──→ macro_strategist ──┐
fundos_data ────────┘──→ asset_analyst ─────┤──→ cross_validate ──→ portfolio_strategist ──→ report_writer ──→ html_renderer
                       └→ intl_comparisons ─┘                                                              └→ pdf_renderer
```

## Key Decisions

| # | Decision | Why |
|---|---|---|
| D001 | Dynamic DAG (with config) | User might want "foco em renda fixa" or "sem cripto" |
| D002 | All data via API, no web_search | User explicitly said "dados reais" |
| D003 | cross_validate step | Deterministic check: LLM numbers match source data |
| D004 | Reuse 4 library workers | Already proven, $0 cost, tested APIs |
| D005 | academic_report template | User wants "relatório técnico" not dashboard |

## What Made This Pipeline Different From Chat

1. **Real data from 4 APIs** — not LLM opinions or web search
2. **Cross-validation** — deterministic step catches hallucinated numbers
3. **Dynamic DAG** — same pipeline handles "foco em renda fixa" and "perfil arrojado"
4. **Reproducible** — `./run.sh` produces consistent output every time
5. **Cost: ~R$1.50** — not R$0 (chat) but adds grounding, validation, professional output

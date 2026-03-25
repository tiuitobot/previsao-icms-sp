# B3 Equities Data Fetcher

**ID:** `renda_variavel_data`
**Extends:** [[_base_ingester]]
**Type:** `deterministic`

Fetches Ibovespa, sector indices, P/L, dividend yield via yfinance. Calculates relative valuation, sector ranking, momentum.

## Library Info

- **Origin:** investimentos-br-2026 (v1)
- **Proven in production:** yes
- **Typical cost:** $0
- **Typical duration:** 28s
- **Quality notes:** yfinance pode ter tickers desatualizados. Dividend yield vem em formato inconsistente para alguns tickers.

**Domain:** `financeiro.investimentos`

## Complementary Workers

- [[macro_data]]
- [[fundos_data]]

## Suggested Fixups

- `normalize_dividend_yield`

## Use Cases

- Analise de acoes BR
- Valuation setorial
- Comparacao com benchmarks

## Known Limitations

- Concrete subclasses must handle encoding detection
- Binary formats (PDF, DOCX) require additional dependencies

---
[[_index|← Back to catalog]] | [[_by_domain|By domain]] | [[_by_type|By type]]

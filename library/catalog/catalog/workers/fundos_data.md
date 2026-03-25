# CVM Fund Data Fetcher

**ID:** `fundos_data`
**Extends:** [[_base_ingester]]
**Type:** `deterministic`

Fetches fund AUM, returns, and flows from CVM open data. Calculates net flows by category, avg alpha vs CDI.

## Library Info

- **Origin:** investimentos-br-2026 (v1)
- **Proven in production:** yes
- **Typical cost:** $0
- **Typical duration:** 2s
- **Quality notes:** CVM CLASSE field pode nao casar com mapping esperado. Tratar como outros se nao reconhecido.

**Domain:** `financeiro.investimentos`

## Complementary Workers

- [[renda_variavel_data]]

## Suggested Fixups

- `normalize_fund_class`

## Use Cases

- Analise da industria de fundos BR
- Captacao liquida por classe
- Performance vs CDI

## Known Limitations

- Concrete subclasses must handle encoding detection
- Binary formats (PDF, DOCX) require additional dependencies

---
[[_index|← Back to catalog]] | [[_by_domain|By domain]] | [[_by_type|By type]]

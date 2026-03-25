# Financial Analyzer

**ID:** `financial_analyzer`
**Extends:** [[_base_llm_analyzer]]
**Type:** `llm`

Analyzes DRE (income statement), balance sheets, and extracts key financial indicators for due diligence.

## Library Info

- **Origin:** due-diligence-pipeline (v1)
- **Typical cost:** $0.05
- **Typical duration:** 25s
- **Quality notes:** From due-diligence test pipeline. Not yet production-proven. Financial extraction accuracy depends on document structure.

**Domain:** `financeiro.due-diligence`
**Also relevant:** `financeiro.contabilidade`

## Complementary Workers

- [[contract_analyzer]]
- [[legal_analyzer]]
- [[risk_consolidator]]

## Use Cases

- Extract key financial indicators from DRE and balance sheets
- Identify financial red flags for due diligence
- Calculate ratios: liquidity, leverage, profitability

## Known Limitations

- DRE format varies by jurisdiction and accounting standard
- Consolidated vs standalone statements must be specified
- Currency conversion not included — assumes single currency

---
[[_index|← Back to catalog]] | [[_by_domain|By domain]] | [[_by_type|By type]]

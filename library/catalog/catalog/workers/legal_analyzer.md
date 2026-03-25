# Legal Analyzer

**ID:** `legal_analyzer`
**Extends:** [[_base_llm_analyzer]]
**Type:** `llm`

Analyzes lawsuits, legal certificates, contingent liabilities, and regulatory compliance for due diligence.

## Library Info

- **Origin:** due-diligence-pipeline (v1)
- **Typical cost:** $0.05
- **Typical duration:** 25s
- **Quality notes:** From due-diligence test pipeline. Not yet production-proven. Pairs with financial_analyzer for complete risk picture.

**Domain:** `juridico.regulatorio`
**Also relevant:** `financeiro.due-diligence`

## Complementary Workers

- [[financial_analyzer]]
- [[contract_analyzer]]
- [[risk_consolidator]]

## Use Cases

- Inventory active and historical lawsuits
- Assess contingent liabilities
- Verify legal certificates and compliance status

## Known Limitations

- Contingent liability estimation is approximate
- Certificate validity dates must be cross-checked externally
- Regulatory compliance scope depends on jurisdiction config

---
[[_index|← Back to catalog]] | [[_by_domain|By domain]] | [[_by_type|By type]]

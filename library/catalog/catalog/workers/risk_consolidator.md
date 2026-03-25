# Risk Consolidator

**ID:** `risk_consolidator`
**Extends:** [[_base_consolidator]]
**Type:** `deterministic`

Computes weighted risk scores from parallel financial, contract, and legal analyses for due diligence summary.

## Library Info

- **Origin:** due-diligence-pipeline (v1)
- **Typical cost:** $0
- **Typical duration:** 2s
- **Quality notes:** From due-diligence test pipeline. Not yet production-proven. Weighted scoring is configurable. Missing inputs default to max risk.

**Domain:** `financeiro.due-diligence`

## Complementary Workers

- [[financial_analyzer]]
- [[contract_analyzer]]
- [[legal_analyzer]]

## Use Cases

- Compute composite risk score from parallel analyses
- Weight financial, legal, and contract risks
- Generate risk summary for decision makers

## Known Limitations

- Default weights are equal — domain experts should calibrate
- Risk score is a composite indicator, not a probability
- Missing analysis inputs are treated as maximum risk

---
[[_index|← Back to catalog]] | [[_by_domain|By domain]] | [[_by_type|By type]]

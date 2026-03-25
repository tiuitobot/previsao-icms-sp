# Base Classifier

**ID:** `_base_classifier`
**Type:** `llm`
**Abstract:** yes (cannot be used directly in DAG)

Classifies and triages findings from multiple sources with confidence scoring.

## Library Info

- **Origin:** pipeline-engine (sprint-3)
- **Proven in production:** yes
- **Typical cost:** $0.02
- **Typical duration:** 10s
- **Quality notes:** Works best after consolidation. Confidence scores should be validated by downstream verifiers.

**Domain:** `generico.classificacao`

## Complementary Workers

- [[_base_consolidator]]
- [[_base_verifier]]
- [[_base_reviewer]]

## Use Cases

- Semantic status assignment (confirmed/probable/refuted)
- Confidence tiering of findings
- Cross-validation classification

## Known Limitations

- Confidence calibration requires domain-specific tuning
- Borderline cases may oscillate between categories across runs

---
[[_index|← Back to catalog]] | [[_by_domain|By domain]] | [[_by_type|By type]]

# Finding Classifier

**ID:** `finding_classifier`
**Extends:** [[_base_classifier]]
**Type:** `llm`

Cross-validation classifier assigning semantic status (confirmed/probable/suggestion/refuted) to merged findings.

## Library Info

- **Origin:** rt-noopenclaw (v37)
- **Proven in production:** yes
- **Typical cost:** $0.02
- **Typical duration:** 12s
- **Quality notes:** Four-status model (confirmed/probable/suggestion/refuted) is production-proven. Cross-validation uses claims + factcheck as evidence.

**Domain:** `generico.classificacao`

## Complementary Workers

- [[orchestrator_merge_helper]]
- [[factcheck_worker]]
- [[confidence_tier_assigner]]

## Use Cases

- Assign semantic status to findings (confirmed/probable/suggestion/refuted)
- Cross-validate findings against claims and factcheck results
- Produce confidence-scored output for downstream tiering

## Known Limitations

- Borderline findings may oscillate between probable and suggestion across runs
- Refuted status requires explicit contradictory evidence
- Classification depends on quality of upstream merge and factcheck

---
[[_index|← Back to catalog]] | [[_by_domain|By domain]] | [[_by_type|By type]]

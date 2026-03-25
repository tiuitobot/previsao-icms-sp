# Base Reviewer

**ID:** `_base_reviewer`
**Type:** `llm`
**Abstract:** yes (cannot be used directly in DAG)

Adversarial review of upstream outputs to detect errors, biases, and unsupported conclusions.

## Library Info

- **Origin:** pipeline-engine (sprint-3)
- **Proven in production:** yes
- **Typical cost:** $0.04
- **Typical duration:** 25s
- **Quality notes:** Most effective when using a different model than the original analyzer (multi-model pattern).

**Domain:** `generico.verificacao`

## Complementary Workers

- [[_base_llm_analyzer]]
- [[_base_classifier]]
- [[_base_verifier]]

## Use Cases

- Adversarial audit of analysis outputs
- Detection of reasoning leaps and unsupported conclusions
- Structured checklist-based review

## Known Limitations

- Adversarial reviewers may flag stylistic issues as substantive
- Effectiveness depends on model capability relative to original analyzer

---
[[_index|← Back to catalog]] | [[_by_domain|By domain]] | [[_by_type|By type]]

# Inferential Consistency Checker

**ID:** `inferential_consistency_checker`
**Extends:** [[_base_reviewer]]
**Type:** `llm`

Detects reasoning leaps where conclusions exceed premises, unsupported analogies, and logical inconsistencies.

## Library Info

- **Origin:** rt-noopenclaw (v37)
- **Proven in production:** yes
- **Typical cost:** $0.04
- **Typical duration:** 20s
- **Quality notes:** Domain-agnostic reasoning checker. Most effective on analytical/argumentative text. Complements factcheck_worker (facts vs logic).

**Domain:** `generico.verificacao`

## Complementary Workers

- [[factcheck_worker]]
- [[adversarial_reviewer]]
- [[finding_classifier]]

## Use Cases

- Detect conclusions that exceed their premises
- Flag unsupported analogies and generalizations
- Identify logical inconsistencies across findings

## Known Limitations

- Cannot evaluate domain-specific logical norms without domain config
- Deductive vs inductive reasoning distinction is imperfect
- May flag intentional rhetorical devices as logical leaps

---
[[_index|← Back to catalog]] | [[_by_domain|By domain]] | [[_by_type|By type]]

# Adversarial Reviewer

**ID:** `adversarial_reviewer`
**Extends:** [[_base_reviewer]]
**Type:** `llm`

Structured 17-point checklist review that challenges classified findings for completeness, accuracy, and fairness.

## Library Info

- **Origin:** rt-noopenclaw (v37)
- **Proven in production:** yes
- **Typical cost:** $0.05
- **Typical duration:** 30s
- **Quality notes:** 17-point checklist covers completeness, accuracy, fairness, consistency, sourcing, and more. Last line of defense before rendering.

**Domain:** `educacional.avaliacao`

## Complementary Workers

- [[finding_classifier]]
- [[inferential_consistency_checker]]
- [[confidence_tier_assigner]]

## Use Cases

- 17-point structured review of analysis output
- Final adversarial check before report compilation
- Quality assurance for classified findings

## Known Limitations

- 17-point checklist is general-purpose — domain-specific checklists may be needed
- Strong model required for meaningful adversarial review
- May produce false positives on well-supported but unusual findings

---
[[_index|← Back to catalog]] | [[_by_domain|By domain]] | [[_by_type|By type]]

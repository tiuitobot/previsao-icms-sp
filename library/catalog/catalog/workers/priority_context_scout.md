# Priority Context Scout

**ID:** `priority_context_scout`
**Extends:** [[_base_scout]]
**Type:** `llm`

Identifies macro vectors and high-priority areas requiring reinforced scrutiny in downstream analysis.

## Library Info

- **Origin:** rt-noopenclaw (v37)
- **Proven in production:** yes
- **Typical cost:** $0.01
- **Typical duration:** 8s
- **Quality notes:** Pairs with temas_extraction. Together they provide a complete triage layer before deep analysis.

**Domain:** `educacional.avaliacao`

## Complementary Workers

- [[temas_extraction]]
- [[scanner_generalist]]
- [[scanner_adversarial]]

## Use Cases

- Identify areas needing reinforced analysis
- Flag macro-level risk vectors
- Guide downstream workers to focus areas

## Known Limitations

- Priority assessment is subjective — calibrate with domain rules
- May over-flag in documents with multiple competing priorities
- Designed as advisory input, not authoritative

---
[[_index|← Back to catalog]] | [[_by_domain|By domain]] | [[_by_type|By type]]

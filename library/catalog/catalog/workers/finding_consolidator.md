# Finding Consolidator

**ID:** `finding_consolidator`
**Extends:** [[_base_consolidator]]
**Type:** `llm`

Merges findings from multiple independent workers into deduplicated, cross-validated list with full provenance. Each finding tracks merged_from, fonte_original, scanner_sources, cross_validated flag. Deduplicates by semantic anchor. Assigns confidence based on independent source count.

## Library Info

- **Origin:** rt-noopenclaw (v37)
- **Proven in production:** yes
- **Typical cost:** $0.05
- **Typical duration:** 20s
- **Quality notes:** From rt-noopenclaw orchestrator pattern. Merges 12+ input streams. Key: provenance tracking (merged_from, fonte_original) enables audit trail. cross_validated flag marks findings confirmed by 2+ independent sources.

**Domain:** `generico.orquestracao`

## Complementary Workers

- [[cross_validate]]
- [[inferential_consistency_checker]]
- [[finding_classifier]]

## Use Cases

- Merge findings from adversarial dual-track scanners
- Consolidate risk assessments from multiple specialized analysts
- Combine researcher outputs with scanner findings for unified view

## Known Limitations

- Deduplication by semantic similarity may miss near-duplicates with different phrasing
- Cross-validation requires 2+ truly independent sources (not derivatives)
- Provenance tracking adds ~30% to output size

---
[[_index|← Back to catalog]] | [[_by_domain|By domain]] | [[_by_type|By type]]

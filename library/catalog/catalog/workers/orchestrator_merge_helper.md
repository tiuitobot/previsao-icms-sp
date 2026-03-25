# Orchestrator Merge Helper

**ID:** `orchestrator_merge_helper`
**Extends:** [[_base_consolidator]]
**Type:** `deterministic`

Deterministic clustering and deduplication of findings by claim_id and literal text anchor.

## Library Info

- **Origin:** rt-noopenclaw (v37)
- **Proven in production:** yes
- **Typical cost:** $0
- **Typical duration:** 2s
- **Quality notes:** Deterministic merge. Uses claim_id for primary clustering, literal anchor for dedup within clusters. Handles multi-scanner output.

**Domain:** `generico.orquestracao`

## Complementary Workers

- [[scanner_generalist]]
- [[scanner_adversarial]]
- [[finding_classifier]]

## Use Cases

- Merge findings from scanner_generalist and scanner_adversarial
- Cluster related findings by claim_id
- Deduplicate using literal text anchors

## Known Limitations

- Literal anchor matching is case-sensitive by default
- Findings without claim_id are grouped by text similarity only
- Large finding sets (>5k) may need batched processing

---
[[_index|← Back to catalog]] | [[_by_domain|By domain]] | [[_by_type|By type]]

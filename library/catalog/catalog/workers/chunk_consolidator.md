# Chunk Consolidator

**ID:** `chunk_consolidator`
**Extends:** [[_base_consolidator]]
**Type:** `deterministic`

Deduplicates and merges outputs from chunked parallel workers using Jaccard similarity and canonical name resolution.

## Library Info

- **Origin:** analise-autos (v5-chunked)
- **Proven in production:** yes
- **Typical cost:** $0
- **Typical duration:** 2s
- **Quality notes:** Deterministic reduce step. Jaccard similarity threshold is configurable. Canonical resolution uses hint_sheet names as ground truth.

**Domain:** `juridico.processual`

## Complementary Workers

- [[party_status_mapper]]
- [[evidence_timeline]]
- [[claim_analyzer]]
- [[decision_value_mapper]]
- [[html_renderer]]

## Use Cases

- Merge chunked analysis outputs into single result
- Deduplicate findings using Jaccard similarity
- Resolve canonical entity names across chunks

## Known Limitations

- Jaccard threshold tuned for Portuguese legal text (0.7 default)
- Canonical resolution may merge distinct entities with similar names
- Very large output sets (>10k items) may be slow

---
[[_index|← Back to catalog]] | [[_by_domain|By domain]] | [[_by_type|By type]]

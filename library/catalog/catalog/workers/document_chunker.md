# Document Chunker

**ID:** `document_chunker`
**Extends:** [[_base_ingester]]
**Type:** `deterministic`

Classifies documents by procedural phase and groups pages into token-budget chunks for parallel LLM analysis.

## Library Info

- **Origin:** analise-autos (v5-chunked)
- **Proven in production:** yes
- **Typical cost:** $0
- **Typical duration:** 3s
- **Quality notes:** Critical enabler for map pattern. Chunk quality directly impacts downstream analysis quality.

**Domain:** `juridico.processual`

## Complementary Workers

- [[hint_sheet_extractor]]
- [[party_status_mapper]]
- [[evidence_timeline]]
- [[claim_analyzer]]
- [[decision_value_mapper]]

## Use Cases

- Split large legal proceedings into LLM-sized chunks
- Classify document sections by procedural phase
- Enable map-parallel analysis of large files

## Known Limitations

- Phase classification heuristics tuned for Brazilian civil procedure
- Token budget assumes tiktoken cl100k_base encoding
- Chunk boundaries may split mid-paragraph

---
[[_index|← Back to catalog]] | [[_by_domain|By domain]] | [[_by_type|By type]]

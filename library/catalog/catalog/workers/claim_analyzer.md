# Claim Analyzer

**ID:** `claim_analyzer`
**Extends:** [[_base_llm_analyzer]]
**Type:** `llm`

Analyzes legal claims, their structural dependencies, procedural status, and resolutions from document chunks.

## Library Info

- **Origin:** analise-autos (v5-chunked)
- **Proven in production:** yes
- **Typical cost:** $0.06
- **Typical duration:** 25s
- **Quality notes:** Works best with hint_sheet providing party names for claim attribution. Consolidation resolves cross-chunk identity.

**Domain:** `juridico.processual`

## Complementary Workers

- [[document_chunker]]
- [[hint_sheet_extractor]]
- [[chunk_consolidator]]

## Use Cases

- Inventory all claims in legal proceedings
- Map claim dependencies and prerequisites
- Track claim resolutions and pending items

## Known Limitations

- Nested claim dependencies may be missed in single-pass analysis
- Partial resolutions (e.g., partial summary judgment) are hard to classify
- Claim identity across chunks depends on consolidation

---
[[_index|← Back to catalog]] | [[_by_domain|By domain]] | [[_by_type|By type]]

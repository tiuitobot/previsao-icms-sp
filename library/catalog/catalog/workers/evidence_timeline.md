# Evidence Timeline

**ID:** `evidence_timeline`
**Extends:** [[_base_llm_analyzer]]
**Type:** `llm`

Extracts chronological events, evidence items, and witness references from legal document chunks.

## Library Info

- **Origin:** analise-autos (v5-chunked)
- **Proven in production:** yes
- **Typical cost:** $0.06
- **Typical duration:** 25s
- **Quality notes:** Chronological ordering is stable. Date extraction benefits from hint_sheet pre-processing.

**Domain:** `juridico.processual`

## Complementary Workers

- [[document_chunker]]
- [[hint_sheet_extractor]]
- [[chunk_consolidator]]

## Use Cases

- Build chronological timeline of legal proceedings
- Catalog evidence items with source references
- Map witness appearances and testimony

## Known Limitations

- Undated events are placed in approximate order
- Witness names may not match party registry exactly
- Overlapping date ranges across chunks need consolidation

---
[[_index|← Back to catalog]] | [[_by_domain|By domain]] | [[_by_type|By type]]

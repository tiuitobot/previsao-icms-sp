# Party Status Mapper

**ID:** `party_status_mapper`
**Extends:** [[_base_llm_analyzer]]
**Type:** `llm`

Extracts parties, lawyers, procedural roles, phase status, and risk indicators from legal document chunks.

## Library Info

- **Origin:** analise-autos (v5-chunked)
- **Proven in production:** yes
- **Typical cost:** $0.06
- **Typical duration:** 25s
- **Quality notes:** Production-proven on 500+ Brazilian lawsuits. Two known fixups for edge cases.

**Domain:** `juridico.processual`

## Complementary Workers

- [[document_chunker]]
- [[hint_sheet_extractor]]
- [[chunk_consolidator]]

## Suggested Fixups

- `monetary_honorarios_direction`
- `party_de_cujus`

## Use Cases

- Map all parties and their procedural roles
- Track lawyer assignments and substitutions
- Identify risk indicators per party

## Known Limitations

- Honorarios direction (who pays) is a known ambiguity source
- De cujus (deceased party) references require special handling
- Party name normalization across chunks depends on consolidation

---
[[_index|← Back to catalog]] | [[_by_domain|By domain]] | [[_by_type|By type]]

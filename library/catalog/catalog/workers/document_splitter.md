# Document Splitter

**ID:** `document_splitter`
**Extends:** [[_base_ingester]]
**Type:** `hybrid`

Splits large documents into blocks by boundary detection (deterministic), then classifies and groups blocks by type. Configurable boundary patterns.

## Library Info

- **Origin:** analise-autos (v5-chunked)
- **Proven in production:** yes
- **Typical cost:** $0.02
- **Typical duration:** 10s
- **Quality notes:** 3-layer classification: filename → keywords → LLM fallback. Deterministic split + optional LLM classification. Duplicate certification detection via similarity matching.

**Domain:** `generico.ingestao`
**Also relevant:** `juridico.ingestao`

## Complementary Workers

- [[pdf_ingester]]
- [[hint_sheet_extractor]]
- [[document_chunker]]

## Use Cases

- Split judicial proceedings into individual peças (petição, sentença, acórdão)
- Split any large document into logical sections by boundary markers
- Classify document sections by type for downstream routing

## Known Limitations

- Boundary patterns are defaulted to Brazilian judicial documents (TJ-SP, SENTENÇA, ACÓRDÃO, etc.)
- Custom boundaries can be passed via boundary_patterns arg
- LLM classification requires OpenAI API key — falls back to keyword-only if unavailable
- Groups by 60K char limit — large documents may span multiple groups

---
[[_index|← Back to catalog]] | [[_by_domain|By domain]] | [[_by_type|By type]]

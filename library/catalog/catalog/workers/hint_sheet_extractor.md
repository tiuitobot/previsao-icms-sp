# Hint Sheet Extractor

**ID:** `hint_sheet_extractor`
**Extends:** [[_base_ingester]]
**Type:** `hybrid`

Extracts structured factual signals from legal text via 20+ regex patterns + optional spaCy NER. Covers dates, monetary values, persons, OAB, CPF/CNPJ, process numbers, legal references, decisions, timeline events. Includes optional LLM validation pass.

## Library Info

- **Origin:** analise-autos (v5-chunked)
- **Proven in production:** yes
- **Typical cost:** $0.01
- **Typical duration:** 5s
- **Quality notes:** Production-proven on 500+ page proceedings. 14 extraction categories, 20+ regex patterns. Consolidates hint_sheet_extractor + hint_sheet_validator from analise-autos.

**Domain:** `juridico.ingestao`
**Also relevant:** `juridico.processual`

## Complementary Workers

- [[pdf_ingester]]
- [[document_splitter]]
- [[procedure_detector]]
- [[document_chunker]]
- [[claim_analyzer]]

## Use Cases

- Extract dates, monetary values, persons from judicial proceedings
- Build structured hint sheet for downstream claim/evidence analyzers
- Identify OAB numbers, process numbers, CPF/CNPJ from raw text
- Validate extracted data with LLM cross-check

## Known Limitations

- Regex patterns optimized for Brazilian legal documents (TJ-SP, CNJ format)
- spaCy is optional — degrades gracefully to regex-only if missing
- Person extraction may include false positives from legal text headers
- Monetary value context classification depends on keyword proximity

---
[[_index|← Back to catalog]] | [[_by_domain|By domain]] | [[_by_type|By type]]

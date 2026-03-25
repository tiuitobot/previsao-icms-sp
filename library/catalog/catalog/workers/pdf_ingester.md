# PDF Ingester

**ID:** `pdf_ingester`
**Extends:** [[_base_ingester]]
**Type:** `deterministic`

Extracts text from PDFs via PyMuPDF (digital) + Azure Document Intelligence (scanned). Classifies pages, removes boilerplate, assembles documents with manifest.

## Library Info

- **Origin:** analise-autos (v5-chunked)
- **Proven in production:** yes
- **Typical cost:** $0.02
- **Typical duration:** 30s
- **Quality notes:** Production-proven on 500+ page judicial PDFs. Hybrid extraction (digital+OCR) with page classification. Boilerplate removal handles TJ-SP, PJe, ESAJ patterns.

**Domain:** `generico.ingestao`
**Also relevant:** `juridico.ingestao`

## Complementary Workers

- [[document_splitter]]
- [[hint_sheet_extractor]]

## Use Cases

- Extract text from judicial proceedings (autos processuais)
- OCR scanned documents with Azure Document Intelligence
- Prepare any PDF corpus for downstream LLM analysis

## Known Limitations

- Azure Document Intelligence requires AZURE_DOC_INTELLIGENCE_ENDPOINT and AZURE_DOC_INTELLIGENCE_KEY env vars
- Falls back to PyMuPDF-only if Azure credentials not set (scanned pages may have poor text)
- 3MB per-chunk limit for Azure OCR (auto-splits larger PDFs)
- Page classification uses text density heuristic — may misclassify mixed pages

---
[[_index|← Back to catalog]] | [[_by_domain|By domain]] | [[_by_type|By type]]

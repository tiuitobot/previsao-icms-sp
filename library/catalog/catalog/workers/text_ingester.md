# Text File Ingester

**ID:** `text_ingester`
**Extends:** [[_base_ingester]]
**Type:** `deterministic`

Reads plain-text and Markdown files from a data directory and returns individual and combined text content.

## Library Info

- **Origin:** pipeline-engine (sprint-3)
- **Typical cost:** $0
- **Typical duration:** 2s
- **Quality notes:** Deterministic — output is reproducible given same input files.

**Domain:** `generico.orquestracao`

## Complementary Workers

- [[_base_scout]]
- [[_base_llm_analyzer]]
- [[json_ingester]]

## Use Cases

- Ingest plain-text documents for analysis pipelines
- Combine multiple text files into a single input blob
- Feed Markdown documentation into LLM workers

## Known Limitations

- Files must be UTF-8 encoded
- Binary files will cause encoding errors
- Very large files are loaded entirely into memory

---
[[_index|← Back to catalog]] | [[_by_domain|By domain]] | [[_by_type|By type]]

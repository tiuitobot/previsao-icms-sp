# JSON/CSV Ingester

**ID:** `json_ingester`
**Extends:** [[_base_ingester]]
**Type:** `deterministic`

Reads JSON and CSV files from a data directory, parses them, and returns structured output for downstream steps.

## Library Info

- **Origin:** pipeline-engine (sprint-3)
- **Typical cost:** $0
- **Typical duration:** 3s
- **Quality notes:** Deterministic — output is reproducible given same input files.

**Domain:** `generico.orquestracao`

## Complementary Workers

- [[_base_scout]]
- [[_base_llm_analyzer]]
- [[text_ingester]]

## Use Cases

- Ingest structured data files for analysis pipelines
- Parse mixed JSON/CSV datasets into unified format
- Input normalization for downstream LLM workers

## Known Limitations

- CSV files must be UTF-8 encoded
- JSON files must be valid — no trailing commas or comments
- Very large files are loaded entirely into memory

---
[[_index|← Back to catalog]] | [[_by_domain|By domain]] | [[_by_type|By type]]

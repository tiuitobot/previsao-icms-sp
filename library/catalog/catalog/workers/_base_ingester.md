# Base Ingester

**ID:** `_base_ingester`
**Type:** `deterministic`
**Abstract:** yes (cannot be used directly in DAG)

Reads input files, normalizes formats, and produces structured JSON for downstream workers.

## Library Info

- **Origin:** pipeline-engine (sprint-3)
- **Proven in production:** yes
- **Typical cost:** $0
- **Typical duration:** 5s
- **Quality notes:** Deterministic — output is reproducible given same input.

**Domain:** `generico.orquestracao`

## Complementary Workers

- [[_base_scout]]
- [[_base_llm_analyzer]]

## Use Cases

- File ingestion and normalization
- Format conversion to structured JSON
- Input validation and sanitization

## Known Limitations

- Concrete subclasses must handle encoding detection
- Binary formats (PDF, DOCX) require additional dependencies

---
[[_index|← Back to catalog]] | [[_by_domain|By domain]] | [[_by_type|By type]]

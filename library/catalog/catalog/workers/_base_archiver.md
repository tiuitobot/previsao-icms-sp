# Base Archiver

**ID:** `_base_archiver`
**Type:** `deterministic`
**Abstract:** yes (cannot be used directly in DAG)

Archives run outputs with full provenance metadata for audit and reproducibility.

## Library Info

- **Origin:** pipeline-engine (sprint-3)
- **Proven in production:** yes
- **Typical cost:** $0
- **Typical duration:** 3s
- **Quality notes:** Final step in most pipelines. Ensures complete provenance chain.

**Domain:** `generico.orquestracao`

## Complementary Workers

- [[_base_renderer]]
- [[_base_verifier]]

## Use Cases

- Run output archival with timestamps
- Provenance tracking for audit compliance
- Reproducibility support via output snapshots

## Known Limitations

- Storage backend must be configured externally
- Large binary outputs may require streaming archival

---
[[_index|← Back to catalog]] | [[_by_domain|By domain]] | [[_by_type|By type]]

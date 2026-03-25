# Procedure Detector

**ID:** `procedure_detector`
**Extends:** [[_base_ingester]]
**Type:** `deterministic`

Detects multiple procedural types in legal proceedings (inventário, execução, usucapião, etc.) using keyword analysis, temporal gap detection, and party-change signals. Pure deterministic, $0.

## Library Info

- **Origin:** analise-autos (v5-chunked)
- **Proven in production:** yes
- **Typical cost:** $0
- **Typical duration:** 3s
- **Quality notes:** Production-proven on multi-procedure proceedings. Deterministic keyword + temporal gap + party-change heuristics. Archival signal detection (trânsito em julgado, arquive-se).

**Domain:** `juridico.ingestao`

## Complementary Workers

- [[hint_sheet_extractor]]
- [[document_splitter]]
- [[claim_analyzer]]

## Use Cases

- Detect if proceedings contain multiple procedures (inventário + execução)
- Identify the active vs archived procedure
- Map documents to their procedural context

## Known Limitations

- Keyword vocabulary covers 13 Brazilian procedural types — custom types need vocabulary extension
- Temporal gap threshold is 12 months — may miss shorter procedure boundaries
- Party-change detection depends on hint_sheet persons data quality

---
[[_index|← Back to catalog]] | [[_by_domain|By domain]] | [[_by_type|By type]]

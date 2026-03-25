# Report Assembler

**ID:** `report_assembler`
**Extends:** [[_base_consolidator]]
**Type:** `deterministic`

Reads all JSON output files from a pipeline run and merges them into a unified report structure.

## Library Info

- **Origin:** pipeline-engine (sprint-3)
- **Typical cost:** $0
- **Typical duration:** 2s
- **Quality notes:** Deterministic assembly. Output order matches alphabetical file order.

**Domain:** `generico.orquestracao`

## Complementary Workers

- [[generic_html_renderer]]
- [[_base_llm_analyzer]]

## Use Cases

- Assemble final report from parallel analysis outputs
- Merge per-step JSON results into a single deliverable
- Provide unified input for HTML rendering step

## Known Limitations

- All input files must be valid JSON
- Merge order is alphabetical by filename
- No deduplication of findings across files — downstream consumers should handle that

---
[[_index|← Back to catalog]] | [[_by_domain|By domain]] | [[_by_type|By type]]

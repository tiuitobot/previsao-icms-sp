# Generic HTML Renderer

**ID:** `generic_html_renderer`
**Extends:** [[_base_renderer]]
**Type:** `deterministic`

Renders structured JSON data through a Jinja2 template into HTML output. Domain-agnostic — any consumer can supply their own template.

## Library Info

- **Origin:** pipeline-engine (sprint-3)
- **Typical cost:** $0
- **Typical duration:** 2s
- **Quality notes:** Deterministic rendering. Consumer provides both template and data.

**Domain:** `generico.orquestracao`

## Complementary Workers

- [[_base_consolidator]]
- [[report_assembler]]

## Use Cases

- HTML report generation from any structured data
- Template-based output formatting for any domain
- Professional document rendering with custom CSS

## Known Limitations

- Template must match document type (academic_report for reports, report for dashboards)
- Requires jinja2 and markdown packages installed
- primary output is metadata JSON — the actual HTML goes to report/report.html

---
[[_index|← Back to catalog]] | [[_by_domain|By domain]] | [[_by_type|By type]]

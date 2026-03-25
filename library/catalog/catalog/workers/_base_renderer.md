# Base Renderer

**ID:** `_base_renderer`
**Type:** `deterministic`
**Abstract:** yes (cannot be used directly in DAG)

Renders structured JSON data through Jinja2 templates into HTML output.

## Library Info

- **Origin:** pipeline-engine (sprint-3)
- **Proven in production:** yes
- **Typical cost:** $0
- **Typical duration:** 2s
- **Quality notes:** Deterministic rendering. Template is the single source of formatting truth.

**Domain:** `generico.orquestracao`

## Complementary Workers

- [[_base_consolidator]]
- [[_base_verifier]]
- [[_base_archiver]]

## Use Cases

- HTML report generation from structured data
- Template-based output formatting
- Professional document rendering with CSS

## Known Limitations

- Template must be compatible with data schema
- Large reports may require streaming rendering

---
[[_index|← Back to catalog]] | [[_by_domain|By domain]] | [[_by_type|By type]]

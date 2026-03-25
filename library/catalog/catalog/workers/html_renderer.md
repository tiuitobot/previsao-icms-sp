# HTML Renderer

**ID:** `html_renderer`
**Extends:** [[_base_renderer]]
**Type:** `deterministic`

Renders consolidated legal analysis into professional HTML using an immutable Jinja2 template.

## Library Info

- **Origin:** analise-autos (v5-chunked)
- **Proven in production:** yes
- **Typical cost:** $0
- **Typical duration:** 1s
- **Quality notes:** Immutable template ensures consistent output format. CSS-only customization prevents layout breakage.

**Domain:** `generico.orquestracao`
**Also relevant:** `juridico.processual`

## Complementary Workers

- [[chunk_consolidator]]

## Use Cases

- Generate professional HTML report from legal analysis
- Produce printable A4-formatted output
- Render party tables, timelines, and value summaries

## Known Limitations

- Template is immutable — customization via CSS only
- Large reports (>500 findings) may render slowly in browsers
- Print layout optimized for A4 paper

---
[[_index|← Back to catalog]] | [[_by_domain|By domain]] | [[_by_type|By type]]

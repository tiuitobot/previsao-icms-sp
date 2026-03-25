# Theme Extractor

**ID:** `theme_extractor`
**Extends:** [[_base_llm_analyzer]]
**Type:** `llm`

Extracts the material's own thematic structure before analysis. Maps themes to canonical taxonomies. Neutralizes tendentious language. All downstream workers use extracted themes to focus search — prevents aimless exploration.

## Library Info

- **Origin:** rt-noopenclaw (v37)
- **Proven in production:** yes
- **Typical cost:** $0.02
- **Typical duration:** 15s
- **Quality notes:** Production-proven in rt-noopenclaw (v37). Theme-first scaffolding prevents aimless LLM exploration — each downstream worker searches for specific themes instead of everything.

**Domain:** `generico.extracao`

## Complementary Workers

- [[claim_extractor]]
- [[priority_context_scout]]

## Use Cases

- Extract themes from legal documents before clause analysis
- Map financial report sections to standard taxonomy before analysis
- Identify key topics in technical report before review

## Known Limitations

- Quality depends on material having identifiable structure
- Taxonomy mapping requires domain-specific taxonomy input for best results
- Tendentious language neutralization may miss subtle framing

---
[[_index|← Back to catalog]] | [[_by_domain|By domain]] | [[_by_type|By type]]

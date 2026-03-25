# Report Compiler

**ID:** `report_compiler`
**Extends:** [[_base_renderer]]
**Type:** `deterministic`

Assembles classified and tiered findings into professional HTML with confidence badges, finding cards, and annexes.

## Library Info

- **Origin:** rt-noopenclaw (v37)
- **Proven in production:** yes
- **Typical cost:** $0
- **Typical duration:** 3s
- **Quality notes:** Deterministic assembly. Badge system (blindado=green, alta_confianca=blue, sugestao=yellow) is production-proven. Annexes include source excerpts.

**Domain:** `educacional.avaliacao`

## Complementary Workers

- [[confidence_tier_assigner]]
- [[adversarial_reviewer]]
- [[run_archiver]]

## Use Cases

- Generate professional HTML report with visual badges
- Render finding cards with confidence indicators
- Compile annexes with source references

## Known Limitations

- Badge colors are hardcoded to blindado/alta_confianca/sugestao tiers
- Annex generation may be slow with many source documents
- Print layout optimized for A4 paper

---
[[_index|← Back to catalog]] | [[_by_domain|By domain]] | [[_by_type|By type]]

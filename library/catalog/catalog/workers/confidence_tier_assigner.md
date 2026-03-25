# Confidence Tier Assigner

**ID:** `confidence_tier_assigner`
**Extends:** [[_base_classifier]]
**Type:** `llm`

Assigns operational confidence tiers (blindado/alta_confianca/sugestao) to findings for report presentation.

## Library Info

- **Origin:** rt-noopenclaw (v37)
- **Proven in production:** yes
- **Typical cost:** $0.02
- **Typical duration:** 10s
- **Quality notes:** Three-tier model: blindado (bulletproof, multiple confirmations), alta_confianca (high confidence), sugestao (suggestion/advisory). Drives report badges.

**Domain:** `generico.classificacao`

## Complementary Workers

- [[finding_classifier]]
- [[adversarial_reviewer]]
- [[report_compiler]]

## Use Cases

- Assign operational confidence tiers to findings
- Distinguish bulletproof findings from suggestions
- Drive visual presentation (badges, colors) in reports

## Known Limitations

- Tier boundaries are calibrated for Portuguese-language legal/technical documents
- Blindado (armored) tier requires multiple independent confirmations
- Sugestao tier findings should be clearly marked as advisory in reports

---
[[_index|← Back to catalog]] | [[_by_domain|By domain]] | [[_by_type|By type]]

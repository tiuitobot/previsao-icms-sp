# Scanner Adversarial

**ID:** `scanner_adversarial`
**Extends:** [[_base_llm_analyzer]]
**Type:** `llm`

Adversarial auditor that challenges primary scanner output using a different model to catch blind spots and biases.

## Library Info

- **Origin:** rt-noopenclaw (v37)
- **Proven in production:** yes
- **Typical cost:** $0.08
- **Typical duration:** 35s
- **Quality notes:** Originally scanner_opus in rt-noopenclaw. Multi-model pattern is core to quality — must use different model family than scanner_generalist.

**Domain:** `educacional.avaliacao`

## Complementary Workers

- [[scanner_generalist]]
- [[finding_classifier]]
- [[orchestrator_merge_helper]]

## Use Cases

- Adversarial audit of primary scanner output
- Multi-model cross-validation of findings
- Bias and blind spot detection

## Known Limitations

- Effectiveness depends on using a genuinely different model from primary scanner
- May flag stylistic differences as substantive findings
- Cost is higher due to strong model requirement

---
[[_index|← Back to catalog]] | [[_by_domain|By domain]] | [[_by_type|By type]]

# Scanner Generalist

**ID:** `scanner_generalist`
**Extends:** [[_base_llm_analyzer]]
**Type:** `llm`

Two-phase document scanning: first applies a prescribed checklist, then performs free-form exploration for unexpected findings.

## Library Info

- **Origin:** rt-noopenclaw (v37)
- **Proven in production:** yes
- **Typical cost:** $0.06
- **Typical duration:** 30s
- **Quality notes:** Originally scanner_gpt in rt-noopenclaw. Two-phase design catches both expected and unexpected issues. Best paired with adversarial scanner.

**Domain:** `educacional.avaliacao`

## Complementary Workers

- [[scanner_adversarial]]
- [[claim_extractor]]
- [[finding_classifier]]

## Use Cases

- Comprehensive document review with structured checklist
- Discovery of unexpected issues via free exploration
- Primary analysis before adversarial review

## Known Limitations

- Free exploration phase may produce low-confidence findings
- Checklist phase is only as good as the checklist
- Long documents may hit token limits in single-pass mode

---
[[_index|← Back to catalog]] | [[_by_domain|By domain]] | [[_by_type|By type]]

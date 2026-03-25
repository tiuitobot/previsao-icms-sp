# Source Link Checker

**ID:** `source_link_checker`
**Extends:** [[_base_verifier]]
**Type:** `deterministic`

Validates URLs, normative references, and citation links found in findings and source materials.

## Library Info

- **Origin:** rt-noopenclaw (v37)
- **Proven in production:** yes
- **Typical cost:** $0
- **Typical duration:** 10s
- **Quality notes:** Deterministic URL and reference checker. Network-dependent. Timeout is configurable. Pairs with factcheck_worker for complete verification.

**Domain:** `generico.verificacao`

## Complementary Workers

- [[factcheck_worker]]
- [[claim_extractor]]
- [[report_compiler]]

## Use Cases

- Validate all URLs referenced in findings
- Check normative references against known databases
- Flag broken or unreachable source links

## Known Limitations

- URL checks require network access
- Paywalled URLs will report as accessible but unverifiable
- Normative reference validation limited to configured databases

---
[[_index|← Back to catalog]] | [[_by_domain|By domain]] | [[_by_type|By type]]

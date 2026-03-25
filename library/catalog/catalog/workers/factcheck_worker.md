# Fact-Check Worker

**ID:** `factcheck_worker`
**Extends:** [[_base_verifier]]
**Type:** `deterministic`

Performs horizontal fact-checking driven by claim inventory, verifying each claim against available evidence.

## Library Info

- **Origin:** rt-noopenclaw (v37)
- **Proven in production:** yes
- **Typical cost:** $0
- **Typical duration:** 5s
- **Quality notes:** Domain-agnostic. Horizontal fact-checking means every claim is checked, not just flagged ones. Pairs naturally with claim_extractor.

**Domain:** `generico.verificacao`

## Complementary Workers

- [[claim_extractor]]
- [[finding_classifier]]
- [[source_link_checker]]

## Use Cases

- Systematic verification of extracted claims
- Evidence-based fact-checking
- Quality gate before classification

## Known Limitations

- Can only verify claims against provided evidence — no external lookup
- Implicit claims without explicit anchors may be skipped
- Confidence scoring is binary (verified/unverified) not probabilistic

---
[[_index|← Back to catalog]] | [[_by_domain|By domain]] | [[_by_type|By type]]

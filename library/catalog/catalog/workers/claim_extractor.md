# Claim Extractor

**ID:** `claim_extractor`
**Extends:** [[_base_claim_extractor]]
**Type:** `llm`

Builds a comprehensive claim_inventory from any document: testable assertions with risk flags, suggested check types, and target workers. Use as MANDATORY Phase 0 input for scanners and researchers — forces coverage of structural risks.

## Library Info

- **Origin:** rt-noopenclaw (v37)
- **Proven in production:** yes
- **Typical cost:** $0.03
- **Typical duration:** 15s
- **Quality notes:** Tier 1 reusability — domain-agnostic, production-proven across legal, educational, and technical documents. Critical upstream dependency.

**Domain:** `generico.extracao`

## Complementary Workers

- [[factcheck_worker]]
- [[finding_classifier]]
- [[scanner_generalist]]

## Use Cases

- Build verifiable claim inventory from any document
- Risk-classify claims for downstream fact-checking
- Provide claim anchors for finding_classifier and factcheck_worker

## Known Limitations

- Implicit claims in rhetorical text are harder to extract
- Very long documents may require chunked processing
- Claim granularity depends on prompt calibration

---
[[_index|← Back to catalog]] | [[_by_domain|By domain]] | [[_by_type|By type]]

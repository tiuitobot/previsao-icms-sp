# Micro Verifier

**ID:** `micro_verifier`
**Extends:** [[_base_verifier]]
**Type:** `llm`

Focused verification of high-severity findings. For each HIGH/MEDIUM finding, runs a targeted check: can it be confirmed, refuted, or corrected? Produces per-finding verdict with evidence. Feeds into verifier gate.

## Library Info

- **Origin:** rt-noopenclaw (v37)
- **Proven in production:** yes
- **Typical cost:** $0.03
- **Typical duration:** 15s
- **Quality notes:** From rt-noopenclaw step 16. Map-eligible: can run one micro-check per finding in parallel. Key: produces per-finding verdict (confirmed/refuted/corrected/inconclusive), not just pass/fail.

**Domain:** `generico.verificacao`

## Complementary Workers

- [[finding_consolidator]]
- [[cross_validate]]
- [[inferential_consistency_checker]]

## Use Cases

- Verify high-risk findings in contract analysis before final report
- Double-check critical financial discrepancies before investor report
- Confirm or refute key claims in due diligence findings

## Known Limitations

- Only verifies HIGH and MEDIUM findings by default (configurable threshold)
- Cannot verify claims that require external data not in pipeline context
- Refutation quality depends on available evidence in ingested_data

---
[[_index|← Back to catalog]] | [[_by_domain|By domain]] | [[_by_type|By type]]

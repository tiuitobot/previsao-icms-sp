# Base Verifier

**ID:** `_base_verifier`
**Type:** `deterministic`
**Abstract:** yes (cannot be used directly in DAG)

Mechanical verification and quality gate that validates outputs against claims and references.

## Library Info

- **Origin:** pipeline-engine (sprint-3)
- **Proven in production:** yes
- **Typical cost:** $0
- **Typical duration:** 5s
- **Quality notes:** Checkpoint recommended. Deterministic — failures are reproducible. Use as quality gate before final output.

**Domain:** `generico.verificacao`

## Complementary Workers

- [[_base_claim_extractor]]
- [[_base_classifier]]
- [[_base_renderer]]

## Use Cases

- Fact-checking against claim inventory
- URL and reference validation
- Quality gate before rendering

## Known Limitations

- Mechanical checks cannot catch semantic errors
- URL validation requires network access

---
[[_index|← Back to catalog]] | [[_by_domain|By domain]] | [[_by_type|By type]]

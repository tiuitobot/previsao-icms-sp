# Base Claim Extractor

**ID:** `_base_claim_extractor`
**Type:** `llm`
**Abstract:** yes (cannot be used directly in DAG)

Extracts verifiable claims from documents with structural risk classification.

## Library Info

- **Origin:** pipeline-engine (sprint-3)
- **Proven in production:** yes
- **Typical cost:** $0.03
- **Typical duration:** 15s
- **Quality notes:** Critical upstream dependency for verifiers and fact-checkers. Claim quality determines pipeline ceiling.

**Domain:** `generico.extracao`

## Complementary Workers

- [[_base_verifier]]
- [[_base_reviewer]]
- [[_base_classifier]]

## Use Cases

- Inventory of verifiable claims in documents
- Risk classification of document assertions
- Input preparation for fact-checking workers

## Known Limitations

- Claim boundary detection depends on document structure
- Implicit claims may be missed without domain-specific prompting

---
[[_index|← Back to catalog]] | [[_by_domain|By domain]] | [[_by_type|By type]]

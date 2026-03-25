# Base LLM Analyzer

**ID:** `_base_llm_analyzer`
**Type:** `llm`
**Abstract:** yes (cannot be used directly in DAG)

Receives structured data, applies a contract-bound LLM prompt, and produces structured analysis output.

## Library Info

- **Origin:** pipeline-engine (sprint-3)
- **Proven in production:** yes
- **Typical cost:** $0.05
- **Typical duration:** 20s
- **Quality notes:** Workhorse pattern. Most domain-specific workers extend this. Map-eligible for chunked processing.

**Domain:** `generico.verificacao`

## Complementary Workers

- [[_base_ingester]]
- [[_base_consolidator]]
- [[_base_verifier]]

## Use Cases

- Structured document analysis
- Domain-specific extraction and classification
- Parallel chunk analysis via map pattern

## Known Limitations

- Output quality depends on contract prompt quality
- Token limits may require chunked input via map pattern

---
[[_index|← Back to catalog]] | [[_by_domain|By domain]] | [[_by_type|By type]]

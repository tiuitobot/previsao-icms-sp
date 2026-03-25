# Base Consolidator

**ID:** `_base_consolidator`
**Type:** `deterministic`
**Abstract:** yes (cannot be used directly in DAG)

Merges outputs from N parallel workers into a single unified result with deduplication.

## Library Info

- **Origin:** pipeline-engine (sprint-3)
- **Proven in production:** yes
- **Typical cost:** $0
- **Typical duration:** 3s
- **Quality notes:** Deterministic reduce step. Pairs naturally with map-eligible analyzers.

**Domain:** `generico.orquestracao`

## Complementary Workers

- [[_base_llm_analyzer]]
- [[_base_classifier]]
- [[_base_renderer]]

## Use Cases

- Reduce step after map-parallel analysis
- Deduplication of findings across workers
- Canonical resolution of conflicting outputs

## Known Limitations

- Merge conflicts require deterministic resolution strategy
- Large output sets may need streaming consolidation

---
[[_index|← Back to catalog]] | [[_by_domain|By domain]] | [[_by_type|By type]]

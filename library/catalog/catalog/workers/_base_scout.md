# Base Scout

**ID:** `_base_scout`
**Type:** `llm`
**Abstract:** yes (cannot be used directly in DAG)

Lightweight LLM triage that classifies and prioritizes input before deep analysis.

## Library Info

- **Origin:** pipeline-engine (sprint-3)
- **Proven in production:** yes
- **Typical cost:** $0.01
- **Typical duration:** 8s
- **Quality notes:** Designed for speed over depth. Use cheap models (gpt-4.1-mini, haiku).

**Domain:** `generico.verificacao`

## Complementary Workers

- [[_base_ingester]]
- [[_base_llm_analyzer]]

## Use Cases

- Pre-analysis triage and prioritization
- Topic/theme extraction
- Routing decisions for downstream workers

## Known Limitations

- Scout output is advisory — downstream workers must validate
- Cheap models may miss subtle classification boundaries

---
[[_index|← Back to catalog]] | [[_by_domain|By domain]] | [[_by_type|By type]]

# Request Interpreter

**ID:** `request_interpreter`
**Type:** `llm`

Reads user request and pipeline config, produces interpretation that customizes the DAG for this run. Enables dynamic pipelines that adapt to user input.

## Library Info

- **Origin:** pipeline-engine ()
- **Typical cost:** $0.02
- **Typical duration:** 3s
- **Quality notes:** Must be first step. Output drives pipeline resolution.

**Domain:** `generico.orquestracao`

## Use Cases

- Dynamic pipeline parametrization from user request

---
[[_index|← Back to catalog]] | [[_by_domain|By domain]] | [[_by_type|By type]]

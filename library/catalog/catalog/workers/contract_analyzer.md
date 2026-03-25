# Contract Analyzer (base class)

**ID:** `contract_analyzer`
**Extends:** [[_base_llm_analyzer]]
**Type:** `llm`
**Abstract:** yes (cannot be used directly in DAG)

Abstract base for contract analysis workers. Do NOT use directly — decompose into specialized workers (clause analysis, risk review, compliance check, financial terms, etc.). A single monolithic analyzer violates the decomposition rule.

## Library Info

- **Origin:** due-diligence-pipeline (v1)
- **Typical cost:** $0.05
- **Typical duration:** 25s
- **Quality notes:** ABSTRACT. Create concrete workers that extend this for specific analysis dimensions (clauses, risks, compliance, financials, parties).

**Domain:** `juridico.contratual`
**Also relevant:** `financeiro.due-diligence`

## Complementary Workers

- [[financial_analyzer]]
- [[legal_analyzer]]
- [[risk_consolidator]]

## Use Cases

- Base class — extend with specialized contract analysis workers
- Defines inputs/outputs contract for contract analysis domain

## Known Limitations

- ABSTRACT — do not use directly in a pipeline
- Decompose into ≥3 specialized workers: clause_analyst, risk_reviewer, compliance_checker, financial_analyst, etc.
- A single worker doing all contract analysis is a chat wrapper, not a pipeline

---
[[_index|← Back to catalog]] | [[_by_domain|By domain]] | [[_by_type|By type]]

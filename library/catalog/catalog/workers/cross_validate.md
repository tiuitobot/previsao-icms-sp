# Cross Validator

**ID:** `cross_validate`
**Extends:** [[_base_verifier]]
**Type:** `deterministic`

Checks LLM output numbers against source data from deterministic steps. Flags discrepancies above tolerance.

## Library Info

- **Origin:** investimentos-br-2026 (v1)
- **Proven in production:** yes
- **Typical cost:** $0
- **Quality notes:** Tolerance 5%. Extrai numeros do LLM output via regex. Pode perder numeros em formato nao padrao.

**Domain:** `generico.verificacao`
**Also relevant:** `financeiro.due-diligence`

## Complementary Workers

- [[macro_data]]
- [[renda_fixa_data]]

## Use Cases

- Validacao de numeros citados pelo LLM
- Anti-hallucination gate

## Known Limitations

- Mechanical checks cannot catch semantic errors
- URL validation requires network access

---
[[_index|← Back to catalog]] | [[_by_domain|By domain]] | [[_by_type|By type]]

# BCB Macro Data Fetcher

**ID:** `macro_data`
**Extends:** [[_base_ingester]]
**Type:** `deterministic`

Fetches Selic, IPCA, cambio, Focus expectations from BCB SGS API. Calculates real interest rate, spreads, trends.

## Library Info

- **Origin:** investimentos-br-2026 (v1)
- **Proven in production:** yes
- **Typical cost:** $0
- **Typical duration:** 2s
- **Quality notes:** BCB SGS API publica, sem autenticacao. Focus API pode retornar vazio fora do horario.

**Domain:** `financeiro.macro`
**Also relevant:** `financeiro.investimentos`

## Complementary Workers

- [[renda_fixa_data]]
- [[renda_variavel_data]]

## Use Cases

- Analise macroeconomica Brasil
- Cenario de juros e inflacao

## Known Limitations

- Concrete subclasses must handle encoding detection
- Binary formats (PDF, DOCX) require additional dependencies

---
[[_index|← Back to catalog]] | [[_by_domain|By domain]] | [[_by_type|By type]]

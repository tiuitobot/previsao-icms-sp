# Tesouro Direto Data Fetcher

**ID:** `renda_fixa_data`
**Extends:** [[_base_ingester]]
**Type:** `deterministic`

Fetches NTN-B, LTN, LFT, NTN-F rates from Tesouro Direto/Transparente. Calculates carry, implied inflation, spreads vs CDI.

## Library Info

- **Origin:** investimentos-br-2026 (v1)
- **Proven in production:** yes
- **Typical cost:** $0
- **Typical duration:** 5s
- **Quality notes:** API principal do Tesouro pode retornar 403. Fallback para Tesouro Transparente CSV funciona.

**Domain:** `financeiro.investimentos`

## Complementary Workers

- [[macro_data]]

## Use Cases

- Analise de titulos publicos
- Carry analysis
- Curva de juros

## Known Limitations

- Concrete subclasses must handle encoding detection
- Binary formats (PDF, DOCX) require additional dependencies

---
[[_index|← Back to catalog]] | [[_by_domain|By domain]] | [[_by_type|By type]]

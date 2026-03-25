# Decision Value Mapper

**ID:** `decision_value_mapper`
**Extends:** [[_base_llm_analyzer]]
**Type:** `llm`

Extracts judicial decisions, monetary values, corrections, and payment obligations from document chunks.

## Library Info

- **Origin:** analise-autos (v5-chunked)
- **Proven in production:** yes
- **Typical cost:** $0.06
- **Typical duration:** 25s
- **Quality notes:** Monetary extraction is high-stakes. Hint sheet pre-extraction of values improves accuracy significantly.

**Domain:** `juridico.processual`
**Also relevant:** `financeiro.contabilidade`

## Complementary Workers

- [[document_chunker]]
- [[hint_sheet_extractor]]
- [[chunk_consolidator]]

## Use Cases

- Extract judicial decisions and their monetary impact
- Map payment obligations and deadlines
- Track value corrections and interest calculations

## Known Limitations

- Monetary correction indices may not be fully resolved
- Conditional values (e.g., 'if appeal fails') require interpretation
- Currency formatting varies across Brazilian courts

---
[[_index|← Back to catalog]] | [[_by_domain|By domain]] | [[_by_type|By type]]

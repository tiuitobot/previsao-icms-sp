# Temas Extraction

**ID:** `temas_extraction`
**Extends:** [[_base_scout]]
**Type:** `llm`

Extracts topics and themes from documents with taxonomy alignment for downstream routing and prioritization.

## Library Info

- **Origin:** rt-noopenclaw (v37)
- **Proven in production:** yes
- **Typical cost:** $0.01
- **Typical duration:** 8s
- **Quality notes:** Lightweight scout. Uses cheap model for speed. Taxonomy alignment improves downstream routing accuracy.

**Domain:** `educacional.avaliacao`

## Complementary Workers

- [[priority_context_scout]]
- [[scanner_generalist]]

## Use Cases

- Topic extraction from any document type
- Theme alignment with predefined taxonomy
- Routing decisions for domain-specific analyzers

## Known Limitations

- Taxonomy alignment depends on taxonomy completeness
- Novel topics not in taxonomy are tagged as 'other'
- Best with Portuguese and English text

---
[[_index|← Back to catalog]] | [[_by_domain|By domain]] | [[_by_type|By type]]

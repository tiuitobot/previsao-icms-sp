# Adversarial Scanner (base class)

**ID:** `adversarial_scanner`
**Extends:** [[_base_llm_analyzer]]
**Type:** `llm`
**Abstract:** yes (cannot be used directly in DAG)

Abstract base for adversarial dual-track scanning. Create TWO concrete scanners that extend this: one generalist (high recall) and one adversarial (audits the first, finds gaps). The adversarial scanner reads the generalist's output as Phase 0 input and produces NON-DUPLICATE findings.

## Library Info

- **Origin:** rt-noopenclaw (v37)
- **Proven in production:** yes
- **Typical cost:** $0.1
- **Typical duration:** 30s
- **Quality notes:** ABSTRACT. From rt-noopenclaw R9: 'Modelo adversarial > modelo redundante. Modelos diferentes cobrem blind spots diferentes.' Create 2 concrete children with different models (e.g., GPT for generalist, Claude for adversarial).

**Domain:** `generico.qualidade`

## Complementary Workers

- [[finding_consolidator]]
- [[inferential_consistency_checker]]
- [[micro_verifier]]

## Use Cases

- Dual-track contract analysis (generalist + auditor)
- Code review (generalist scanner + security-focused adversarial)
- Financial analysis (analyst + challenger)
- Due diligence (investigator + skeptic)

## Known Limitations

- ABSTRACT — create 2 concrete scanners (generalist + adversarial)
- Adversarial scanner MUST read generalist output first (Phase 0 dependency)
- Use DIFFERENT models for each scanner (R9: adversarial > redundant)
- Explicit deduplication rule: adversarial cannot produce findings on same issue as generalist

---
[[_index|← Back to catalog]] | [[_by_domain|By domain]] | [[_by_type|By type]]

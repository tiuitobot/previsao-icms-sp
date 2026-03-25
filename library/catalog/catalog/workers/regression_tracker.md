# Regression Tracker

**ID:** `regression_tracker`
**Extends:** [[_base_verifier]]
**Type:** `deterministic`

Compares current run findings against a prior run. Flags findings that disappeared (regression), changed severity, or were added. Deterministic — compares JSON output files between runs by finding ID and semantic anchor.

## Library Info

- **Origin:** rt-noopenclaw (v37)
- **Proven in production:** yes
- **Typical cost:** $0
- **Typical duration:** 2s
- **Quality notes:** Deterministic, $0. From rt-noopenclaw step 40. Critical for iterative pipelines — catches when a HIGH finding silently disappears between runs.

**Domain:** `generico.qualidade`

## Complementary Workers

- [[finding_consolidator]]
- [[cross_validate]]

## Use Cases

- Detect quality regression between pipeline iterations
- Track finding stability across contract revisions
- Compare analysis results before/after contract amendment

## Known Limitations

- Requires prior run in workspace/outputs/runs/ (uses latest symlink or explicit --prior-run)
- Finding matching by ID — if IDs changed between runs, may not match
- Semantic matching fallback uses title similarity (Levenshtein)

---
[[_index|← Back to catalog]] | [[_by_domain|By domain]] | [[_by_type|By type]]

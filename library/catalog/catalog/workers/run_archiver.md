# Run Archiver

**ID:** `run_archiver`
**Extends:** [[_base_archiver]]
**Type:** `deterministic`

Archives all run outputs to a timestamped directory with complete provenance metadata and manifest.

## Library Info

- **Origin:** rt-noopenclaw (v37)
- **Proven in production:** yes
- **Typical cost:** $0
- **Typical duration:** 2s
- **Quality notes:** Final pipeline step. Timestamped directories enable run comparison. Manifest includes all step hashes for reproducibility.

**Domain:** `generico.orquestracao`

## Complementary Workers

- [[report_compiler]]

## Use Cases

- Archive complete run outputs with timestamps
- Generate provenance manifest for audit
- Enable run comparison and reproducibility

## Known Limitations

- Archive directory must be writable
- No built-in cloud storage support — local filesystem only
- Compression adds latency for large output sets

---
[[_index|← Back to catalog]] | [[_by_domain|By domain]] | [[_by_type|By type]]

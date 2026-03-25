"""Append-only JSONL event ledger for pipeline runs.

Emits one JSON line per state transition to both:
- Per-run ledger: {run_dir}/ledger.jsonl
- Global ledger: workspace/outputs/runs/ledger-global.jsonl

Enables post-hoc analysis, debugging, cost tracking, and cross-run queries.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class Ledger:
    """Append-only JSONL event writer with optional global ledger."""

    def __init__(self, output_dir: Path, global_path: Path | None = None):
        self._path = output_dir / "ledger.jsonl"
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = open(self._path, "a", encoding="utf-8")

        self._global_fh = None
        if global_path:
            global_path.parent.mkdir(parents=True, exist_ok=True)
            self._global_fh = open(global_path, "a", encoding="utf-8")

    def emit(self, event: str, **kwargs: Any) -> None:
        """Write a single event line. Flushes immediately."""
        record = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "event": event,
            **kwargs,
        }
        line = json.dumps(record, ensure_ascii=False) + "\n"
        self._fh.write(line)
        self._fh.flush()

        if self._global_fh:
            self._global_fh.write(line)
            self._global_fh.flush()

    def close(self) -> None:
        if self._fh and not self._fh.closed:
            self._fh.close()
        if self._global_fh and not self._global_fh.closed:
            self._global_fh.close()

    def __enter__(self) -> "Ledger":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

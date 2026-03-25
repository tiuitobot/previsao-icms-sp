"""Run manifest and output directory management.

Creates structured output directories and writes manifest.json
with run metadata for auditability and reproducibility.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

RUNNER_VERSION = "0.1.0"


def _file_hash(path: Path, algo: str = "sha256") -> str:
    h = hashlib.new(algo)
    try:
        h.update(path.read_bytes())
    except OSError:
        return ""
    return f"{algo}:{h.hexdigest()[:16]}"


def _dir_hash(path: Path) -> str:
    h = hashlib.sha256()
    if path.is_dir():
        for f in sorted(path.glob("*")):
            h.update(f"{f.name}:{f.stat().st_size}".encode())
    return f"sha256:{h.hexdigest()[:16]}"


def init_run_dir(base_dir: Path, run_id: str) -> dict[str, Path]:
    """Create structured output directory for a run."""
    root = base_dir / "runs" / run_id
    paths = {
        "root": root,
        "steps": root / "steps",
        "chunks": root / "chunks",
        "consolidated": root / "chunks" / "consolidated",
        "report": root / "report",
    }
    for p in paths.values():
        p.mkdir(parents=True, exist_ok=True)
    return paths


class RunManifest:
    """Manages the manifest.json for a pipeline run."""

    def __init__(self, run_dir: Path, run_id: str, pipeline_path: str, data_dir: str, cli_args: list[str] | None = None):
        self.run_dir = run_dir
        self._data: dict[str, Any] = {
            "run_id": run_id,
            "pipeline": pipeline_path,
            "pipeline_hash": _file_hash(Path(pipeline_path)) if Path(pipeline_path).exists() else "",
            "data_dir": data_dir,
            "data_hash": _dir_hash(Path(data_dir)) if Path(data_dir).is_dir() else "",
            "started_at": datetime.now(timezone.utc).isoformat(),
            "completed_at": None,
            "status": "running",
            "total_cost_usd": 0.0,
            "total_duration_s": 0,
            "steps_ok": 0,
            "steps_failed": 0,
            "fixups_applied": 0,
            "fixups_skipped": 0,
            "runner_version": RUNNER_VERSION,
            "cli_args": cli_args or [],
        }

    def finalize(self, status: str, total_cost: float, total_duration: float, steps_ok: int, steps_failed: int, fixups_applied: int = 0, fixups_skipped: int = 0) -> None:
        self._data.update({
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "status": status,
            "total_cost_usd": round(total_cost, 4),
            "total_duration_s": round(total_duration, 1),
            "steps_ok": steps_ok,
            "steps_failed": steps_failed,
            "fixups_applied": fixups_applied,
            "fixups_skipped": fixups_skipped,
        })
        out = self.run_dir / "manifest.json"
        out.write_text(json.dumps(self._data, ensure_ascii=False, indent=2), encoding="utf-8")

    def append_to_index(self, base_dir: Path) -> None:
        """Append run summary to index.jsonl and organize by status."""
        runs_dir = base_dir / "runs"
        index_path = runs_dir / "index.jsonl"
        index_path.parent.mkdir(parents=True, exist_ok=True)

        status = self._data.get("status", "unknown")
        run_id = self._data["run_id"]

        line = json.dumps({
            "run_id": run_id,
            "pipeline": self._data["pipeline"],
            "status": status,
            "started_at": self._data["started_at"],
            "completed_at": self._data.get("completed_at"),
            "total_duration_s": self._data.get("total_duration_s"),
            "total_cost_usd": self._data.get("total_cost_usd"),
            "steps_ok": self._data.get("steps_ok"),
            "steps_failed": self._data.get("steps_failed"),
        }, ensure_ascii=False)
        with open(index_path, "a", encoding="utf-8") as f:
            f.write(line + "\n")

        # Organize by status: success/ and failed/
        status_dir = runs_dir / ("success" if status == "completed" else "failed")
        status_dir.mkdir(parents=True, exist_ok=True)
        status_link = status_dir / run_id
        if not status_link.exists():
            try:
                status_link.symlink_to(self.run_dir)
            except OSError:
                pass  # symlinks may not work on all OS

        # Update latest symlink for successful runs
        if status == "completed":
            latest = runs_dir / "latest"
            try:
                if latest.is_symlink() or latest.exists():
                    latest.unlink()
                latest.symlink_to(self.run_dir)
            except OSError:
                pass

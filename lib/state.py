"""Persistent run state for resume support.

Tracks the status of each step on disk. If the runner restarts with
the same --run-id, completed steps are skipped and their outputs
loaded from disk.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class RunState:
    """Persistent state tracker for a pipeline run."""

    def __init__(self, output_dir: Path, run_id: str, pipeline: str):
        self._path = output_dir / "run_state.json"
        self._data: dict[str, Any]

        if self._path.exists():
            self._data = json.loads(self._path.read_text(encoding="utf-8"))
        else:
            self._data = {
                "run_id": run_id,
                "pipeline": pipeline,
                "started_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": None,
                "status": "running",
                "steps": {},
            }

    def get_step_status(self, step_id: str) -> str:
        step = self._data.get("steps", {}).get(step_id)
        if step is None:
            return "pending"
        return step.get("status", "pending")

    def mark_running(self, step_id: str) -> None:
        steps = self._data.setdefault("steps", {})
        steps[step_id] = {
            "status": "running",
            "started_at": datetime.now(timezone.utc).isoformat(),
        }
        self.save()

    def mark_done(self, step_id: str, output_path: str = "", cost_usd: float = 0.0, duration_s: float = 0.0) -> None:
        steps = self._data.setdefault("steps", {})
        entry = steps.get(step_id, {})
        entry.update({
            "status": "done",
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "output_path": output_path,
            "cost_usd": round(cost_usd, 4),
            "duration_s": round(duration_s, 1),
        })
        steps[step_id] = entry
        self.save()

    def mark_failed(self, step_id: str, error: str, non_blocking: bool = False) -> None:
        steps = self._data.setdefault("steps", {})
        entry = steps.get(step_id, {})
        entry.update({
            "status": "failed",
            "error": error[:500],
            "non_blocking": non_blocking,
            "completed_at": datetime.now(timezone.utc).isoformat(),
        })
        steps[step_id] = entry
        self.save()

    def is_resumable(self, step_id: str) -> bool:
        step = self._data.get("steps", {}).get(step_id)
        if not step or step.get("status") != "done":
            return False
        return True

    def save(self) -> None:
        self._data["updated_at"] = datetime.now(timezone.utc).isoformat()
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps(self._data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def summary(self) -> dict[str, int]:
        steps = self._data.get("steps", {})
        counts = {"pending": 0, "running": 0, "done": 0, "failed": 0}
        for step in steps.values():
            status = step.get("status", "pending")
            counts[status] = counts.get(status, 0) + 1
        return counts

    def finalize(self, status: str) -> None:
        self._data["status"] = status
        self.save()

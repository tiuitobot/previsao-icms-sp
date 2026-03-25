"""Live terminal UI for pipeline execution.

Shows a real-time table of step progress with status, timing, and cost.
Falls back gracefully to no-op if rich is not installed, stdout is not
a TTY, or --no-ui flag is set.
"""

from __future__ import annotations

import time
from typing import Any


class LiveUI:
    """Live terminal progress display using rich."""

    STATUS_SYMBOLS = {
        "pending": "[dim]○ pend[/dim]",
        "running": "[bold yellow]⟳ run[/bold yellow]",
        "done": "[green]✓ done[/green]",
        "failed": "[red]✗ fail[/red]",
        "skipped": "[dim]⊘ skip[/dim]",
    }

    def __init__(self, pipeline_name: str, run_id: str, steps: list[dict[str, Any]]):
        self._pipeline = pipeline_name
        self._run_id = run_id
        self._step_order = [s["id"] for s in steps]
        self._status: dict[str, str] = {sid: "pending" for sid in self._step_order}
        self._duration: dict[str, float] = {}
        self._cost: dict[str, float] = {}
        self._map_progress: dict[str, tuple[int, int]] = {}
        self._start_time = time.time()
        self._total_cost = 0.0
        self._live = None
        self._console = None

        try:
            from rich.live import Live
            from rich.console import Console
            self._console = Console()
            self._live = Live(self._build_table(), console=self._console, refresh_per_second=2)
        except ImportError:
            pass

    def _build_table(self) -> Any:
        from rich.table import Table

        table = Table(title=f"Pipeline: {self._pipeline}  Run: {self._run_id}", show_edge=False)
        table.add_column("Step", style="bold", width=28)
        table.add_column("Status", width=12)
        table.add_column("Time", justify="right", width=10)
        table.add_column("Cost", justify="right", width=10)

        elapsed_total = time.time() - self._start_time

        for sid in self._step_order:
            status = self._status.get(sid, "pending")
            symbol = self.STATUS_SYMBOLS.get(status, status)

            if sid in self._map_progress and status == "running":
                done, total = self._map_progress[sid]
                filled = int(done / max(total, 1) * 6)
                bar = "\u2588" * filled + "\u2591" * (6 - filled)
                symbol = f"[bold yellow][{bar}] {done}/{total}[/bold yellow]"

            dur = self._duration.get(sid)
            time_str = self._fmt(dur) if dur is not None else "-"
            cost = self._cost.get(sid, 0)
            cost_str = f"${cost:.2f}" if cost > 0 else "-"
            table.add_row(sid, symbol, time_str, cost_str)

        table.add_section()
        table.add_row("", "", f"[bold]{self._fmt(elapsed_total)}[/bold]", f"[bold]${self._total_cost:.2f}[/bold]")
        return table

    @staticmethod
    def _fmt(seconds: float | None) -> str:
        if seconds is None:
            return "-"
        if seconds < 60:
            return f"{seconds:.1f}s"
        return f"{int(seconds // 60)}m{seconds % 60:02.0f}s"

    def update_step(self, step_id: str, status: str, duration_s: float | None = None, cost_usd: float = 0.0) -> None:
        self._status[step_id] = status
        if duration_s is not None:
            self._duration[step_id] = duration_s
        if cost_usd > 0:
            self._cost[step_id] = cost_usd
            self._total_cost = sum(self._cost.values())
        if self._live:
            self._live.update(self._build_table())

    def update_map_progress(self, map_step_id: str, done: int, total: int) -> None:
        self._map_progress[map_step_id] = (done, total)
        if self._live:
            self._live.update(self._build_table())

    def __enter__(self) -> "LiveUI":
        if self._live:
            self._live.__enter__()
        return self

    def __exit__(self, *exc: Any) -> None:
        if self._live:
            self._live.__exit__(*exc)
        if self._console:
            self._console.print(self._build_table())


class NoopUI:
    """No-op UI for non-TTY or --no-ui mode."""

    def update_step(self, step_id: str, status: str, **kwargs: Any) -> None:
        pass

    def update_map_progress(self, map_step_id: str, done: int, total: int) -> None:
        pass

    def __enter__(self) -> "NoopUI":
        return self

    def __exit__(self, *exc: Any) -> None:
        pass


def create_ui(pipeline_name: str, run_id: str, steps: list[dict], *, no_ui: bool = False) -> LiveUI | NoopUI:
    import sys
    if no_ui or not sys.stdout.isatty():
        return NoopUI()
    try:
        return LiveUI(pipeline_name, run_id, steps)
    except Exception:
        return NoopUI()

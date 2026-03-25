# SMOKE-EXEMPT: requires claude CLI installed
"""Executor plugin for Claude CLI.

Runs prompts via the `claude` CLI as a subprocess with --print for
direct output. Uses --dangerously-skip-permissions when tools are needed.

Requires `claude` to be installed and on PATH.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

from lib.executors import BaseExecutor, ExecutorResult

ROOT = Path(__file__).resolve().parent.parent.parent


def _extract_json(stdout: str) -> str | None:
    """Extract JSON from stdout that may contain extra text."""
    text = (stdout or "").strip()
    if not text:
        return None
    for start_char, end_char in [("{", "}"), ("[", "]")]:
        first = text.find(start_char)
        last = text.rfind(end_char)
        if first != -1 and last > first:
            return text[first:last + 1]
    return None


class Executor(BaseExecutor):
    name = "claude_cli"

    def run(
        self,
        *,
        prompt: str,
        system_prompt: str = "",
        schema_path: str | None = None,
        model: str = "claude-sonnet-4-6",
        thinking_level: str = "low",
        temperature: float | None = None,
        max_tokens: int = 16384,
        file_ids: list[str] | None = None,
        extra: dict[str, Any] | None = None,
    ) -> ExecutorResult:
        claude_bin = shutil.which("claude")
        if not claude_bin:
            raise RuntimeError("claude CLI not found on PATH")

        extra = extra or {}
        tools_requested = extra.get("tools", [])
        needs_permissions = bool(tools_requested) or extra.get("allow_tools", False)

        full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt

        cmd = [claude_bin, "--print", "--model", model]

        # Allow tools access when needed (web_search, file access, etc.)
        if needs_permissions:
            cmd.append("--dangerously-skip-permissions")

        # Add directory access
        add_dirs = extra.get("add_dirs")
        if add_dirs:
            for d in (add_dirs if isinstance(add_dirs, list) else [add_dirs]):
                cmd.extend(["--add-dir", str(d)])

        # Schema-guided output
        if schema_path:
            schema_full = ROOT / schema_path if not Path(schema_path).is_absolute() else Path(schema_path)
            if schema_full.exists():
                schema_text = schema_full.read_text(encoding="utf-8")
                full_prompt += f"\n\nOutput MUST conform to this JSON Schema:\n```json\n{schema_text}\n```"
            cmd.extend(["--output-format", "json"])

        full_prompt += "\n\nRetorne somente o JSON final, sem markdown, explicacoes ou cercas de codigo."

        result = subprocess.run(
            cmd,
            input=full_prompt,
            capture_output=True,
            text=True,
            timeout=600,
            cwd=str(ROOT),
        )

        content = result.stdout.strip()
        if result.returncode != 0 and not content:
            content = result.stderr.strip() or f"claude CLI exited with code {result.returncode}"

        # Try to extract JSON
        json_text = _extract_json(content)
        if json_text:
            content = json_text

        # Strip markdown fences
        if content.startswith("```"):
            lines = content.splitlines()
            content = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

        return ExecutorResult(content=content, usage={}, model=model, executor_name=self.name)

    def is_available(self) -> bool:
        return shutil.which("claude") is not None

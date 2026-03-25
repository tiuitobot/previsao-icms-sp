# SMOKE-EXEMPT: requires copilot CLI installed
"""Executor plugin for GitHub Copilot CLI.

Runs prompts via the `copilot` CLI as a subprocess with --yolo --autopilot
for auto-approve. Based on production copilot_cli_runner from rt-noopenclaw
and dag-previsao-icms repos.

Requires `copilot` to be installed and on PATH.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

from lib.executors import BaseExecutor, ExecutorResult

ROOT = Path(__file__).resolve().parent.parent.parent

MODEL_MAP = {
    "mini": "gpt-5-mini",
    "gpt": "gpt-5.4",
    "gpt54": "gpt-5.4",
    "gpt-5.4": "gpt-5.4",
    "gpt-5-mini": "gpt-5-mini",
    "gpt-4.1": "gpt-4.1",
    "gpt-4.1-mini": "gpt-4.1-mini",
}

THINKING_HINTS = {
    "low": "Pense de forma objetiva e direta.",
    "medium": "Think step by step antes de concluir.",
    "high": "Think harder e revise os pontos mais frageis antes de concluir.",
}


def _extract_json(stdout: str) -> str | None:
    """Extract JSON from stdout that may contain extra text."""
    text = (stdout or "").strip()
    if not text:
        return None
    # Find JSON boundaries (start char to last matching end char)
    for start_char, end_char in [("{", "}"), ("[", "]")]:
        first = text.find(start_char)
        last = text.rfind(end_char)
        if first != -1 and last > first:
            return text[first:last + 1]
    return None


class Executor(BaseExecutor):
    name = "copilot_cli"

    def run(
        self,
        *,
        prompt: str,
        system_prompt: str = "",
        schema_path: str | None = None,
        model: str = "gpt-5-mini",
        thinking_level: str = "low",
        temperature: float | None = None,
        max_tokens: int = 16384,
        file_ids: list[str] | None = None,
        extra: dict[str, Any] | None = None,
    ) -> ExecutorResult:
        copilot_bin = shutil.which("copilot")
        if not copilot_bin:
            raise RuntimeError("copilot CLI not found on PATH")

        resolved_model = MODEL_MAP.get(model, model)
        thinking_hint = THINKING_HINTS.get(thinking_level, THINKING_HINTS["medium"])

        # Build prompt
        parts = []
        if system_prompt:
            parts.append(system_prompt)

        parts.append(prompt)
        parts.append(f"\nOrientacao de raciocinio: {thinking_hint}")
        parts.append("Retorne somente o JSON final no stdout, sem markdown, explicacoes ou cercas de codigo.")

        if schema_path:
            schema_full = ROOT / schema_path if not Path(schema_path).is_absolute() else Path(schema_path)
            if schema_full.exists():
                schema_text = schema_full.read_text(encoding="utf-8")
                parts.append(f"\nOutput MUST conform to this JSON Schema:\n{schema_text}")

        full_prompt = "\n\n".join(parts)

        cmd = [
            copilot_bin,
            "-p", full_prompt,
            "--model", resolved_model,
            "--yolo",
            "--autopilot",
            "--no-ask-user",
            "--add-dir", str(ROOT),
            "--output-format", "text",
            "--no-color",
        ]

        import os
        env = dict(os.environ)
        env.pop("GITHUB_TOKEN", None)  # Avoid PAT conflicts with copilot auth

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600,
            cwd=str(ROOT),
            env=env,
        )

        content = result.stdout.strip()
        if result.returncode != 0 and not content:
            content = result.stderr.strip() or f"copilot CLI exited with code {result.returncode}"

        # Try to extract JSON from output
        json_text = _extract_json(content)
        if json_text:
            content = json_text

        # Strip markdown fences
        if content.startswith("```"):
            lines = content.splitlines()
            content = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

        return ExecutorResult(content=content, usage={}, model=resolved_model, executor_name=self.name)

    def is_available(self) -> bool:
        return shutil.which("copilot") is not None

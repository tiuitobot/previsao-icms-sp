# SMOKE-EXEMPT: requires API keys to test
"""Executor plugin for Anthropic Messages API.

Standalone — uses the anthropic SDK directly.
Requires ANTHROPIC_API_KEY environment variable.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from lib.executors import BaseExecutor, ExecutorResult

ROOT = Path(__file__).resolve().parent.parent.parent


class Executor(BaseExecutor):
    name = "anthropic_api"

    def run(
        self,
        *,
        prompt: str,
        system_prompt: str = "",
        schema_path: str | None = None,
        model: str = "claude-sonnet-4-6",
        thinking_level: str = "medium",
        temperature: float | None = None,
        max_tokens: int = 16384,
        file_ids: list[str] | None = None,
        extra: dict[str, Any] | None = None,
    ) -> ExecutorResult:
        try:
            import anthropic
        except ImportError:
            raise RuntimeError("anthropic package not installed. Run: pip install anthropic")

        client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

        kwargs: dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }

        if system_prompt:
            kwargs["system"] = system_prompt

        if temperature is not None:
            kwargs["temperature"] = temperature

        # Extended thinking
        thinking_map = {"low": 1024, "medium": 4096, "high": 16384}
        budget = thinking_map.get(thinking_level, 0)
        if budget:
            kwargs["thinking"] = {"type": "enabled", "budget_tokens": budget}

        resp = client.messages.create(**kwargs)

        content = ""
        for block in resp.content:
            if block.type == "text":
                content += block.text

        if content.startswith("```"):
            lines = content.splitlines()
            content = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

        usage = {}
        if resp.usage:
            usage = {
                "input_tokens": resp.usage.input_tokens,
                "output_tokens": resp.usage.output_tokens,
                "total_tokens": resp.usage.input_tokens + resp.usage.output_tokens,
            }

        return ExecutorResult(content=content, usage=usage, model=model, executor_name=self.name)

    def is_available(self) -> bool:
        return bool(os.environ.get("ANTHROPIC_API_KEY"))

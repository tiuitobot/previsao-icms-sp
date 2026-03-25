# SMOKE-EXEMPT: requires API keys to test
"""Executor plugin for Kimi K2.5 via Azure AI Foundry.

Uses OpenAI-compatible endpoint. Requires either:
- AZURE_KIMI_API_KEY + AZURE_KIMI_ENDPOINT, or
- KIMI_API_KEY + KIMI_ENDPOINT
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from lib.executors import BaseExecutor, ExecutorResult

ROOT = Path(__file__).resolve().parent.parent.parent


class Executor(BaseExecutor):
    name = "kimi_api"

    def run(
        self,
        *,
        prompt: str,
        system_prompt: str = "",
        schema_path: str | None = None,
        model: str = "kimi-k2.5",
        thinking_level: str = "medium",
        temperature: float | None = None,
        max_tokens: int = 16384,
        file_ids: list[str] | None = None,
        extra: dict[str, Any] | None = None,
    ) -> ExecutorResult:
        try:
            from openai import OpenAI
        except ImportError:
            raise RuntimeError("openai package not installed. Run: pip install openai")

        api_key = os.environ.get("AZURE_KIMI_API_KEY") or os.environ.get("KIMI_API_KEY", "")
        endpoint = os.environ.get("AZURE_KIMI_ENDPOINT") or os.environ.get("KIMI_ENDPOINT", "")

        if not api_key or not endpoint:
            raise RuntimeError("Kimi API requires AZURE_KIMI_API_KEY + AZURE_KIMI_ENDPOINT (or KIMI_API_KEY + KIMI_ENDPOINT)")

        client = OpenAI(api_key=api_key, base_url=endpoint)

        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        kwargs: dict[str, Any] = {"model": model, "messages": messages, "max_tokens": max_tokens}
        if temperature is not None:
            kwargs["temperature"] = temperature

        resp = client.chat.completions.create(**kwargs)
        content = resp.choices[0].message.content or ""

        if content.startswith("```"):
            lines = content.splitlines()
            content = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

        usage = {}
        if resp.usage:
            usage = {
                "prompt_tokens": resp.usage.prompt_tokens,
                "completion_tokens": resp.usage.completion_tokens,
                "total_tokens": resp.usage.total_tokens,
            }

        return ExecutorResult(content=content, usage=usage, model=model, executor_name=self.name)

    def is_available(self) -> bool:
        return bool(
            (os.environ.get("AZURE_KIMI_API_KEY") and os.environ.get("AZURE_KIMI_ENDPOINT"))
            or (os.environ.get("KIMI_API_KEY") and os.environ.get("KIMI_ENDPOINT"))
        )

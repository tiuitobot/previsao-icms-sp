# SMOKE-EXEMPT: requires API keys to test
"""Executor plugin for OpenAI API direct (Responses API)."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from lib.executors import BaseExecutor, ExecutorResult

ROOT = Path(__file__).resolve().parent.parent.parent


class Executor(BaseExecutor):
    name = "openai_api"

    def run(
        self,
        *,
        prompt: str,
        system_prompt: str = "",
        schema_path: str | None = None,
        model: str = "gpt-4.1",
        thinking_level: str = "low",
        temperature: float | None = None,
        max_tokens: int = 16384,
        file_ids: list[str] | None = None,
        extra: dict[str, Any] | None = None,
    ) -> ExecutorResult:
        from openai import OpenAI

        client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

        input_parts: list[dict[str, Any]] = []
        if file_ids:
            for fid in file_ids:
                input_parts.append({"type": "file", "file_id": fid})
        input_parts.append({"type": "message", "role": "user", "content": prompt})

        kwargs: dict[str, Any] = {"model": model, "input": input_parts}
        if system_prompt:
            kwargs["instructions"] = system_prompt
        if max_tokens:
            kwargs["max_output_tokens"] = max_tokens

        # Schema-based structured output
        if schema_path:
            schema_full = ROOT / schema_path if not Path(schema_path).is_absolute() else Path(schema_path)
            skip = bool(extra and extra.get("skip_schema_format"))
            if schema_full.exists() and not skip:
                schema = json.loads(schema_full.read_text(encoding="utf-8"))
                kwargs["text"] = {"format": {"type": "json_schema", "name": "output", "strict": True, "schema": schema}}
            else:
                kwargs["text"] = {"format": {"type": "json_object"}}

        # Thinking/reasoning
        thinking_map = {"low": "low", "medium": "medium", "high": "high"}
        if thinking_level in thinking_map:
            kwargs["reasoning"] = {"effort": thinking_map[thinking_level]}

        resp = client.responses.create(**kwargs)

        content = ""
        for item in resp.output:
            if getattr(item, "type", "") == "message":
                for block in item.content:
                    if getattr(block, "type", "") == "output_text":
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
        return bool(os.environ.get("OPENAI_API_KEY")) and not os.environ.get("AZURE_OPENAI_ENDPOINT")

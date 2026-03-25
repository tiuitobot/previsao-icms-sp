# SMOKE-EXEMPT: requires API keys to test
"""Executor plugin for Azure OpenAI (Responses API).

Uses the Responses API exclusively — supports web_search, code_interpreter,
file_search, structured output, and reasoning. Requires:
  AZURE_OPENAI_API_KEY
  AZURE_OPENAI_ENDPOINT
  AZURE_OPENAI_API_VERSION (default: 2025-04-01-preview)

Tools are enabled via extra["tools"] in the step entry, e.g.:
  "args": {"tools": ["web_search"]}
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

from lib.executors import BaseExecutor, ExecutorResult

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent.parent

THINKING_MAP = {"low": "low", "medium": "medium", "high": "high"}


class Executor(BaseExecutor):
    name = "azure_openai"

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
        from openai import AzureOpenAI

        client = AzureOpenAI(
            api_key=os.environ["AZURE_OPENAI_API_KEY"],
            azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
            api_version=os.environ.get("AZURE_OPENAI_API_VERSION", "2025-04-01-preview"),
        )

        extra = extra or {}
        tools_requested = extra.get("tools", [])

        # Build input
        input_parts: list[dict[str, Any]] = []
        if file_ids:
            for fid in file_ids:
                input_parts.append({"type": "input_file", "file_id": fid})
        input_parts.append({"type": "input_text", "text": prompt})

        request: dict[str, Any] = {
            "model": model,
            "input": [
                *(([{"role": "developer", "content": system_prompt}] if system_prompt else [])),
                {"role": "user", "content": input_parts},
            ],
        }

        if max_tokens:
            request["max_output_tokens"] = max_tokens
        if temperature is not None:
            request["temperature"] = temperature

        # Tools
        tools: list[dict[str, Any]] = []
        for t in tools_requested:
            if isinstance(t, str):
                tools.append({"type": t})
            elif isinstance(t, dict):
                tools.append(t)
        if tools:
            request["tools"] = tools
            logger.info("Azure Responses API: tools=%s", [t.get("type", t) for t in tools])

        # Reasoning — only for reasoning-capable models (o3, o4, gpt-5)
        REASONING_MODELS = ("o3", "o4", "gpt-5")
        if thinking_level in THINKING_MAP and any(model.startswith(p) for p in REASONING_MODELS):
            request["reasoning"] = {"effort": THINKING_MAP[thinking_level]}

        # Schema-guided structured output
        # Note: web_search is incompatible with JSON mode — skip schema format when using tools
        has_web_search = any(t.get("type") == "web_search" if isinstance(t, dict) else t == "web_search" for t in tools)
        if schema_path and not has_web_search:
            schema_full = ROOT / schema_path if not Path(schema_path).is_absolute() else Path(schema_path)
            skip = bool(extra.get("skip_schema_format"))
            if schema_full.exists() and not skip:
                schema = json.loads(schema_full.read_text(encoding="utf-8"))
                # Azure requires additionalProperties:false for strict schema mode
                if schema.get("additionalProperties") is False:
                    request["text"] = {
                        "format": {
                            "type": "json_schema",
                            "name": "output",
                            "strict": True,
                            "schema": schema,
                        },
                    }
                else:
                    # Inject schema as text instruction instead
                    schema_text = json.dumps(schema, indent=2, ensure_ascii=False)
                    input_msg = request["input"][-1]
                    if isinstance(input_msg.get("content"), list):
                        for part in input_msg["content"]:
                            if part.get("type") == "input_text":
                                part["text"] += f"\n\nOutput MUST conform to this JSON Schema:\n```json\n{schema_text}\n```"
                                break
                    request["text"] = {"format": {"type": "json_object"}}
            else:
                request["text"] = {"format": {"type": "json_object"}}

        logger.debug("Azure Responses API: model=%s, tools=%d", model, len(tools))
        resp = client.responses.create(**request)

        # Extract content
        content = ""
        for item in resp.output:
            if getattr(item, "type", "") == "message":
                for block in item.content:
                    if getattr(block, "type", "") == "output_text":
                        content += block.text

        # Strip markdown fences
        if content.startswith("```"):
            lines = content.splitlines()
            content = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

        # Usage
        usage = {}
        if resp.usage:
            cached = 0
            reasoning = 0
            if hasattr(resp.usage, "input_tokens_details") and resp.usage.input_tokens_details:
                cached = getattr(resp.usage.input_tokens_details, "cached_tokens", 0) or 0
            if hasattr(resp.usage, "output_tokens_details") and resp.usage.output_tokens_details:
                reasoning = getattr(resp.usage.output_tokens_details, "reasoning_tokens", 0) or 0
            usage = {
                "input_tokens": resp.usage.input_tokens,
                "output_tokens": resp.usage.output_tokens,
                "total_tokens": resp.usage.total_tokens,
                "cached_tokens": cached,
                "reasoning_tokens": reasoning,
            }

        return ExecutorResult(content=content, usage=usage, model=model, executor_name=self.name)

    def is_available(self) -> bool:
        return bool(os.environ.get("AZURE_OPENAI_API_KEY") and os.environ.get("AZURE_OPENAI_ENDPOINT"))

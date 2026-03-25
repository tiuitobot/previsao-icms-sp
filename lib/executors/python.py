"""Executor plugin for deterministic Python steps.

Runs a Python function directly -- no LLM, no API, $0 cost.
"""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from typing import Any

from lib.executors import BaseExecutor, ExecutorResult

ROOT = Path(__file__).resolve().parent.parent.parent


class Executor(BaseExecutor):
    name = "python"

    def run(
        self,
        *,
        prompt: str,
        system_prompt: str = "",
        schema_path: str | None = None,
        model: str = "",
        thinking_level: str = "",
        temperature: float | None = None,
        max_tokens: int = 0,
        file_ids: list[str] | None = None,
        extra: dict[str, Any] | None = None,
    ) -> ExecutorResult:
        extra = extra or {}
        script = extra.get("script", "")
        func_name = extra.get("function", "main")
        kwargs = extra.get("kwargs", {})

        if not script:
            raise ValueError("Python executor requires extra.script")

        module_path = script.replace("/", ".").removesuffix(".py")

        sys.path.insert(0, str(ROOT))
        mod = importlib.import_module(module_path)
        fn = getattr(mod, func_name)

        result = fn(**kwargs)
        if isinstance(result, dict):
            content = json.dumps(result, ensure_ascii=False, indent=2)
        else:
            content = str(result) if result is not None else ""

        return ExecutorResult(content=content, usage={}, model="python", executor_name=self.name)

    def is_available(self) -> bool:
        return True

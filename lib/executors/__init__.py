"""Executor plugin system.

Each executor implements a standard interface for running pipeline steps
against a specific backend (OpenAI API, Anthropic API, CLI tools, Python).

Usage:
    from lib.executors import get_executor
    executor = get_executor("python")
    result = executor.run(prompt="...", extra={"script": "...", "function": "main"})
"""

from __future__ import annotations

from typing import Any


class ExecutorResult:
    """Standardized result from any executor."""

    __slots__ = ("content", "usage", "model", "executor_name")

    def __init__(self, content: str, usage: dict[str, int] | None = None, model: str = "", executor_name: str = ""):
        self.content = content
        self.usage = usage or {}
        self.model = model
        self.executor_name = executor_name

    @property
    def input_tokens(self) -> int:
        return self.usage.get("input_tokens", 0) or self.usage.get("prompt_tokens", 0)

    @property
    def output_tokens(self) -> int:
        return self.usage.get("output_tokens", 0) or self.usage.get("completion_tokens", 0)

    @property
    def estimated_cost_usd(self) -> float:
        return self.usage.get("estimated_cost_usd", 0.0)


class BaseExecutor:
    """Abstract base for all executor plugins."""

    name: str = "base"

    def run(
        self,
        *,
        prompt: str,
        system_prompt: str = "",
        schema_path: str | None = None,
        model: str = "",
        thinking_level: str = "low",
        temperature: float | None = None,
        max_tokens: int = 16384,
        file_ids: list[str] | None = None,
        extra: dict[str, Any] | None = None,
    ) -> ExecutorResult:
        raise NotImplementedError

    def is_available(self) -> bool:
        return False


_REGISTRY: dict[str, type[BaseExecutor]] = {}


def register_executor(name: str, cls: type[BaseExecutor]) -> None:
    _REGISTRY[name] = cls


def get_executor(name: str) -> BaseExecutor:
    """Get an executor instance by name. Lazy-imports from lib.executors.<name>."""
    if name in _REGISTRY:
        return _REGISTRY[name]()

    try:
        import importlib
        mod = importlib.import_module(f"lib.executors.{name}")
        cls = getattr(mod, "Executor", None)
        if cls and issubclass(cls, BaseExecutor):
            _REGISTRY[name] = cls
            return cls()
    except (ImportError, AttributeError):
        pass

    raise ValueError(f"Unknown executor: {name}. Available: {list(_REGISTRY.keys())}")


def list_executors() -> list[str]:
    return sorted(_REGISTRY.keys())

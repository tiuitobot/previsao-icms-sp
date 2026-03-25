# SMOKE-EXEMPT: requires codex CLI installed
"""Executor plugin for Codex CLI.

Runs prompts via `codex exec` with --json --dangerously-bypass-approvals-and-sandbox
for non-interactive worker mode. Based on production codex_runner from analise-autos.

Key features:
- codex exec with JSONL event stream + --output-last-message for reliable output
- Schema normalization for Codex compatibility (additionalProperties:false)
- Multi-layer result extraction (last_message → events → stdout)
- Reasoning effort configuration
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from lib.executors import BaseExecutor, ExecutorResult

ROOT = Path(__file__).resolve().parent.parent.parent

THINKING_MAP = {"low": "low", "medium": "medium", "high": "high", "xhigh": "high"}


def _normalize_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Normalize schema for Codex compatibility (additionalProperties:false everywhere)."""
    def project(node: Any) -> Any:
        if not isinstance(node, dict):
            return node
        result: dict[str, Any] = {}
        node_type = node.get("type")
        if isinstance(node_type, list):
            for t in ("object", "array", "string", "number", "integer", "boolean"):
                if t in node_type:
                    node_type = t
                    break
            else:
                node_type = node_type[0] if node_type else "string"
        if node_type:
            result["type"] = node_type
        if node_type == "object":
            props = node.get("properties", {})
            result["properties"] = {k: project(v) for k, v in props.items()} if isinstance(props, dict) else {}
            result["required"] = list(result["properties"].keys())
            result["additionalProperties"] = False
        elif node_type == "array" and "items" in node:
            result["items"] = project(node["items"])
        for key in ("description", "title", "enum", "const", "minimum", "maximum", "pattern", "minLength", "maxLength"):
            if key in node:
                result[key] = node[key]
        return result

    projected = project(schema)
    if isinstance(projected, dict):
        projected.pop("$schema", None)
    return projected


def _write_schema(schema_path: str) -> Path | None:
    """Write Codex-compatible schema to temp location."""
    canonical = Path(schema_path)
    if not canonical.is_absolute():
        canonical = ROOT / schema_path
    if not canonical.exists():
        return None
    schema = json.loads(canonical.read_text(encoding="utf-8"))
    normalized = _normalize_schema(schema)
    derived_dir = ROOT / "workspace" / "outputs" / "_codex_schemas"
    derived_dir.mkdir(parents=True, exist_ok=True)
    derived = derived_dir / canonical.name
    derived.write_text(json.dumps(normalized, ensure_ascii=False, indent=2), encoding="utf-8")
    return derived


def _extract_json(text: str) -> str | None:
    """Extract JSON from text that may contain extra content."""
    content = (text or "").strip()
    if not content:
        return None
    if content.startswith("```"):
        lines = content.splitlines()
        lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        content = "\n".join(lines).strip()
    if content.startswith("{") or content.startswith("["):
        return content
    for sc, ec in [("{", "}"), ("[", "]")]:
        first, last = content.find(sc), content.rfind(ec)
        if first != -1 and last > first:
            return content[first:last + 1]
    return None


def _extract_from_events(events_text: str) -> str | None:
    """Extract result from Codex JSONL event stream."""
    candidates = []
    for line in events_text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict):
            continue
        # Check data.content
        data = event.get("data", {})
        if isinstance(data, dict):
            content = data.get("content")
            if isinstance(content, str) and content.strip():
                candidates.append(content)
            elif isinstance(content, list):
                for chunk in content:
                    if isinstance(chunk, dict):
                        t = chunk.get("text") or chunk.get("content")
                        if isinstance(t, str) and t.strip():
                            candidates.append(t)
            summary = data.get("summary")
            if isinstance(summary, str) and summary.strip():
                candidates.append(summary)
        # Check item.content
        item = event.get("item", {})
        if isinstance(item, dict) and item.get("type") in ("message", "agent_message"):
            ic = item.get("content")
            if isinstance(ic, list):
                for block in ic:
                    if isinstance(block, dict) and block.get("type") in ("output_text", "text"):
                        t = block.get("text")
                        if isinstance(t, str) and t.strip():
                            candidates.append(t)

    for c in reversed(candidates):
        j = _extract_json(c)
        if j:
            try:
                json.loads(j)
                return j
            except json.JSONDecodeError:
                continue
    return candidates[-1].strip() if candidates else None


class Executor(BaseExecutor):
    name = "codex_cli"

    def run(
        self,
        *,
        prompt: str,
        system_prompt: str = "",
        schema_path: str | None = None,
        model: str = "gpt-5.4",
        thinking_level: str = "low",
        temperature: float | None = None,
        max_tokens: int = 16384,
        file_ids: list[str] | None = None,
        extra: dict[str, Any] | None = None,
    ) -> ExecutorResult:
        codex_bin = shutil.which("codex")
        if not codex_bin:
            raise RuntimeError("codex CLI not found on PATH")

        extra = extra or {}
        reasoning = THINKING_MAP.get(thinking_level, "low")

        # Build prompt
        full_prompt = ""
        if system_prompt:
            full_prompt += f"{system_prompt}\n\n"
        full_prompt += prompt
        full_prompt += "\n\nRetorne somente o JSON final, sem markdown fences ou texto extra."

        # Temp file for last message
        last_msg_file = tempfile.NamedTemporaryFile(mode="w+", suffix=".txt", delete=False)
        last_msg_path = Path(last_msg_file.name)
        last_msg_file.close()

        cmd = [
            codex_bin, "exec",
            "-m", model,
            "--json",
            "--dangerously-bypass-approvals-and-sandbox",
            "-c", f'model_reasoning_effort="{reasoning}"',
            "--output-last-message", str(last_msg_path),
        ]

        # Add directories
        add_dirs = extra.get("add_dirs", [])
        if isinstance(add_dirs, str):
            add_dirs = [add_dirs]
        for d in add_dirs:
            dpath = Path(d) if Path(d).is_absolute() else ROOT / d
            cmd.extend(["--add-dir", str(dpath)])

        # Schema
        if schema_path:
            schema_file = _write_schema(schema_path)
            if schema_file:
                cmd.extend(["--output-schema", str(schema_file)])

        cmd.append("-")  # read prompt from stdin

        result = subprocess.run(
            cmd,
            input=full_prompt,
            capture_output=True,
            text=True,
            timeout=600,
            cwd=str(ROOT),
        )

        # Extract result: last_message → events → stdout
        last_message = ""
        if last_msg_path.exists():
            last_message = last_msg_path.read_text(encoding="utf-8", errors="replace")
            last_msg_path.unlink(missing_ok=True)

        content = None

        # Priority 1: last message file
        if last_message.strip():
            j = _extract_json(last_message)
            if j:
                content = j
            else:
                content = last_message.strip()

        # Priority 2: JSONL events from stdout
        if not content and result.stdout:
            content = _extract_from_events(result.stdout)

        # Priority 3: raw stdout
        if not content:
            j = _extract_json(result.stdout)
            content = j or result.stdout.strip()

        if not content and result.returncode != 0:
            content = result.stderr.strip() or f"codex failed (rc={result.returncode})"

        return ExecutorResult(content=content or "", usage={}, model=model, executor_name=self.name)

    def is_available(self) -> bool:
        return shutil.which("codex") is not None

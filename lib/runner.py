"""Generic DAG runner for pipeline-engine.

Reads any pipeline DAG from a JSON file, resolves step definitions,
dispatches to executor plugins, and supports normal / map / reduce
step types with persistent state, event ledger, and live UI.

Usage:
    python -m lib.runner --pipeline pipelines/my-pipeline.json --data-dir data/input

    # Or programmatically:
    from lib.runner import run_pipeline
    run_pipeline("pipelines/my-pipeline.json", data_dir="data/input")
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError, as_completed
from datetime import datetime
from pathlib import Path
from typing import Any

from lib.executors import get_executor, ExecutorResult
from lib.fixups import load_registry, build_chain, run_chain
from lib.gates import run_gates, check_checkpoint, approve_checkpoint, reject_checkpoint
from lib.manifest import init_run_dir, RunManifest
from lib.ledger import Ledger
from lib.state import RunState
from lib.utils import strip_markdown_fences, truncate_json_safe

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent


def _load_env() -> None:
    """Load .env file from repo root if present."""
    env_file = ROOT / ".env"
    if not env_file.exists():
        return
    import os as _os
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        line = line.removeprefix("export").strip()
        if "=" not in line:
            continue
        k, _, v = line.partition("=")
        k, v = k.strip(), v.strip().strip("'\"")
        if k and k not in _os.environ:
            _os.environ[k] = v


_load_env()


# ---------------------------------------------------------------------------
# Cost estimation
# ---------------------------------------------------------------------------

def _estimate_cost(usage: dict, model: str) -> float:
    """Rough USD cost estimate from token counts."""
    input_t = usage.get("input_tokens", 0) or usage.get("prompt_tokens", 0)
    output_t = usage.get("output_tokens", 0) or usage.get("completion_tokens", 0)
    # Conservative defaults per 1M tokens
    PRICING = {
        "gpt-4.1": (2.0, 8.0),
        "gpt-4.1-mini": (0.4, 1.6),
        "gpt-5.4": (5.0, 15.0),
        "claude-sonnet-4-6": (3.0, 15.0),
        "kimi-k2.5": (1.0, 4.0),
    }
    in_price, out_price = PRICING.get(model, (2.0, 8.0))
    return (input_t * in_price + output_t * out_price) / 1_000_000


# ---------------------------------------------------------------------------
# Pipeline / step loading
# ---------------------------------------------------------------------------

def load_pipeline(path: str | Path, *, validate: bool = True) -> dict[str, Any]:
    """Load a pipeline DAG JSON with optional validation."""
    p = Path(path)
    if not p.is_absolute():
        p = ROOT / p
    pipeline = json.loads(p.read_text(encoding="utf-8"))

    if validate:
        _validate_pipeline(pipeline)

    return pipeline


def _validate_pipeline(pipeline: dict[str, Any]) -> None:
    """Validate pipeline structure: required fields, dep refs, step refs."""
    if "steps" not in pipeline:
        raise ValueError("Pipeline JSON missing 'steps' array")
    if not isinstance(pipeline["steps"], list):
        raise ValueError("Pipeline 'steps' must be an array")

    step_ids = set()
    for s in pipeline["steps"]:
        if "id" not in s:
            raise ValueError(f"Step missing 'id': {s}")
        if s["id"] in step_ids:
            raise ValueError(f"Duplicate step id: {s['id']}")
        step_ids.add(s["id"])

    for s in pipeline["steps"]:
        for dep in s.get("depends_on", []):
            if dep not in step_ids:
                raise ValueError(f"Step '{s['id']}' depends_on '{dep}' which does not exist in the pipeline")

    # Schema validation if jsonschema is available
    schema_path = ROOT / "contracts" / "pipeline.schema.json"
    if schema_path.exists():
        try:
            import jsonschema
            schema = json.loads(schema_path.read_text(encoding="utf-8"))
            jsonschema.validate(pipeline, schema)
        except ImportError:
            pass  # jsonschema not installed, skip
        except jsonschema.ValidationError as e:
            logger.warning("Pipeline schema validation warning: %s", e.message)


_STEP_CACHE: dict[str, dict[str, Any]] = {}


def load_step_definition(step_id: str) -> dict[str, Any] | None:
    """Load a canonical step definition from contracts/steps/."""
    if step_id in _STEP_CACHE:
        return _STEP_CACHE[step_id]

    path = ROOT / "contracts" / "steps" / f"{step_id}.json"
    if not path.exists():
        return None

    step = json.loads(path.read_text(encoding="utf-8"))
    _STEP_CACHE[step_id] = step
    return step


def _resolve_contract(step_def: dict, step_entry: dict, base_model: str) -> str:
    """Resolve the contract .md path for a step."""
    if step_entry.get("contract"):
        return step_entry["contract"]

    model = step_entry.get("model") or base_model or ""
    contracts = step_def.get("contracts", {})

    if model in contracts:
        return contracts[model]
    for key, path in contracts.items():
        if model.startswith(key) or key in model:
            return path

    if contracts:
        return next(iter(contracts.values()))
    return ""


def _resolve_executor_name(step_def: dict, step_entry: dict, base_executor: str) -> str:
    """Resolve which executor to use for a step."""
    if step_entry.get("executor"):
        return step_entry["executor"]

    step_type = step_def.get("type", "llm")
    if step_type == "deterministic":
        return "python"

    return base_executor or "openai_api"


# ---------------------------------------------------------------------------
# Topological sort (Kahn's algorithm with cycle detection)
# ---------------------------------------------------------------------------

def _topo_sort(steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id = {s["id"]: s for s in steps}
    in_degree: dict[str, int] = {s["id"]: 0 for s in steps}
    adjacency: dict[str, list[str]] = {s["id"]: [] for s in steps}

    for s in steps:
        for dep in s.get("depends_on", []):
            if dep in by_id:
                adjacency[dep].append(s["id"])
                in_degree[s["id"]] += 1

    queue = [sid for sid, deg in in_degree.items() if deg == 0]
    result = []
    while queue:
        queue.sort()
        node = queue.pop(0)
        result.append(by_id[node])
        for neighbor in adjacency[node]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    if len(result) != len(steps):
        missing = set(s["id"] for s in steps) - set(s["id"] for s in result)
        raise ValueError(f"Cycle detected in DAG. Steps not resolved: {missing}")

    return result


def _topo_waves(steps: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    """Group steps into parallel waves. Steps in the same wave have all
    dependencies satisfied and can execute concurrently."""
    by_id = {s["id"]: s for s in steps}
    in_degree: dict[str, int] = {s["id"]: 0 for s in steps}
    adjacency: dict[str, list[str]] = {s["id"]: [] for s in steps}

    for s in steps:
        for dep in s.get("depends_on", []):
            if dep in by_id:
                adjacency[dep].append(s["id"])
                in_degree[s["id"]] += 1

    queue = sorted([sid for sid, deg in in_degree.items() if deg == 0])
    waves: list[list[dict[str, Any]]] = []

    while queue:
        wave = [by_id[sid] for sid in queue]
        waves.append(wave)
        next_queue = []
        for sid in queue:
            for neighbor in adjacency[sid]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    next_queue.append(neighbor)
        queue = sorted(next_queue)

    resolved = sum(len(w) for w in waves)
    if resolved != len(steps):
        missing = set(s["id"] for s in steps) - {s["id"] for w in waves for s in w}
        raise ValueError(f"Cycle detected in DAG. Steps not resolved: {missing}")

    return waves


# ---------------------------------------------------------------------------
# Step execution
# ---------------------------------------------------------------------------

_MAX_DEP_CHARS = 30_000


def _build_prompt(step_def: dict, step_entry: dict, contract_path: str, context: dict[str, Any]) -> tuple[str, str]:
    """Build system_prompt and user_prompt for an LLM step.

    Uses intelligent data routing: each declared input dependency is
    included individually (not concatenated wholesale) and truncated
    with ``truncate_json_safe`` when it exceeds ``_MAX_DEP_CHARS`` to
    avoid wasting tokens on irrelevant data.
    """
    # --- system prompt ---
    # Temporal context: inject real date so the LLM knows "today"
    temporal_ctx = (
        f"Data atual: {datetime.now().strftime('%Y-%m-%d')}. "
        "Use esta data como referência temporal, não a data do seu treinamento. "
        "Dados, legislação e fatos devem refletir o presente, não o passado.\n\n"
    )
    system_prompt = temporal_ctx
    if contract_path:
        full_path = ROOT / contract_path
        if full_path.exists():
            raw = full_path.read_text(encoding="utf-8")
            system_prompt = temporal_ctx + strip_markdown_fences(raw)

    # --- user prompt: include only declared dependency outputs ---
    user_parts: list[str] = []
    inputs = step_def.get("inputs", {})
    required_deps = inputs.get("required", [])
    optional_deps = inputs.get("optional", [])

    for dep_id in required_deps + optional_deps:
        key = f"_output_{dep_id}"
        if key not in context:
            continue
        data = context[key]

        if isinstance(data, dict):
            serialized = json.dumps(data, ensure_ascii=False, indent=2)
        elif isinstance(data, str):
            serialized = data
        else:
            serialized = str(data)

        original_len = len(serialized)

        if original_len > _MAX_DEP_CHARS:
            serialized = truncate_json_safe(serialized, _MAX_DEP_CHARS)
            meta = f"\n\n_[Truncated from {original_len:,} to {len(serialized):,} chars]_"
        else:
            meta = ""

        if isinstance(data, (dict, list)):
            user_parts.append(f"## {dep_id}\n```json\n{serialized}\n```{meta}")
        else:
            user_parts.append(f"## {dep_id}\n{serialized}{meta}")

    # Inject chunk data for map steps
    if "_chunk" in context:
        chunk_data = context["_chunk"]
        if isinstance(chunk_data, dict):
            chunk_serialized = json.dumps(chunk_data, ensure_ascii=False, indent=2)
        else:
            chunk_serialized = str(chunk_data)
        if len(chunk_serialized) > _MAX_DEP_CHARS:
            chunk_serialized = truncate_json_safe(chunk_serialized, _MAX_DEP_CHARS)
        user_parts.insert(0, f"## _chunk (current item to analyze)\n```json\n{chunk_serialized}\n```\n")

    # Inject user_context from interpreter (dynamic DAG)
    args = step_entry.get("args", {})
    user_context = args.get("user_context", "")
    if user_context:
        user_parts.insert(0, f"## User Request\n{user_context}\n")

    # Fallback: pass step_input or raw_docs_text only when no deps matched
    if not user_parts or (len(user_parts) == 1 and user_context):
        if "raw_docs_text" in context:
            fallback = context["raw_docs_text"]
            if len(fallback) > _MAX_DEP_CHARS * 4:
                fallback = truncate_json_safe(fallback, _MAX_DEP_CHARS * 4)
            user_parts.append(fallback)
        elif "step_input" in context:
            fallback = json.dumps(context["step_input"], ensure_ascii=False, indent=2)
            if len(fallback) > _MAX_DEP_CHARS * 2:
                fallback = truncate_json_safe(fallback, _MAX_DEP_CHARS * 2)
            user_parts.append(fallback)
        else:
            user_parts.append("No input data available.")

    return system_prompt, "\n\n".join(user_parts)


def _execute_step(
    step_entry: dict[str, Any],
    step_def: dict[str, Any],
    pipeline: dict[str, Any],
    context: dict[str, Any],
    output_dir: Path,
) -> tuple[dict[str, Any], float]:
    """Execute a single normal step. Returns (output_dict, cost_usd)."""
    step_id = step_entry["id"]
    step_type = step_def.get("type", "llm")
    base_model = pipeline.get("base_model", "gpt-4.1")
    base_executor = pipeline.get("base_executor", "openai_api")

    executor_name = _resolve_executor_name(step_def, step_entry, base_executor)
    executor = get_executor(executor_name)

    if step_type == "deterministic" or executor_name == "python":
        script = step_def.get("script", "")
        func = step_def.get("function", "main")
        kwargs = dict(step_entry.get("args", {}))

        for k, v in list(kwargs.items()):
            if isinstance(v, str) and v.startswith("{") and v.endswith("}"):
                ref = v[1:-1]
                if ref == "data_dir":
                    kwargs[k] = str(context.get("_data_dir", ""))
                elif ref == "output_dir":
                    kwargs[k] = str(context.get("_output_dir", ""))
                elif ref in context:
                    kwargs[k] = context[ref]

        result = executor.run(prompt="", extra={"script": script, "function": func, "kwargs": kwargs})

        try:
            output = json.loads(result.content)
        except (json.JSONDecodeError, TypeError):
            output = {"_raw": result.content}
    else:
        contract_path = _resolve_contract(step_def, step_entry, base_model)
        model = step_entry.get("model") or base_model
        thinking = step_entry.get("thinking_level") or "medium"
        schema_path = step_entry.get("schema") or step_def.get("outputs", {}).get("schema")

        system_prompt, user_prompt = _build_prompt(step_def, step_entry, contract_path, context)

        result = executor.run(
            prompt=user_prompt,
            system_prompt=system_prompt,
            schema_path=schema_path,
            model=model,
            thinking_level=thinking,
            temperature=step_entry.get("temperature"),
            extra=step_entry.get("args"),
        )

        content = strip_markdown_fences(result.content)

        try:
            output = json.loads(content)
        except json.JSONDecodeError:
            output = {"_raw": content}

    # Resolve output_file references (Codex CLI saves large outputs to temp files)
    if isinstance(output, dict) and "output_file" in output and len(output) < 10:
        ref_path = Path(output["output_file"])
        if ref_path.exists():
            try:
                ref_data = json.loads(ref_path.read_text(encoding="utf-8"))
                logger.info("Resolved output_file reference: %s (%d bytes)", ref_path, ref_path.stat().st_size)
                output = ref_data
            except (json.JSONDecodeError, OSError):
                pass

    # Estimate cost from executor result usage
    model_used = result.model or step_entry.get("model") or base_model
    cost_usd = _estimate_cost(result.usage, model_used)

    primary_file = step_def.get("outputs", {}).get("primary", f"{step_id}.json")
    out_path = output_dir / primary_file
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")

    logger.info("Step %s completed (%s). Output: %s  cost=$%.4f", step_id, executor_name, out_path.name, cost_usd)
    return output, cost_usd


def _execute_map_step(
    step_entry: dict[str, Any],
    pipeline: dict[str, Any],
    context: dict[str, Any],
    output_dir: Path,
) -> tuple[dict[str, list[dict[str, Any]]], float]:
    """Execute a map step: run sub-steps per chunk partition. Returns (outputs, cost_usd)."""
    map_config = step_entry.get("map_config", {})
    partition_from = map_config.get("partition_from", "")
    partition_key = map_config.get("partition_key", "chunks")
    sub_steps = map_config.get("steps", [])
    parallel_chunks = map_config.get("parallel_chunks", True)
    max_concurrent = map_config.get("max_concurrent_chunks", 4)
    output_pattern = map_config.get("output_pattern", "chunk{chunk_index}_{step_id}.json")

    partitioner_output = context.get(f"_output_{partition_from}", {})
    partitions = partitioner_output.get(partition_key, [])

    if not partitions:
        logger.warning("Map step %s: no partitions found", step_entry["id"])
        return {}, 0.0

    logger.info("Map step %s: %d partitions, %d sub-steps", step_entry["id"], len(partitions), len(sub_steps))
    all_outputs: dict[str, list[dict[str, Any]]] = {ss["step"]: [] for ss in sub_steps}
    map_cost = 0.0

    def _run_chunk(chunk_index: int, chunk: dict) -> tuple[int, dict[str, dict], float]:
        from copy import deepcopy
        chunk_outputs = {}
        chunk_cost = 0.0
        chunk_context = deepcopy(context)
        chunk_context["_chunk"] = chunk
        chunk_context["_chunk_index"] = chunk_index

        for sub in sub_steps:
            sub_step_id = sub["step"]
            sub_def = load_step_definition(sub_step_id) or {"id": sub_step_id, "type": "llm", "outputs": {"primary": f"{sub_step_id}.json"}}
            sub_entry = {
                "id": f"chunk{chunk_index}_{sub_step_id}",
                "step": sub_step_id,
                "model": sub.get("model") or step_entry.get("model"),
                "executor": sub.get("executor") or step_entry.get("executor"),
                "contract": sub.get("contract"),
                "thinking_level": sub.get("thinking_level"),
            }
            output, sub_cost = _execute_step(sub_entry, sub_def, pipeline, chunk_context, output_dir)
            chunk_cost += sub_cost
            filename = output_pattern.format(chunk_index=chunk_index, step_id=sub_step_id)
            (output_dir / filename).write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
            chunk_outputs[sub_step_id] = output
        return chunk_index, chunk_outputs, chunk_cost

    if parallel_chunks and len(partitions) > 1:
        # Collect results indexed by chunk_index to preserve ordering
        indexed_results: dict[int, tuple[dict[str, dict], float]] = {}
        with ThreadPoolExecutor(max_workers=max_concurrent) as pool:
            futures = {pool.submit(_run_chunk, i, chunk): i for i, chunk in enumerate(partitions)}
            for future in as_completed(futures):
                try:
                    idx, chunk_outputs, chunk_cost = future.result()
                    indexed_results[idx] = (chunk_outputs, chunk_cost)
                except Exception:
                    logger.exception("Map chunk %d failed", futures[future])
        # Append in chunk order
        for idx in sorted(indexed_results.keys()):
            chunk_outputs, chunk_cost = indexed_results[idx]
            map_cost += chunk_cost
            for step_id, output in chunk_outputs.items():
                all_outputs[step_id].append(output)
    else:
        for i, chunk in enumerate(partitions):
            _, chunk_outputs, chunk_cost = _run_chunk(i, chunk)
            map_cost += chunk_cost
            for step_id, output in chunk_outputs.items():
                all_outputs[step_id].append(output)

    return all_outputs, map_cost


def _execute_reduce_step(
    step_entry: dict[str, Any],
    step_def: dict[str, Any],
    pipeline: dict[str, Any],
    context: dict[str, Any],
    output_dir: Path,
) -> tuple[dict[str, Any], float]:
    """Execute a reduce step: consolidate map outputs. Returns (output, cost_usd)."""
    reduce_config = step_entry.get("reduce_config", {})
    map_step_id = reduce_config.get("from", "")
    map_outputs = context.get(f"_map_outputs_{map_step_id}", {})

    if not map_outputs:
        logger.warning("Reduce step %s: no map outputs from %s", step_entry["id"], map_step_id)
        return {}, 0.0

    # Try running as a normal step (deterministic consolidator)
    step_type = step_def.get("type", "llm")
    if step_type == "deterministic" and step_def.get("script"):
        context["_map_outputs"] = map_outputs
        return _execute_step(step_entry, step_def, pipeline, context, output_dir)

    logger.info("Reduce step %s: consolidated %d worker types", step_entry["id"], len(map_outputs))
    return {"_map_outputs": map_outputs}, 0.0


def _print_dry_run(pipeline_name: str, sorted_steps: list[dict], pipeline: dict) -> None:
    """Print DAG as a visual tree."""
    base_model = pipeline.get("base_model", "")
    base_executor = pipeline.get("base_executor", "")
    total_cost = pipeline.get("cost_estimate_usd", 0)

    try:
        from rich.tree import Tree
        from rich.console import Console

        cost_str = f"~${total_cost:.2f}" if total_cost else "$?"
        tree = Tree(f"[bold]Pipeline: {pipeline_name}[/bold]  ({len(sorted_steps)} steps, est. {cost_str})")

        for s in sorted_steps:
            step_ref = s.get("step", s["id"])
            step_def = load_step_definition(step_ref) or {}
            stype = s.get("type", "normal")
            step_type_label = step_def.get("type", "?")
            executor = _resolve_executor_name(step_def, s, base_executor)
            model = s.get("model") or base_model or ""
            cost = step_def.get("cost_estimate", {})
            cost_val = cost.get("fixed_usd", 0) if isinstance(cost, dict) else 0
            cs = f"${cost_val:.2f}" if cost_val else "$0"
            nb = " [dim](non-blocking)[/dim]" if s.get("non_blocking") else ""

            if stype == "map":
                mc = s.get("map_config", {})
                sub_steps = mc.get("steps", [])
                label = f"[bold yellow]{s['id']}[/bold yellow] MAP {len(sub_steps)} workers/chunk ({executor}/{model}) [{step_type_label}]{nb}"
                node = tree.add(label)
                for ss in sub_steps:
                    node.add(f"{ss['step']}")
            elif stype == "reduce":
                rc = s.get("reduce_config", {})
                from_id = rc.get("from", "?")
                label = f"[bold cyan]{s['id']}[/bold cyan] REDUCE <- {from_id} ({executor}, {cs}) [{step_type_label}]{nb}"
                tree.add(label)
            else:
                if executor == "python":
                    label = f"[green]{s['id']}[/green] ({executor}, {cs}) [{step_type_label}]{nb}"
                else:
                    label = f"[blue]{s['id']}[/blue] ({executor}/{model}, ~{cs}) [{step_type_label}]{nb}"
                tree.add(label)

        Console().print(tree)

    except ImportError:
        print(f"Pipeline: {pipeline_name} ({len(sorted_steps)} steps)")
        for i, s in enumerate(sorted_steps):
            print(f"  {i + 1}. {s['id']} (type={s.get('type', 'normal')})")


# ---------------------------------------------------------------------------
# Fail-fast executor availability check
# ---------------------------------------------------------------------------

# Map of executor names to the env vars they typically require.
_EXECUTOR_ENV_HINTS: dict[str, list[str]] = {
    "openai_api": ["OPENAI_API_KEY"],
    "anthropic_api": ["ANTHROPIC_API_KEY"],
    "azure_openai": ["AZURE_OPENAI_API_KEY", "AZURE_OPENAI_ENDPOINT"],
    "kimi_api": ["KIMI_API_KEY or AZURE_KIMI_API_KEY"],
    "claude_cli": ["(claude CLI in PATH)"],
    "codex_cli": ["(codex CLI in PATH)"],
}


def _check_executor_availability(steps: list[dict[str, Any]], pipeline: dict[str, Any]) -> None:
    """Pre-flight check: verify every executor the pipeline needs is reachable.

    Blocking steps with unavailable executors raise RuntimeError.
    Non-blocking steps only emit a warning.
    """
    base_executor = pipeline.get("base_executor", "openai_api")
    checked: dict[str, bool] = {}  # executor_name -> available?
    missing_blocking: list[str] = []

    for step_entry in steps:
        step_ref = step_entry.get("step", step_entry["id"])
        step_def = load_step_definition(step_ref) or {"id": step_ref, "type": "llm"}
        executor_name = _resolve_executor_name(step_def, step_entry, base_executor)
        non_blocking = step_entry.get("non_blocking", False)

        if executor_name in checked:
            available = checked[executor_name]
        else:
            try:
                executor = get_executor(executor_name)
                available = executor.is_available()
            except ValueError:
                available = False
            checked[executor_name] = available

        if not available:
            env_hint = ", ".join(_EXECUTOR_ENV_HINTS.get(executor_name, ["(unknown)"]))
            if non_blocking:
                logger.warning(
                    "Executor '%s' not available (needed by non-blocking step '%s'). "
                    "Needs: %s — step will likely fail at runtime.",
                    executor_name, step_entry["id"], env_hint,
                )
            else:
                missing_blocking.append(f"  - {executor_name} (step '{step_entry['id']}') — needs {env_hint}")

        # Also check map sub-steps
        if step_entry.get("type") == "map":
            for sub in step_entry.get("map_config", {}).get("steps", []):
                sub_ref = sub.get("step", "")
                sub_def = load_step_definition(sub_ref) or {"id": sub_ref, "type": "llm"}
                sub_exec = sub.get("executor") or _resolve_executor_name(sub_def, sub, base_executor)
                if sub_exec not in checked:
                    try:
                        executor = get_executor(sub_exec)
                        checked[sub_exec] = executor.is_available()
                    except ValueError:
                        checked[sub_exec] = False
                if not checked[sub_exec]:
                    env_hint = ", ".join(_EXECUTOR_ENV_HINTS.get(sub_exec, ["(unknown)"]))
                    if non_blocking:
                        logger.warning(
                            "Executor '%s' not available (map sub-step '%s' in non-blocking '%s').",
                            sub_exec, sub_ref, step_entry["id"],
                        )
                    else:
                        missing_blocking.append(f"  - {sub_exec} (map sub-step '{sub_ref}' in '{step_entry['id']}') — needs {env_hint}")

    if missing_blocking:
        msg = "Fail-fast: required executor(s) not available:\n" + "\n".join(missing_blocking)
        raise RuntimeError(msg)

    logger.info("Executor pre-flight check passed (%d executor(s) verified)", len(checked))


# ---------------------------------------------------------------------------
# Main pipeline execution
# ---------------------------------------------------------------------------

def run_pipeline(
    pipeline_path: str | Path,
    *,
    data_dir: str | Path = "",
    run_id: str | None = None,
    dry_run: bool = False,
    fixup_ids: list[str] | None = None,
    fixup_categories: list[str] | None = None,
    process_type: str | None = None,
    skip_fixups: bool = False,
    resume: bool = False,
    no_ui: bool = False,
    supervised: bool = False,
    _cli_args: list[str] | None = None,
) -> dict[str, Any]:
    """Execute a full pipeline from a DAG JSON."""
    pipeline = load_pipeline(pipeline_path)
    pipeline_name = pipeline.get("name", "unknown")
    run_id = run_id or datetime.now().strftime("%Y%m%d-%H%M%S")
    data_dir_path = Path(data_dir or pipeline.get("data_dir", "data"))
    if not data_dir_path.is_absolute():
        data_dir_path = ROOT / data_dir_path

    base_output = ROOT / "workspace" / "outputs"
    paths = init_run_dir(base_output, run_id)
    output_dir = paths["root"]

    manifest = RunManifest(
        run_dir=output_dir, run_id=run_id,
        pipeline_path=str(pipeline_path), data_dir=str(data_dir_path),
        cli_args=_cli_args,
    )

    logger.info("=" * 60)
    logger.info("PIPELINE: %s (run_id=%s)", pipeline_name, run_id)
    logger.info("Data: %s", data_dir_path)
    logger.info("Output: %s", output_dir)
    logger.info("=" * 60)

    if dry_run:
        steps = pipeline.get("steps", [])
        sorted_steps = _topo_sort(steps)
        _print_dry_run(pipeline_name, sorted_steps, pipeline)
        return {"dry_run": True, "steps": [s["id"] for s in sorted_steps]}

    context: dict[str, Any] = {
        "_data_dir": str(data_dir_path),
        "_output_dir": str(output_dir),
        "_run_id": run_id,
        "_pipeline": pipeline_name,
        "_paths": {k: str(v) for k, v in paths.items()},
    }

    # Load input files from data dir
    if data_dir_path.is_dir():
        raw_docs = []
        for txt_file in sorted(data_dir_path.glob("*")):
            if txt_file.is_file() and txt_file.suffix in (".txt", ".json", ".csv", ".md"):
                try:
                    raw_docs.append(txt_file.read_text(encoding="utf-8", errors="ignore"))
                except OSError:
                    continue
        if raw_docs:
            context["raw_docs_text"] = "\n\n---\n\n".join(raw_docs)

    steps = pipeline.get("steps", [])
    waves = _topo_waves(steps)
    sorted_steps = [s for w in waves for s in w]  # flat list for UI
    step_results: dict[str, Any] = {}
    start_time = time.time()

    global_ledger_path = base_output / "runs" / "ledger-global.jsonl"
    ledger = Ledger(output_dir, global_path=global_ledger_path)
    state = RunState(output_dir, run_id, pipeline_name)
    ledger.emit("pipeline_start", pipeline=pipeline_name, run_id=run_id,
                data_dir=str(data_dir_path), step_count=len(sorted_steps),
                wave_count=len(waves), resume=resume)

    from lib.ui import create_ui
    ui = create_ui(pipeline_name, run_id, sorted_steps, no_ui=no_ui)

    # --- Fail-fast: check executor availability before running any steps ---
    _check_executor_availability(steps, pipeline)

    total_cost = 0.0  # accumulate across all steps

    def _run_one_step(step_entry: dict) -> dict[str, Any] | None:
        """Execute a single step with validation, retry, timeout, and checkpoint.

        Returns None on success, or a dict with pause/error info.
        Raises on fatal (blocking) failure.
        """
        nonlocal total_cost
        from copy import deepcopy

        step_id = step_entry["id"]
        step_ref = step_entry.get("step", step_id)
        step_type = step_entry.get("type", "normal")
        non_blocking = step_entry.get("non_blocking", False)

        step_def = load_step_definition(step_ref) or {
            "id": step_ref, "type": "llm", "outputs": {"primary": f"{step_ref}.json"}
        }

        # Optional: skip if executor unavailable
        if step_entry.get("optional"):
            executor_name = _resolve_executor_name(step_def, step_entry, pipeline.get("base_executor", ""))
            try:
                executor = get_executor(executor_name)
                if not executor.is_available():
                    raise ValueError("not available")
            except (ValueError, Exception):
                logger.info("[%s] Skipping (optional, executor '%s' not available)", step_id, executor_name)
                ledger.emit("step_skipped", step_id=step_id, reason="optional_executor_unavailable", executor=executor_name)
                ui.update_step(step_id, "skipped")
                stub = {"status": "stub", "executor": executor_name, "step_id": step_id, "reason": "executor_not_available"}
                context[f"_output_{step_id}"] = stub
                step_results[step_id] = {"type": step_type, "skipped": True, "reason": "optional"}
                state.mark_done(step_id)
                return None

        # Resume: skip completed steps
        if resume and state.is_resumable(step_id):
            logger.info("[%s] Skipping (already completed)", step_id)
            ledger.emit("step_skipped", step_id=step_id, reason="resumed")
            ui.update_step(step_id, "skipped")
            step_results[step_id] = {"type": step_type, "resumed": True}
            # Reload output from disk for downstream steps
            for candidate in [output_dir / step_def.get("outputs", {}).get("primary", f"{step_id}.json"),
                              paths["steps"] / f"{step_id}.json"]:
                if candidate.exists():
                    try:
                        context[f"_output_{step_id}"] = json.loads(candidate.read_text(encoding="utf-8"))
                    except (json.JSONDecodeError, OSError):
                        pass
                    break
            # Check checkpoint approval on resume
            if step_entry.get("checkpoint"):
                cp = state._data.get("steps", {}).get(step_id, {}).get("checkpoint_status", "pending")
                if cp == "pending":
                    logger.info("[%s] Checkpoint still pending", step_id)
                    state.finalize("paused")
                    ledger.emit("pipeline_paused", step_id=step_id, reason="checkpoint_pending")
                    return {"paused": True, "waiting_on": step_id, "run_id": run_id}
            return None

        # Timeout: per-step override or pipeline default (10 min)
        timeout_seconds = step_entry.get("timeout_seconds") or pipeline.get("default_timeout_seconds", 600)

        # Retry loop
        retry_config = step_entry.get("retry", {})
        max_attempts = retry_config.get("max_attempts", 1)
        backoff_s = retry_config.get("backoff_seconds", 5)

        for attempt in range(1, max_attempts + 1):
            step_start = time.time()
            state.mark_running(step_id)
            ui.update_step(step_id, "running")
            logger.info("[%s] Starting (type=%s, attempt %d/%d, timeout=%ds)...",
                        step_id, step_type, attempt, max_attempts, timeout_seconds)
            ledger.emit("step_start", step_id=step_id, step_type=step_type, attempt=attempt,
                        executor=_resolve_executor_name(step_def, step_entry, pipeline.get("base_executor", "")),
                        model=step_entry.get("model") or pipeline.get("base_model", ""))

            try:
                # Wrap execution in a thread with timeout
                def _do_execute():
                    if step_type == "map":
                        return ("map", _execute_map_step(step_entry, pipeline, context, output_dir))
                    elif step_type == "reduce":
                        return ("reduce", _execute_reduce_step(step_entry, step_def, pipeline, context, output_dir))
                    else:
                        return ("normal", _execute_step(step_entry, step_def, pipeline, context, output_dir))

                with ThreadPoolExecutor(max_workers=1) as timeout_pool:
                    future = timeout_pool.submit(_do_execute)
                    try:
                        exec_type, exec_result = future.result(timeout=timeout_seconds)
                    except FuturesTimeoutError:
                        future.cancel()
                        raise TimeoutError(
                            f"Step {step_id} timed out after {timeout_seconds}s"
                        )

                step_cost = 0.0
                if exec_type == "map":
                    map_outputs, step_cost = exec_result
                    context[f"_map_outputs_{step_id}"] = map_outputs
                    step_results[step_id] = {"type": "map", "workers": list(map_outputs.keys()),
                                             "chunks": len(next(iter(map_outputs.values()), [])),
                                             "cost_usd": step_cost}
                elif exec_type == "reduce":
                    output, step_cost = exec_result
                    context[f"_output_{step_id}"] = output
                    step_results[step_id] = {"type": "reduce", "cost_usd": step_cost}
                else:
                    output, step_cost = exec_result
                    context[f"_output_{step_id}"] = output
                    step_results[step_id] = {"type": "normal", "cost_usd": step_cost}

                total_cost += step_cost

            except Exception as exc:
                elapsed = time.time() - step_start
                if attempt < max_attempts:
                    logger.warning("[%s] Attempt %d failed, retrying in %ds: %s", step_id, attempt, backoff_s, exc)
                    ledger.emit("step_retry", step_id=step_id, attempt=attempt, error=str(exc)[:200])
                    time.sleep(backoff_s)
                    continue
                ledger.emit("step_error", step_id=step_id, error=str(exc)[:200], non_blocking=non_blocking)
                state.mark_failed(step_id, str(exc)[:200], non_blocking=non_blocking)
                ui.update_step(step_id, "failed", duration_s=elapsed)
                if non_blocking:
                    logger.warning("[%s] Failed (non-blocking): %s", step_id, exc)
                    step_results[step_id] = {"type": step_type, "error": str(exc), "non_blocking": True}
                    return None
                else:
                    logger.error("[%s] Failed: %s", step_id, exc)
                    step_results[step_id] = {"type": step_type, "error": str(exc)}
                    ledger.emit("pipeline_error", error=str(exc)[:200])
                    state.finalize("failed")
                    raise

            elapsed = time.time() - step_start
            logger.info("[%s] Executed in %.1fs (cost=$%.4f)", step_id, elapsed, step_cost)

            # --- Validation gates ---
            validation_config = step_entry.get("validation")
            step_schema = step_entry.get("schema") or step_def.get("outputs", {}).get("schema")
            output_for_gate = context.get(f"_output_{step_id}", {})
            output_path_str = str(output_dir / step_def.get("outputs", {}).get("primary", f"{step_id}.json"))

            if validation_config or step_schema:
                gate_result = run_gates(step_id, output_for_gate, output_path_str, validation_config, step_schema)
                if not gate_result["passed"]:
                    ledger.emit("validation_fail", step_id=step_id, attempt=attempt)
                    if attempt < max_attempts:
                        logger.warning("[%s] Validation failed, retrying (%d/%d)", step_id, attempt, max_attempts)
                        time.sleep(backoff_s)
                        continue
                    state.mark_failed(step_id, "validation_failed_max_retries")
                    ui.update_step(step_id, "failed", duration_s=elapsed)
                    if not non_blocking:
                        raise RuntimeError(f"Step {step_id} failed validation after {max_attempts} attempts")
                    step_results[step_id] = {"type": step_type, "error": "validation_failed", "non_blocking": True}
                    return None
                else:
                    ledger.emit("validation_pass", step_id=step_id)

            # Step succeeded
            ledger.emit("step_done", step_id=step_id, duration_s=round(elapsed, 1), cost_usd=step_cost)
            state.mark_done(step_id, duration_s=elapsed, cost_usd=step_cost)
            ui.update_step(step_id, "done", duration_s=elapsed)

            # --- Checkpoint gate ---
            if step_entry.get("checkpoint"):
                logger.info("[%s] Checkpoint — waiting for approval", step_id)
                ledger.emit("checkpoint_pending", step_id=step_id)
                state._data.setdefault("steps", {}).setdefault(step_id, {})["checkpoint_status"] = "pending"
                state.save()
                logger.info("[%s] Run paused. Approve: --approve-checkpoint --step %s --run-id %s", step_id, step_id, run_id)
                state.finalize("paused")
                ledger.emit("pipeline_paused", step_id=step_id, reason="checkpoint_pending")
                return {"paused": True, "waiting_on": step_id, "run_id": run_id}

            return None  # success, no pause

        return None  # should not reach here

    try:
     with ui:
      for wave_idx, wave in enumerate(waves):
        logger.info("--- Wave %d: %d step(s) [%s] ---", wave_idx + 1, len(wave),
                     ", ".join(s["id"] for s in wave))

        if len(wave) == 1:
            # Single step — run directly (no thread overhead)
            result = _run_one_step(wave[0])
            if result and result.get("paused"):
                return result
        else:
            # Multiple independent steps — run in parallel
            with ThreadPoolExecutor(max_workers=len(wave)) as pool:
                futures = {pool.submit(_run_one_step, s): s for s in wave}
                for future in as_completed(futures):
                    step_entry = futures[future]
                    try:
                        result = future.result()
                        if result and result.get("paused"):
                            # Cancel remaining futures and return pause
                            for f in futures:
                                f.cancel()
                            return result
                    except Exception:
                        # Error already logged by _run_one_step
                        # Cancel remaining futures
                        for f in futures:
                            f.cancel()
                        raise

        # --- Supervised mode: pause after each wave for implantador review ---
        if supervised and wave_idx < len(waves) - 1:
            checkpoint_step_id = f"wave_{wave_idx + 1}_review"
            cp_status = state._data.get("steps", {}).get(checkpoint_step_id, {}).get("checkpoint_status")

            if cp_status == "approved":
                logger.info("[SUPERVISED] Wave %d review already approved — continuing", wave_idx + 1)
            else:
                wave_step_ids = [s["id"] for s in wave]
                # Collect outputs from this wave for review summary
                wave_outputs_summary = {}
                for sid in wave_step_ids:
                    out_key = f"_output_{sid}"
                    if out_key in context and isinstance(context[out_key], dict):
                        output = context[out_key]
                        wave_outputs_summary[sid] = {
                            "keys": list(output.keys()),
                            "size_bytes": len(json.dumps(output, ensure_ascii=False)),
                        }

                logger.info("[SUPERVISED] Wave %d/%d completed — pausing for review", wave_idx + 1, len(waves))
                logger.info("[SUPERVISED] Steps completed: %s", ", ".join(wave_step_ids))
                for sid, summary in wave_outputs_summary.items():
                    logger.info("[SUPERVISED]   %s → keys: %s (%d bytes)", sid, summary["keys"], summary["size_bytes"])
                logger.info("[SUPERVISED] Next wave: %s", ", ".join(s["id"] for s in waves[wave_idx + 1]))

                # Save wave review metadata
                review_file = output_dir / f"wave_{wave_idx + 1}_review.json"
                review_data = {
                    "wave": wave_idx + 1,
                    "total_waves": len(waves),
                    "steps_completed": wave_step_ids,
                    "outputs_summary": wave_outputs_summary,
                    "next_wave_steps": [s["id"] for s in waves[wave_idx + 1]],
                }
                review_file.write_text(json.dumps(review_data, ensure_ascii=False, indent=2), encoding="utf-8")

                # Use checkpoint mechanism to pause
                state._data.setdefault("steps", {}).setdefault(checkpoint_step_id, {})["checkpoint_status"] = "pending"
                state.save()
                ledger.emit("wave_review_pending", wave=wave_idx + 1, steps=wave_step_ids)
                state.finalize("paused")
                ledger.emit("pipeline_paused", step_id=checkpoint_step_id, reason="supervised_wave_review")
                return {
                    "paused": True,
                    "waiting_on": checkpoint_step_id,
                    "run_id": run_id,
                    "wave": wave_idx + 1,
                    "supervised": True,
                    "review_file": str(review_file),
                }

      # Apply fixups if any are registered
      if not skip_fixups:
          registry = load_registry()
          if registry.get("fixups"):
              chain = build_chain(registry, fixup_ids=fixup_ids, categories=fixup_categories, process_type=process_type)
              if chain:
                  # Find the main output to fix up
                  for key in ("_output_compile_summary", "_output_compile_report"):
                      if key in context and isinstance(context[key], dict):
                          context[key] = run_chain(chain, context[key], docs_dir=data_dir_path)
                          for fid in context[key].pop("_fixups_applied", []):
                              ledger.emit("fixup_applied", fixup_id=fid)
                          for fid in context[key].pop("_fixups_skipped", []):
                              ledger.emit("fixup_skipped", fixup_id=fid)
                          break

      total_time = time.time() - start_time
      steps_ok = sum(1 for v in step_results.values() if not v.get("error"))
      steps_failed = sum(1 for v in step_results.values() if v.get("error") and not v.get("non_blocking"))

      run_meta = {
          "pipeline": pipeline_name,
          "run_id": run_id,
          "data_dir": str(data_dir_path),
          "output_dir": str(output_dir),
          "total_time_seconds": round(total_time, 1),
          "total_cost_usd": round(total_cost, 4),
          "steps": step_results,
      }
      (output_dir / "run_metadata.json").write_text(
          json.dumps(run_meta, ensure_ascii=False, indent=2), encoding="utf-8"
      )

      status = "completed" if steps_failed == 0 else "failed"
      manifest.finalize(status=status, total_cost=total_cost, total_duration=total_time, steps_ok=steps_ok, steps_failed=steps_failed)
      manifest.append_to_index(base_output)
      state.finalize(status)
      ledger.emit("pipeline_done", total_duration_s=round(total_time, 1), steps_ok=steps_ok, steps_failed=steps_failed)
    finally:
      ledger.close()

    logger.info("=" * 60)
    logger.info("PIPELINE COMPLETE — %s (%.1fs)", run_id, total_time)
    logger.info("=" * 60)

    return run_meta


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="Pipeline Engine — Generic DAG Runner")
    parser.add_argument("--pipeline", help="Path to pipeline DAG JSON")
    parser.add_argument("--data-dir", default="", help="Override input data directory")
    parser.add_argument("--run-id", default=None, help="Run identifier (default: timestamp)")
    parser.add_argument("--dry-run", action="store_true", help="Show execution order without running")
    parser.add_argument("--process-type", default=None, help="Process type for fixup selection")
    parser.add_argument("--skip-fixups", action="store_true", help="Skip post-processing fixups")
    parser.add_argument("--fixup-categories", nargs="*", default=None)
    parser.add_argument("--resume", nargs="?", const=True, default=False,
                        help="Resume a previous run. Optionally: --resume RUN_ID (or use --run-id)")
    parser.add_argument("--no-ui", action="store_true", help="Disable live terminal UI")
    parser.add_argument("--supervised", action="store_true",
                        help="Supervised mode: pause after each wave for implantador review. Use for first run.")
    parser.add_argument("--list-pipelines", action="store_true", help="List available pipelines and exit")
    parser.add_argument("--validate", action="store_true", help="Validate pipeline JSON without executing")
    parser.add_argument("--approve-checkpoint", action="store_true", help="Approve a pending checkpoint")
    parser.add_argument("--reject-checkpoint", action="store_true", help="Reject a pending checkpoint")
    parser.add_argument("--step", default=None, help="Step ID for checkpoint operations")
    parser.add_argument("--reason", default="", help="Reason for checkpoint rejection")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    if args.list_pipelines:
        pipelines_dir = ROOT / "pipelines"
        if pipelines_dir.exists():
            for f in sorted(pipelines_dir.glob("*.json")):
                try:
                    dag = json.loads(f.read_text(encoding="utf-8"))
                    name = dag.get("name", "")
                    steps_count = len(dag.get("steps", []))
                    cost = dag.get("cost_estimate_usd", "?")
                    print(f"  {f.name:<40s} {steps_count:>2d} steps  ~${cost}  {name}")
                except Exception:
                    print(f"  {f.name:<40s}  (parse error)")
        else:
            print("No pipelines/ directory found.")
        return 0

    if not args.pipeline:
        parser.error("--pipeline is required (or use --list-pipelines)")

    if args.validate:
        try:
            load_pipeline(args.pipeline, validate=True)
            logger.info("Pipeline validation PASSED: %s", args.pipeline)
            return 0
        except (ValueError, json.JSONDecodeError) as e:
            logger.error("Pipeline validation FAILED: %s", e)
            return 1

    # Handle checkpoint approve/reject
    if args.approve_checkpoint or args.reject_checkpoint:
        if not args.run_id or not args.step:
            parser.error("--approve-checkpoint / --reject-checkpoint require --run-id and --step")
        base_output = ROOT / "workspace" / "outputs"
        state_path = base_output / "runs" / args.run_id / "run_state.json"
        if not state_path.exists():
            logger.error("Run state not found: %s", state_path)
            return 1
        state_data = json.loads(state_path.read_text(encoding="utf-8"))
        if args.approve_checkpoint:
            approve_checkpoint(state_data, args.step)
            logger.info("Checkpoint approved for step %s in run %s", args.step, args.run_id)
        else:
            if not args.reason:
                parser.error("--reject-checkpoint requires --reason")
            reject_checkpoint(state_data, args.step, args.reason)
            logger.info("Checkpoint rejected for step %s: %s", args.step, args.reason)
        state_path.write_text(json.dumps(state_data, ensure_ascii=False, indent=2), encoding="utf-8")
        return 0

    try:
        # Handle --resume RUN_ID shorthand (sets both resume=True and run_id)
        resume_flag = bool(args.resume)
        run_id = args.run_id
        if isinstance(args.resume, str) and args.resume is not True:
            resume_flag = True
            run_id = run_id or args.resume

        result = run_pipeline(
            args.pipeline,
            data_dir=args.data_dir,
            run_id=run_id,
            dry_run=args.dry_run,
            process_type=args.process_type,
            skip_fixups=args.skip_fixups,
            resume=resume_flag,
            no_ui=args.no_ui,
            supervised=args.supervised,
            fixup_categories=args.fixup_categories,
            _cli_args=sys.argv[1:],
        )
        if isinstance(result, dict) and result.get("paused"):
            waiting = result.get("waiting_on")
            logger.info("Pipeline paused at checkpoint: %s", waiting)
            if result.get("supervised"):
                logger.info("[SUPERVISED] Review outputs in: %s", result.get("review_file", ""))
                logger.info("[SUPERVISED] Check step outputs, field names, and data quality before approving.")
            logger.info("To approve:  python -m lib.runner --pipeline %s --run-id %s --approve-checkpoint --step %s",
                        args.pipeline, result["run_id"], waiting)
            logger.info("To reject:   python -m lib.runner --pipeline %s --run-id %s --reject-checkpoint --step %s --reason '...'",
                        args.pipeline, result["run_id"], waiting)
            if result.get("supervised"):
                logger.info("To resume (keep supervised): python -m lib.runner --pipeline %s --run-id %s --resume --supervised",
                            args.pipeline, result["run_id"])
            return 0
    except Exception:
        logger.exception("Pipeline failed")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

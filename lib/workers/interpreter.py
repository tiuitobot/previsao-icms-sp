"""Request interpreter worker.

Reads a user request and a pipeline config, then produces a resolved
pipeline JSON tailored to this specific run. This enables dynamic DAGs
where the pipeline adapts based on user input.

The interpreter is a meta-step that runs BEFORE the main pipeline.
It reads:
  - user_request.json (from data/)
  - pipeline config (pipelines/v1.config.json)
  - the base pipeline (pipelines/v1.json)

And produces:
  - A resolved pipeline JSON with steps activated/deactivated and parameters set
  - An interpretation summary for downstream steps

The interpreter is an LLM step — it uses judgment to map free-text
requests to pipeline configuration decisions.
"""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any


def resolve_pipeline(
    base_pipeline: dict[str, Any],
    config: dict[str, Any],
    interpretation: dict[str, Any],
) -> dict[str, Any]:
    """Apply interpreter decisions to the base pipeline.

    Args:
        base_pipeline: The full pipeline JSON with all possible steps
        config: The pipeline config with conditional_steps and parameterizable
        interpretation: The LLM interpreter's output with decisions

    Returns:
        Resolved pipeline JSON ready for execution
    """
    resolved = deepcopy(base_pipeline)
    steps = resolved["steps"]

    # 1. Deactivate skipped steps
    skip_ids = set(interpretation.get("skip_steps", []))
    if skip_ids:
        # Remove skipped steps and any depends_on references to them
        steps = [s for s in steps if s["id"] not in skip_ids]
        for s in steps:
            s["depends_on"] = [d for d in s.get("depends_on", []) if d not in skip_ids]
        resolved["steps"] = steps

    # 2. Apply parameters to steps
    params = interpretation.get("step_params", {})
    for step in resolved["steps"]:
        if step["id"] in params:
            step_params = params[step["id"]]
            args = step.setdefault("args", {})
            args.update(step_params)

    # 3. Apply contract overrides
    contract_overrides = interpretation.get("contract_overrides", {})
    for step in resolved["steps"]:
        if step["id"] in contract_overrides:
            step["contract"] = contract_overrides[step["id"]]

    # 4. Inject user context into all LLM steps
    user_context = interpretation.get("user_context", "")
    if user_context:
        for step in resolved["steps"]:
            if step.get("executor", "") != "python":
                args = step.setdefault("args", {})
                args["user_context"] = user_context

    # 5. Update pipeline metadata
    resolved["_resolved"] = True
    resolved["_interpretation"] = {
        "request": interpretation.get("original_request", ""),
        "skipped": list(skip_ids),
        "params_applied": list(params.keys()),
    }

    return resolved


def main(
    *,
    data_dir: str = "",
    pipeline_path: str = "",
    config_path: str = "",
    output_dir: str = "",
    **kwargs: Any,
) -> dict:
    """Interpret user request and resolve pipeline.

    This is called as a deterministic step BEFORE the main pipeline runs.
    It reads the interpreter LLM output and applies it to the base pipeline.

    For the LLM interpretation step, see the contract template.
    This function handles the deterministic resolution after the LLM decides.
    """
    root = Path(data_dir).parent if data_dir else Path(".")

    # Read user request
    request_path = Path(data_dir) / "user_request.json" if data_dir else None
    user_request = ""
    if request_path and request_path.exists():
        req_data = json.loads(request_path.read_text(encoding="utf-8"))
        user_request = req_data.get("user_request", "")

    # Read base pipeline
    if pipeline_path:
        base = json.loads(Path(pipeline_path).read_text(encoding="utf-8"))
    else:
        # Try to find in standard location
        for candidate in [root / "pipelines" / "v1.json", root / "pipelines"]:
            if candidate.is_file():
                base = json.loads(candidate.read_text(encoding="utf-8"))
                break
            elif candidate.is_dir():
                files = sorted(candidate.glob("*.json"))
                if files:
                    base = json.loads(files[0].read_text(encoding="utf-8"))
                    break
        else:
            return {"error": "No pipeline JSON found", "resolved": False}

    # Read config if exists
    config = {}
    if config_path and Path(config_path).exists():
        config = json.loads(Path(config_path).read_text(encoding="utf-8"))
    else:
        # Try standard location
        cfg = Path(pipeline_path).with_suffix(".config.json") if pipeline_path else None
        if cfg and cfg.exists():
            config = json.loads(cfg.read_text(encoding="utf-8"))

    # Read LLM interpretation if available (from a prior LLM step)
    interp_path = Path(output_dir) / "interpretation.json" if output_dir else None
    interpretation = {}
    if interp_path and interp_path.exists():
        interpretation = json.loads(interp_path.read_text(encoding="utf-8"))

    # If no LLM interpretation yet, create a default one (no changes)
    if not interpretation:
        interpretation = {
            "original_request": user_request,
            "skip_steps": [],
            "step_params": {},
            "contract_overrides": {},
            "user_context": user_request,
        }

    # Resolve
    resolved = resolve_pipeline(base, config, interpretation)

    # Write resolved pipeline
    if output_dir:
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        resolved_path = out / "pipeline.resolved.json"
        resolved_path.write_text(
            json.dumps(resolved, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    return {
        "resolved": True,
        "original_request": user_request,
        "total_steps": len(resolved["steps"]),
        "skipped_steps": interpretation.get("skip_steps", []),
        "params_applied": list(interpretation.get("step_params", {}).keys()),
    }

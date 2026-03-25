"""Validation gates and checkpoint logic for the pipeline runner.

Gates are mechanical checks that block downstream execution:
- Schema validation (jsonschema against output)
- R10a plugin validation (custom mechanical checks)
- Checkpoint approval (human-in-the-loop pause)
"""

from __future__ import annotations

import importlib
import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# Schema validation gate
# ---------------------------------------------------------------------------

def validate_schema(output: dict[str, Any], schema_path: str) -> dict[str, Any]:
    """Validate step output against a JSON Schema.

    Returns {"status": "pass"|"fail", "errors": [...]}.
    """
    try:
        import jsonschema
    except ImportError:
        logger.warning("jsonschema not installed — skipping schema validation")
        return {"status": "pass", "errors": [], "skipped": True}

    full_path = Path(schema_path)
    if not full_path.is_absolute():
        full_path = ROOT / schema_path

    if not full_path.exists():
        return {"status": "fail", "errors": [f"Schema file not found: {schema_path}"]}

    schema = json.loads(full_path.read_text(encoding="utf-8"))
    validator = jsonschema.Draft202012Validator(schema)
    errors = [{"path": list(e.path), "message": e.message} for e in validator.iter_errors(output)]

    return {
        "status": "pass" if not errors else "fail",
        "errors": errors,
        "schema": schema_path,
    }


# ---------------------------------------------------------------------------
# R10a plugin validation gate
# ---------------------------------------------------------------------------

def validate_r10a(output_path: str, plugin_class: str, reference_data: str = "", step_id: str = "") -> dict[str, Any]:
    """Run an R10a validation plugin against step output.

    plugin_class is a dotted path like 'lib.r10_plugins.passthrough.PassthroughPlugin'.
    Returns the plugin result dict with at least {"status": "PASS"|"FAIL"}.
    """
    try:
        parts = plugin_class.rsplit(".", 1)
        if len(parts) == 2:
            mod = importlib.import_module(parts[0])
            cls = getattr(mod, parts[1])
        else:
            # Try as module with default class
            mod = importlib.import_module(plugin_class)
            cls = getattr(mod, "PassthroughPlugin", None) or getattr(mod, "Plugin", None)
            if cls is None:
                return {"status": "FAIL", "errors": [f"No plugin class found in {plugin_class}"]}

        plugin = cls()
        result = plugin.validate(output_path, reference_data, step_id)
        return result

    except Exception as exc:
        return {"status": "FAIL", "errors": [f"Plugin error: {exc}"]}


# ---------------------------------------------------------------------------
# Combined gate runner
# ---------------------------------------------------------------------------

def run_gates(
    step_id: str,
    output: dict[str, Any],
    output_path: str,
    validation_config: dict[str, Any] | None,
    step_schema: str | None,
) -> dict[str, Any]:
    """Run all configured validation gates for a step.

    Returns {"passed": bool, "schema_result": ..., "r10a_result": ..., "max_retries": int}.
    """
    result: dict[str, Any] = {"passed": True, "max_retries": 0}

    # Determine schema path (validation config overrides step-level schema)
    schema_path = None
    plugin_class = None
    reference_data = ""
    max_retries = 0

    if validation_config:
        schema_path = validation_config.get("schema")
        plugin_class = validation_config.get("plugin")
        reference_data = validation_config.get("reference_data", "")
        max_retries = validation_config.get("max_retries", 2)

    if not schema_path and step_schema:
        schema_path = step_schema

    result["max_retries"] = max_retries

    # Schema validation
    if schema_path:
        schema_result = validate_schema(output, schema_path)
        result["schema_result"] = schema_result
        if schema_result["status"] != "pass":
            result["passed"] = False
            logger.warning("Step %s: schema validation FAILED (%d errors)", step_id, len(schema_result["errors"]))

    # R10a plugin validation
    if plugin_class:
        r10a_result = validate_r10a(output_path, plugin_class, reference_data, step_id)
        result["r10a_result"] = r10a_result
        status = str(r10a_result.get("status", "")).upper()
        if status != "PASS":
            result["passed"] = False
            logger.warning("Step %s: R10a validation FAILED", step_id)

    return result


# ---------------------------------------------------------------------------
# Checkpoint logic
# ---------------------------------------------------------------------------

def check_checkpoint(step_entry: dict, state_data: dict) -> str:
    """Check checkpoint status for a step.

    Returns: 'not_applicable' | 'pending' | 'approved' | 'rejected'
    """
    if not step_entry.get("checkpoint"):
        return "not_applicable"

    step_id = step_entry["id"]
    step_state = state_data.get("steps", {}).get(step_id, {})
    return step_state.get("checkpoint_status", "pending")


def approve_checkpoint(state_data: dict, step_id: str) -> dict:
    """Mark a checkpoint as approved."""
    steps = state_data.setdefault("steps", {})
    entry = steps.setdefault(step_id, {})
    entry["checkpoint_status"] = "approved"
    return state_data


def reject_checkpoint(state_data: dict, step_id: str, reason: str) -> dict:
    """Mark a checkpoint as rejected. Step can be re-run with --resume."""
    steps = state_data.setdefault("steps", {})
    entry = steps.setdefault(step_id, {})
    entry["checkpoint_status"] = "rejected"
    entry["checkpoint_reason"] = reason
    # Reset step status so it can be re-run
    entry["status"] = "pending"
    return state_data

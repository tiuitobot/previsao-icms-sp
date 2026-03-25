"""Post-processing fixup library.

Fixups are deterministic corrections for known LLM failure modes.
They are domain knowledge encoded as code -- reusable across any
pipeline that touches the same data type.

Usage:
    from lib.fixups import load_registry, build_chain, run_chain

    registry = load_registry()
    chain = build_chain(registry)
    context = run_chain(chain, context, docs_dir=Path("data/input"))
"""

from __future__ import annotations

import importlib
import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_REGISTRY_PATH = Path(__file__).parent / "registry.json"


def load_registry(path: Path | None = None) -> dict[str, Any]:
    p = path or _REGISTRY_PATH
    if not p.exists():
        return {"fixups": []}
    return json.loads(p.read_text(encoding="utf-8"))


def list_fixups(registry: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    reg = registry or load_registry()
    fixups = list(reg.get("fixups", []))
    fixups.sort(key=lambda f: f.get("priority", 50))
    return fixups


def select_fixups(
    registry: dict[str, Any],
    *,
    fixup_ids: list[str] | None = None,
    categories: list[str] | None = None,
    process_type: str | None = None,
    exclude: list[str] | None = None,
) -> list[dict[str, Any]]:
    all_fixups = list_fixups(registry)
    exclude_set = set(exclude or [])

    if fixup_ids is not None:
        id_set = set(fixup_ids)
        selected = [f for f in all_fixups if f["id"] in id_set]
    elif categories is not None:
        cat_set = set(categories)
        selected = [f for f in all_fixups if f.get("category") in cat_set]
    else:
        selected = list(all_fixups)

    if process_type:
        filtered = []
        for f in selected:
            ptypes = f.get("applicability", {}).get("process_types", [])
            if not ptypes or process_type in ptypes:
                filtered.append(f)
        selected = filtered

    return [f for f in selected if f["id"] not in exclude_set]


def build_chain(
    registry: dict[str, Any],
    *,
    fixup_ids: list[str] | None = None,
    categories: list[str] | None = None,
    process_type: str | None = None,
    exclude: list[str] | None = None,
) -> list[dict[str, Any]]:
    selected = select_fixups(registry, fixup_ids=fixup_ids, categories=categories, process_type=process_type, exclude=exclude)

    selected_ids = {f["id"] for f in selected}
    all_by_id = {f["id"]: f for f in list_fixups(registry)}

    added = True
    while added:
        added = False
        for f in list(selected):
            for dep_id in f.get("depends_on", []):
                if dep_id not in selected_ids and dep_id in all_by_id:
                    selected.append(all_by_id[dep_id])
                    selected_ids.add(dep_id)
                    added = True

    selected.sort(key=lambda f: f.get("priority", 50))
    return selected


def run_chain(chain: list[dict[str, Any]], context: dict[str, Any], docs_dir: Path | None = None) -> dict[str, Any]:
    applied: list[str] = []
    skipped: list[str] = []

    for fixup_def in chain:
        fid = fixup_def["id"]
        module_name = fixup_def.get("module", "")
        func_name = fixup_def.get("function", "apply")

        if not module_name:
            skipped.append(fid)
            continue

        try:
            mod = importlib.import_module(f"lib.fixups.{module_name}")
            fn = getattr(mod, func_name, None)
        except (ImportError, AttributeError):
            skipped.append(fid)
            continue

        if fn is None:
            skipped.append(fid)
            continue

        inputs = fixup_def.get("inputs", {})
        required_keys = inputs.get("required_context_keys", [])
        if any(k not in context for k in required_keys):
            skipped.append(fid)
            continue

        if inputs.get("needs_raw_docs") and docs_dir is None:
            skipped.append(fid)
            continue

        try:
            context = fn(context, docs_dir)
            applied.append(fid)
        except Exception:
            skipped.append(fid)
            logger.exception("Fixup %s failed, skipped", fid)

    context["_fixups_applied"] = applied
    context["_fixups_skipped"] = skipped
    return context

"""Inheritance resolver for step definitions and fixup registries.

Implements a simple single-inheritance model where a child object
declares `"extends": "parent_id"` and inherits all fields from
the parent that it does not explicitly override.

Rules:
- `id` is never inherited (always the child's own)
- `extends` is consumed, not propagated
- Dicts are shallow-merged (child keys override parent keys)
- Lists are replaced, not appended (child list wins entirely)
- Scalars are replaced
- Multi-level inheritance works (A extends B extends C)
- Circular inheritance is detected and raises ValueError
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any


def _merge(parent: dict[str, Any], child: dict[str, Any]) -> dict[str, Any]:
    """Merge child over parent. Child wins on conflict."""
    result = deepcopy(parent)

    for key, value in child.items():
        if key in ("id", "extends"):
            continue
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            # Shallow merge for dicts — child keys win
            merged = dict(result[key])
            merged.update(value)
            result[key] = merged
        else:
            result[key] = deepcopy(value)

    # abstract is intrinsic — never inherited from parent
    if "abstract" not in child and "abstract" in result:
        del result["abstract"]

    result["id"] = child["id"]
    result["_extends"] = child.get("extends", "")
    return result


def resolve_inheritance(
    objects: list[dict[str, Any]],
    *,
    id_key: str = "id",
) -> list[dict[str, Any]]:
    """Resolve inheritance for a list of objects.

    Each object may have an `extends` field pointing to another object's ID.
    Returns a new list with all inheritance resolved (fully flattened).
    Objects without `extends` are returned as-is.
    """
    by_id = {obj[id_key]: obj for obj in objects}
    resolved: dict[str, dict[str, Any]] = {}

    def _resolve(obj_id: str, chain: set[str] | None = None) -> dict[str, Any]:
        if obj_id in resolved:
            return resolved[obj_id]

        if obj_id not in by_id:
            raise ValueError(f"Inheritance target not found: {obj_id}")

        chain = chain or set()
        if obj_id in chain:
            raise ValueError(f"Circular inheritance detected: {chain | {obj_id}}")
        chain = chain | {obj_id}

        obj = by_id[obj_id]
        parent_id = obj.get("extends")

        if not parent_id:
            resolved[obj_id] = deepcopy(obj)
            return resolved[obj_id]

        parent = _resolve(parent_id, chain)
        merged = _merge(parent, obj)
        resolved[obj_id] = merged
        return merged

    for obj in objects:
        _resolve(obj[id_key])

    # Preserve original order
    return [resolved[obj[id_key]] for obj in objects]


def build_family_tree(objects: list[dict[str, Any]]) -> dict[str, list[str]]:
    """Build a family tree: parent_id → [child_ids].

    Returns a dict where each key is a root/parent step ID and the
    value is a list of IDs that extend it (directly or transitively).
    """
    children_of: dict[str, list[str]] = {}
    for obj in objects:
        parent_id = obj.get("extends")
        if parent_id:
            children_of.setdefault(parent_id, []).append(obj["id"])

    # Find roots (objects that are parents but don't extend anything)
    all_children = {obj["id"] for obj in objects if obj.get("extends")}
    roots = set()
    for obj in objects:
        if not obj.get("extends"):
            if obj["id"] in children_of:
                roots.add(obj["id"])

    tree: dict[str, list[str]] = {}
    for root in sorted(roots):
        tree[root] = sorted(children_of.get(root, []))

    return tree

#!/usr/bin/env python3
"""Generate pipeline documentation from pipeline.json and step definitions.

Reads a pipeline DAG, resolves step definitions, and produces:
  - PIPELINE_OVERVIEW.md  (internal docs, original mode)
  - README.md             (publication-ready consumer README via --readme)

Usage:
    # Internal pipeline overview (original behavior)
    python3 scripts/generate_pipeline_docs.py --pipeline pipelines/v1.json --root .

    # Publication-ready consumer README
    python3 scripts/generate_pipeline_docs.py --pipeline pipelines/v1.json --root . --readme

    # Print to stdout instead of file
    python3 scripts/generate_pipeline_docs.py --pipeline examples/hello-dag/pipeline.json --root examples/hello-dag --readme --stdout
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# JSON helpers
# ---------------------------------------------------------------------------

def load_json(path: Path) -> dict:
    """Load a JSON file, returning an empty dict on failure."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        print(f"  Warning: could not load {path}: {exc}", file=sys.stderr)
        return {}


# ---------------------------------------------------------------------------
# Step definition resolution
# ---------------------------------------------------------------------------

def resolve_step_definitions(pipeline: dict, root: Path, pipeline_path: Path) -> dict[str, dict]:
    """For each step in the pipeline, try to find its canonical step definition JSON.

    Search order:
      1. <pipeline_dir>/contracts/steps/<step>.json
      2. <root>/contracts/steps/<step>.json
      3. <root>/library/workers/<step>.json  (engine library)
    """
    search_dirs = [
        pipeline_path.parent / "contracts" / "steps",
        root / "contracts" / "steps",
        root / "library" / "workers",
    ]
    step_defs: dict[str, dict] = {}
    for step_entry in pipeline.get("steps", []):
        step_id = step_entry.get("step", step_entry.get("id", ""))
        for d in search_dirs:
            candidate = d / f"{step_id}.json"
            if candidate.exists():
                step_defs[step_id] = load_json(candidate)
                break
        if step_id not in step_defs:
            step_defs[step_id] = {}
    return step_defs


# ---------------------------------------------------------------------------
# ASCII DAG generation
# ---------------------------------------------------------------------------

def build_ascii_dag(pipeline: dict) -> str:
    """Build an ASCII flowchart from the pipeline dependency graph.

    Produces a top-to-bottom layout showing steps grouped by topological level,
    with arrows indicating dependencies.
    """
    steps = pipeline.get("steps", [])
    if not steps:
        return "(no steps defined)"

    # Build adjacency and in-degree maps
    step_ids = [s["id"] for s in steps]
    deps: dict[str, list[str]] = {}
    children: dict[str, list[str]] = defaultdict(list)
    in_degree: dict[str, int] = {s: 0 for s in step_ids}

    for s in steps:
        sid = s["id"]
        depends = s.get("depends_on", [])
        deps[sid] = depends
        in_degree[sid] = len(depends)
        for parent in depends:
            children[parent].append(sid)

    # Topological sort into levels (Kahn's algorithm)
    levels: list[list[str]] = []
    degree_copy = dict(in_degree)
    queue = [s for s in step_ids if degree_copy[s] == 0]

    while queue:
        levels.append(sorted(queue))
        next_queue = []
        for node in queue:
            for child in children[node]:
                degree_copy[child] -= 1
                if degree_copy[child] == 0:
                    next_queue.append(child)
        queue = next_queue

    # Check for orphans (cycle detection fallback)
    placed = {s for level in levels for s in level}
    orphans = [s for s in step_ids if s not in placed]
    if orphans:
        levels.append(orphans)

    # Render ASCII: box-based layout
    box_width = max((len(s) for s in step_ids), default=8) + 4  # padding inside brackets

    def box(name: str) -> str:
        padded = name.center(box_width)
        return f"[{padded}]"

    full_box_width = box_width + 2  # includes the [ ]
    gap = 4  # space between boxes on the same level

    lines: list[str] = []

    for level_idx, level in enumerate(levels):
        # Build the row of boxes
        boxes = [box(s) for s in level]
        box_line = (" " * gap).join(boxes)
        lines.append(box_line)

        # Draw connectors to the next level
        if level_idx < len(levels) - 1:
            next_level = levels[level_idx + 1]
            n_curr = len(level)
            n_next = len(next_level)

            if n_curr == 1 and n_next == 1:
                # Simple vertical pipe
                mid = full_box_width // 2
                lines.append(" " * mid + "|")
                lines.append(" " * mid + "v")
            elif n_curr == 1 and n_next > 1:
                # Fan-out: one parent splits to multiple children
                mid = full_box_width // 2
                lines.append(" " * mid + "|")
                # Calculate positions of child box centers
                child_centers = []
                for i in range(n_next):
                    child_centers.append(i * (full_box_width + gap) + full_box_width // 2)
                left = child_centers[0]
                right = child_centers[-1]
                bar_line = [" "] * (right + 1)
                for c in child_centers:
                    bar_line[c] = "+"
                for i in range(left, right + 1):
                    if bar_line[i] == " ":
                        bar_line[i] = "-"
                # Connect from the parent center
                if mid < left:
                    bar_line[mid] = "+"
                elif mid > right:
                    bar_line[mid] = "+"
                else:
                    bar_line[mid] = "+"
                lines.append("".join(bar_line))
                arrow_line = [" "] * (right + 1)
                for c in child_centers:
                    arrow_line[c] = "v"
                lines.append("".join(arrow_line))
            elif n_curr > 1 and n_next == 1:
                # Fan-in: multiple parents merge to one child
                parent_centers = []
                for i in range(n_curr):
                    parent_centers.append(i * (full_box_width + gap) + full_box_width // 2)
                left = parent_centers[0]
                right = parent_centers[-1]
                pipe_line = [" "] * (right + 1)
                for c in parent_centers:
                    pipe_line[c] = "|"
                lines.append("".join(pipe_line))
                bar_line = [" "] * (right + 1)
                for c in parent_centers:
                    bar_line[c] = "+"
                for i in range(left, right + 1):
                    if bar_line[i] == " ":
                        bar_line[i] = "-"
                lines.append("".join(bar_line))
                # Arrow down to the child center
                child_mid = full_box_width // 2
                merge_mid = (left + right) // 2
                arrow_line = [" "] * max(merge_mid + 1, child_mid + 1)
                arrow_line[merge_mid] = "|"
                lines.append("".join(arrow_line))
                arrow_line2 = [" "] * max(merge_mid + 1, child_mid + 1)
                arrow_line2[merge_mid] = "v"
                lines.append("".join(arrow_line2))
            else:
                # General case: multiple to multiple — draw vertical pipes
                parent_centers = []
                for i in range(n_curr):
                    parent_centers.append(i * (full_box_width + gap) + full_box_width // 2)
                max_pos = max(parent_centers) if parent_centers else 0
                pipe_line = [" "] * (max_pos + 1)
                for c in parent_centers:
                    pipe_line[c] = "|"
                lines.append("".join(pipe_line))
                arrow_line = [" "] * (max_pos + 1)
                for c in parent_centers:
                    arrow_line[c] = "v"
                lines.append("".join(arrow_line))

    return "\n".join(lines)


def build_dependency_text(pipeline: dict) -> str:
    """Build a text representation of step dependencies."""
    steps = pipeline.get("steps", [])
    if not steps:
        return "(no steps defined)"

    lines = []
    for s in steps:
        sid = s["id"]
        depends = s.get("depends_on", [])
        if depends:
            for dep in depends:
                lines.append(f"{dep} --> {sid}")
        else:
            lines.append(f"(start) --> {sid}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Table builders
# ---------------------------------------------------------------------------

def build_steps_table(pipeline: dict, step_defs: dict[str, dict]) -> str:
    """Build the markdown steps table."""
    rows = []
    for s in pipeline.get("steps", []):
        sid = s["id"]
        sdef = step_defs.get(s.get("step", sid), {})
        stype = sdef.get("type", s.get("type", "normal"))
        executor = s.get("executor", pipeline.get("base_executor", "-"))
        desc = sdef.get("description", sdef.get("name", "-"))
        checkpoint = "Yes" if s.get("checkpoint", False) else "-"
        rows.append(f"| {sid} | {stype} | {executor} | {desc} | {checkpoint} |")
    return "\n".join(rows) if rows else "| (none) | - | - | - | - |"


def build_contracts_table(pipeline: dict, step_defs: dict[str, dict]) -> str:
    """Build the markdown contracts table."""
    rows = []
    for s in pipeline.get("steps", []):
        sid = s["id"]
        sdef = step_defs.get(s.get("step", sid), {})
        contracts = sdef.get("contracts", {})
        model = s.get("model", pipeline.get("base_model", "-"))
        if contracts:
            for model_key, contract_path in contracts.items():
                rows.append(f"| {sid} | {contract_path} | {model_key} | - |")
        else:
            contract = s.get("contract", "-")
            if contract != "-":
                rows.append(f"| {sid} | {contract} | {model or '-'} | - |")
            else:
                step_type = sdef.get("type", "")
                note = "deterministic (no contract)" if step_type == "deterministic" else "-"
                rows.append(f"| {sid} | - | {model or '-'} | {note} |")
    return "\n".join(rows) if rows else "| (none) | - | - | - |"


def build_cost_table(pipeline: dict, step_defs: dict[str, dict]) -> tuple[str, str]:
    """Build the cost estimate table and total."""
    rows = []
    total = 0.0
    for s in pipeline.get("steps", []):
        sid = s["id"]
        sdef = step_defs.get(s.get("step", sid), {})
        executor = s.get("executor", pipeline.get("base_executor", "-"))
        cost_info = sdef.get("cost_estimate", {})
        fixed = cost_info.get("fixed_usd", 0)
        per_chunk = cost_info.get("per_chunk_usd", 0)
        notes = cost_info.get("notes", "")
        if fixed or per_chunk:
            cost_str = f"${fixed:.2f}"
            if per_chunk:
                cost_str += f" + ${per_chunk:.2f}/chunk"
            if notes:
                cost_str += f" ({notes})"
        else:
            cost_str = "$0.00"
        total += fixed
        rows.append(f"| {sid} | {executor} | {cost_str} |")

    pipeline_cost = pipeline.get("cost_estimate_usd")
    if pipeline_cost is not None and pipeline_cost > total:
        total = pipeline_cost

    total_str = f"${total:.2f}"
    table = "\n".join(rows) if rows else "| (none) | - | $0.00 |"
    return table, total_str


def build_quality_controls(pipeline: dict, step_defs: dict[str, dict]) -> tuple[str, str, str]:
    """Extract validation gates, checkpoints, and fixups."""
    validations = []
    checkpoints = []
    fixups = []

    for s in pipeline.get("steps", []):
        sid = s["id"]
        sdef = step_defs.get(s.get("step", sid), {})

        if s.get("validation") or s.get("schema"):
            schema = s.get("schema", "")
            if not schema and s.get("validation"):
                schema = s["validation"].get("schema", "")
            validations.append(f"`{sid}` ({schema or 'configured'})")

        if sdef.get("outputs", {}).get("schema"):
            if sid not in [v.split("`")[1] for v in validations if "`" in v]:
                validations.append(f"`{sid}` ({sdef['outputs']['schema']})")

        if s.get("checkpoint"):
            checkpoints.append(f"`{sid}`")

        for fixup in sdef.get("suggested_fixups", []):
            fixups.append(f"`{fixup}` (suggested for `{sid}`)")

    return (
        ", ".join(validations) if validations else "(none configured)",
        ", ".join(checkpoints) if checkpoints else "(none configured)",
        ", ".join(fixups) if fixups else "(none registered)",
    )


# ---------------------------------------------------------------------------
# Cost formatting
# ---------------------------------------------------------------------------

def format_cost(usd: float) -> str:
    """Format a cost value for human display."""
    if usd == 0:
        return "$0.00"
    if usd < 0.01:
        return f"~${usd:.3f}"
    return f"~${usd:.2f}"


def cost_badge_str(usd: float) -> str:
    """Format cost for a shields.io badge URL (URL-safe, no spaces)."""
    if usd == 0:
        return "%240.00"
    if usd < 0.01:
        return f"~%24{usd:.3f}"
    return f"~%24{usd:.2f}"


# ---------------------------------------------------------------------------
# Unicode box-drawing DAG
# ---------------------------------------------------------------------------

def _topo_layers(steps: list[dict]) -> list[list[dict]]:
    """Topologically sort steps into layers for rendering.

    Each layer contains steps whose dependencies are all in earlier layers.
    """
    placed: set[str] = set()
    layers: list[list[dict]] = []
    remaining = list(steps)
    while remaining:
        layer = [s for s in remaining if all(d in placed for d in s.get("depends_on", []))]
        if not layer:
            layer = [remaining[0]]
        for s in layer:
            placed.add(s["id"])
        remaining = [s for s in remaining if s["id"] not in placed]
        layers.append(layer)
    return layers


def _make_box(label: str, annotation: str) -> tuple[list[str], int]:
    """Create a Unicode box with annotation line.

    Returns (list_of_lines, width) where all lines are the same width.
    """
    inner_min = max(len(label) + 2, len(annotation) + 2)
    width = inner_min + 2  # borders
    if width % 2 == 0:
        width += 1  # prefer odd widths for centered connectors

    top = "┌" + "─" * (width - 2) + "┐"
    mid = "│" + label.center(width - 2) + "│"
    bot = "└" + "─" * (width - 2) + "┘"
    ann = annotation.center(width)
    return [top, mid, bot, ann], width


def build_unicode_dag(pipeline: dict, step_defs: dict[str, dict]) -> str:
    """Build a professional Unicode box-drawing DAG from the pipeline.

    Layout: layers are rendered top-to-bottom. Steps in the same layer
    are placed side by side. Connectors use Unicode box-drawing characters.

    Handles skip-connections (a step depending on a non-adjacent layer)
    by routing vertical pipes through intermediate layers alongside the boxes.
    """
    raw_steps = pipeline.get("steps", [])
    if not raw_steps:
        return "(empty pipeline)"

    layers = _topo_layers(raw_steps)

    # Map step id -> layer index
    step_layer: dict[str, int] = {}
    for li, layer in enumerate(layers):
        for s in layer:
            step_layer[s["id"]] = li

    # Pre-build box data for each step
    box_info: dict[str, dict] = {}
    for s in raw_steps:
        sid = s["id"]
        sdef = step_defs.get(s.get("step", sid), {})
        executor = s.get("executor", pipeline.get("base_executor", "python"))
        model = s.get("model", pipeline.get("base_model", ""))
        cost_est = sdef.get("cost_estimate", {})
        cost_usd = cost_est.get("fixed_usd", 0)
        ann_parts = []
        if model:
            ann_parts.append(model)
        else:
            ann_parts.append(executor)
        ann_parts.append(format_cost(cost_usd))
        if s.get("checkpoint"):
            ann_parts.append("checkpoint")
        annotation = ", ".join(ann_parts)
        box_lines, box_width = _make_box(sid, annotation)
        box_info[sid] = {"lines": box_lines, "width": box_width}

    GAP = 4  # horizontal gap between boxes in same layer

    # For skip-connections, we need to reserve a "pass-through lane" in
    # intermediate layers. We allocate an extra column to the right of
    # the boxes in layers that need it.
    #
    # Collect all edges that skip layers.
    pass_through_lanes: dict[int, list[tuple[str, str]]] = defaultdict(list)
    #   key = intermediate layer index, value = list of (parent_id, child_id) edges passing through
    for s in raw_steps:
        sid = s["id"]
        for dep in s.get("depends_on", []):
            dep_layer = step_layer.get(dep)
            sid_layer = step_layer.get(sid)
            if dep_layer is not None and sid_layer is not None:
                for mid_layer in range(dep_layer + 1, sid_layer):
                    pass_through_lanes[mid_layer].append((dep, sid))

    output_lines: list[str] = []

    # Track the horizontal center of each box for connector drawing
    box_centers: dict[str, int] = {}
    # Track pass-through pipe x-positions
    passthrough_x: dict[str, int] = {}  # keyed by "parent->child"

    # Pre-calculate the total width used by boxes at each layer so
    # passthrough lanes are always placed outside the box area.
    layer_box_widths: dict[int, int] = {}
    for li, layer in enumerate(layers):
        x = 0
        for s in layer:
            x += box_info[s["id"]]["width"] + GAP
        layer_box_widths[li] = x - GAP if layer else 0

    # Determine passthrough x positions BEFORE rendering so they are
    # consistent across all layers. Each unique edge gets a fixed column
    # that is to the right of the widest box area across all layers it
    # passes through (and the source/target layers).
    pt_lane_offset = 0  # incremented for each unique edge
    for s in raw_steps:
        sid = s["id"]
        for dep in s.get("depends_on", []):
            dep_layer_idx = step_layer.get(dep)
            sid_layer_idx = step_layer.get(sid)
            if dep_layer_idx is not None and sid_layer_idx is not None:
                if sid_layer_idx - dep_layer_idx > 1:
                    key = f"{dep}->{sid}"
                    if key not in passthrough_x:
                        # Find the max box area width across all layers this pipe passes
                        involved = list(range(dep_layer_idx, sid_layer_idx + 1))
                        max_box_area = max(layer_box_widths.get(li, 0) for li in involved)
                        x_pos = max_box_area + GAP + pt_lane_offset * 2
                        passthrough_x[key] = x_pos
                        pt_lane_offset += 1

    for layer_idx, layer in enumerate(layers):
        # Calculate positions for boxes in this layer
        x_offset = 0
        positions: list[tuple[int, dict]] = []
        for s in layer:
            sid = s["id"]
            w = box_info[sid]["width"]
            positions.append((x_offset, s))
            box_centers[sid] = x_offset + w // 2
            x_offset += w + GAP

        # Draw connectors from previous layers to this layer
        if layer_idx > 0:
            # Gather all connections arriving at this layer:
            # (source_x, child_x) where source_x is either a box center
            # or a pass-through pipe from a previous layer
            connections: list[tuple[int, int]] = []
            for s in layer:
                sid = s["id"]
                for dep in s.get("depends_on", []):
                    dep_layer_idx = step_layer.get(dep)
                    if dep_layer_idx is None:
                        continue
                    if dep_layer_idx == layer_idx - 1:
                        # Direct connection from previous layer
                        if dep in box_centers:
                            connections.append((box_centers[dep], box_centers[sid]))
                    else:
                        # Skip-connection: source is a pass-through pipe
                        key = f"{dep}->{sid}"
                        if key in passthrough_x:
                            connections.append((passthrough_x[key], box_centers[sid]))

            # Also include pass-through pipes that START at this transition
            # (from layer_idx-1 boxes to pass-through lanes)
            for parent_id, child_id in pass_through_lanes.get(layer_idx, []):
                parent_layer_idx = step_layer.get(parent_id)
                key = f"{parent_id}->{child_id}"
                if parent_layer_idx == layer_idx - 1:
                    # Starting a new pass-through from the parent box
                    if parent_id in box_centers and key in passthrough_x:
                        connections.append((box_centers[parent_id], passthrough_x[key]))

            if connections:
                parent_xs = sorted(set(c[0] for c in connections))
                child_xs = sorted(set(c[1] for c in connections))
                all_xs = sorted(set(parent_xs + child_xs))
                max_x = max(all_xs)

                # Also draw continuing pass-through pipes from earlier layers
                continuing_pts = []
                for prev_layer in range(layer_idx):
                    for parent_id, child_id in pass_through_lanes.get(prev_layer, []):
                        child_layer = step_layer.get(child_id)
                        if child_layer is not None and child_layer > layer_idx:
                            key = f"{parent_id}->{child_id}"
                            if key in passthrough_x:
                                continuing_pts.append(passthrough_x[key])

                # Line 1: vertical pipes down from sources
                pipe = [" "] * (max_x + 1)
                for px in parent_xs:
                    pipe[px] = "│"
                for ptx in continuing_pts:
                    if ptx < len(pipe):
                        pipe[ptx] = "│"
                    else:
                        pipe.extend([" "] * (ptx - len(pipe) + 1))
                        pipe[ptx] = "│"
                output_lines.append("".join(pipe).rstrip())

                # Line 2: horizontal bar if needed
                need_bar = len(all_xs) > 1
                if need_bar:
                    bar = [" "] * (max_x + 1)
                    bar_min = min(all_xs)
                    bar_max = max(all_xs)
                    for i in range(bar_min, bar_max + 1):
                        bar[i] = "─"
                    parent_set = set(parent_xs)
                    child_set = set(child_xs)
                    for x in all_xs:
                        is_parent = x in parent_set
                        is_child = x in child_set
                        is_left = x == bar_min
                        is_right = x == bar_max
                        if is_parent and is_child:
                            bar[x] = "┼"
                        elif is_parent and is_left:
                            bar[x] = "└"
                        elif is_parent and is_right:
                            bar[x] = "┘"
                        elif is_parent:
                            bar[x] = "┴"
                        elif is_child and is_left:
                            bar[x] = "┌"
                        elif is_child and is_right:
                            bar[x] = "┐"
                        elif is_child:
                            bar[x] = "┬"
                    # Continuing pass-through pipes pass through the bar
                    for ptx in continuing_pts:
                        if ptx < len(bar):
                            if bar[ptx] == " ":
                                bar[ptx] = "│"
                            elif bar[ptx] == "─":
                                bar[ptx] = "┼"
                    output_lines.append("".join(bar).rstrip())

                    # Line 3: vertical pipes down to children
                    pipe2 = [" "] * (max_x + 1)
                    for cx in child_xs:
                        pipe2[cx] = "│"
                    for ptx in continuing_pts:
                        if ptx < len(pipe2):
                            pipe2[ptx] = "│"
                        else:
                            pipe2.extend([" "] * (ptx - len(pipe2) + 1))
                            pipe2[ptx] = "│"
                    output_lines.append("".join(pipe2).rstrip())
            else:
                # No direct connections but maybe pass-through pipes
                continuing_pts = []
                for prev_layer in range(layer_idx):
                    for parent_id, child_id in pass_through_lanes.get(prev_layer, []):
                        child_layer = step_layer.get(child_id)
                        if child_layer is not None and child_layer > layer_idx:
                            key = f"{parent_id}->{child_id}"
                            if key in passthrough_x:
                                continuing_pts.append(passthrough_x[key])
                if continuing_pts:
                    max_x = max(continuing_pts)
                    pipe = [" "] * (max_x + 1)
                    for ptx in continuing_pts:
                        pipe[ptx] = "│"
                    output_lines.append("".join(pipe).rstrip())

        # Render the box lines for this layer
        for row_idx in range(4):  # top, mid, bot, annotation
            line_parts: list[str] = []
            cursor = 0
            for x_start, s in positions:
                sid = s["id"]
                bi = box_info[sid]
                if x_start > cursor:
                    line_parts.append(" " * (x_start - cursor))
                line_parts.append(bi["lines"][row_idx])
                cursor = x_start + bi["width"]

            # Add pass-through pipes alongside boxes
            line_str = "".join(line_parts)
            pt_edges_here = pass_through_lanes.get(layer_idx, [])
            # Also include continuing pass-throughs from earlier
            all_pt_xs: list[int] = []
            for parent_id, child_id in pt_edges_here:
                key = f"{parent_id}->{child_id}"
                if key in passthrough_x:
                    all_pt_xs.append(passthrough_x[key])
            for prev_layer in range(layer_idx):
                for parent_id, child_id in pass_through_lanes.get(prev_layer, []):
                    child_layer = step_layer.get(child_id)
                    if child_layer is not None and child_layer > layer_idx:
                        key = f"{parent_id}->{child_id}"
                        if key in passthrough_x:
                            px = passthrough_x[key]
                            if px not in all_pt_xs:
                                all_pt_xs.append(px)

            if all_pt_xs:
                max_pt = max(all_pt_xs)
                if max_pt >= len(line_str):
                    line_str += " " * (max_pt - len(line_str) + 1)
                line_chars = list(line_str)
                for ptx in all_pt_xs:
                    if ptx < len(line_chars) and line_chars[ptx] == " ":
                        line_chars[ptx] = "│"
                    elif ptx >= len(line_chars):
                        line_chars.extend([" "] * (ptx - len(line_chars)))
                        line_chars.append("│")
                output_lines.append("".join(line_chars).rstrip())
            else:
                output_lines.append(line_str.rstrip())

    return "\n".join(output_lines)


# ---------------------------------------------------------------------------
# Data-flow diagram
# ---------------------------------------------------------------------------

def build_data_flow(pipeline: dict, step_defs: dict[str, dict]) -> str:
    """Build a linear data-flow text diagram."""
    steps = pipeline.get("steps", [])
    if not steps:
        return "(no steps)"

    # Detect input format from data_dir
    data_dir = pipeline.get("data_dir", "data")
    input_format = "JSON"

    # Detect output format from last step
    last_step = steps[-1]
    last_id = last_step.get("step", last_step.get("id", ""))
    last_def = step_defs.get(last_id, {})
    output_file = last_def.get("outputs", {}).get("primary", f"{last_id}.json")
    output_format = output_file.rsplit(".", 1)[-1].upper() if "." in output_file else "JSON"

    lines = [f"Input ({input_format})"]
    for s in steps:
        sid = s["id"]
        sdef = step_defs.get(s.get("step", sid), {})
        stype = sdef.get("type", s.get("type", "normal"))
        executor = s.get("executor", pipeline.get("base_executor", "python"))
        name = sdef.get("name", sid.replace("_", " ").title())
        lines.append(f"  \u2192 {name} [{stype}, {executor}]")
    lines.append(f"  \u2192 Output ({output_format})")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Enriched step list for README template
# ---------------------------------------------------------------------------

def _enrich_steps_for_readme(
    pipeline: dict, step_defs: dict[str, dict]
) -> list[dict[str, Any]]:
    """Build a list of enriched step dicts for the Jinja2 README template."""
    enriched: list[dict[str, Any]] = []
    for idx, s in enumerate(pipeline.get("steps", [])):
        sid = s.get("id", s.get("step", f"step_{idx}"))
        sdef = step_defs.get(s.get("step", sid), {})

        name = sdef.get("name", sid.replace("_", " ").title())
        description = sdef.get("description", "")
        step_type = sdef.get("type", s.get("type", "normal"))
        executor = s.get("executor", pipeline.get("base_executor", "python"))
        model = s.get("model", pipeline.get("base_model", ""))
        cost_est = sdef.get("cost_estimate", {})
        cost_usd = cost_est.get("fixed_usd", 0)
        checkpoint = s.get("checkpoint", False)
        output_file = sdef.get("outputs", {}).get("primary", f"{sid}.json")
        contract_path = ""
        contracts_obj = sdef.get("contracts", {})
        if contracts_obj:
            contract_path = next(iter(contracts_obj.values()), "")

        enriched.append({
            "number": idx,
            "id": sid,
            "name": name,
            "description": description,
            "type": step_type,
            "executor": executor,
            "model": model if model else "",
            "depends_on": s.get("depends_on", []),
            "cost_usd": cost_usd,
            "cost": format_cost(cost_usd),
            "checkpoint": checkpoint,
            "output_file": output_file,
            "contract_path": contract_path,
        })
    return enriched


# ---------------------------------------------------------------------------
# README generation (consumer-facing, publication-ready)
# ---------------------------------------------------------------------------

def generate_readme(
    pipeline_path: str | Path,
    root: str | Path | None = None,
    output_path: str | Path | None = None,
    *,
    engine_root: str | Path | None = None,
) -> str:
    """Generate a publication-ready README.md from a pipeline definition.

    Args:
        pipeline_path: Path to the pipeline JSON file.
        root: Consumer repo root (where contracts/steps/ live).
              Defaults to the pipeline file's parent directory.
        output_path: Where to write the README. If None, returns the string only.
        engine_root: Pipeline engine root (where templates/ live).
                     Defaults to auto-detect from this script's location.

    Returns:
        The rendered README content.
    """
    from jinja2 import Environment, FileSystemLoader

    pipeline_path = Path(pipeline_path).resolve()
    pipeline = load_json(pipeline_path)

    if root is None:
        root = pipeline_path.parent
    else:
        root = Path(root).resolve()

    if engine_root is None:
        engine_root = Path(__file__).resolve().parent.parent
    else:
        engine_root = Path(engine_root).resolve()

    template_dir = engine_root / "templates"

    # Resolve step definitions
    step_defs = resolve_step_definitions(pipeline, root, pipeline_path)

    # Enrich steps
    steps = _enrich_steps_for_readme(pipeline, step_defs)

    # Pipeline metadata
    pipeline_name = pipeline.get("name", "pipeline")
    version = pipeline.get("version", "v1")
    description = pipeline.get("description", "")
    base_model = pipeline.get("base_model", "")

    # Total cost
    total_cost_usd = sum(s["cost_usd"] for s in steps)
    total_cost = format_cost(total_cost_usd)

    # Checkpoints
    checkpoint_steps = [s["name"] for s in steps if s.get("checkpoint")]
    checkpoints_str = ", ".join(checkpoint_steps) if checkpoint_steps else "None configured"

    # Schema validations
    schemas_dir = root / "contracts" / "schemas"
    schema_steps = []
    if schemas_dir.exists():
        for sf in schemas_dir.glob("*.schema.json"):
            step_id = sf.stem.replace(".schema", "")
            matching = [s for s in steps if s["id"] == step_id]
            if matching:
                schema_steps.append(matching[0]["name"])
    schema_str = ", ".join(schema_steps) if schema_steps else "All steps"

    # Contracts table data
    contracts = []
    for s in steps:
        if s["type"] not in ("deterministic",):
            contracts.append({
                "step": s["name"],
                "contract": s.get("contract_path") or f"contracts/steps/{s['id']}.json",
                "model": s["model"] if s["model"] else base_model if base_model else "--",
                "purpose": s["description"][:80] if s["description"] else "--",
            })

    # Cost breakdown
    cost_breakdown = [{"component": s["name"], "cost": s["cost"]} for s in steps]

    # Final output file
    final_output = steps[-1]["output_file"] if steps else "output.json"

    # Unicode DAG
    ascii_dag = build_unicode_dag(pipeline, step_defs)

    # Data flow
    data_flow = build_data_flow(pipeline, step_defs)

    # Render template
    env = Environment(
        loader=FileSystemLoader(str(template_dir)),
        keep_trailing_newline=True,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    template = env.get_template("README.consumer.md.j2")

    rendered = template.render(
        pipeline_name=pipeline_name,
        one_line_description=description,
        status="active",
        status_color="brightgreen",
        cost_badge=cost_badge_str(total_cost_usd),
        step_count=len(steps),
        last_updated=date.today().isoformat(),
        description=description,
        ascii_dag=ascii_dag,
        steps=steps,
        total_cost=total_cost,
        data_flow=data_flow,
        version=version,
        final_output=final_output,
        checkpoints=checkpoints_str,
        schema_validations=schema_str,
        fixups="None configured",
        contracts=contracts if contracts else None,
        cost_breakdown=cost_breakdown,
        archetype_name=pipeline.get("archetype", "custom"),
        repo_dir=pipeline_name,
    )

    if output_path is not None:
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(rendered, encoding="utf-8")
        print(f"README generated: {out}")

    return rendered


# ---------------------------------------------------------------------------
# Template rendering
# ---------------------------------------------------------------------------

def render_overview(template_path: Path, replacements: dict[str, str]) -> str:
    """Simple {{ key }} replacement in a template file."""
    if template_path.exists():
        content = template_path.read_text(encoding="utf-8")
    else:
        # Fallback: use inline minimal template
        content = "# Pipeline Overview: {{ pipeline_name }}\n\n{{ dag_flowchart }}\n"

    for key, value in replacements.items():
        content = content.replace("{{ " + key + " }}", value)

    return content


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate pipeline documentation from pipeline.json"
    )
    parser.add_argument(
        "--pipeline", required=True,
        help="Path to pipeline JSON file"
    )
    parser.add_argument(
        "--root", default=".",
        help="Root directory of the project (default: current dir)"
    )
    parser.add_argument(
        "--output", default=None,
        help="Output file path (default depends on mode)"
    )
    parser.add_argument(
        "--template", default=None,
        help="Template file path (default: auto-detect from engine or local templates)"
    )
    parser.add_argument(
        "--readme", action="store_true",
        help="Generate publication-ready consumer README.md instead of PIPELINE_OVERVIEW.md"
    )
    parser.add_argument(
        "--stdout", action="store_true",
        help="Print output to stdout instead of writing a file"
    )
    parser.add_argument(
        "--engine-root", default=None,
        help="Pipeline engine root directory (for --readme mode, defaults to auto-detect)"
    )
    args = parser.parse_args()

    root = Path(args.root).resolve()
    pipeline_path = Path(args.pipeline).resolve()

    if not pipeline_path.exists():
        print(f"Error: pipeline file not found: {pipeline_path}", file=sys.stderr)
        sys.exit(1)

    # ── README mode ───────────────────────────────────────────────────
    if args.readme:
        output_path = args.output
        if args.stdout:
            output_path = None
        elif output_path is None:
            output_path = str(root / "README.md")

        content = generate_readme(
            pipeline_path=pipeline_path,
            root=root,
            output_path=output_path,
            engine_root=args.engine_root,
        )
        if args.stdout:
            print(content)
        return

    # ── Original PIPELINE_OVERVIEW mode ───────────────────────────────
    pipeline = load_json(pipeline_path)
    if not pipeline:
        print(f"Error: could not parse pipeline: {pipeline_path}", file=sys.stderr)
        sys.exit(1)

    print(f"Generating docs for pipeline: {pipeline.get('name', 'unknown')}")
    print(f"  Pipeline file: {pipeline_path}")
    print(f"  Root: {root}")

    # Resolve step definitions
    step_defs = resolve_step_definitions(pipeline, root, pipeline_path)
    print(f"  Resolved {len(step_defs)} step definitions")

    # Build all content
    dag_flowchart = build_ascii_dag(pipeline)
    dependency_graph = build_dependency_text(pipeline)
    steps_table = build_steps_table(pipeline, step_defs)
    contracts_table = build_contracts_table(pipeline, step_defs)
    cost_table, total_cost = build_cost_table(pipeline, step_defs)
    validation_gates, checkpoints, fixups = build_quality_controls(pipeline, step_defs)

    # Find template
    if args.template:
        template_path = Path(args.template).resolve()
    else:
        # Search order: local templates, engine templates
        candidates = [
            root / "templates" / "docs" / "PIPELINE_OVERVIEW.md.j2",
            Path(__file__).resolve().parent.parent / "templates" / "docs" / "PIPELINE_OVERVIEW.md.j2",
        ]
        template_path = next((c for c in candidates if c.exists()), candidates[-1])

    print(f"  Template: {template_path}")

    replacements = {
        "pipeline_name": pipeline.get("name", "unnamed"),
        "objective": pipeline.get("description", "(no description)"),
        "dag_flowchart": dag_flowchart,
        "dependency_graph": dependency_graph,
        "steps_table": steps_table,
        "contracts_table": contracts_table,
        "data_dir": pipeline.get("data_dir", "data/"),
        "cost_table": cost_table,
        "total_cost": total_cost,
        "validation_gates": validation_gates,
        "checkpoints": checkpoints,
        "fixups": fixups,
    }

    content = render_overview(template_path, replacements)

    if args.stdout:
        print(content)
        return

    # Write output
    if args.output:
        output_path = Path(args.output).resolve()
    else:
        output_path = root / "docs" / "PIPELINE_OVERVIEW.md"

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")
    print(f"  Written: {output_path}")
    print("Done.")


if __name__ == "__main__":
    main()

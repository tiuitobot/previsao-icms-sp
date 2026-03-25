"""Generic HTML renderer worker.

Renders a Jinja2 template with JSON data into HTML. Supports:
- Template selection via template_path or template_name parameter
- Markdown-to-HTML conversion via |md filter
- Multiple data source resolution (explicit path, output_dir search, context)
- Output to report/ subdirectory

Templates available:
- pages/academic_report.html.j2 — technical/academic reports (serif, justified, numbered sections)
- pages/report.html.j2 — dashboard/audit reports (sidebar, KPIs, finding cards)
- pages/dashboard.html.j2 — dashboards (KPIs, alerts, summary table)
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    from jinja2 import Environment, FileSystemLoader
except ImportError:
    Environment = None  # type: ignore[assignment, misc]
    FileSystemLoader = None  # type: ignore[assignment, misc]

try:
    import markdown as _md_lib
except ImportError:
    _md_lib = None  # type: ignore[assignment]

ROOT = Path(__file__).resolve().parent.parent.parent


def _md_filter(text: str) -> str:
    """Convert markdown to HTML. Falls back to plain text if markdown not installed."""
    if not text:
        return ""
    if _md_lib:
        return _md_lib.markdown(str(text), extensions=["tables", "fenced_code"])
    return f"<p>{text}</p>"


def _find_data_file(output_dir: str, names: list[str]) -> Path | None:
    """Search for a data file in common locations."""
    for name in names:
        for base in [Path(output_dir), Path(output_dir) / "steps", Path(output_dir) / "report"]:
            candidate = base / name
            if candidate.exists():
                return candidate
    return None


def main(
    *,
    output_dir: str = "",
    template_path: str = "",
    template_name: str = "",
    data_path: str = "",
    data_file: str = "report_draft.json",
    **kwargs: Any,
) -> dict:
    """Render HTML from a Jinja2 template and JSON data.

    Parameters
    ----------
    output_dir:
        Pipeline run output directory. Used to find data and write output.
    template_path:
        Full path to template file. If empty, uses template_name.
    template_name:
        Template name relative to templates/ dir (e.g. "pages/academic_report.html.j2").
        Default: "pages/report.html.j2"
    data_path:
        Explicit path to JSON data file. If empty, searches output_dir for data_file.
    data_file:
        Name of the data file to search for in output_dir. Default: "report_draft.json"
    """
    if Environment is None:
        raise ImportError("jinja2 is required — pip install jinja2")

    # Resolve template
    if template_path:
        tmpl_file = Path(template_path)
        templates_dir = tmpl_file.parent
        tmpl_name = tmpl_file.name
    else:
        templates_dir = ROOT / "templates"
        tmpl_name = template_name or "pages/report.html.j2"

    if not templates_dir.is_dir():
        raise FileNotFoundError(f"Templates directory not found: {templates_dir}")

    # Resolve data
    if data_path and Path(data_path).is_file():
        data = json.loads(Path(data_path).read_text(encoding="utf-8"))
    elif output_dir:
        found = _find_data_file(output_dir, [data_file, "report_draft.json", "summary_report.json"])
        if found is None:
            raise FileNotFoundError(f"{data_file} not found in {output_dir}")
        data = json.loads(found.read_text(encoding="utf-8"))
    else:
        raise ValueError("Either data_path or output_dir must be provided")

    # Handle _raw text output (from web_search steps that don't produce JSON)
    if "_raw" in data and len(data) == 1:
        data = {"title": "Report", "sections": [{"title": "Content", "content_markdown": data["_raw"]}]}

    # Setup Jinja2 with markdown filter
    env = Environment(
        loader=FileSystemLoader(str(templates_dir)),
        autoescape=False,
    )
    env.filters["md"] = _md_filter

    template = env.get_template(tmpl_name)
    rendered = template.render(**data)

    # Write to report/ subdir — filename derived from template name or explicit
    report_dir = Path(output_dir) / "report" if output_dir else Path(".")
    report_dir.mkdir(parents=True, exist_ok=True)
    # Derive output filename: pages/academic_report.html.j2 → academic_report.html
    output_filename = kwargs.get("output_filename", "")
    if not output_filename:
        stem = Path(tmpl_name).stem  # "academic_report.html" from .j2
        if stem.endswith(".html"):
            output_filename = stem
        else:
            output_filename = stem + ".html"
    html_path = report_dir / output_filename
    html_path.write_text(rendered, encoding="utf-8")

    return {
        "html_path": str(html_path),
        "rendered_chars": len(rendered),
        "template": tmpl_name,
    }

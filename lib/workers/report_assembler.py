"""Generic report assembler worker.

Reads all JSON files from a run output directory and merges them into a
unified report structure.
"""

from __future__ import annotations

import glob
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def main(*, output_dir: str, **kwargs: Any) -> dict:
    """Assemble a unified report from JSON files in *output_dir*.

    Parameters
    ----------
    output_dir:
        Directory containing per-step JSON output files.

    Returns
    -------
    dict with keys ``title``, ``sections``, ``generated_at``.
    """
    out_path = Path(output_dir)
    if not out_path.is_dir():
        raise FileNotFoundError(f"output_dir does not exist: {output_dir}")

    json_files = sorted(glob.glob(str(out_path / "*.json")))

    sections: list[dict[str, Any]] = []
    for filepath in json_files:
        basename = os.path.basename(filepath)
        with open(filepath, "r", encoding="utf-8") as fh:
            try:
                content = json.load(fh)
            except json.JSONDecodeError:
                content = {"_error": f"Invalid JSON in {basename}"}

        sections.append({
            "source_file": basename,
            "data": content,
        })

    title = kwargs.get("title", "Pipeline Run Report")

    return {
        "title": title,
        "sections": sections,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

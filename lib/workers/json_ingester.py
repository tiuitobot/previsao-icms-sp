"""Generic JSON/CSV ingester worker.

Reads all matching files from a data directory, parses them, and returns
structured output suitable for downstream pipeline steps.
"""

from __future__ import annotations

import csv
import glob
import json
import os
from pathlib import Path
from typing import Any


def main(*, data_dir: str, file_patterns: str = "*.json,*.csv", **kwargs: Any) -> dict:
    """Ingest JSON and CSV files from *data_dir*.

    Parameters
    ----------
    data_dir:
        Directory containing input files.
    file_patterns:
        Comma-separated glob patterns (default ``"*.json,*.csv"``).

    Returns
    -------
    dict with keys ``files``, ``total_files``, ``data`` (filename -> parsed content).
    """
    data_path = Path(data_dir)
    if not data_path.is_dir():
        raise FileNotFoundError(f"data_dir does not exist: {data_dir}")

    patterns = [p.strip() for p in file_patterns.split(",")]

    matched_files: list[str] = []
    for pattern in patterns:
        matched_files.extend(sorted(glob.glob(str(data_path / pattern))))

    # Deduplicate while preserving order
    seen: set[str] = set()
    unique_files: list[str] = []
    for f in matched_files:
        if f not in seen:
            seen.add(f)
            unique_files.append(f)

    data: dict[str, Any] = {}
    file_basenames: list[str] = []

    for filepath in unique_files:
        basename = os.path.basename(filepath)
        file_basenames.append(basename)

        if filepath.endswith(".json"):
            with open(filepath, "r", encoding="utf-8") as fh:
                data[basename] = json.load(fh)
        elif filepath.endswith(".csv"):
            with open(filepath, "r", encoding="utf-8", newline="") as fh:
                reader = csv.DictReader(fh)
                data[basename] = list(reader)
        else:
            # Treat unknown extensions matched by glob as raw text
            with open(filepath, "r", encoding="utf-8") as fh:
                data[basename] = fh.read()

    return {
        "files": file_basenames,
        "total_files": len(file_basenames),
        "data": data,
    }

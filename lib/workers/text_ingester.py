"""Generic text-file ingester worker.

Reads all matching text files from a data directory and returns their
content both individually and as a combined blob.
"""

from __future__ import annotations

import glob
import os
from pathlib import Path
from typing import Any


def main(*, data_dir: str, file_patterns: str = "*.txt,*.md", **kwargs: Any) -> dict:
    """Ingest plain-text files from *data_dir*.

    Parameters
    ----------
    data_dir:
        Directory containing input files.
    file_patterns:
        Comma-separated glob patterns (default ``"*.txt,*.md"``).

    Returns
    -------
    dict with keys ``files``, ``total_files``, ``combined_text``, ``per_file``.
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

    per_file: dict[str, str] = {}
    file_basenames: list[str] = []
    combined_parts: list[str] = []

    for filepath in unique_files:
        basename = os.path.basename(filepath)
        file_basenames.append(basename)

        with open(filepath, "r", encoding="utf-8") as fh:
            content = fh.read()

        per_file[basename] = content
        combined_parts.append(content)

    return {
        "files": file_basenames,
        "total_files": len(file_basenames),
        "combined_text": "\n\n".join(combined_parts),
        "per_file": per_file,
    }

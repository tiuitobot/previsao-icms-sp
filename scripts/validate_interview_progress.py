#!/usr/bin/env python3
# SMOKE-EXEMPT: validation script, runs during intake interview
"""In-flight interview gate — validates findings before phase transitions.

Usage:
    python3 scripts/validate_interview_progress.py --phase 2
    python3 scripts/validate_interview_progress.py --phase 3.5
    python3 scripts/validate_interview_progress.py --phase 4
    python3 scripts/validate_interview_progress.py --phase build

Each phase has cumulative requirements. The script reads
.agent/INTAKE_INTERVIEW.md and checks if the required fields
for that phase are filled.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path.cwd()

PLACEHOLDER_PATTERNS = [
    r"\{[A-Z_]+\}",        # {PLACEHOLDER}
    r"^\(fill\b",           # (fill in) — but not "(filled during"
    r"\bTBD\b",             # TBD as whole word — not "todos"
    r"\bTODO\b",            # TODO as whole word — not "todos"
    r"^\.\.\.\s*$",         # ... alone on a line — not "..." in text
]

# Phase requirements (cumulative)
PHASE_REQUIREMENTS: dict[str, dict] = {
    "2": {
        "label": "Phase 2 (Data Investigation)",
        "required": ["Topic", "Problem", "Expected Output"],
        "message": "Complete Phase 1 before investigating data.",
    },
    "3.5": {
        "label": "Phase 3.5 (Product Summary)",
        "required": ["Topic", "Problem", "Expected Output", "Domain", "Data Sources", "Research Results"],
        "message": "Complete data investigation AND research before presenting product summary.",
    },
    "4": {
        "label": "Phase 4 (Architecture)",
        "required": ["Topic", "Problem", "Expected Output", "Domain", "Audience", "Data Sources", "Research Results", "Output Design"],
        "message": "Complete all discovery phases before designing architecture.",
    },
    "build": {
        "label": "Build",
        "required": ["Topic", "Problem", "Expected Output", "Domain", "Audience", "Success Criteria", "Data Sources", "Research Results", "Output Design"],
        "min_fields": 8,
        "message": "Fill at least 8 of 12 fields before building.",
    },
}


def _is_filled(value: str) -> bool:
    """Check if a field value is actually filled (not placeholder)."""
    v = value.strip()
    # Remove field labels like "Answer:", "domain:", "apis_found:" etc.
    v = re.sub(r"^(?:Answer|domain|subdomain|sources|apis_found|libraries_found|repos_found|methodology|output_type|output_format|template|size|language|dag_type|budget|checkpoints|cadence|notes|steps|architecture_notes|catalog_search_results)\s*:", "", v, flags=re.MULTILINE | re.IGNORECASE).strip()
    if not v or len(v) < 5:
        return False
    for pattern in PLACEHOLDER_PATTERNS:
        if re.search(pattern, v, re.IGNORECASE):
            return False
    return True


def _is_research_filled(value: str) -> bool:
    """Special check for research — must have EXTERNAL research, not just catalog.

    Requires at least 2 of 4 subcampos (apis_found, libraries_found,
    repos_found, methodology) with real content (not 'pending', not just
    catalog worker names).
    """
    # Extract subcampo values
    subcampos = {}
    for key in ("apis_found", "libraries_found", "repos_found", "methodology"):
        m = re.search(rf"^{key}:\s*(.+?)(?=\n\w+:|$)", value, re.MULTILINE | re.DOTALL)
        if m:
            val = m.group(1).strip()
            # Filter out non-answers
            if val and val.lower() not in ("pending", "n/a", "none", "nenhum", "nenhuma"):
                # Filter out catalog-only references (pdf_ingester, hint_sheet_extractor, etc.)
                catalog_only = all(
                    w in val.lower() for w in val.lower().split() if len(w) > 3
                ) if "catalog" in val.lower() or "_" in val else False
                if not catalog_only:
                    subcampos[key] = val

    # Need at least 2 subcampos with real external content
    return len(subcampos) >= 2


def _parse_fields(path: Path) -> dict[str, str]:
    """Extract field values from intake document."""
    content = path.read_text(encoding="utf-8")

    findings_start = content.find("## Findings")
    if findings_start >= 0:
        content = content[findings_start:]

    fields = {}
    current_field = None
    current_value = []

    for line in content.splitlines():
        header_match = re.match(r"^##\s+(?:\d+\.\s+)?(\w[\w\s]*?)(?:\s*\[.*\])?\s*$", line)
        if header_match:
            if current_field:
                fields[current_field] = "\n".join(current_value).strip()
            current_field = header_match.group(1).strip()
            current_value = []
        elif current_field:
            current_value.append(line)

    if current_field:
        fields[current_field] = "\n".join(current_value).strip()

    return fields


def validate(phase: str) -> int:
    """Validate interview progress for a given phase. Returns 0 if OK, 1 if blocked."""
    req = PHASE_REQUIREMENTS.get(phase)
    if not req:
        print(f"Unknown phase: {phase}. Valid: {', '.join(PHASE_REQUIREMENTS.keys())}")
        return 1

    intake_path = ROOT / ".agent" / "INTAKE_INTERVIEW.md"
    if not intake_path.exists():
        print(f"BLOCKED — {req['label']}: .agent/INTAKE_INTERVIEW.md not found.")
        print("  Start the interview and fill findings as you go.")
        return 1

    fields = _parse_fields(intake_path)

    missing = []
    unfilled = []

    for field_name in req["required"]:
        found = False
        for fn, fv in fields.items():
            if field_name.lower() in fn.lower():
                found = True
                # Special handling for Research
                if "research" in field_name.lower():
                    if not _is_research_filled(fv):
                        unfilled.append(field_name)
                elif not _is_filled(fv):
                    unfilled.append(field_name)
                break
        if not found:
            missing.append(field_name)

    if missing or unfilled:
        print(f"BLOCKED — {req['label']}")
        if missing:
            print(f"  Missing fields: {', '.join(missing)}")
        if unfilled:
            print(f"  Empty fields: {', '.join(unfilled)}")
        print(f"  {req['message']}")
        print(f"  Fill these in .agent/INTAKE_INTERVIEW.md before proceeding.")
        return 1

    # Check minimum field count for build phase
    min_fields = req.get("min_fields", 0)
    if min_fields:
        filled_count = sum(
            1 for fn, fv in fields.items()
            if _is_filled(fv) and fn.lower() not in ("findings",)
        )
        if filled_count < min_fields:
            print(f"BLOCKED — {req['label']}: only {filled_count} fields filled, need {min_fields}.")
            return 1

    print(f"OK — {req['label']}: all required fields filled. Proceed.")
    return 0


def main():
    parser = argparse.ArgumentParser(description="Validate interview progress before phase transition")
    parser.add_argument("--phase", required=True, choices=list(PHASE_REQUIREMENTS.keys()),
                        help="Phase to validate readiness for")
    args = parser.parse_args()
    return validate(args.phase)


if __name__ == "__main__":
    raise SystemExit(main())

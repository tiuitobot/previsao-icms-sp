# SMOKE-EXEMPT: library worker, runs inside pipeline runner
"""Regression Tracker — compare current run findings against prior run.

Flags findings that disappeared, changed severity, or were added.
Deterministic, $0.

Args:
    output_dir: current run output directory
    prior_run_dir: explicit prior run path (optional, uses latest symlink)
    findings_file: name of findings JSON to compare (default: auto-detect)
"""

from __future__ import annotations

import json
from difflib import SequenceMatcher
from pathlib import Path


def _find_prior_run(output_dir: Path) -> Path | None:
    """Find the latest successful prior run."""
    runs_dir = output_dir.parent
    latest = runs_dir / "latest"
    if latest.is_symlink() or latest.exists():
        target = latest.resolve()
        if target != output_dir.resolve():
            return target

    # Fallback: find most recent success/ entry that's not current
    success_dir = runs_dir / "success"
    if success_dir.exists():
        for entry in sorted(success_dir.iterdir(), reverse=True):
            resolved = entry.resolve()
            if resolved != output_dir.resolve():
                return resolved
    return None


def _find_findings_file(run_dir: Path) -> Path | None:
    """Auto-detect the main findings file in a run."""
    candidates = [
        "consolidated_findings.json",
        "classifier.json",
        "report_synthesizer.json",
        "risk_analyst.json",
        "risk_reviewer.json",
    ]
    for name in candidates:
        f = run_dir / name
        if f.exists():
            return f
    return None


def _extract_findings(data: dict) -> list[dict]:
    """Extract finding list from various output formats."""
    for key in ("findings", "riscos", "finding_cards", "clausulas", "verificacoes"):
        if key in data and isinstance(data[key], list):
            return data[key]
    return []


def _finding_id(f: dict) -> str:
    """Get finding identifier."""
    return f.get("id", f.get("clausula_ref", f.get("numero", f.get("norma", ""))))


def _finding_title(f: dict) -> str:
    """Get finding title for matching."""
    return f.get("title", f.get("titulo", f.get("descricao", f.get("resumo", ""))))


def _similarity(a: str, b: str) -> float:
    """Simple string similarity."""
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def main(output_dir: str = "", prior_run_dir: str = "", findings_file: str = "") -> dict:
    """Compare current findings against prior run."""
    od = Path(output_dir) if output_dir else Path(".")

    # Find prior run
    if prior_run_dir:
        prior = Path(prior_run_dir)
    else:
        prior = _find_prior_run(od)

    if not prior or not prior.exists():
        return {
            "status": "ok",
            "message": "No prior run found for comparison",
            "regressions": [],
            "new_findings": [],
        }

    # Find findings files
    if findings_file:
        current_file = od / findings_file
        prior_file = prior / findings_file
    else:
        current_file = _find_findings_file(od)
        if current_file:
            prior_file = prior / current_file.name
        else:
            return {"status": "ok", "message": "No findings file found in current run"}

    if not current_file or not current_file.exists():
        return {"status": "ok", "message": "Current findings file not found"}
    if not prior_file or not prior_file.exists():
        return {"status": "ok", "message": f"Prior findings file not found: {prior_file}"}

    current_data = json.loads(current_file.read_text())
    prior_data = json.loads(prior_file.read_text())

    current_findings = _extract_findings(current_data)
    prior_findings = _extract_findings(prior_data)

    # Match findings
    regressions = []  # in prior but not in current
    new_findings = []  # in current but not in prior
    severity_changes = []
    matched_current = set()

    for pf in prior_findings:
        pid = _finding_id(pf)
        ptitle = _finding_title(pf)
        psev = pf.get("severidade", pf.get("severity", ""))

        # Try ID match
        found = False
        for i, cf in enumerate(current_findings):
            cid = _finding_id(cf)
            if cid and cid == pid:
                matched_current.add(i)
                csev = cf.get("severidade", cf.get("severity", ""))
                if csev != psev and psev and csev:
                    severity_changes.append({
                        "id": pid,
                        "title": ptitle[:80],
                        "prior_severity": psev,
                        "current_severity": csev,
                    })
                found = True
                break

        if not found and ptitle:
            # Fuzzy title match
            for i, cf in enumerate(current_findings):
                if i in matched_current:
                    continue
                ctitle = _finding_title(cf)
                if _similarity(ptitle, ctitle) > 0.7:
                    matched_current.add(i)
                    found = True
                    break

        if not found:
            regressions.append({
                "id": pid,
                "title": ptitle[:80],
                "severity": psev,
                "message": "Finding from prior run disappeared",
            })

    # New findings (in current but not matched)
    for i, cf in enumerate(current_findings):
        if i not in matched_current:
            new_findings.append({
                "id": _finding_id(cf),
                "title": _finding_title(cf)[:80],
                "severity": cf.get("severidade", cf.get("severity", "")),
            })

    return {
        "status": "ok",
        "prior_run": str(prior),
        "current_findings_count": len(current_findings),
        "prior_findings_count": len(prior_findings),
        "regressions": regressions,
        "new_findings": new_findings,
        "severity_changes": severity_changes,
        "stable_findings": len(matched_current) - len(severity_changes),
    }

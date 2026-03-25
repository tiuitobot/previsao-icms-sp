# SMOKE-EXEMPT: library worker, runs inside pipeline runner
"""Cross Validate — check LLM outputs against hint_sheet extracted data.

Standard worker: compares LLM-generated values against deterministic
extraction. Flags discrepancies.

Args (from pipeline step):
    output_dir: run output directory (reads upstream JSONs)
"""

from __future__ import annotations

import json
import re
from pathlib import Path


def _load(output_dir: Path, name: str) -> dict:
    f = output_dir / f"{name}.json"
    if f.exists():
        try:
            return json.loads(f.read_text())
        except json.JSONDecodeError:
            return {}
    return {}


def _normalize_money(raw: str) -> float | None:
    """Parse R$ 1.234,56 → 1234.56"""
    clean = re.sub(r"[R$\s]", "", raw).replace(".", "").replace(",", ".")
    try:
        return float(clean)
    except ValueError:
        return None


def main(output_dir: str = "") -> dict:
    """Cross-validate LLM outputs against hint_sheet."""
    od = Path(output_dir) if output_dir else Path(".")

    hint = _load(od, "hint_sheet_extractor")
    discrepancies: list[dict] = []

    # Discover all LLM output files (anything not in the known deterministic set)
    deterministic = {"pdf_ingester", "hint_sheet_extractor", "cross_validate",
                     "html_renderer", "html_quality_checker", "manifest", "run_state",
                     "run_metadata", "quality_report"}
    llm_outputs: dict[str, dict] = {}
    for f in od.glob("*.json"):
        name = f.stem
        if name not in deterministic and not name.startswith("_"):
            try:
                llm_outputs[name] = json.loads(f.read_text())
            except json.JSONDecodeError:
                pass

    # Check 1: Monetary values — LLM mentions vs hint_sheet extraction
    hint_money_raw = {v.get("raw", "") for v in hint.get("monetary_values", [])}
    hint_money_values = set()
    for v in hint.get("monetary_values", []):
        parsed = _normalize_money(v.get("raw", ""))
        if parsed:
            hint_money_values.add(parsed)

    for name, data in llm_outputs.items():
        text = json.dumps(data, ensure_ascii=False)
        # Find R$ patterns in LLM output
        for m in re.finditer(r"R\$\s*[\d\.]+,\d{2}", text):
            parsed = _normalize_money(m.group(0))
            if parsed and parsed > 100 and parsed not in hint_money_values:
                discrepancies.append({
                    "type": "money_not_in_source",
                    "detail": f"{name}: {m.group(0)} not found in hint_sheet extraction",
                    "severity": "medium",
                    "source": name,
                })

    # Check 2: Dates — LLM mentions vs hint_sheet
    hint_dates = {d.get("date", "") for d in hint.get("dates", [])}
    for name, data in llm_outputs.items():
        text = json.dumps(data, ensure_ascii=False)
        for m in re.finditer(r"\b(\d{4})-(\d{2})-(\d{2})\b", text):
            date_str = m.group(0)
            if date_str not in hint_dates and date_str != "2026-03-24":  # exclude today
                discrepancies.append({
                    "type": "date_not_in_source",
                    "detail": f"{name}: date {date_str} not in hint_sheet",
                    "severity": "low",
                    "source": name,
                })

    # Check 3: Party documents (CPF/CNPJ) referenced by LLM vs hint_sheet
    hint_docs = {d.get("number", "") for d in hint.get("cpf_cnpj", [])}
    for name, data in llm_outputs.items():
        text = json.dumps(data, ensure_ascii=False)
        for m in re.finditer(r"\b\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}\b", text):
            if m.group(0) not in hint_docs:
                discrepancies.append({
                    "type": "cnpj_not_in_source",
                    "detail": f"{name}: CNPJ {m.group(0)} not in hint_sheet",
                    "severity": "high",
                    "source": name,
                })
        for m in re.finditer(r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b", text):
            if m.group(0) not in hint_docs:
                discrepancies.append({
                    "type": "cpf_not_in_source",
                    "detail": f"{name}: CPF {m.group(0)} not in hint_sheet",
                    "severity": "high",
                    "source": name,
                })

    # Check 4: Clause count consistency (if clause analyst exists)
    for name in ("clause_analyst", "clause_mapper", "clause_risk_analyzer"):
        if name in llm_outputs:
            data = llm_outputs[name]
            claimed = data.get("total_clausulas", 0)
            actual = len(data.get("clausulas", []))
            if claimed and claimed != actual:
                discrepancies.append({
                    "type": "count_mismatch",
                    "detail": f"{name}: claims {claimed} clauses but lists {actual}",
                    "severity": "low",
                })
            break

    # Check 5: Risk references valid clauses
    clause_data = llm_outputs.get("clause_analyst", llm_outputs.get("clause_mapper", {}))
    clause_nums = {c.get("numero", "") for c in clause_data.get("clausulas", [])}
    for name in ("risk_analyst", "risk_reviewer", "risk_assessor"):
        if name in llm_outputs:
            for r in llm_outputs[name].get("riscos", []):
                ref = r.get("clausula_ref", "")
                if ref and clause_nums and ref not in clause_nums:
                    discrepancies.append({
                        "type": "invalid_clause_ref",
                        "detail": f"{name}: risk references clause '{ref}' not in clause map",
                        "severity": "high",
                    })

    # Deduplicate
    seen: set[str] = set()
    unique: list[dict] = []
    for d in discrepancies:
        sig = json.dumps(d, sort_keys=True)
        if sig not in seen:
            seen.add(sig)
            unique.append(d)

    return {
        "status": "ok",
        "total_discrepancies": len(unique),
        "by_severity": {
            s: sum(1 for d in unique if d.get("severity") == s)
            for s in ("high", "medium", "low")
        },
        "discrepancies": unique,
        "hint_sheet_stats": hint.get("meta", {}),
    }

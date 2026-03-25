# SMOKE-EXEMPT: library worker, runs inside pipeline runner
"""Hint Sheet Extractor — regex extraction of structured signals from text.

Standard worker: extracts dates, monetary values, percentages, persons,
CPF/CNPJ, OAB, legal references from contract/legal text.

Args (from pipeline step):
    output_dir: run output directory (reads pdf_ingester.json from here)
"""

from __future__ import annotations

import json
import re
from pathlib import Path

DATE_RE = re.compile(r"\b(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})\b")
MONEY_RE = re.compile(r"R\$\s*[\d\.]+,\d{2}", re.IGNORECASE)
PERCENT_RE = re.compile(r"\b\d{1,3}[,\.]\d{1,4}\s*%", re.IGNORECASE)
CPF_RE = re.compile(r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b")
CNPJ_RE = re.compile(r"\b\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}\b")
OAB_RE = re.compile(r"\bOAB(?:/[A-Z]{2})?\s*\d{1,3}(?:\.\d{3}){0,2}\b", re.IGNORECASE)
LEGAL_RE = re.compile(r"\b(?:arts?\.?\s*\d+|Lei\s+n[ºo°]?\s*[\d\./-]+)\b", re.IGNORECASE)
PERSON_RE = re.compile(
    r"\b(?:Dr\.?|Dra\.?|Sr\.?|Sra\.?)\s+"
    r"([A-ZÁÉÍÓÚÂÊÔÃÕÇ][A-Za-zÁÉÍÓÚÂÊÔÃÕÇáéíóúâêôãõç']+"
    r"(?:\s+(?:[A-ZÁÉÍÓÚÂÊÔÃÕÇ][A-Za-zÁÉÍÓÚÂÊÔÃÕÇáéíóúâêôãõç']+|da|de|do|das|dos)){1,6})",
)


def _ctx(text: str, start: int, end: int, radius: int = 80) -> str:
    return " ".join(text[max(0, start - radius):min(len(text), end + radius)].split())


def main(output_dir: str = "") -> dict:
    """Extract structured signals from upstream pdf_ingester output."""
    text = ""
    if output_dir:
        f = Path(output_dir) / "pdf_ingester.json"
        if f.exists():
            text = json.loads(f.read_text()).get("text", "")
    if not text:
        return {"status": "error", "message": "No text from pdf_ingester"}

    r: dict[str, list] = {
        "dates": [], "monetary_values": [], "percentages": [],
        "persons": [], "cpf_cnpj": [], "oab_numbers": [], "legal_references": [],
    }

    for m in DATE_RE.finditer(text):
        try:
            r["dates"].append({
                "date": f"{m.group(3)}-{int(m.group(2)):02d}-{int(m.group(1)):02d}",
                "context": _ctx(text, m.start(), m.end()),
            })
        except ValueError:
            pass

    for m in MONEY_RE.finditer(text):
        r["monetary_values"].append({"raw": m.group(0), "context": _ctx(text, m.start(), m.end())})
    for m in PERCENT_RE.finditer(text):
        r["percentages"].append({"raw": m.group(0), "context": _ctx(text, m.start(), m.end())})
    for m in CPF_RE.finditer(text):
        r["cpf_cnpj"].append({"type": "CPF", "number": m.group(0)})
    for m in CNPJ_RE.finditer(text):
        r["cpf_cnpj"].append({"type": "CNPJ", "number": m.group(0)})
    for m in OAB_RE.finditer(text):
        r["oab_numbers"].append({"oab": m.group(0)})
    for m in LEGAL_RE.finditer(text):
        r["legal_references"].append({"reference": m.group(0), "context": _ctx(text, m.start(), m.end())})

    seen: set[str] = set()
    for m in PERSON_RE.finditer(text):
        name = m.group(1).strip()
        if name not in seen:
            seen.add(name)
            r["persons"].append({"name": name, "context": _ctx(text, m.start(), m.end())})

    r["meta"] = {k: len(v) for k, v in r.items() if k != "meta"}
    r["status"] = "ok"
    return r

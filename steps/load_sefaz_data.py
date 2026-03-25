"""Load ICMS-SP historical data from SEFAZ Excel."""
import json
import openpyxl
from pathlib import Path
from datetime import datetime


def main(*, output_dir: str = "", data_dir: str = "", sefaz_file: str = "dados_sefaz.xlsx", **kwargs) -> dict:
    """Load SEFAZ Excel and extract ICMS-SP series."""
    od = Path(output_dir)

    # Resolve sefaz file path
    resolved = None
    for base in [Path(data_dir), Path("data"), Path(".")]:
        candidate = base / sefaz_file
        if candidate.exists():
            resolved = str(candidate)
            break
    if resolved is None:
        resolved = str(Path(data_dir) / sefaz_file)

    wb = openpyxl.load_workbook(resolved, data_only=True)
    ws = wb.active

    icms_records = []
    for row in ws.iter_rows(min_row=2, values_only=True):
        if row[0] and isinstance(row[0], datetime) and row[1] is not None:
            icms_records.append({
                "data": row[0].strftime("%Y-%m-%d"),
                "icms_sp": float(row[1])
            })

    last_date = icms_records[-1]["data"] if icms_records else None

    result = {
        "icms_sp_series": icms_records,
        "last_observed_date": last_date,
        "n_observations": len(icms_records),
        "status": "ok"
    }

    out_file = od / "load_sefaz_data.json"
    out_file.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    return result

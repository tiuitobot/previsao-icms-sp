"""Fetch macro data from BCB SGS (IBC-BR), IPEA (IGP-DI), and Focus expectations."""
import json
import requests
import pandas as pd
from pathlib import Path
from datetime import datetime


def main(*, output_dir: str = "", **kwargs) -> dict:
    """Fetch all macro data from public APIs."""
    od = Path(output_dir)

    # 1. IBC-BR from BCB SGS
    ibc_url = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.24363/dados?formato=json"
    resp = requests.get(ibc_url, timeout=30)
    resp.raise_for_status()
    ibc_raw = resp.json()
    ibc_records = []
    for r in ibc_raw:
        ibc_records.append({
            "data": pd.to_datetime(r["data"], format="%d/%m/%Y").strftime("%Y-%m-%d"),
            "ibc_br": float(r["valor"])
        })

    # 2. IGP-DI from IPEA
    igp_url = "http://www.ipeadata.gov.br/api/odata4/ValoresSerie(SERCODIGO='IGP12_IGPDI12')"
    resp = requests.get(igp_url, timeout=30)
    resp.raise_for_status()
    igp_raw = resp.json()["value"]
    igp_records = []
    for r in igp_raw:
        dt = r["VALDATA"][:10]
        if dt >= "2003-01-01":
            igp_records.append({"data": dt, "igp_di": float(r["VALVALOR"])})

    # 3. Focus expectations from BCB Olinda — current year AND next year
    current_year = datetime.now().year
    focus_expectations = {}
    focus_by_year = {}
    focus_survey_date = None

    for ref_year in [current_year, current_year + 1]:
        focus_url = (
            f"https://olinda.bcb.gov.br/olinda/servico/Expectativas/versao/v1/odata/"
            f"ExpectativasMercadoAnuais?$filter=DataReferencia%20eq%20'{ref_year}'"
            f"&$orderby=Data%20desc&$top=100&$format=json"
        )
        try:
            resp = requests.get(focus_url, timeout=30)
            resp.raise_for_status()
            focus_raw = resp.json()["value"]
            focus_df = pd.DataFrame(focus_raw)

            year_data = {}
            for indicator in ["PIB Total", "IGP-M", "IPCA", "Selic"]:
                match = focus_df[focus_df["Indicador"] == indicator]
                if len(match) > 0:
                    year_data[indicator] = float(match.iloc[0]["Mediana"])
                    # Capture survey date from the most recent entry
                    if focus_survey_date is None and "Data" in match.columns:
                        focus_survey_date = str(match.iloc[0]["Data"])[:10]

            if year_data:
                focus_by_year[str(ref_year)] = year_data
                # Backward compat: flat dict uses current year values
                if ref_year == current_year:
                    focus_expectations = dict(year_data)
        except Exception:
            pass

    result = {
        "ibc_br": ibc_records,
        "igp_di": igp_records,
        "focus_expectations": focus_expectations,
        "focus_by_year": focus_by_year,
        "data_freshness": {
            "ibc_br_last": ibc_records[-1]["data"] if ibc_records else None,
            "igp_di_last": igp_records[-1]["data"] if igp_records else None,
            "focus_survey_date": focus_survey_date,
            "focus_reference_years": list(focus_by_year.keys()),
        },
        "status": "ok"
    }

    # Save to disk
    out_file = od / "fetch_macro_data.json"
    out_file.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    return result

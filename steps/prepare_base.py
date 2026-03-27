"""Prepare consolidated base: merge macro + SEFAZ, create lags, dummies, projections."""
import json
import numpy as np
import pandas as pd
from pathlib import Path
from calendar import monthrange
from datetime import datetime


def _dias_uteis(ano, mes):
    """Calculate business days in a month."""
    dias_total = monthrange(ano, mes)[1]
    return sum(1 for dia in range(1, dias_total + 1)
               if datetime(ano, mes, dia).weekday() < 5)


def _load(od: Path, name: str) -> dict:
    f = od / f"{name}.json"
    return json.loads(f.read_text()) if f.exists() else {}


def main(*, output_dir: str = "", **kwargs) -> dict:
    """Build consolidated base with features."""
    od = Path(output_dir)

    # Get upstream data from disk
    macro = _load(od, "fetch_macro_data")
    sefaz = _load(od, "load_sefaz_data")

    # Default scenario params (interpreter removed — use defaults)
    pib_override = None
    inflation_override = None

    # Dynamic horizon: forecast rest of current year + next year
    # Determine from ICMS data when available, else use current year
    icms_series = sefaz.get("icms_sp_series", [])
    if icms_series:
        last_icms_year = int(icms_series[-1]["data"][:4])
    else:
        last_icms_year = datetime.now().year
    horizon_end = last_icms_year + 1

    # Build date range
    dates = pd.date_range(start="2003-01-01", end=f"{horizon_end}-12-01", freq="MS")
    df = pd.DataFrame({"data": dates})
    df["ano"] = df["data"].dt.year
    df["mes"] = df["data"].dt.month

    # Merge IBC-BR
    ibc_df = pd.DataFrame(macro.get("ibc_br", []))
    if len(ibc_df) > 0:
        ibc_df["data"] = pd.to_datetime(ibc_df["data"])
        df = df.merge(ibc_df, on="data", how="left")
    else:
        df["ibc_br"] = np.nan

    # Merge IGP-DI
    igp_df = pd.DataFrame(macro.get("igp_di", []))
    if len(igp_df) > 0:
        igp_df["data"] = pd.to_datetime(igp_df["data"])
        df = df.merge(igp_df, on="data", how="left")
    else:
        df["igp_di"] = np.nan

    # Merge ICMS-SP
    icms_df = pd.DataFrame(sefaz.get("icms_sp_series", []))
    if len(icms_df) > 0:
        icms_df["data"] = pd.to_datetime(icms_df["data"])
        df = df.merge(icms_df, on="data", how="left")
    else:
        df["icms_sp"] = np.nan

    # Business days
    df["dias_uteis"] = df.apply(lambda x: _dias_uteis(int(x["ano"]), int(x["mes"])), axis=1)

    # Structural dummies (from original model)
    df["LS2008NOV"] = (((df["ano"] == 2008) & (df["mes"] >= 11)) | (df["ano"] > 2008)).astype(int)
    df["TC2020APR04"] = ((df["ano"] == 2020) & (df["mes"] >= 4) & (df["mes"] <= 7)).astype(int)
    df["TC2022OUT05"] = (((df["ano"] == 2022) & (df["mes"] >= 10)) |
                          ((df["ano"] == 2023) & (df["mes"] <= 5))).astype(int)

    # Lags
    for col in ["ibc_br", "igp_di", "dias_uteis"]:
        if col in df.columns:
            for lag in range(1, 5):
                df[f"{col}_lag{lag}"] = df[col].shift(lag)

    # Seasonal lag: log(ICMS) at t-12 for M' models (subset AR at lag 12)
    if df["icms_sp"].notna().any():
        df["log_icms_lag12"] = np.log(df["icms_sp"]).shift(12)

    # Forward projection for IBC-BR using Focus/PIB + seasonal profile
    focus = macro.get("focus_expectations", {})
    pib_growth = float(pib_override) / 100 if pib_override else (focus.get("PIB Total", 2.5) / 100)

    last_ibc_date = df.loc[df["ibc_br"].notna(), "data"].iloc[-1]

    # Build seasonal profile from last 5 complete years of observed IBC-BR
    last_obs_year = last_ibc_date.year
    seasonal_years = range(last_obs_year - 5, last_obs_year)
    seasonal_factors = np.ones(12)
    year_profiles = []
    for yr in seasonal_years:
        yr_data = df[(df["ano"] == yr) & df["ibc_br"].notna()]
        if len(yr_data) == 12:
            yr_mean = yr_data["ibc_br"].mean()
            if yr_mean > 0:
                year_profiles.append(yr_data["ibc_br"].values / yr_mean)
    if year_profiles:
        seasonal_factors = np.mean(year_profiles, axis=0)

    # Calibrate projection level: target annual mean = last_full_year_mean × (1 + growth)
    # Use last full year of observed data as base level
    last_full_year = df[(df["ano"] == last_obs_year - 1) & df["ibc_br"].notna()]
    if len(last_full_year) == 12:
        base_annual_mean = last_full_year["ibc_br"].mean()
    else:
        base_annual_mean = df.loc[df["ibc_br"].notna(), "ibc_br"].tail(12).mean()

    # Project each future month: trend × seasonal factor
    future_mask = (df["data"] > last_ibc_date) & df["ibc_br"].isna()
    for idx in df[future_mask].index:
        row = df.loc[idx]
        years_ahead = row["ano"] - (last_obs_year - 1)
        target_annual_mean = base_annual_mean * ((1 + pib_growth) ** years_ahead)
        month_idx = int(row["mes"]) - 1
        df.loc[idx, "ibc_br"] = target_annual_mean * seasonal_factors[month_idx]

    # Forward projection for IGP-DI — calibrate to Focus annual target (dec-to-dec)
    igpm_growth = float(inflation_override) / 100 if inflation_override else (focus.get("IGP-M", 5.0) / 100)

    last_igp = df.loc[df["igp_di"].notna(), "igp_di"].iloc[-1] if df["igp_di"].notna().any() else 100.0
    last_igp_date = df.loc[df["igp_di"].notna(), "data"].iloc[-1]

    # Find Dec of previous year as reference for annual inflation target
    last_obs_year_igp = last_igp_date.year
    dec_prev_mask = (df["ano"] == last_obs_year_igp - 1) & (df["mes"] == 12) & df["igp_di"].notna()
    if dec_prev_mask.any():
        igp_dec_prev = float(df.loc[dec_prev_mask, "igp_di"].iloc[0])
    else:
        igp_dec_prev = last_igp / (1 + igpm_growth)

    # Target: IGP-DI(Dec current year) = IGP-DI(Dec prev year) × (1 + Focus)
    igp_dec_target = igp_dec_prev * (1 + igpm_growth)

    # How many months from last observed to Dec of the target year?
    target_dec = pd.Timestamp(f"{last_obs_year_igp}-12-01")
    if last_igp_date >= target_dec:
        # Already past Dec → target next year's Dec
        target_dec = pd.Timestamp(f"{last_obs_year_igp + 1}-12-01")
        igp_dec_target = igp_dec_prev * ((1 + igpm_growth) ** 2)

    months_to_dec = max(1, (target_dec.year - last_igp_date.year) * 12 + (target_dec.month - last_igp_date.month))
    # Solve for monthly rate: last_igp × (1+r)^months = igp_dec_target
    calibrated_monthly = (igp_dec_target / last_igp) ** (1 / months_to_dec) - 1

    future_mask_igp = (df["data"] > last_igp_date) & df["igp_di"].isna()
    for i, idx in enumerate(df[future_mask_igp].index):
        row = df.loc[idx]
        months_from_last = (row["ano"] - last_igp_date.year) * 12 + (row["mes"] - last_igp_date.month)
        df.loc[idx, "igp_di"] = last_igp * ((1 + calibrated_monthly) ** months_from_last)

    # Recalculate lags after projection fill
    for col in ["ibc_br", "igp_di"]:
        for lag in range(1, 5):
            df[f"{col}_lag{lag}"] = df[col].shift(lag)

    # Split train/future
    last_icms_date = df.loc[df["icms_sp"].notna(), "data"].max() if df["icms_sp"].notna().any() else pd.Timestamp("2024-01-01")
    train = df[df["data"] <= last_icms_date].copy()
    future = df[df["data"] > last_icms_date].copy()

    # Convert to serializable format
    def df_to_records(frame):
        frame = frame.copy()
        frame["data"] = frame["data"].dt.strftime("%Y-%m-%d")
        return frame.replace({np.nan: None}).to_dict(orient="records")

    result = {
        "base_data": df_to_records(df),
        "train_data": df_to_records(train),
        "future_data": df_to_records(future),
        "n_columns": len(df.columns),
        "n_rows": len(df),
        "horizon_end": horizon_end,
        "scenario_params": {
            "pib_growth_pct": round(pib_growth * 100, 2),
            "igpm_growth_pct": round(igpm_growth * 100, 2),
            "source": "Focus consensus" if not pib_override else "user override",
        },
        "status": "ok"
    }

    out_file = od / "prepare_base.json"
    out_file.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    return result

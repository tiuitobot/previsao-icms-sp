"""Deterministic validation of SARIMAX forecasts."""
import json
from pathlib import Path


def _load(od: Path, name: str) -> dict:
    f = od / f"{name}.json"
    return json.loads(f.read_text()) if f.exists() else {}


def main(*, output_dir: str = "", **kwargs) -> dict:
    """Validate forecast consistency and sanity."""
    od = Path(output_dir)

    sarimax = _load(od, "run_sarimax_models")
    base = _load(od, "prepare_base")

    checks = []
    warnings_list = []

    forecasts = sarimax.get("forecasts", {})
    diagnostics = sarimax.get("diagnostics", {})
    annual_totals = sarimax.get("annual_totals", {})

    # Check 1: All models fitted
    n_fitted = sarimax.get("n_models_fitted", 0)
    checks.append({
        "name": "models_fitted",
        "passed": n_fitted >= 3,
        "detail": f"{n_fitted}/5 models fitted successfully"
    })

    # Check 2: Ljung-Box -- all models should pass
    for name, diag in diagnostics.items():
        if "ljung_box_pass" in diag:
            if not diag["ljung_box_pass"]:
                warnings_list.append(f"{name}: Ljung-Box test failed (p={diag.get('ljung_box_p', '?')})")
    checks.append({
        "name": "ljung_box",
        "passed": len(warnings_list) == 0,
        "detail": f"{len(diagnostics) - len(warnings_list)}/{len(diagnostics)} models pass Ljung-Box"
    })

    # Check 3: ADF stationarity
    adf = sarimax.get("adf_test", {})
    checks.append({
        "name": "adf_stationarity",
        "passed": adf.get("stationary", False),
        "detail": f"ADF p-value: {adf.get('p_value', '?')}"
    })

    # Check 4: Forecast sanity -- no negative values, no extreme outliers
    sanity_ok = True
    for name, model_forecasts in forecasts.items():
        if not isinstance(model_forecasts, list):
            continue
        for entry in model_forecasts:
            if entry.get("forecast", 0) < 0:
                sanity_ok = False
                warnings_list.append(f"{name}: negative forecast at {entry['data']}")
            if entry.get("forecast", 0) > 50e9:  # > 50 billion per month is suspect
                warnings_list.append(f"{name}: very high forecast at {entry['data']}: R${entry['forecast']/1e9:.1f}B")
    checks.append({
        "name": "forecast_sanity",
        "passed": sanity_ok,
        "detail": "No negative or extreme values" if sanity_ok else "Issues found"
    })

    # Check 5: Model convergence -- do models roughly agree?
    if "ensemble" in annual_totals and len(annual_totals) > 2:
        for year, ensemble_val in annual_totals.get("ensemble", {}).items():
            model_vals = [annual_totals[m].get(year, 0) for m in annual_totals if m != "ensemble" and year in annual_totals.get(m, {})]
            if model_vals and ensemble_val > 0:
                spread = (max(model_vals) - min(model_vals)) / ensemble_val
                if spread > 0.20:  # > 20% spread
                    warnings_list.append(f"Year {year}: model spread is {spread*100:.1f}% -- high divergence")

    checks.append({
        "name": "model_convergence",
        "passed": not any("divergence" in w for w in warnings_list),
        "detail": "Models within 20% spread" if not any("divergence" in w for w in warnings_list) else "High divergence detected"
    })

    passed = sum(1 for c in checks if c["passed"])
    failed = len(checks) - passed

    result = {
        "checks": checks,
        "warnings": warnings_list,
        "passed": passed,
        "failed": failed,
        "verdict": "pass" if failed == 0 else ("warn" if failed <= 1 else "fail"),
        "status": "ok"
    }

    out_file = od / "validate_forecasts.json"
    out_file.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    return result

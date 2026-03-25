"""Fit 5 SARIMAX models, produce forecasts and diagnostics."""
import json
import numpy as np
import pandas as pd
from pathlib import Path
import warnings
warnings.filterwarnings("ignore")

from statsmodels.tsa.statespace.sarimax import SARIMAX
from statsmodels.stats.diagnostic import acorr_ljungbox
from statsmodels.tsa.stattools import adfuller


def _to_python(obj):
    """Convert numpy types to Python native for JSON serialization."""
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    return obj


class _NumpyEncoder(json.JSONEncoder):
    """JSON encoder that handles numpy types."""
    def default(self, obj):
        val = _to_python(obj)
        if val is not obj:
            return val
        return super().default(obj)


# Model specifications from the original Rmd
MODEL_SPECS = {
    "Modelo 1": {
        "order": (1, 1, 1),
        "seasonal_order": (0, 0, 0, 12),
        "exog_cols": ["dias_uteis", "LS2008NOV", "TC2020APR04", "TC2022OUT05"],
        "description": "SARIMA(1,1,1) + Dummies"
    },
    "Modelo 2": {
        "order": (3, 1, 0),
        "seasonal_order": (2, 0, 0, 12),
        "exog_cols": ["igp_di_lag1", "ibc_br_lag1", "dias_uteis", "LS2008NOV", "TC2020APR04", "TC2022OUT05"],
        "description": "SARIMAX(3,1,0)(2,0,0) + IGP-DI/IBC-BR lag1"
    },
    "Modelo 3": {
        "order": (0, 1, 1),
        "seasonal_order": (0, 1, 1, 12),
        "exog_cols": ["igp_di", "ibc_br", "ibc_br_lag1", "dias_uteis", "LS2008NOV", "TC2020APR04", "TC2022OUT05"],
        "description": "SARIMAX(0,1,1)(0,1,1) + IGP-DI/IBC-BR"
    },
    "Modelo 4": {
        "order": (0, 1, 1),
        "seasonal_order": (0, 1, 2, 12),
        "exog_cols": ["ibc_br", "ibc_br_lag1", "dias_uteis", "LS2008NOV", "TC2020APR04", "TC2022OUT05"],
        "description": "SARIMAX(0,1,1)(0,1,2) + IBC-BR (sem inflacao)"
    },
    "Modelo 5": {
        "order": (0, 1, 1),
        "seasonal_order": (0, 1, 2, 12),
        "exog_cols": ["igp_di", "ibc_br", "ibc_br_lag1", "LS2008NOV", "TC2020APR04", "TC2022OUT05"],
        "description": "SARIMAX(0,1,1)(0,1,2) + IGP-DI/IBC-BR (sem dias uteis)"
    }
}


def _fit_model(y, X, order, seasonal_order):
    """Fit a single SARIMAX model.

    Instead of boolean-masking (which can create gaps in the time series and
    confuse SARIMAX / Ljung-Box), we find the first row where all columns are
    valid and slice from there — preserving a contiguous series.
    """
    valid = X.notna().all(axis=1) & y.notna()
    # Find the first valid index and take everything from there.
    # Any interior NaNs are forward-filled to avoid gaps.
    first_valid = valid.idxmax()  # first True
    y_clean = y.loc[first_valid:].copy()
    X_clean = X.loc[first_valid:].copy()

    # Forward-fill stray interior NaNs (rare, but safe)
    X_clean = X_clean.ffill()
    y_clean = y_clean.ffill()

    # Drop any remaining NaN at the very end (cannot ffill those)
    both_valid = X_clean.notna().all(axis=1) & y_clean.notna()
    y_clean = y_clean[both_valid]
    X_clean = X_clean[both_valid]

    model = SARIMAX(y_clean, exog=X_clean, order=order, seasonal_order=seasonal_order,
                    enforce_stationarity=False, enforce_invertibility=False)
    result = model.fit(disp=False)
    return result


def _load(od: Path, name: str) -> dict:
    f = od / f"{name}.json"
    return json.loads(f.read_text()) if f.exists() else {}


def main(*, output_dir: str = "", **kwargs) -> dict:
    """Run all SARIMAX models."""
    od = Path(output_dir)

    base = _load(od, "prepare_base")

    train_records = base.get("train_data", [])
    future_records = base.get("future_data", [])

    if not train_records:
        return {"status": "error", "message": "No training data available"}

    train_df = pd.DataFrame(train_records)
    train_df["data"] = pd.to_datetime(train_df["data"])
    future_df = pd.DataFrame(future_records)
    future_df["data"] = pd.to_datetime(future_df["data"])

    # Run all 5 models by default
    model_names = list(MODEL_SPECS.keys())

    y = np.log(train_df["icms_sp"].astype(float))

    # ADF test
    adf_result = adfuller(y.diff().dropna())

    models_output = {}
    forecasts_output = {}
    diagnostics_output = {}

    for name in model_names:
        spec = MODEL_SPECS.get(name)
        if not spec:
            continue

        try:
            X_train = train_df[spec["exog_cols"]].astype(float)
            result = _fit_model(y, X_train, spec["order"], spec["seasonal_order"])

            # Diagnostics — Ljung-Box with NaN-safe residual handling
            resid = result.resid.copy()
            resid = resid[resid.notna()]  # drop any NaN residuals

            lb_pval = None
            lb_error = None
            try:
                # Use lags=[12] (list) to avoid issues with short series
                lb = acorr_ljungbox(resid, lags=[12], return_df=True)
                lb_pval = float(lb["lb_pvalue"].iloc[-1])
                if np.isnan(lb_pval):
                    lb_pval = None
                    lb_error = "Ljung-Box returned NaN p-value"
            except Exception as lb_exc:
                lb_error = f"Ljung-Box error: {lb_exc}"

            diag_entry = {
                "aic": round(_to_python(result.aic), 2),
                "bic": round(_to_python(result.bic), 2),
                "loglik": round(_to_python(result.llf), 2),
                "n_obs": _to_python(result.nobs),
                "n_resid_used": len(resid),
                "description": spec["description"],
            }
            if lb_pval is not None:
                diag_entry["ljung_box_p"] = round(lb_pval, 4)
                diag_entry["ljung_box_pass"] = lb_pval > 0.05
            else:
                diag_entry["ljung_box_p"] = None
                diag_entry["ljung_box_pass"] = None
                diag_entry["ljung_box_error"] = lb_error

            diagnostics_output[name] = diag_entry

            # Coefficients
            models_output[name] = {
                "specification": spec["description"],
                "order": list(spec["order"]),
                "seasonal_order": list(spec["seasonal_order"]),
                "exog_cols": spec["exog_cols"],
                "coefficients": {k: round(_to_python(v), 6) for k, v in result.params.items()},
            }

            # Forecast
            X_future = future_df[spec["exog_cols"]].astype(float)
            forecast = result.get_forecast(steps=len(future_df), exog=X_future)
            predicted = np.exp(forecast.predicted_mean).values

            # Confidence intervals
            ci = forecast.conf_int()
            ci_lower = np.exp(ci.iloc[:, 0]).values
            ci_upper = np.exp(ci.iloc[:, 1]).values

            forecasts_output[name] = []
            for i, row in future_df.iterrows():
                idx = i - future_df.index[0]
                forecasts_output[name].append({
                    "data": row["data"].strftime("%Y-%m-%d"),
                    "forecast": round(_to_python(predicted[idx]), 2),
                    "ci_lower": round(_to_python(ci_lower[idx]), 2),
                    "ci_upper": round(_to_python(ci_upper[idx]), 2),
                })
        except Exception as e:
            diagnostics_output[name] = {"error": str(e)}
            models_output[name] = {"error": str(e)}

    # Ensemble mean
    valid_models = [n for n in model_names if n in forecasts_output and isinstance(forecasts_output[n], list)]
    ensemble = []
    if valid_models:
        n_periods = len(forecasts_output[valid_models[0]])
        for i in range(n_periods):
            values = [forecasts_output[m][i]["forecast"] for m in valid_models]
            date = forecasts_output[valid_models[0]][i]["data"]
            ensemble.append({
                "data": date,
                "forecast": round(_to_python(np.mean(values)), 2),
                "min": round(_to_python(np.min(values)), 2),
                "max": round(_to_python(np.max(values)), 2),
            })

    # Annual totals
    annual_totals = {}
    for name in valid_models + ["ensemble"]:
        data = ensemble if name == "ensemble" else forecasts_output.get(name, [])
        if not data:
            continue
        by_year = {}
        for entry in data:
            year = entry["data"][:4]
            by_year.setdefault(year, 0)
            by_year[year] += entry["forecast"]
        annual_totals[name] = {y: round(v / 1e9, 2) for y, v in by_year.items()}

    # Best model by AIC
    valid_diag = {n: d for n, d in diagnostics_output.items() if "aic" in d}
    best_model = min(valid_diag, key=lambda n: valid_diag[n]["aic"]) if valid_diag else None

    # Confidence intervals from Monte Carlo (simplified: use forecast CI from best model)
    confidence_intervals = {}
    if best_model and best_model in forecasts_output:
        confidence_intervals = {
            "model": best_model,
            "intervals": forecasts_output[best_model],
        }

    result = {
        "models": models_output,
        "forecasts": forecasts_output,
        "diagnostics": diagnostics_output,
        "ensemble_mean": ensemble,
        "confidence_intervals": confidence_intervals,
        "annual_totals": annual_totals,
        "best_model": best_model,
        "adf_test": {
            "statistic": round(_to_python(adf_result[0]), 4),
            "p_value": round(_to_python(adf_result[1]), 4),
            "stationary": _to_python(adf_result[1]) < 0.05,
        },
        "n_models_fitted": len(valid_models),
        "status": "ok"
    }

    out_file = od / "run_sarimax_models.json"
    out_file.write_text(json.dumps(result, ensure_ascii=False, indent=2, cls=_NumpyEncoder), encoding="utf-8")

    return result

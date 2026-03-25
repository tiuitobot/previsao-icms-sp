"""Fit 5 SARIMAX models, produce forecasts, Monte Carlo simulations, and diagnostics."""
import json
import numpy as np
import pandas as pd
from pathlib import Path
import warnings
warnings.filterwarnings("ignore")

from statsmodels.tsa.statespace.sarimax import SARIMAX
from statsmodels.stats.diagnostic import acorr_ljungbox
from statsmodels.tsa.stattools import adfuller

# Monte Carlo configuration
N_SIMULATIONS = 1000
MC_PERCENTILES = [5, 25, 50, 75, 95]


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


def _run_monte_carlo(fitted_result, n_steps, exog_future, n_simulations=N_SIMULATIONS):
    """Run Monte Carlo simulation for a fitted model.

    Generates n_simulations forward paths using model.simulate(),
    returns simulation paths in real (exp) scale.

    Returns None if simulation fails.
    """
    try:
        sims_log = np.zeros((n_simulations, n_steps))
        for s in range(n_simulations):
            sim = fitted_result.simulate(
                nsimulations=n_steps, anchor='end', exog=exog_future
            )
            sims_log[s, :] = np.asarray(sim)
        # Convert from log scale to real scale
        sims_real = np.exp(sims_log)
        return sims_real
    except Exception:
        return None


def _run_oos_validation(train_df, y_full, spec, holdout_months=12):
    """Out-of-sample validation: hold out last N months, fit on rest, compute MAPE.

    Returns dict with mape, status, and details; or error info on failure.
    """
    n_total = len(train_df)
    if n_total <= holdout_months + 24:
        # Not enough data for meaningful validation
        return {"status": "insufficient_data", "mape": None}

    train_subset = train_df.iloc[:-holdout_months].copy()
    test_subset = train_df.iloc[-holdout_months:].copy()

    y_train = y_full.iloc[:-holdout_months].copy()
    y_test_real = test_subset["icms_sp"].astype(float).values

    try:
        X_train = train_subset[spec["exog_cols"]].astype(float)
        X_test = test_subset[spec["exog_cols"]].astype(float)

        fitted = _fit_model(y_train, X_train, spec["order"], spec["seasonal_order"])
        pred = fitted.get_forecast(steps=len(test_subset), exog=X_test)
        pred_real = np.exp(pred.predicted_mean).values

        # MAPE: Mean Absolute Percentage Error
        mape = float(np.mean(np.abs((y_test_real - pred_real) / y_test_real)) * 100)

        return {
            "status": "ok",
            "mape": round(mape, 2),
            "holdout_months": holdout_months,
            "holdout_start": test_subset["data"].iloc[0].strftime("%Y-%m-%d"),
            "holdout_end": test_subset["data"].iloc[-1].strftime("%Y-%m-%d"),
        }
    except Exception as exc:
        return {"status": "error", "mape": None, "error": str(exc)}


def _load(od: Path, name: str) -> dict:
    f = od / f"{name}.json"
    return json.loads(f.read_text()) if f.exists() else {}


def main(*, output_dir: str = "", **kwargs) -> dict:
    """Run all SARIMAX models with Monte Carlo simulation and OOS validation."""
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
    n_future = len(future_df)

    # ADF test
    adf_result = adfuller(y.diff().dropna())

    models_output = {}
    forecasts_output = {}
    diagnostics_output = {}
    # Monte Carlo: collect simulation paths per model (real scale, shape: [N_SIMULATIONS, n_future])
    mc_simulations = {}

    for name in model_names:
        spec = MODEL_SPECS.get(name)
        if not spec:
            continue

        try:
            X_train = train_df[spec["exog_cols"]].astype(float)
            result = _fit_model(y, X_train, spec["order"], spec["seasonal_order"])

            # --- Out-of-sample validation (MAPE) ---
            oos_result = _run_oos_validation(train_df, y, spec)

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
                "mape": oos_result.get("mape"),
                "oos_validation": oos_result,
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

            # Forecast (point estimate + analytical CI — kept for backward compat)
            X_future = future_df[spec["exog_cols"]].astype(float)
            forecast = result.get_forecast(steps=n_future, exog=X_future)
            predicted = np.exp(forecast.predicted_mean).values

            # Analytical confidence intervals
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

            # --- Monte Carlo simulation ---
            sims = _run_monte_carlo(result, n_future, X_future, N_SIMULATIONS)
            if sims is not None:
                mc_simulations[name] = sims
                diagnostics_output[name]["monte_carlo"] = "ok"
            else:
                diagnostics_output[name]["monte_carlo"] = "simulation_failed"

        except Exception as e:
            diagnostics_output[name] = {"error": str(e)}
            models_output[name] = {"error": str(e)}

    # Ensemble mean (point forecasts — backward compat)
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

    # =========================================================================
    # Monte Carlo ensemble: stack all simulation paths across models
    # =========================================================================
    mc_models_used = [n for n in valid_models if n in mc_simulations]
    mc_confidence_intervals = []
    mc_ensemble_paths = None

    if mc_models_used:
        # Stack: shape [n_models, N_SIMULATIONS, n_future]
        # Then mean across models → [N_SIMULATIONS, n_future] (ensemble paths)
        stacked = np.stack([mc_simulations[n] for n in mc_models_used], axis=0)
        mc_ensemble_paths = np.mean(stacked, axis=0)  # [N_SIMULATIONS, n_future]

        # Monthly percentile CIs from ensemble paths
        future_dates = future_df["data"].dt.strftime("%Y-%m-%d").tolist()
        for t in range(n_future):
            col = mc_ensemble_paths[:, t]
            entry = {"data": future_dates[t]}
            for p in MC_PERCENTILES:
                entry[f"p{p}"] = round(float(np.percentile(col, p)), 2)
            mc_confidence_intervals.append(entry)

    # =========================================================================
    # Annual totals — now with CI bands from Monte Carlo
    # =========================================================================
    annual_totals = {}
    future_years = future_df["data"].dt.year.values

    # Per-model annual totals (point forecasts — backward compat)
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

    # Ensemble annual totals with Monte Carlo CIs
    if mc_ensemble_paths is not None:
        unique_years = sorted(set(future_years))
        mc_annual = {}
        for yr in unique_years:
            yr_indices = np.where(future_years == yr)[0]
            if len(yr_indices) == 0:
                continue
            # Sum each simulation path over the months of this year
            annual_sums = np.sum(mc_ensemble_paths[:, yr_indices], axis=1)  # [N_SIMULATIONS]
            yr_entry = {}
            for p in MC_PERCENTILES:
                key = {5: "low_95", 25: "low_50", 50: "median", 75: "high_50", 95: "high_95"}[p]
                yr_entry[key] = round(float(np.percentile(annual_sums, p)) / 1e9, 2)
            yr_entry["mean"] = round(float(np.mean(annual_sums)) / 1e9, 2)
            mc_annual[str(yr)] = yr_entry
        annual_totals["ensemble_mc"] = mc_annual

        # Per-model annual CIs from Monte Carlo
        for name in mc_models_used:
            model_sims = mc_simulations[name]  # [N_SIMULATIONS, n_future]
            mc_model_annual = {}
            for yr in unique_years:
                yr_indices = np.where(future_years == yr)[0]
                if len(yr_indices) == 0:
                    continue
                annual_sums = np.sum(model_sims[:, yr_indices], axis=1)
                yr_entry = {}
                for p in MC_PERCENTILES:
                    key = {5: "low_95", 25: "low_50", 50: "median", 75: "high_50", 95: "high_95"}[p]
                    yr_entry[key] = round(float(np.percentile(annual_sums, p)) / 1e9, 2)
                yr_entry["mean"] = round(float(np.mean(annual_sums)) / 1e9, 2)
                mc_model_annual[str(yr)] = yr_entry
            annual_totals[f"{name}_mc"] = mc_model_annual

    # Best model by AIC
    valid_diag = {n: d for n, d in diagnostics_output.items() if "aic" in d}
    best_model = min(valid_diag, key=lambda n: valid_diag[n]["aic"]) if valid_diag else None

    # Best model by MAPE (out-of-sample)
    valid_mape = {n: d["mape"] for n, d in diagnostics_output.items()
                  if "mape" in d and d.get("mape") is not None}
    best_model_mape = min(valid_mape, key=lambda n: valid_mape[n]) if valid_mape else None

    # Confidence intervals from Monte Carlo
    confidence_intervals = {
        "source": "monte_carlo_ensemble" if mc_confidence_intervals else "analytical_best_model",
        "n_models_in_ensemble": len(mc_models_used),
        "models_used": mc_models_used,
    }
    if mc_confidence_intervals:
        confidence_intervals["intervals"] = mc_confidence_intervals
    elif best_model and best_model in forecasts_output:
        # Fallback to analytical CI from best model
        confidence_intervals["model"] = best_model
        confidence_intervals["intervals"] = forecasts_output[best_model]

    result = {
        "models": models_output,
        "forecasts": forecasts_output,
        "diagnostics": diagnostics_output,
        "ensemble_mean": ensemble,
        "confidence_intervals": confidence_intervals,
        "annual_totals": annual_totals,
        "best_model": best_model,
        "best_model_mape": best_model_mape,
        "adf_test": {
            "statistic": round(_to_python(adf_result[0]), 4),
            "p_value": round(_to_python(adf_result[1]), 4),
            "stationary": _to_python(adf_result[1]) < 0.05,
        },
        "monte_carlo_config": {
            "n_simulations": N_SIMULATIONS,
            "percentiles_used": MC_PERCENTILES,
            "models_simulated": len(mc_models_used),
            "models_failed": len(valid_models) - len(mc_models_used),
        },
        "n_models_fitted": len(valid_models),
        "status": "ok"
    }

    out_file = od / "run_sarimax_models.json"
    out_file.write_text(json.dumps(result, ensure_ascii=False, indent=2, cls=_NumpyEncoder), encoding="utf-8")

    return result

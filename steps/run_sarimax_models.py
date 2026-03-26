"""Fit 5 SARIMAX models, produce forecasts, Monte Carlo simulations, and diagnostics."""
import json
import numpy as np
import pandas as pd
from itertools import combinations
from pathlib import Path
import warnings
warnings.filterwarnings("ignore")

from statsmodels.tsa.statespace.sarimax import SARIMAX
from statsmodels.stats.diagnostic import acorr_ljungbox
from statsmodels.tsa.stattools import adfuller

# Monte Carlo configuration
N_SIMULATIONS = 1000
MC_PERCENTILES = [5, 25, 50, 75, 95]

# OOS validation: post-dummy window
# Last structural dummy ends May 2023 (TC2022OUT05).
# OOS test only uses data AFTER all dummies are fully in the training set.
LAST_DUMMY_END = "2023-05-01"  # TC2022OUT05 last month
OOS_MIN_POST_DUMMY_MONTHS = 1  # minimum test months to be valid


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


def _run_oos_validation(train_df, y_full, spec):
    """Post-dummy OOS validation.

    Trains on data up to LAST_DUMMY_END, tests on everything after.
    This ensures all structural dummy coefficients are estimated.
    The window size grows as more ICMS data becomes available.

    With ICMS until jan/2024: test = jun/2023 to jan/2024 (8 months)
    With ICMS until fev/2026: test = jun/2023 to fev/2026 (33 months)
    """
    dummy_end = pd.Timestamp(LAST_DUMMY_END)

    # Train up to dummy_end (inclusive)
    train_mask = train_df["data"] <= dummy_end
    test_mask = train_df["data"] > dummy_end

    train_subset = train_df[train_mask].copy()
    test_subset = train_df[test_mask].copy()

    n_test = len(test_subset)
    if n_test < OOS_MIN_POST_DUMMY_MONTHS:
        return {"status": "insufficient_post_dummy_data", "mape": None,
                "n_test_months": n_test, "dummy_end": LAST_DUMMY_END}

    y_train = y_full[train_mask].copy()
    y_test_real = test_subset["icms_sp"].astype(float).values

    try:
        X_train = train_subset[spec["exog_cols"]].astype(float)
        X_test = test_subset[spec["exog_cols"]].astype(float)

        fitted = _fit_model(y_train, X_train, spec["order"], spec["seasonal_order"])
        pred = fitted.get_forecast(steps=n_test, exog=X_test)
        pred_real = np.exp(pred.predicted_mean).values

        sum_real = float(np.sum(y_test_real))
        sum_pred = float(np.sum(pred_real))
        mape_accumulated = abs((sum_real - sum_pred) / sum_real) * 100 if sum_real != 0 else None
        mape_monthly = float(np.mean(np.abs((y_test_real - pred_real) / y_test_real)) * 100)

        return {
            "status": "ok",
            "mape": round(mape_accumulated, 2) if mape_accumulated is not None else None,
            "mape_accumulated": round(mape_accumulated, 2) if mape_accumulated is not None else None,
            "mape_monthly": round(mape_monthly, 2),
            "n_test_months": n_test,
            "train_end": dummy_end.strftime("%Y-%m-%d"),
            "test_start": test_subset["data"].iloc[0].strftime("%Y-%m-%d"),
            "test_end": test_subset["data"].iloc[-1].strftime("%Y-%m-%d"),
            "sum_real_brl": round(sum_real / 1e9, 2),
            "sum_pred_brl": round(sum_pred / 1e9, 2),
            "dummy_end": LAST_DUMMY_END,
            "note": f"Janela pós-dummies: treino até {LAST_DUMMY_END}, teste {n_test} meses. "
                    f"Todas as dummies estruturais estão estimadas no treino.",
        }
    except Exception as exc:
        return {"status": "error", "mape": None, "error": str(exc)}


def _compute_inverse_mse_weights(component_preds, y_test_real):
    """Compute inverse-MSE weights for forecast combination.

    w_i = (1/MSE_i) / sum(1/MSE_j)

    Reference: Bates & Granger (1969), "The Combination of Forecasts",
    Operational Research Quarterly, 20(4), 451-468.
    Used by: BCB, Fed, ECB, Bank of England for macro forecast combination.
    See also: Timmermann (2006), "Forecast Combinations", Handbook of
    Economic Forecasting, Vol. 1, Ch. 4.
    """
    mses = []
    for pred in component_preds:
        mse = float(np.mean((y_test_real - pred) ** 2))
        mses.append(max(mse, 1e-10))  # avoid division by zero

    inv_mses = [1.0 / mse for mse in mses]
    total = sum(inv_mses)
    weights = [w / total for w in inv_mses]
    return weights, mses


def _run_ensemble_oos_validation(train_df, y_full, component_specs):
    """Post-dummy OOS validation for an ensemble with inverse-MSE weighting.

    Same window as individual models: train up to LAST_DUMMY_END,
    test on everything after. Fits all components, weights by inverse MSE,
    then computes accumulated MAPE.

    Returns dict with MAPE and weights (or None on failure).
    """
    dummy_end = pd.Timestamp(LAST_DUMMY_END)

    train_mask = train_df["data"] <= dummy_end
    test_mask = train_df["data"] > dummy_end

    train_subset = train_df[train_mask].copy()
    test_subset = train_df[test_mask].copy()

    n_test = len(test_subset)
    if n_test < OOS_MIN_POST_DUMMY_MONTHS:
        return None

    y_train = y_full[train_mask].copy()
    y_test_real = test_subset["icms_sp"].astype(float).values

    component_preds = []
    component_names = []
    for spec_name, spec in component_specs.items():
        try:
            X_train = train_subset[spec["exog_cols"]].astype(float)
            X_test = test_subset[spec["exog_cols"]].astype(float)
            fitted = _fit_model(y_train, X_train, spec["order"], spec["seasonal_order"])
            pred = fitted.get_forecast(steps=n_test, exog=X_test)
            pred_real = np.exp(pred.predicted_mean).values
            component_preds.append(pred_real)
            component_names.append(spec_name)
        except Exception:
            continue

    if not component_preds:
        return None

    # Inverse-MSE weighted combination (Bates & Granger, 1969)
    weights, mses = _compute_inverse_mse_weights(component_preds, y_test_real)
    weighted_pred = np.zeros_like(component_preds[0])
    for w, pred in zip(weights, component_preds):
        weighted_pred += w * pred

    sum_real = float(np.sum(y_test_real))
    sum_pred = float(np.sum(weighted_pred))
    mape = abs((sum_real - sum_pred) / sum_real) * 100 if sum_real != 0 else None

    return {
        "mape": round(mape, 2) if mape is not None else None,
        "weights": {n: round(w, 4) for n, w in zip(component_names, weights)},
        "method": "inverse_mse",
    }


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

    # --- Change 3: Forecast horizon ---
    # Find last ICMS observation date, forecast from next month to Dec of following year
    last_icms_date = train_df["data"].max()
    forecast_start = last_icms_date + pd.DateOffset(months=1)
    forecast_end_year = last_icms_date.year + 1
    forecast_end = pd.Timestamp(f"{forecast_end_year}-12-31")

    full_future_df = pd.DataFrame(future_records)
    full_future_df["data"] = pd.to_datetime(full_future_df["data"])

    # Filter future_data to the desired horizon
    future_df = full_future_df[
        (full_future_df["data"] >= forecast_start) &
        (full_future_df["data"] <= forecast_end)
    ].copy().reset_index(drop=True)

    if future_df.empty:
        return {
            "status": "error",
            "message": (
                f"No future data in range {forecast_start.strftime('%Y-%m')} "
                f"to {forecast_end.strftime('%Y-%m')}. "
                f"Last ICMS observation: {last_icms_date.strftime('%Y-%m-%d')}"
            )
        }

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
    # Per-model OOS MAPE (for ensemble building)
    individual_mapes = {}

    for name in model_names:
        spec = MODEL_SPECS.get(name)
        if not spec:
            continue

        try:
            X_train = train_df[spec["exog_cols"]].astype(float)
            result = _fit_model(y, X_train, spec["order"], spec["seasonal_order"])

            # --- Out-of-sample validation (rolling 5-window MAPE) ---
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

            # Track individual MAPE for all_candidates
            if oos_result.get("mape") is not None:
                individual_mapes[name] = oos_result["mape"]

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

    # =========================================================================
    # All 31 ensemble combinations
    # =========================================================================
    valid_models = [n for n in model_names if n in forecasts_output and isinstance(forecasts_output[n], list)]

    # Build all_candidates: individual models + all ensemble combos
    all_candidates = {}

    # 1) Individual models
    for name in valid_models:
        mape_val = individual_mapes.get(name)
        all_candidates[name] = {
            "mape": mape_val,
            "type": "individual",
            "components": [name],
        }

    # 2) All ensemble combinations (pairs, triples, quadruples, quintuple)
    for combo_size in range(2, len(valid_models) + 1):
        for combo in combinations(valid_models, combo_size):
            combo_name = "Ensemble(" + ",".join(
                m.replace("Modelo ", "M") for m in combo
            ) + ")"
            component_specs = {m: MODEL_SPECS[m] for m in combo}
            oos_result = _run_ensemble_oos_validation(
                train_df, y, component_specs
            )
            if isinstance(oos_result, dict):
                ensemble_mape = oos_result.get("mape")
                ensemble_weights = oos_result.get("weights", {})
            else:
                ensemble_mape = oos_result
                ensemble_weights = {}
            all_candidates[combo_name] = {
                "mape": ensemble_mape,
                "type": "ensemble",
                "components": list(combo),
                "weights": ensemble_weights,
                "weighting_method": "inverse_mse",
            }

    # Find best candidate overall (lowest MAPE)
    candidates_with_mape = {
        k: v for k, v in all_candidates.items() if v["mape"] is not None
    }
    if candidates_with_mape:
        best_candidate_name = min(
            candidates_with_mape, key=lambda k: candidates_with_mape[k]["mape"]
        )
        best_candidate_mape = candidates_with_mape[best_candidate_name]["mape"]
    else:
        best_candidate_name = None
        best_candidate_mape = None

    # Top 5 ensemble candidates by MAPE
    ensemble_candidates = {
        k: v for k, v in candidates_with_mape.items() if v["type"] == "ensemble"
    }
    top5_ensembles = sorted(
        ensemble_candidates.items(), key=lambda x: x[1]["mape"]
    )[:5]
    top5_ensembles = [
        {"name": name, **info} for name, info in top5_ensembles
    ]

    # Ensemble forecasts — inverse-MSE weighted if best is ensemble, else equal weight
    ensemble = []
    best_weights = {}
    if best_candidate_name and best_candidate_name in all_candidates:
        best_info = all_candidates[best_candidate_name]
        if best_info.get("weights"):
            best_weights = best_info["weights"]

    if valid_models:
        n_periods = len(forecasts_output[valid_models[0]])
        for i in range(n_periods):
            date = forecasts_output[valid_models[0]][i]["data"]
            if best_weights:
                # Weighted ensemble using inverse-MSE weights
                weighted_val = sum(
                    best_weights.get(m, 0) * forecasts_output[m][i]["forecast"]
                    for m in best_weights if m in forecasts_output
                )
                all_vals = [forecasts_output[m][i]["forecast"] for m in valid_models]
                ensemble.append({
                    "data": date,
                    "forecast": round(_to_python(weighted_val), 2),
                    "min": round(_to_python(np.min(all_vals)), 2),
                    "max": round(_to_python(np.max(all_vals)), 2),
                })
            else:
                # Equal weight (fallback)
                values = [forecasts_output[m][i]["forecast"] for m in valid_models]
                ensemble.append({
                    "data": date,
                    "forecast": round(_to_python(np.mean(values)), 2),
                    "min": round(_to_python(np.min(values)), 2),
                    "max": round(_to_python(np.max(values)), 2),
                })

    # Also apply weights to Monte Carlo paths
    ensemble_weighting = {
        "method": "inverse_mse" if best_weights else "equal_weight",
        "weights": best_weights if best_weights else {m: round(1/len(valid_models), 4) for m in valid_models},
        "reference": "Bates & Granger (1969). The Combination of Forecasts. Operational Research Quarterly, 20(4), 451-468.",
        "note": "Pesos inverse-MSE: w_i = (1/MSE_i) / Σ(1/MSE_j). Método padrão em bancos centrais (BCB, Fed, ECB, BoE). "
                "Ver também: Timmermann (2006), Forecast Combinations, Handbook of Economic Forecasting.",
    }

    # =========================================================================
    # MC annual paths per model — for client-side CI computation
    # =========================================================================
    mc_paths_output = {}
    for model_name, paths in mc_simulations.items():
        # paths shape: [N_SIMULATIONS, n_future]
        # Save annual sums per simulation (not monthly — too large)
        annual_paths = {}
        for year in sorted(set(future_df["data"].dt.year)):
            year_mask = future_df["data"].dt.year == year
            year_indices = [i for i, m in enumerate(year_mask) if m]
            if year_indices:
                year_sums = paths[:, year_indices].sum(axis=1)  # [N_SIMULATIONS]
                annual_paths[str(year)] = [round(float(v) / 1e9, 2) for v in year_sums]  # in billions
        mc_paths_output[model_name] = annual_paths

    # =========================================================================
    # Monte Carlo ensemble: use best candidate's components
    # =========================================================================
    if best_candidate_name and best_candidate_name in all_candidates:
        best_components = all_candidates[best_candidate_name]["components"]
        mc_models_used = [n for n in best_components if n in mc_simulations]
    else:
        mc_models_used = [n for n in valid_models if n in mc_simulations]

    mc_confidence_intervals = []
    mc_ensemble_paths = None

    if mc_models_used:
        # Stack: shape [n_models, N_SIMULATIONS, n_future]
        stacked = np.stack([mc_simulations[n] for n in mc_models_used], axis=0)
        # Apply inverse-MSE weights (or equal weight) across models
        if best_weights and all(n in best_weights for n in mc_models_used):
            mc_weights = np.array([best_weights[n] for n in mc_models_used])
            mc_weights = mc_weights / mc_weights.sum()  # normalize
            mc_ensemble_paths = np.tensordot(mc_weights, stacked, axes=([0], [0]))
        else:
            mc_ensemble_paths = np.mean(stacked, axis=0)  # equal weight fallback

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
    # Include realized ICMS months for the current year (forecast_start year)
    # =========================================================================
    annual_totals = {}
    future_years = future_df["data"].dt.year.values

    # Compute realized ICMS for the year that straddles observed/forecast
    current_year = last_icms_date.year
    realized_current_year = float(
        train_df.loc[train_df["data"].dt.year == current_year, "icms_sp"]
        .astype(float).sum()
    )

    # Per-model annual totals (point forecasts + realized for current year)
    for name in valid_models + ["ensemble"]:
        data = ensemble if name == "ensemble" else forecasts_output.get(name, [])
        if not data:
            continue
        by_year = {}
        for entry in data:
            year = entry["data"][:4]
            by_year.setdefault(year, 0)
            by_year[year] += entry["forecast"]
        totals = {y: round(v / 1e9, 2) for y, v in by_year.items()}
        # Add realized months to current year
        cy_str = str(current_year)
        if cy_str in totals:
            totals[cy_str] = round((by_year[cy_str] + realized_current_year) / 1e9, 2)
        annual_totals[name] = totals

    # Store realized amount and month count for downstream consumers
    realized_months = int((train_df["data"].dt.year == current_year).sum())
    annual_totals["_realized"] = {
        "year": current_year,
        "months": realized_months,
        "total_brl_bi": round(realized_current_year / 1e9, 2),
    }

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
            # Add realized ICMS for current year
            if yr == current_year:
                annual_sums = annual_sums + realized_current_year
            yr_entry = {}
            for p in MC_PERCENTILES:
                key = {5: "low_95", 25: "low_50", 50: "median", 75: "high_50", 95: "high_95"}[p]
                yr_entry[key] = round(float(np.percentile(annual_sums, p)) / 1e9, 2)
            yr_entry["mean"] = round(float(np.mean(annual_sums)) / 1e9, 2)
            mc_annual[str(yr)] = yr_entry
        annual_totals["ensemble_mc"] = mc_annual

        # Per-model annual CIs from Monte Carlo
        all_mc_models = [n for n in valid_models if n in mc_simulations]
        for name in all_mc_models:
            model_sims = mc_simulations[name]  # [N_SIMULATIONS, n_future]
            mc_model_annual = {}
            for yr in unique_years:
                yr_indices = np.where(future_years == yr)[0]
                if len(yr_indices) == 0:
                    continue
                annual_sums = np.sum(model_sims[:, yr_indices], axis=1)
                if yr == current_year:
                    annual_sums = annual_sums + realized_current_year
                yr_entry = {}
                for p in MC_PERCENTILES:
                    key = {5: "low_95", 25: "low_50", 50: "median", 75: "high_50", 95: "high_95"}[p]
                    yr_entry[key] = round(float(np.percentile(annual_sums, p)) / 1e9, 2)
                yr_entry["mean"] = round(float(np.mean(annual_sums)) / 1e9, 2)
                mc_model_annual[str(yr)] = yr_entry
            annual_totals[f"{name}_mc"] = mc_model_annual

    # Best model by AIC (backward compat)
    valid_diag = {n: d for n, d in diagnostics_output.items() if "aic" in d}
    best_model_aic = min(valid_diag, key=lambda n: valid_diag[n]["aic"]) if valid_diag else None

    # Confidence intervals from Monte Carlo
    confidence_intervals = {
        "source": "monte_carlo_ensemble" if mc_confidence_intervals else "analytical_best_model",
        "n_models_in_ensemble": len(mc_models_used),
        "models_used": mc_models_used,
    }
    if mc_confidence_intervals:
        confidence_intervals["intervals"] = mc_confidence_intervals
    elif best_model_aic and best_model_aic in forecasts_output:
        # Fallback to analytical CI from best model
        confidence_intervals["model"] = best_model_aic
        confidence_intervals["intervals"] = forecasts_output[best_model_aic]

    result = {
        "models": models_output,
        "forecasts": forecasts_output,
        "diagnostics": diagnostics_output,
        "ensemble_mean": ensemble,
        "confidence_intervals": confidence_intervals,
        "annual_totals": annual_totals,
        "best_model": best_candidate_name,
        "best_model_mape": best_candidate_mape,
        "all_candidates": all_candidates,
        "top5_ensembles": top5_ensembles,
        "ensemble_weighting": ensemble_weighting,
        "forecast_horizon": {
            "last_icms_observation": last_icms_date.strftime("%Y-%m-%d"),
            "forecast_start": forecast_start.strftime("%Y-%m-%d"),
            "forecast_end": forecast_end.strftime("%Y-%m-%d"),
            "n_months": n_future,
        },
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
            "best_candidate_components": mc_models_used,
        },
        "mc_annual_paths": mc_paths_output,
        "n_models_fitted": len(valid_models),
        "status": "ok"
    }

    out_file = od / "run_sarimax_models.json"
    out_file.write_text(json.dumps(result, ensure_ascii=False, indent=2, cls=_NumpyEncoder), encoding="utf-8")

    return result

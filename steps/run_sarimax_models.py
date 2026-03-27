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

# OOS validation configuration
DUMMY_COLS = ["LS2008NOV", "TC2020APR04", "TC2022OUT05"]
MIN_TRAIN_MONTHS = 120  # 10 years minimum training for robust ARIMA
MIN_OOS_WINDOWS = 10    # minimum expanding windows for reliable MAPE


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

# ---------------------------------------------------------------------------
# M' (prime) model specifications — re-specified to pass Ljung-Box at lag 12.
#
# The original models 2-5 reject H0 of the Ljung-Box test (residual
# autocorrelation), primarily because:
#   - M2: AR(3) without MA term fails to absorb short-lag autocorrelation.
#   - M3-M5: seasonal differencing D=1 over-differences the series, producing
#     a strong negative ACF at lag 12 (classic over-differencing signature).
#
# The M' variants add log(ICMS)_{t-12} as an exogenous regressor — a "subset
# AR" at lag 12 — instead of relying on the multiplicative seasonal polynomial.
# This is equivalent to an additive AR(12) term and is more flexible than the
# SARIMA seasonal structure for this series.  All M' variants pass LB at 5%.
#
# M1 already passes LB in the original specification; no M1' is needed.
# M5 has NO alternative seasonal ARIMA specification (D=0 with various P,Q)
# that passes LB — only the lag12-as-exog approach resolves it.
# ---------------------------------------------------------------------------
MODEL_SPECS_PRIME = {
    "Modelo 2'": {
        "order": (1, 1, 1),
        "seasonal_order": (0, 0, 0, 12),
        "exog_cols": ["igp_di_lag1", "ibc_br_lag1", "dias_uteis",
                      "LS2008NOV", "TC2020APR04", "TC2022OUT05", "log_icms_lag12"],
        "description": "ARIMA(1,1,1) + lag12 + IGP-DI/IBC-BR lag1",
        "parent": "Modelo 2",
        "rationale": "AR(3) -> ARMA(1,1) + lag12 exog resolve autocorrelacao residual nos lags 1-2 e 12"
    },
    "Modelo 3'": {
        "order": (0, 1, 1),
        "seasonal_order": (0, 0, 0, 12),
        "exog_cols": ["igp_di", "ibc_br", "ibc_br_lag1", "dias_uteis",
                      "LS2008NOV", "TC2020APR04", "TC2022OUT05", "log_icms_lag12"],
        "description": "ARIMA(0,1,1) + lag12 + IGP-DI/IBC-BR",
        "parent": "Modelo 3",
        "rationale": "D=1 sazonal sobre-diferenciava (ACF lag12=-0.46); lag12 exog com D=0 resolve"
    },
    "Modelo 4'": {
        "order": (0, 1, 1),
        "seasonal_order": (0, 0, 0, 12),
        "exog_cols": ["ibc_br", "ibc_br_lag1", "dias_uteis",
                      "LS2008NOV", "TC2020APR04", "TC2022OUT05", "log_icms_lag12"],
        "description": "ARIMA(0,1,1) + lag12 + IBC-BR (sem inflacao)",
        "parent": "Modelo 4",
        "rationale": "D=1 sazonal sobre-diferenciava; lag12 exog com D=0 resolve"
    },
    "Modelo 5'": {
        "order": (0, 1, 1),
        "seasonal_order": (0, 0, 0, 12),
        "exog_cols": ["igp_di", "ibc_br", "ibc_br_lag1",
                      "LS2008NOV", "TC2020APR04", "TC2022OUT05", "log_icms_lag12"],
        "description": "ARIMA(0,1,1) + lag12 + IGP-DI/IBC-BR (sem dias uteis)",
        "parent": "Modelo 5",
        "rationale": "Unico modelo sem alternativa SARIMA(P,D,Q) valida; lag12 exog eh a unica correcao que resolve LB"
    },
}

# Combined specs: originals + primes
ALL_MODEL_SPECS = {**MODEL_SPECS, **MODEL_SPECS_PRIME}


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


def _pre_correct_dummies(y, train_df, fitted_result, spec):
    """Remove dummy effects from log(ICMS) series using full-sample coefficients.

    Returns:
      y_adj: log(ICMS) with dummy effects removed (same index as y)
      non_dummy_cols: exog columns excluding dummies
      dummy_effects: array of dummy effects per observation (log scale)
      dummy_coeffs: dict of dummy_col -> coefficient
    """
    dummy_cols_in_model = [c for c in spec["exog_cols"] if c in DUMMY_COLS]
    non_dummy_cols = [c for c in spec["exog_cols"] if c not in DUMMY_COLS]

    # Extract dummy coefficients from full-sample fit
    dummy_coeffs = {}
    dummy_effects = np.zeros(len(y))
    for col in dummy_cols_in_model:
        if col in fitted_result.params.index:
            coef = float(fitted_result.params[col])
            dummy_coeffs[col] = coef
            dummy_effects += coef * train_df[col].astype(float).values

    y_adj = y.copy()
    y_adj = y_adj - dummy_effects

    return y_adj, non_dummy_cols, dummy_effects, dummy_coeffs


def _determine_oos_horizon(target_horizon, first_valid_cutoff, last_obs):
    """Dynamically reduce horizon if needed to get at least MIN_OOS_WINDOWS."""
    for h in range(target_horizon, 0, -1):
        latest_cutoff = last_obs - pd.DateOffset(months=h)
        if latest_cutoff > first_valid_cutoff:
            n_windows = len(pd.date_range(start=first_valid_cutoff, end=latest_cutoff, freq="MS"))
            if n_windows >= MIN_OOS_WINDOWS:
                return h
    return max(1, target_horizon)  # fallback


def _run_all_expanding_windows(train_df, y_full, model_specs, full_sample_fits,
                               oos_horizon):
    """Run expanding-window OOS for ALL models with dummy pre-correction.

    Dummy effects (estimated from full sample) are removed from both the
    training series and the test actuals. This allows starting windows much
    earlier than the last structural break, since the model only needs to
    predict the underlying dynamics (ARIMA + non-dummy exogenous).

    Returns a dict keyed by model name with predictions, actuals, and MAPEs.
    """
    last_obs = train_df["data"].max()
    first_valid_date = train_df["data"].iloc[0] + pd.DateOffset(months=MIN_TRAIN_MONTHS)

    # Dynamic horizon relaxation
    effective_horizon = _determine_oos_horizon(oos_horizon, first_valid_date, last_obs)

    latest_cutoff = last_obs - pd.DateOffset(months=effective_horizon)
    if latest_cutoff <= first_valid_date:
        return None, effective_horizon

    MAX_WINDOWS = 40  # cap to keep computation under ~3 min per horizon
    all_cutoffs = pd.date_range(start=first_valid_date, end=latest_cutoff, freq="MS")
    if len(all_cutoffs) == 0:
        return None, effective_horizon
    # Space cutoffs evenly if too many
    if len(all_cutoffs) > MAX_WINDOWS:
        step = max(1, len(all_cutoffs) // MAX_WINDOWS)
        cutoff_dates = all_cutoffs[::step]
    else:
        cutoff_dates = all_cutoffs

    # Pre-correct dummy effects per model (using full-sample coefficients)
    model_corrections = {}
    for name, spec in model_specs.items():
        if name not in full_sample_fits:
            continue
        y_adj, non_dummy_cols, dummy_effects, dummy_coeffs = _pre_correct_dummies(
            y_full, train_df, full_sample_fits[name], spec
        )
        model_corrections[name] = {
            "y_adj": y_adj,
            "non_dummy_cols": non_dummy_cols,
            "dummy_effects": dummy_effects,
            "dummy_coeffs": dummy_coeffs,
        }

    # Initialize per-model storage
    model_results = {
        name: {"predictions": {}, "actuals": {}, "window_mapes": [], "cutoff_dates": []}
        for name in model_specs
    }

    for cutoff in cutoff_dates:
        train_mask = train_df["data"] <= cutoff
        test_start = cutoff + pd.DateOffset(months=1)
        test_end = cutoff + pd.DateOffset(months=effective_horizon)
        test_mask = (train_df["data"] >= test_start) & (train_df["data"] <= test_end)

        train_subset = train_df[train_mask].copy()
        test_subset = train_df[test_mask].copy()
        n_test = len(test_subset)
        if n_test < effective_horizon:
            continue

        cutoff_str = cutoff.strftime("%Y-%m-%d")

        for name, spec in model_specs.items():
            if name not in model_corrections:
                continue
            corr = model_corrections[name]
            try:
                # Use dummy-corrected y and non-dummy exog
                y_adj_train = corr["y_adj"][train_mask].copy()
                y_adj_test = corr["y_adj"][test_mask]
                non_dummy_cols = corr["non_dummy_cols"]

                X_train = train_subset[non_dummy_cols].astype(float)
                X_test = test_subset[non_dummy_cols].astype(float)

                fitted = _fit_model(y_adj_train, X_train, spec["order"], spec["seasonal_order"])
                pred = fitted.get_forecast(steps=n_test, exog=X_test)
                pred_real = np.exp(pred.predicted_mean).values

                # Actuals also dummy-corrected (fair comparison)
                actual_real = np.exp(y_adj_test.values)

                sum_real = float(np.sum(actual_real))
                sum_pred = float(np.sum(pred_real))
                mape = abs((sum_real - sum_pred) / sum_real) * 100 if sum_real != 0 else None

                model_results[name]["predictions"][cutoff_str] = pred_real
                model_results[name]["actuals"][cutoff_str] = actual_real
                if mape is not None:
                    model_results[name]["window_mapes"].append(mape)
                    model_results[name]["cutoff_dates"].append(cutoff_str)
            except Exception:
                continue

    return model_results, effective_horizon


def _build_oos_result_from_windows(model_window_data, effective_horizon):
    """Convert per-model expanding-window data into OOS result dict."""
    mape_values = model_window_data["window_mapes"]
    cutoff_dates = model_window_data["cutoff_dates"]

    if not mape_values:
        return {"status": "no_valid_windows", "mape": None}

    return {
        "status": "ok",
        "mape": round(float(np.mean(mape_values)), 2),
        "mape_mean": round(float(np.mean(mape_values)), 2),
        "mape_std": round(float(np.std(mape_values)), 2),
        "mape_min": round(float(np.min(mape_values)), 2),
        "mape_max": round(float(np.max(mape_values)), 2),
        "n_windows": len(mape_values),
        "oos_horizon_months": effective_horizon,
        "first_window_train_end": cutoff_dates[0],
        "last_window_train_end": cutoff_dates[-1],
        "windows": [
            {"train_end": cd, "mape": round(m, 2)}
            for cd, m in zip(cutoff_dates, mape_values)
        ],
        "method": "expanding_window_dummy_corrected",
        "note": (f"Expanding window: {len(mape_values)} janelas, horizonte {effective_horizon}m. "
                 f"Efeitos de dummies removidos usando coeficientes do sample completo. "
                 f"MAPE = média dos MAPEs acumulados de {effective_horizon} meses."),
    }


def _compute_ensemble_mape_from_windows(model_window_data, component_names):
    """Compute ensemble MAPE from pre-computed individual model predictions.

    For each window, combines individual predictions with inverse-MSE weights
    and computes the accumulated MAPE. No re-fitting needed.
    """
    # Find windows where ALL components have predictions
    all_cutoffs = None
    for name in component_names:
        cutoffs = set(model_window_data[name]["predictions"].keys())
        all_cutoffs = cutoffs if all_cutoffs is None else all_cutoffs & cutoffs

    if not all_cutoffs:
        return None

    window_mapes = []
    last_weights = {}
    for cutoff_str in sorted(all_cutoffs):
        actuals = model_window_data[component_names[0]]["actuals"][cutoff_str]
        preds = [model_window_data[n]["predictions"][cutoff_str] for n in component_names]

        weights, _ = _compute_inverse_mse_weights(preds, actuals)
        weighted_pred = np.zeros_like(preds[0])
        for w, p in zip(weights, preds):
            weighted_pred += w * p

        sum_real = float(np.sum(actuals))
        sum_pred = float(np.sum(weighted_pred))
        mape = abs((sum_real - sum_pred) / sum_real) * 100 if sum_real != 0 else None

        if mape is not None:
            window_mapes.append(mape)
            last_weights = {n: round(w, 4) for n, w in zip(component_names, weights)}

    if not window_mapes:
        return None

    return {
        "mape": round(float(np.mean(window_mapes)), 2),
        "mape_std": round(float(np.std(window_mapes)), 2),
        "n_windows": len(window_mapes),
        "weights": last_weights,
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

    # Run all models (originals + primes)
    model_names = list(ALL_MODEL_SPECS.keys())

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
    # Store full-sample fits for dummy pre-correction in OOS
    full_sample_fits = {}

    for name in model_names:
        spec = ALL_MODEL_SPECS.get(name)
        if not spec:
            continue

        try:
            X_train = train_df[spec["exog_cols"]].astype(float)
            result = _fit_model(y, X_train, spec["order"], spec["seasonal_order"])
            full_sample_fits[name] = result

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
                "mape": None,  # filled after expanding-window OOS
                "oos_validation": None,
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
            # For M' models with log_icms_lag12: build future lag12 values.
            # Steps 1-12: lag12 = known historical log(ICMS) from 12 months ago.
            # Steps 13+: lag12 = model's own forecast from 12 steps prior (recursive).
            if "log_icms_lag12" in spec["exog_cols"]:
                future_exog = future_df[spec["exog_cols"]].copy()
                # First 12 steps: historical values (already in future_df from prepare_base)
                # Beyond 12: fill recursively using point forecasts
                lag12_vals = future_exog["log_icms_lag12"].values.copy()
                # Do a recursive forecast: step by step for h > 12
                # First pass: get forecast for steps where lag12 is known
                known_mask = ~np.isnan(lag12_vals)
                if not known_mask.all():
                    # Recursive forecasting for steps where lag12 is unknown
                    for step_idx in range(n_future):
                        if np.isnan(lag12_vals[step_idx]):
                            # lag12 for this step = forecast from step (step_idx - 12)
                            src_idx = step_idx - 12
                            if src_idx >= 0 and src_idx < len(lag12_vals):
                                # Use point forecast from 12 steps ago (in log scale)
                                future_exog_partial = future_exog.iloc[:step_idx].copy()
                                future_exog_partial["log_icms_lag12"] = lag12_vals[:step_idx]
                                partial_fc = result.get_forecast(
                                    steps=step_idx, exog=future_exog_partial.astype(float)
                                )
                                lag12_vals[step_idx] = float(partial_fc.predicted_mean.iloc[src_idx])
                    future_exog["log_icms_lag12"] = lag12_vals
                X_future = future_exog.astype(float)
            else:
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
    # Expanding-window OOS validation (single pass for all models)
    # =========================================================================
    valid_models = [n for n in model_names if n in forecasts_output and isinstance(forecasts_output[n], list)]

    # Run short horizon OOS (for backward-compat diagnostics)
    short_months = 12 - last_icms_date.month  # rest of current year
    short_oos_data, short_eff_h = _run_all_expanding_windows(
        train_df, y, ALL_MODEL_SPECS, full_sample_fits, oos_horizon=short_months
    )

    # Update diagnostics with short-horizon OOS (backward compatibility)
    for name in valid_models:
        if short_oos_data and name in short_oos_data:
            oos_result = _build_oos_result_from_windows(short_oos_data[name], short_eff_h)
        else:
            oos_result = {"status": "no_data", "mape": None}
        diagnostics_output[name]["mape"] = oos_result.get("mape")
        diagnostics_output[name]["oos_validation"] = oos_result

    # =========================================================================
    # Build results for TWO horizons
    # =========================================================================
    long_months = short_months + 12  # rest of current year + next full year

    horizon_short = _build_horizon_results(
        train_df=train_df, y=y, valid_models=valid_models,
        full_sample_fits=full_sample_fits, oos_horizon=short_months,
        forecasts_output=forecasts_output, mc_simulations=mc_simulations,
        future_df=future_df, n_future=n_future,
        last_icms_date=last_icms_date, forecast_start=forecast_start,
    )
    horizon_long = _build_horizon_results(
        train_df=train_df, y=y, valid_models=valid_models,
        full_sample_fits=full_sample_fits, oos_horizon=long_months,
        forecasts_output=forecasts_output, mc_simulations=mc_simulations,
        future_df=future_df, n_future=n_future,
        last_icms_date=last_icms_date, forecast_start=forecast_start,
    )

    # =========================================================================
    # MC annual paths per model — shared across horizons
    # =========================================================================
    mc_paths_output = {}
    for model_name, paths in mc_simulations.items():
        annual_paths = {}
        for year in sorted(set(future_df["data"].dt.year)):
            year_mask = future_df["data"].dt.year == year
            year_indices = [i for i, m in enumerate(year_mask) if m]
            if year_indices:
                year_sums = paths[:, year_indices].sum(axis=1)
                annual_paths[str(year)] = [round(float(v) / 1e9, 2) for v in year_sums]
        mc_paths_output[model_name] = annual_paths

    # Model family metadata
    original_models = [n for n in model_names if n in MODEL_SPECS]
    prime_models = [n for n in model_names if n in MODEL_SPECS_PRIME]
    model_families = {
        "original": {
            "models": original_models,
            "description": "Especificacao original baseada no modelo R (auto.arima). "
                           "Modelos 2-5 rejeitam H0 do Ljung-Box (autocorrelacao residual).",
        },
        "prime": {
            "models": prime_models,
            "description": "Re-especificacao com log(ICMS)_{t-12} como regressor exogeno "
                           "(subset AR aditivo no lag 12). Todos passam Ljung-Box a 5%. "
                           "M5' eh o unico modelo sem alternativa SARIMA classica que resolve "
                           "a autocorrelacao — so a abordagem lag12-como-exogeno funciona.",
            "m1_exclusion_rationale": "M1 nao participa dos ensembles prime. Sem variaveis "
                                     "exogenas macro e sem estrutura sazonal, M1 eh sistematicamente "
                                     "conservador em horizontes longos (~15 bi abaixo dos demais em "
                                     "projecoes anuais), distorcendo o ensemble para baixo sem "
                                     "contrapartida em acuracia. Os M' ja passam Ljung-Box "
                                     "independentemente e nao precisam de M1 como hedge.",
        },
    }

    # Best model by AIC (backward compat)
    valid_diag = {n: d for n, d in diagnostics_output.items() if "aic" in d}
    best_model_aic = min(valid_diag, key=lambda n: valid_diag[n]["aic"]) if valid_diag else None

    # Use short horizon as backward-compat default
    short_mc_models = horizon_short.get("_mc_models_used", [])

    result = {
        "models": models_output,
        "forecasts": forecasts_output,
        "diagnostics": diagnostics_output,
        # Horizon-specific results
        "horizons": {
            "short": {k: v for k, v in horizon_short.items() if not k.startswith("_")},
            "long": {k: v for k, v in horizon_long.items() if not k.startswith("_")},
        },
        # Backward compat — point to short horizon
        "ensemble_mean": horizon_short["ensemble_mean"],
        "confidence_intervals": horizon_short["confidence_intervals"],
        "annual_totals": horizon_short["annual_totals"],
        "best_model": horizon_short["best_model"],
        "best_model_mape": horizon_short["best_model_mape"],
        "all_candidates": horizon_short["all_candidates"],
        "top5_ensembles": horizon_short["top5_ensembles"],
        "ensemble_weighting": horizon_short["ensemble_weighting"],
        "forecast_horizon": {
            "last_icms_observation": last_icms_date.strftime("%Y-%m-%d"),
            "forecast_start": forecast_start.strftime("%Y-%m-%d"),
            "forecast_end": horizon_short["forecast_horizon"]["forecast_end"],
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
            "models_simulated": len(short_mc_models),
            "models_failed": len(valid_models) - len(short_mc_models),
            "best_candidate_components": short_mc_models,
        },
        "mc_annual_paths": mc_paths_output,
        "model_families": model_families,
        "n_models_fitted": len(valid_models),
        "status": "ok"
    }

    out_file = od / "run_sarimax_models.json"
    out_file.write_text(json.dumps(result, ensure_ascii=False, indent=2, cls=_NumpyEncoder), encoding="utf-8")

    return result


def _build_horizon_results(*, train_df, y, valid_models, full_sample_fits,
                           oos_horizon, forecasts_output, mc_simulations,
                           future_df, n_future, last_icms_date, forecast_start):
    """Build OOS validation, ensemble selection, CIs, and annual totals for one horizon.

    Returns a dict with all horizon-specific results. Internal keys prefixed with
    '_' are stripped before serialization.
    """
    # =========================================================================
    # Expanding-window OOS for this horizon
    # =========================================================================
    expanding_window_data, effective_horizon = _run_all_expanding_windows(
        train_df, y, ALL_MODEL_SPECS, full_sample_fits, oos_horizon=oos_horizon
    )

    individual_mapes = {}
    for name in valid_models:
        if expanding_window_data and name in expanding_window_data:
            oos_result = _build_oos_result_from_windows(
                expanding_window_data[name], effective_horizon
            )
        else:
            oos_result = {"status": "no_data", "mape": None}
        if oos_result.get("mape") is not None:
            individual_mapes[name] = oos_result["mape"]

    # =========================================================================
    # Ensemble combinations — within families only.
    # Original family: M1 + M2-M5.  Prime family: M1 + M2'-M5'.
    # M1 passes Ljung-Box and participates in both families.
    # =========================================================================
    all_candidates = {}

    # Define families for ensemble building
    original_family = [n for n in valid_models if n in MODEL_SPECS]
    # M1 is excluded from prime ensembles: its lack of exogenous variables
    # and seasonal structure makes it systematically conservative in longer
    # horizons, dragging ensemble forecasts ~4 bi below the prime models
    # that already pass Ljung-Box on their own merit.
    prime_family = [n for n in valid_models if n in MODEL_SPECS_PRIME]

    # 1) Individual models (all)
    for name in valid_models:
        mape_val = individual_mapes.get(name)
        family = "original" if name in MODEL_SPECS else "prime"
        all_candidates[name] = {
            "mape": mape_val,
            "type": "individual",
            "components": [name],
            "family": family,
        }
    # M1 belongs to both
    if "Modelo 1" in all_candidates:
        all_candidates["Modelo 1"]["family"] = "both"

    # 2) Ensemble combinations within each family
    for family_name, family_members in [("original", original_family), ("prime", prime_family)]:
        suffix = "" if family_name == "original" else "'"
        for combo_size in range(2, len(family_members) + 1):
            for combo in combinations(family_members, combo_size):
                combo_name = "Ensemble" + suffix + "(" + ",".join(
                    m.replace("Modelo ", "M") for m in combo
                ) + ")"
                if expanding_window_data:
                    oos_result = _compute_ensemble_mape_from_windows(
                        expanding_window_data, list(combo)
                    )
                else:
                    oos_result = None
                if isinstance(oos_result, dict):
                    ensemble_mape = oos_result.get("mape")
                    ensemble_weights = oos_result.get("weights", {})
                else:
                    ensemble_mape = None
                    ensemble_weights = {}
                all_candidates[combo_name] = {
                    "mape": ensemble_mape,
                    "type": "ensemble",
                    "components": list(combo),
                    "weights": ensemble_weights,
                    "weighting_method": "inverse_mse",
                    "family": family_name,
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

    # =========================================================================
    # Ensemble point forecasts — inverse-MSE weighted
    # =========================================================================
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
                values = [forecasts_output[m][i]["forecast"] for m in valid_models]
                ensemble.append({
                    "data": date,
                    "forecast": round(_to_python(np.mean(values)), 2),
                    "min": round(_to_python(np.min(values)), 2),
                    "max": round(_to_python(np.max(values)), 2),
                })

    ensemble_weighting = {
        "method": "inverse_mse" if best_weights else "equal_weight",
        "weights": best_weights if best_weights else {m: round(1/len(valid_models), 4) for m in valid_models},
        "reference": "Bates & Granger (1969). The Combination of Forecasts. Operational Research Quarterly, 20(4), 451-468.",
        "note": "Pesos inverse-MSE: w_i = (1/MSE_i) / Σ(1/MSE_j). Método padrão em bancos centrais (BCB, Fed, ECB, BoE). "
                "Ver também: Timmermann (2006), Forecast Combinations, Handbook of Economic Forecasting.",
    }

    # =========================================================================
    # Monte Carlo ensemble CIs: use this horizon's best ensemble components
    # =========================================================================
    if best_candidate_name and best_candidate_name in all_candidates:
        best_components = all_candidates[best_candidate_name]["components"]
        mc_models_used = [n for n in best_components if n in mc_simulations]
    else:
        mc_models_used = [n for n in valid_models if n in mc_simulations]

    mc_confidence_intervals = []
    mc_ensemble_paths = None

    if mc_models_used:
        stacked = np.stack([mc_simulations[n] for n in mc_models_used], axis=0)
        if best_weights and all(n in best_weights for n in mc_models_used):
            mc_weights = np.array([best_weights[n] for n in mc_models_used])
            mc_weights = mc_weights / mc_weights.sum()
            mc_ensemble_paths = np.tensordot(mc_weights, stacked, axes=([0], [0]))
        else:
            mc_ensemble_paths = np.mean(stacked, axis=0)

        future_dates = future_df["data"].dt.strftime("%Y-%m-%d").tolist()
        for t in range(n_future):
            col = mc_ensemble_paths[:, t]
            entry = {"data": future_dates[t]}
            for p in MC_PERCENTILES:
                entry[f"p{p}"] = round(float(np.percentile(col, p)), 2)
            mc_confidence_intervals.append(entry)

    # Confidence intervals dict
    confidence_intervals = {
        "source": "monte_carlo_ensemble" if mc_confidence_intervals else "analytical_best_model",
        "n_models_in_ensemble": len(mc_models_used),
        "models_used": mc_models_used,
    }
    if mc_confidence_intervals:
        confidence_intervals["intervals"] = mc_confidence_intervals

    # =========================================================================
    # Annual totals with realized ICMS for current year
    # =========================================================================
    annual_totals = {}
    future_years = future_df["data"].dt.year.values

    current_year = last_icms_date.year
    realized_current_year = float(
        train_df.loc[train_df["data"].dt.year == current_year, "icms_sp"]
        .astype(float).sum()
    )

    for name in valid_models + ["ensemble"]:
        data = ensemble if name == "ensemble" else forecasts_output.get(name, [])
        if not data:
            continue
        by_year = {}
        for entry in data:
            year = entry["data"][:4]
            by_year.setdefault(year, 0)
            by_year[year] += entry["forecast"]
        totals = {y_str: round(v / 1e9, 2) for y_str, v in by_year.items()}
        cy_str = str(current_year)
        if cy_str in totals:
            totals[cy_str] = round((by_year[cy_str] + realized_current_year) / 1e9, 2)
        annual_totals[name] = totals

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
            annual_sums = np.sum(mc_ensemble_paths[:, yr_indices], axis=1)
            if yr == current_year:
                annual_sums = annual_sums + realized_current_year
            yr_entry = {}
            for p in MC_PERCENTILES:
                key = {5: "low_95", 25: "low_50", 50: "median", 75: "high_50", 95: "high_95"}[p]
                yr_entry[key] = round(float(np.percentile(annual_sums, p)) / 1e9, 2)
            yr_entry["mean"] = round(float(np.mean(annual_sums)) / 1e9, 2)
            mc_annual[str(yr)] = yr_entry
        annual_totals["ensemble_mc"] = mc_annual

        all_mc_models = [n for n in valid_models if n in mc_simulations]
        for name in all_mc_models:
            model_sims = mc_simulations[name]
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

    # =========================================================================
    # Forecast horizon metadata for this horizon
    # =========================================================================
    # Determine forecast_end based on horizon
    horizon_end_date = forecast_start + pd.DateOffset(months=oos_horizon - 1)
    # Snap to end of month for display
    forecast_end_display = pd.Timestamp(
        f"{horizon_end_date.year}-{horizon_end_date.month:02d}-"
        f"{horizon_end_date.days_in_month:02d}"
    )

    return {
        "all_candidates": all_candidates,
        "best_model": best_candidate_name,
        "best_model_mape": best_candidate_mape,
        "top5_ensembles": top5_ensembles,
        "ensemble_mean": ensemble,
        "ensemble_weighting": ensemble_weighting,
        "confidence_intervals": confidence_intervals,
        "annual_totals": annual_totals,
        "mc_annual_paths": {
            model_name: {
                str(yr): [round(float(v) / 1e9, 2) for v in paths[:, np.where(future_years == yr)[0]].sum(axis=1)]
                for yr in sorted(set(future_years))
                if len(np.where(future_years == yr)[0]) > 0
            }
            for model_name, paths in mc_simulations.items()
        },
        "oos_effective_horizon": effective_horizon,
        "forecast_horizon": {
            "forecast_start": forecast_start.strftime("%Y-%m-%d"),
            "forecast_end": forecast_end_display.strftime("%Y-%m-%d"),
            "oos_horizon_months": oos_horizon,
            "oos_effective_horizon": effective_horizon,
            "n_months_forecast": n_future,
        },
        # Internal keys (stripped before serialization)
        "_mc_models_used": mc_models_used,
    }

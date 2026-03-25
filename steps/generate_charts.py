"""Generate Plotly (interactive) and matplotlib (static) charts.

Charts produced:
  Plotly (interactive JSON):
    1. forecast_comparison — all models + ensemble
    2. annual_totals — ensemble annual totals
    3. fan_chart — historical + forecast with 50%/95% CI bands
    4. annual_totals_ci — bar chart with asymmetric error bars
    5. mape_by_model — horizontal bars for ALL candidates (individual + ensemble)
    6. exogenous_panel — 2x2 subplot: IBC-BR, IGP-DI, dias úteis, dummies

  Matplotlib (static PNG for academic report):
    1. forecast_comparison
    2. diagnostics_heatmap
    3. residual_diagnostics — 2x2 per best model: series, histogram, ACF, Q-Q
    4. fan_chart_static — historical + forecast with CI bands
"""
import json
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")


# ---------------------------------------------------------------------------
# Professional seaborn theme (applied once at module level for static charts)
# ---------------------------------------------------------------------------
_SNS_RC = {
    "figure.figsize": (14, 8),
    "axes.titlesize": 16,
    "axes.labelsize": 12,
    "xtick.labelsize": 10,
    "ytick.labelsize": 10,
    "legend.fontsize": 11,
    "grid.alpha": 0.3,
    "axes.spines.top": False,
    "axes.spines.right": False,
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load(od: Path, name: str) -> dict:
    f = od / f"{name}.json"
    return json.loads(f.read_text()) if f.exists() else {}


def _build_historical_series(base_data: list) -> pd.DataFrame:
    """Build a DataFrame of historical ICMS + exogenous from prepare_base."""
    if not base_data:
        return pd.DataFrame()
    df = pd.DataFrame(base_data)
    df["data"] = pd.to_datetime(df["data"])
    for col in [c for c in df.columns if c != "data"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def _extract_ci_monthly(sarimax_results: dict) -> list:
    """Extract monthly confidence interval data.

    Priority:
      1. confidence_intervals.monthly (Monte Carlo percentiles)
      2. Synthesize from per-model ci_lower/ci_upper of the best model
      3. Synthesize from ensemble min/max
    """
    ci_block = sarimax_results.get("confidence_intervals", {})

    # Case 1: full percentile data from Monte Carlo
    if isinstance(ci_block, dict) and "monthly" in ci_block:
        return ci_block["monthly"]

    # Case 1b: intervals key (actual key used by run_sarimax_models)
    if isinstance(ci_block, dict) and "intervals" in ci_block:
        intervals = ci_block["intervals"]
        if isinstance(intervals, list) and intervals and "p5" in intervals[0]:
            return intervals

    # Case 2: per-model CI from best model
    best = sarimax_results.get("best_model")
    forecasts = sarimax_results.get("forecasts", {})
    if best and best in forecasts and isinstance(forecasts[best], list):
        model_fc = forecasts[best]
        result = []
        for entry in model_fc:
            result.append({
                "data": entry["data"],
                "p5": entry.get("ci_lower", entry["forecast"] * 0.90),
                "p25": entry["forecast"] * 0.97,  # approximate
                "p50": entry["forecast"],
                "p75": entry["forecast"] * 1.03,
                "p95": entry.get("ci_upper", entry["forecast"] * 1.10),
            })
        return result

    # Case 3: ensemble min/max
    ensemble = sarimax_results.get("ensemble_mean", [])
    if ensemble:
        result = []
        for e in ensemble:
            fc = e["forecast"]
            lo = e.get("min", fc * 0.92)
            hi = e.get("max", fc * 1.08)
            result.append({
                "data": e["data"],
                "p5": lo * 0.95,
                "p25": lo,
                "p50": fc,
                "p75": hi,
                "p95": hi * 1.05,
            })
        return result

    return []


def _get_all_candidates(sarimax_results: dict) -> dict:
    """Extract all MAPE candidates from sarimax results.

    Tries all_candidates first, then falls back to diagnostics.
    Returns dict: {name: {"mape": float, "type": str}}.
    """
    # Prefer all_candidates if it exists
    all_cands = sarimax_results.get("all_candidates", {})
    if all_cands:
        return all_cands

    # Fallback: build from diagnostics
    diagnostics = sarimax_results.get("diagnostics", {})
    candidates = {}
    for model_name, diag in diagnostics.items():
        if isinstance(diag, dict) and "mape" in diag and diag["mape"] is not None:
            candidates[model_name] = {
                "mape": diag["mape"],
                "type": "individual",
            }
    return candidates


# ---------------------------------------------------------------------------
# Plotly interactive charts
# ---------------------------------------------------------------------------

def _generate_plotly_charts(sarimax_results: dict, base_data: list) -> dict:
    """Generate Plotly JSON chart specs."""
    try:
        import plotly.graph_objects as go
        from plotly.subplots import make_subplots
        from plotly.utils import PlotlyJSONEncoder
    except ImportError:
        return {"error": "plotly not installed"}

    forecasts = sarimax_results.get("forecasts", {})
    ensemble = sarimax_results.get("ensemble_mean", [])

    charts = {}

    # ------------------------------------------------------------------
    # Chart 1: Forecast comparison — all models + ensemble
    # ------------------------------------------------------------------
    fig = go.Figure()
    colors = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd"]
    for i, (name, model_fc) in enumerate(forecasts.items()):
        if not isinstance(model_fc, list):
            continue
        dates = [f["data"] for f in model_fc]
        values = [f["forecast"] / 1e9 for f in model_fc]
        fig.add_trace(go.Scatter(x=dates, y=values, name=name,
                                  line=dict(color=colors[i % len(colors)], width=1.5),
                                  opacity=0.6))
    if ensemble:
        dates = [e["data"] for e in ensemble]
        values = [e["forecast"] / 1e9 for e in ensemble]
        fig.add_trace(go.Scatter(x=dates, y=values, name="Ensemble",
                                  line=dict(color="black", width=3)))
    fig.update_layout(
        title="Previsão ICMS-SP por Modelo",
        xaxis_title="Data", yaxis_title="R$ bilhões",
        template="plotly_white", height=500
    )
    charts["forecast_comparison"] = json.loads(json.dumps(fig.to_dict(), cls=PlotlyJSONEncoder))

    # ------------------------------------------------------------------
    # Chart 2: Annual totals
    # ------------------------------------------------------------------
    annual = sarimax_results.get("annual_totals", {})
    if annual.get("ensemble"):
        years = list(annual["ensemble"].keys())
        fig3 = go.Figure(data=[
            go.Bar(x=years, y=[annual["ensemble"][y] for y in years],
                   text=[f"R$ {annual['ensemble'][y]:.1f}B" for y in years],
                   textposition="auto", marker_color="#1f77b4")
        ])
        fig3.update_layout(title="Previsão Anual ICMS-SP (Ensemble)",
                           yaxis_title="R$ bilhões", template="plotly_white", height=400)
        charts["annual_totals"] = json.loads(json.dumps(fig3.to_dict(), cls=PlotlyJSONEncoder))

    # ------------------------------------------------------------------
    # Chart 3: Fan chart with CI bands
    # ------------------------------------------------------------------
    ci_monthly = _extract_ci_monthly(sarimax_results)
    hist_df = _build_historical_series(base_data)

    # Resolve best model label for fan chart
    best_model = sarimax_results.get("best_model_mape") or sarimax_results.get("best_model") or "mediana"
    best_mape = None
    # Try to get MAPE from all_candidates or diagnostics
    all_cands = _get_all_candidates(sarimax_results)
    if best_model in all_cands:
        best_mape = all_cands[best_model].get("mape")
    if best_mape is None:
        diagnostics = sarimax_results.get("diagnostics", {})
        if best_model in diagnostics and isinstance(diagnostics[best_model], dict):
            best_mape = diagnostics[best_model].get("mape")

    if best_mape is not None:
        forecast_label = f"Previsão — {best_model} (MAPE {best_mape:.1f}%)"
    else:
        forecast_label = f"Previsão — {best_model}"

    if ci_monthly:
        fig_fan = go.Figure()

        # Historical series
        if not hist_df.empty and "icms_sp" in hist_df.columns:
            hist = hist_df[hist_df["icms_sp"].notna()].copy()
            fig_fan.add_trace(go.Scatter(
                x=hist["data"], y=hist["icms_sp"] / 1e9,
                name="ICMS Realizado",
                line=dict(color="#2C3E50", width=2.5),
            ))

        ci_dates = [c["data"] for c in ci_monthly]
        p5 = [c["p5"] / 1e9 for c in ci_monthly]
        p25 = [c["p25"] / 1e9 for c in ci_monthly]
        p50 = [c["p50"] / 1e9 for c in ci_monthly]
        p75 = [c["p75"] / 1e9 for c in ci_monthly]
        p95 = [c["p95"] / 1e9 for c in ci_monthly]

        # 95% band (outer)
        fig_fan.add_trace(go.Scatter(
            x=ci_dates + ci_dates[::-1],
            y=p95 + p5[::-1],
            fill="toself",
            fillcolor="rgba(31, 119, 180, 0.12)",
            line=dict(color="rgba(255,255,255,0)"),
            name="IC 95%",
            showlegend=True,
        ))

        # 50% band (inner)
        fig_fan.add_trace(go.Scatter(
            x=ci_dates + ci_dates[::-1],
            y=p75 + p25[::-1],
            fill="toself",
            fillcolor="rgba(31, 119, 180, 0.30)",
            line=dict(color="rgba(255,255,255,0)"),
            name="IC 50%",
            showlegend=True,
        ))

        # Forecast line (labeled with best model + MAPE)
        fig_fan.add_trace(go.Scatter(
            x=ci_dates, y=p50,
            name=forecast_label,
            line=dict(color="#E74C3C", width=2.5, dash="dash"),
        ))

        # Vertical separator
        if not hist_df.empty and "icms_sp" in hist_df.columns:
            last_hist = hist_df.loc[hist_df["icms_sp"].notna(), "data"].max()
            vline_x = str(last_hist)[:10]
            fig_fan.add_shape(type="line",
                x0=vline_x, x1=vline_x, y0=0, y1=1, yref="paper",
                line=dict(dash="dot", color="#7F8C8D", width=1),
            )

        fig_fan.update_layout(
            title="ICMS-SP: Histórico e Previsão com Intervalos de Confiança",
            xaxis_title="Data", yaxis_title="R$ bilhões",
            template="plotly_white", height=550,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        )
        charts["fan_chart"] = json.loads(json.dumps(fig_fan.to_dict(), cls=PlotlyJSONEncoder))

    # ------------------------------------------------------------------
    # Chart 4: Annual totals with asymmetric error bars
    # ------------------------------------------------------------------
    if ci_monthly and annual.get("ensemble"):
        ci_df = pd.DataFrame(ci_monthly)
        ci_df["data"] = pd.to_datetime(ci_df["data"])
        ci_df["year"] = ci_df["data"].dt.year.astype(str)

        annual_ci = ci_df.groupby("year").agg(
            p5_sum=("p5", "sum"),
            p50_sum=("p50", "sum"),
            p95_sum=("p95", "sum"),
        ).reset_index()

        years_ci = annual_ci["year"].tolist()
        p50_vals = (annual_ci["p50_sum"] / 1e9).tolist()
        err_minus = ((annual_ci["p50_sum"] - annual_ci["p5_sum"]) / 1e9).tolist()
        err_plus = ((annual_ci["p95_sum"] - annual_ci["p50_sum"]) / 1e9).tolist()

        fig5 = go.Figure(data=[
            go.Bar(
                x=years_ci, y=p50_vals,
                text=[f"R$ {v:.1f}B" for v in p50_vals],
                textposition="outside",
                marker_color="#3498DB",
                error_y=dict(
                    type="data", symmetric=False,
                    array=err_plus, arrayminus=err_minus,
                    color="black", thickness=1.5, width=6,
                ),
            )
        ])
        fig5.update_layout(
            title="Totais Anuais com Intervalos de Confiança (IC 95%)",
            yaxis_title="R$ bilhões", template="plotly_white", height=450,
        )
        charts["annual_totals_ci"] = json.loads(json.dumps(fig5.to_dict(), cls=PlotlyJSONEncoder))

    # ------------------------------------------------------------------
    # Chart 5: MAPE by model — ALL candidates (individual + ensemble)
    # ------------------------------------------------------------------
    all_candidates = _get_all_candidates(sarimax_results)

    if all_candidates:
        # Sort by MAPE ascending
        sorted_cands = sorted(all_candidates.items(), key=lambda x: x[1]["mape"])

        # Cap at top 15 if too many for readability
        if len(sorted_cands) > 15:
            sorted_cands = sorted_cands[:15]

        model_names_sorted = [m[0] for m in sorted_cands]
        mape_values = [m[1]["mape"] for m in sorted_cands]
        cand_types = [m[1].get("type", "individual") for m in sorted_cands]

        # Color: green for best, blue for individual, orange for ensemble
        best_name = model_names_sorted[0] if model_names_sorted else None

        def _cand_color(name, ctype):
            if name == best_name:
                return "#2ECC71"  # green for best
            elif ctype == "ensemble":
                return "#F39C12"  # orange for ensemble
            else:
                return "#3498DB"  # blue for individual

        bar_colors = [_cand_color(n, t) for n, t in zip(model_names_sorted, cand_types)]

        fig6 = go.Figure(data=[
            go.Bar(
                y=model_names_sorted, x=mape_values,
                orientation="h",
                marker_color=bar_colors,
                text=[f"{v:.1f}%" for v in mape_values],
                textposition="outside",
            )
        ])
        # Add threshold lines
        fig6.add_vline(x=5, line_dash="dash", line_color="#2ECC71", opacity=0.6,
                       annotation_text="5% (bom)")
        fig6.add_vline(x=10, line_dash="dash", line_color="#E74C3C", opacity=0.6,
                       annotation_text="10% (alerta)")

        fig6.update_layout(
            title="MAPE por Modelo — Todos os Candidatos (Out-of-Sample)",
            xaxis_title="MAPE (%)",
            template="plotly_white",
            height=max(400, len(model_names_sorted) * 28 + 120),
            yaxis=dict(autorange="reversed"),
        )
        charts["mape_by_model"] = json.loads(json.dumps(fig6.to_dict(), cls=PlotlyJSONEncoder))

    # ------------------------------------------------------------------
    # Chart 6: Exogenous variables panel — 2x2 subplot
    # ------------------------------------------------------------------
    if not hist_df.empty:
        fig7 = make_subplots(
            rows=2, cols=2,
            subplot_titles=("IBC-BR (Atividade Econômica)", "IGP-DI (Inflação)",
                            "Dias Úteis por Mês", "Dummies Estruturais"),
            vertical_spacing=0.12, horizontal_spacing=0.08,
        )

        # Determine where projections start (last observed ICMS date)
        last_obs_date = None
        if "icms_sp" in hist_df.columns:
            obs_mask = hist_df["icms_sp"].notna()
            if obs_mask.any():
                last_obs_date = hist_df.loc[obs_mask, "data"].max()

        # IBC-BR: split observed vs projected
        if "ibc_br" in hist_df.columns:
            mask = hist_df["ibc_br"].notna()
            ibc_data = hist_df.loc[mask].copy()
            if last_obs_date is not None:
                obs_part = ibc_data[ibc_data["data"] <= last_obs_date]
                proj_part = ibc_data[ibc_data["data"] > last_obs_date]
            else:
                obs_part = ibc_data
                proj_part = pd.DataFrame()

            if not obs_part.empty:
                fig7.add_trace(go.Scatter(
                    x=obs_part["data"], y=obs_part["ibc_br"],
                    name="IBC-BR (observado)", line=dict(color="#3498DB", width=2),
                    showlegend=False,
                ), row=1, col=1)
            if not proj_part.empty:
                # Connect projected to last observed point
                if not obs_part.empty:
                    bridge = pd.DataFrame([obs_part.iloc[-1]])
                    proj_with_bridge = pd.concat([bridge, proj_part], ignore_index=True)
                else:
                    proj_with_bridge = proj_part
                fig7.add_trace(go.Scatter(
                    x=proj_with_bridge["data"], y=proj_with_bridge["ibc_br"],
                    name="IBC-BR (projeção)", line=dict(color="#3498DB", width=2, dash="dash"),
                    opacity=0.6, showlegend=False,
                ), row=1, col=1)

        # IGP-DI: split observed vs projected
        if "igp_di" in hist_df.columns:
            mask = hist_df["igp_di"].notna()
            igp_data = hist_df.loc[mask].copy()
            if last_obs_date is not None:
                obs_part = igp_data[igp_data["data"] <= last_obs_date]
                proj_part = igp_data[igp_data["data"] > last_obs_date]
            else:
                obs_part = igp_data
                proj_part = pd.DataFrame()

            if not obs_part.empty:
                fig7.add_trace(go.Scatter(
                    x=obs_part["data"], y=obs_part["igp_di"],
                    name="IGP-DI (observado)", line=dict(color="#E74C3C", width=2),
                    showlegend=False,
                ), row=1, col=2)
            if not proj_part.empty:
                if not obs_part.empty:
                    bridge = pd.DataFrame([obs_part.iloc[-1]])
                    proj_with_bridge = pd.concat([bridge, proj_part], ignore_index=True)
                else:
                    proj_with_bridge = proj_part
                fig7.add_trace(go.Scatter(
                    x=proj_with_bridge["data"], y=proj_with_bridge["igp_di"],
                    name="IGP-DI (projeção)", line=dict(color="#E74C3C", width=2, dash="dash"),
                    opacity=0.6, showlegend=False,
                ), row=1, col=2)

        # Dias úteis
        if "dias_uteis" in hist_df.columns:
            mask = hist_df["dias_uteis"].notna()
            fig7.add_trace(go.Bar(
                x=hist_df.loc[mask, "data"], y=hist_df.loc[mask, "dias_uteis"],
                name="Dias úteis", marker_color="#2ECC71", opacity=0.7,
                showlegend=False,
            ), row=2, col=1)

        # Dummies
        dummy_cols = {
            "LS2008NOV": ("Crise 2008", "red"),
            "TC2020APR04": ("Pandemia 2020", "blue"),
            "TC2022OUT05": ("LC 194/2022", "orange"),
        }
        for col, (label, color) in dummy_cols.items():
            if col in hist_df.columns:
                mask = hist_df[col].notna()
                fig7.add_trace(go.Scatter(
                    x=hist_df.loc[mask, "data"], y=hist_df.loc[mask, col],
                    name=label, fill="tozeroy",
                    line=dict(color=color, width=0),
                    fillcolor=f"rgba({','.join(str(c) for c in _hex_to_rgb(color))}, 0.3)",
                ), row=2, col=2)

        fig7.update_layout(
            title="Variáveis Exógenas do Modelo",
            template="plotly_white", height=700,
            legend=dict(orientation="h", yanchor="bottom", y=-0.12, xanchor="center", x=0.5),
        )
        charts["exogenous_panel"] = json.loads(json.dumps(fig7.to_dict(), cls=PlotlyJSONEncoder))

    return charts


def _hex_to_rgb(color_name: str) -> tuple:
    """Convert CSS color name or hex to RGB tuple."""
    color_map = {
        "red": (255, 0, 0),
        "blue": (0, 0, 255),
        "orange": (255, 165, 0),
        "green": (0, 128, 0),
    }
    if color_name in color_map:
        return color_map[color_name]
    if color_name.startswith("#") and len(color_name) == 7:
        return (int(color_name[1:3], 16), int(color_name[3:5], 16), int(color_name[5:7], 16))
    return (128, 128, 128)


# ---------------------------------------------------------------------------
# Matplotlib / Seaborn static charts
# ---------------------------------------------------------------------------

def _generate_static_charts(sarimax_results: dict, output_dir: Path, base_data: list) -> dict:
    """Generate static matplotlib/seaborn PNG charts."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import seaborn as sns
        sns.set_theme(style="whitegrid", font_scale=1.1, rc=_SNS_RC)
    except ImportError:
        return {"error": "matplotlib/seaborn not installed"}

    charts = {}
    forecasts = sarimax_results.get("forecasts", {})
    ensemble = sarimax_results.get("ensemble_mean", [])
    diagnostics = sarimax_results.get("diagnostics", {})

    charts_dir = output_dir / "charts"
    charts_dir.mkdir(exist_ok=True)

    # ------------------------------------------------------------------
    # Chart 1: Forecast comparison
    # ------------------------------------------------------------------
    fig, ax = plt.subplots(figsize=(14, 6))
    for name, model_fc in forecasts.items():
        if not isinstance(model_fc, list):
            continue
        dates = pd.to_datetime([f["data"] for f in model_fc])
        values = [f["forecast"] / 1e9 for f in model_fc]
        ax.plot(dates, values, label=name, alpha=0.6, linewidth=1.5)
    if ensemble:
        dates = pd.to_datetime([e["data"] for e in ensemble])
        values = [e["forecast"] / 1e9 for e in ensemble]
        ax.plot(dates, values, label="Ensemble", color="black", linewidth=2.5)
    ax.set_title("Previsão ICMS-SP por Modelo", fontsize=14, fontweight="bold")
    ax.set_ylabel("R$ bilhões")
    ax.legend(loc="upper left")
    plt.tight_layout()
    path = charts_dir / "forecast_comparison.png"
    fig.savefig(path, dpi=300, bbox_inches="tight")
    plt.close()
    charts["forecast_comparison"] = str(path)

    # ------------------------------------------------------------------
    # Chart 2: Diagnostic heatmap
    # ------------------------------------------------------------------
    valid_diag = {n: d for n, d in diagnostics.items() if "aic" in d}
    if valid_diag:
        fig, ax = plt.subplots(figsize=(8, 5))
        metrics = ["aic", "bic", "loglik", "ljung_box_p"]
        data = []
        for name in valid_diag:
            row = [valid_diag[name].get(m, 0) for m in metrics]
            data.append(row)
        df_heat = pd.DataFrame(data, index=list(valid_diag.keys()), columns=["AIC", "BIC", "Log-Lik", "Ljung-Box p"])
        sns.heatmap(df_heat, annot=True, fmt=".1f", cmap="RdYlGn_r", ax=ax, linewidths=0.5)
        ax.set_title("Diagnósticos por Modelo", fontsize=13, fontweight="bold")
        plt.tight_layout()
        path = charts_dir / "diagnostics_heatmap.png"
        fig.savefig(path, dpi=300, bbox_inches="tight")
        plt.close()
        charts["diagnostics_heatmap"] = str(path)

    # ------------------------------------------------------------------
    # Chart 3: Residual diagnostics — 2x2 per best model
    # ------------------------------------------------------------------
    charts.update(_generate_residual_diagnostics(sarimax_results, output_dir, charts_dir))

    # ------------------------------------------------------------------
    # Chart 4: Fan chart static version
    # ------------------------------------------------------------------
    charts.update(_generate_fan_chart_static(sarimax_results, base_data, charts_dir))

    return charts


def _generate_residual_diagnostics(sarimax_results: dict, output_dir: Path, charts_dir: Path) -> dict:
    """Generate residual diagnostics: series, histogram, ACF, Q-Q plot.

    Refits the best model to extract residuals (the JSON output does not store
    raw residual arrays — only summary diagnostics).
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import seaborn as sns

    charts = {}
    best_model = sarimax_results.get("best_model")
    if not best_model:
        return charts

    # Load training data and refit the best model to get residuals
    base = _load(output_dir, "prepare_base")
    train_records = base.get("train_data", [])
    if not train_records:
        return charts

    try:
        from statsmodels.tsa.statespace.sarimax import SARIMAX
        from statsmodels.graphics.tsaplots import plot_acf
        from scipy import stats as sp_stats
    except ImportError:
        return charts

    # Import model specs (inline to avoid circular deps)
    MODEL_SPECS = {
        "Modelo 1": {
            "order": (1, 1, 1), "seasonal_order": (0, 0, 0, 12),
            "exog_cols": ["dias_uteis", "LS2008NOV", "TC2020APR04", "TC2022OUT05"],
        },
        "Modelo 2": {
            "order": (3, 1, 0), "seasonal_order": (2, 0, 0, 12),
            "exog_cols": ["igp_di_lag1", "ibc_br_lag1", "dias_uteis", "LS2008NOV", "TC2020APR04", "TC2022OUT05"],
        },
        "Modelo 3": {
            "order": (0, 1, 1), "seasonal_order": (0, 1, 1, 12),
            "exog_cols": ["igp_di", "ibc_br", "ibc_br_lag1", "dias_uteis", "LS2008NOV", "TC2020APR04", "TC2022OUT05"],
        },
        "Modelo 4": {
            "order": (0, 1, 1), "seasonal_order": (0, 1, 2, 12),
            "exog_cols": ["ibc_br", "ibc_br_lag1", "dias_uteis", "LS2008NOV", "TC2020APR04", "TC2022OUT05"],
        },
        "Modelo 5": {
            "order": (0, 1, 1), "seasonal_order": (0, 1, 2, 12),
            "exog_cols": ["igp_di", "ibc_br", "ibc_br_lag1", "LS2008NOV", "TC2020APR04", "TC2022OUT05"],
        },
    }

    spec = MODEL_SPECS.get(best_model)
    if not spec:
        return charts

    try:
        train_df = pd.DataFrame(train_records)
        train_df["data"] = pd.to_datetime(train_df["data"])
        y = np.log(train_df["icms_sp"].astype(float))
        X = train_df[spec["exog_cols"]].astype(float)

        # Contiguous slice (same logic as run_sarimax_models._fit_model)
        valid = X.notna().all(axis=1) & y.notna()
        first_valid = valid.idxmax()
        y_clean = y.loc[first_valid:].copy().ffill()
        X_clean = X.loc[first_valid:].copy().ffill()
        both_valid = X_clean.notna().all(axis=1) & y_clean.notna()
        y_clean = y_clean[both_valid]
        X_clean = X_clean[both_valid]

        model = SARIMAX(y_clean, exog=X_clean,
                        order=spec["order"], seasonal_order=spec["seasonal_order"],
                        enforce_stationarity=False, enforce_invertibility=False)
        result = model.fit(disp=False)
        resid = result.resid.dropna()
    except Exception:
        return charts

    if len(resid) < 20:
        return charts

    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle(f"Diagnóstico de Resíduos — {best_model}", fontsize=16, fontweight="bold", y=1.02)

    # (0,0) Residual time series
    ax = axes[0, 0]
    ax.plot(resid.index, resid.values, color="#2C3E50", linewidth=0.8)
    ax.axhline(y=0, color="#E74C3C", linestyle="--", linewidth=1)
    ax.fill_between(resid.index,
                     -2 * resid.std(), 2 * resid.std(),
                     alpha=0.1, color="#3498DB", label="+/- 2 sigma")
    ax.set_title("Série de Resíduos", fontweight="bold")
    ax.set_ylabel("Resíduo")
    ax.legend(loc="upper right", fontsize=9)

    # (0,1) Histogram + KDE
    ax = axes[0, 1]
    sns.histplot(resid, kde=True, ax=ax, color="#3498DB", edgecolor="white", alpha=0.7, stat="density")
    # Overlay normal curve
    x_range = np.linspace(resid.min(), resid.max(), 200)
    ax.plot(x_range, sp_stats.norm.pdf(x_range, resid.mean(), resid.std()),
            color="#E74C3C", linewidth=2, label="Normal teórica")
    ax.set_title("Histograma dos Resíduos", fontweight="bold")
    ax.set_xlabel("Resíduo")
    ax.legend(fontsize=9)

    # (1,0) ACF
    ax = axes[1, 0]
    try:
        plot_acf(resid, ax=ax, lags=min(36, len(resid) // 2 - 1),
                 alpha=0.05, zero=False, title="")
        ax.set_title("Autocorrelação (ACF)", fontweight="bold")
        ax.set_xlabel("Lag")
    except Exception:
        ax.text(0.5, 0.5, "ACF indisponível", ha="center", va="center", transform=ax.transAxes)

    # (1,1) Q-Q plot
    ax = axes[1, 1]
    try:
        sp_stats.probplot(resid, dist="norm", plot=ax)
        ax.set_title("Q-Q Plot (Normal)", fontweight="bold")
        ax.get_lines()[0].set_markersize(4)
        ax.get_lines()[0].set_markerfacecolor("#3498DB")
        ax.get_lines()[0].set_markeredgecolor("#2C3E50")
        ax.get_lines()[1].set_color("#E74C3C")
        ax.get_lines()[1].set_linewidth(2)
    except Exception:
        ax.text(0.5, 0.5, "Q-Q indisponível", ha="center", va="center", transform=ax.transAxes)

    plt.tight_layout()
    path = charts_dir / "residual_diagnostics.png"
    fig.savefig(path, dpi=300, bbox_inches="tight")
    plt.close()
    charts["residual_diagnostics"] = str(path)

    return charts


def _generate_fan_chart_static(sarimax_results: dict, base_data: list, charts_dir: Path) -> dict:
    """Generate static matplotlib fan chart with CI bands."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates

    charts = {}
    ci_monthly = _extract_ci_monthly(sarimax_results)
    if not ci_monthly:
        return charts

    hist_df = _build_historical_series(base_data)

    # Resolve best model label
    best_model = sarimax_results.get("best_model_mape") or sarimax_results.get("best_model") or "mediana"
    best_mape = None
    all_cands = _get_all_candidates(sarimax_results)
    if best_model in all_cands:
        best_mape = all_cands[best_model].get("mape")
    if best_mape is None:
        diagnostics = sarimax_results.get("diagnostics", {})
        if best_model in diagnostics and isinstance(diagnostics[best_model], dict):
            best_mape = diagnostics[best_model].get("mape")

    if best_mape is not None:
        forecast_label = f"Previsão — {best_model} (MAPE {best_mape:.1f}%)"
    else:
        forecast_label = f"Previsão — {best_model}"

    fig, ax = plt.subplots(figsize=(14, 7))

    # Historical series
    if not hist_df.empty and "icms_sp" in hist_df.columns:
        hist = hist_df[hist_df["icms_sp"].notna()].copy()
        ax.plot(hist["data"], hist["icms_sp"] / 1e9,
                label="ICMS Realizado", color="#2C3E50", linewidth=2)

    # CI data
    ci_dates = pd.to_datetime([c["data"] for c in ci_monthly])
    p5 = np.array([c["p5"] / 1e9 for c in ci_monthly])
    p25 = np.array([c["p25"] / 1e9 for c in ci_monthly])
    p50 = np.array([c["p50"] / 1e9 for c in ci_monthly])
    p75 = np.array([c["p75"] / 1e9 for c in ci_monthly])
    p95 = np.array([c["p95"] / 1e9 for c in ci_monthly])

    # 95% band (outer)
    ax.fill_between(ci_dates, p5, p95,
                     alpha=0.15, color="#1f77b4", label="IC 95%")
    # 50% band (inner)
    ax.fill_between(ci_dates, p25, p75,
                     alpha=0.30, color="#1f77b4", label="IC 50%")
    # Forecast line
    ax.plot(ci_dates, p50, color="#E74C3C", linewidth=2.5, linestyle="--",
            label=forecast_label)

    # Vertical separator
    if not hist_df.empty and "icms_sp" in hist_df.columns:
        last_hist = hist_df.loc[hist_df["icms_sp"].notna(), "data"].max()
        ax.axvline(x=last_hist, color="#7F8C8D", linestyle=":", alpha=0.7,
                   label="Início previsão")

    ax.set_title("ICMS-SP: Histórico e Previsão com Intervalos de Confiança",
                 fontsize=14, fontweight="bold", pad=15)
    ax.set_xlabel("Data")
    ax.set_ylabel("R$ bilhões")
    ax.legend(loc="upper left", frameon=True)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax.xaxis.set_major_locator(mdates.YearLocator())

    plt.tight_layout()
    path = charts_dir / "fan_chart.png"
    fig.savefig(path, dpi=300, bbox_inches="tight")
    plt.close()
    charts["fan_chart_static"] = str(path)

    return charts


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main(*, output_dir: str = "", **kwargs) -> dict:
    """Generate all charts."""
    od = Path(output_dir)

    sarimax = _load(od, "run_sarimax_models")
    base = _load(od, "prepare_base")
    base_data = base.get("base_data", [])

    plotly_charts = _generate_plotly_charts(sarimax, base_data)
    static_charts = _generate_static_charts(sarimax, od, base_data)

    result = {
        "plotly_charts": plotly_charts,
        "static_charts": static_charts,
        "chart_paths": [v for v in static_charts.values() if isinstance(v, str)],
        "status": "ok"
    }

    out_file = od / "generate_charts.json"
    out_file.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    return result

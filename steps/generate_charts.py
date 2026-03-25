"""Generate Plotly (interactive) and matplotlib (static) charts."""
import json
import base64
import io
from pathlib import Path

import numpy as np
import pandas as pd


def _load(od: Path, name: str) -> dict:
    f = od / f"{name}.json"
    return json.loads(f.read_text()) if f.exists() else {}


def _generate_plotly_charts(sarimax_results: dict) -> dict:
    """Generate Plotly JSON chart specs."""
    try:
        import plotly.graph_objects as go
        from plotly.utils import PlotlyJSONEncoder
    except ImportError:
        return {"error": "plotly not installed"}

    forecasts = sarimax_results.get("forecasts", {})
    ensemble = sarimax_results.get("ensemble_mean", [])
    diagnostics = sarimax_results.get("diagnostics", {})

    charts = {}

    # Chart 1: Forecast comparison (all models + ensemble)
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
        title="Previsao ICMS-SP por Modelo",
        xaxis_title="Data", yaxis_title="R$ bilhoes",
        template="plotly_white", height=500
    )
    charts["forecast_comparison"] = json.loads(json.dumps(fig.to_dict(), cls=PlotlyJSONEncoder))

    # Chart 2: AIC comparison bar chart
    valid_diag = {n: d for n, d in diagnostics.items() if "aic" in d}
    if valid_diag:
        fig2 = go.Figure(data=[
            go.Bar(x=list(valid_diag.keys()),
                   y=[d["aic"] for d in valid_diag.values()],
                   marker_color=["#2ca02c" if n == sarimax_results.get("best_model") else "#1f77b4"
                                  for n in valid_diag.keys()])
        ])
        fig2.update_layout(title="AIC por Modelo (menor = melhor)",
                           yaxis_title="AIC", template="plotly_white", height=400)
        charts["aic_comparison"] = json.loads(json.dumps(fig2.to_dict(), cls=PlotlyJSONEncoder))

    # Chart 3: Annual totals
    annual = sarimax_results.get("annual_totals", {})
    if annual.get("ensemble"):
        years = list(annual["ensemble"].keys())
        fig3 = go.Figure(data=[
            go.Bar(x=years, y=[annual["ensemble"][y] for y in years],
                   text=[f"R$ {annual['ensemble'][y]:.1f}B" for y in years],
                   textposition="auto", marker_color="#1f77b4")
        ])
        fig3.update_layout(title="Previsao Anual ICMS-SP (Ensemble)",
                           yaxis_title="R$ bilhoes", template="plotly_white", height=400)
        charts["annual_totals"] = json.loads(json.dumps(fig3.to_dict(), cls=PlotlyJSONEncoder))

    return charts


def _generate_static_charts(sarimax_results: dict, output_dir: Path) -> dict:
    """Generate static matplotlib/seaborn PNG charts."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import seaborn as sns
        sns.set_theme(style="whitegrid", font_scale=1.1)
    except ImportError:
        return {"error": "matplotlib/seaborn not installed"}

    charts = {}
    forecasts = sarimax_results.get("forecasts", {})
    ensemble = sarimax_results.get("ensemble_mean", [])
    diagnostics = sarimax_results.get("diagnostics", {})

    charts_dir = output_dir / "charts"
    charts_dir.mkdir(exist_ok=True)

    # Chart 1: Forecast comparison
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
    ax.set_title("Previsao ICMS-SP por Modelo", fontsize=14, fontweight="bold")
    ax.set_ylabel("R$ bilhoes")
    ax.legend(loc="upper left")
    plt.tight_layout()
    path = charts_dir / "forecast_comparison.png"
    fig.savefig(path, dpi=300, bbox_inches="tight")
    plt.close()
    charts["forecast_comparison"] = str(path)

    # Chart 2: AIC bar chart
    valid_diag = {n: d for n, d in diagnostics.items() if "aic" in d}
    if valid_diag:
        fig, ax = plt.subplots(figsize=(10, 5))
        names = list(valid_diag.keys())
        aics = [d["aic"] for d in valid_diag.values()]
        colors = ["#2ca02c" if n == sarimax_results.get("best_model") else "#4c72b0" for n in names]
        ax.barh(names, aics, color=colors)
        ax.set_xlabel("AIC")
        ax.set_title("AIC por Modelo (menor = melhor)", fontsize=13, fontweight="bold")
        plt.tight_layout()
        path = charts_dir / "aic_comparison.png"
        fig.savefig(path, dpi=300, bbox_inches="tight")
        plt.close()
        charts["aic_comparison"] = str(path)

    # Chart 3: Diagnostic heatmap
    if valid_diag:
        fig, ax = plt.subplots(figsize=(8, 5))
        metrics = ["aic", "bic", "loglik", "ljung_box_p"]
        data = []
        for name in valid_diag:
            row = [valid_diag[name].get(m, 0) for m in metrics]
            data.append(row)
        df_heat = pd.DataFrame(data, index=list(valid_diag.keys()), columns=["AIC", "BIC", "Log-Lik", "Ljung-Box p"])
        sns.heatmap(df_heat, annot=True, fmt=".1f", cmap="RdYlGn_r", ax=ax, linewidths=0.5)
        ax.set_title("Diagnosticos por Modelo", fontsize=13, fontweight="bold")
        plt.tight_layout()
        path = charts_dir / "diagnostics_heatmap.png"
        fig.savefig(path, dpi=300, bbox_inches="tight")
        plt.close()
        charts["diagnostics_heatmap"] = str(path)

    return charts


def main(*, output_dir: str = "", **kwargs) -> dict:
    """Generate all charts."""
    od = Path(output_dir)

    sarimax = _load(od, "run_sarimax_models")

    plotly_charts = _generate_plotly_charts(sarimax)
    static_charts = _generate_static_charts(sarimax, od)

    result = {
        "plotly_charts": plotly_charts,
        "static_charts": static_charts,
        "chart_paths": list(static_charts.values()) if isinstance(static_charts, dict) else [],
        "status": "ok"
    }

    out_file = od / "generate_charts.json"
    out_file.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    return result

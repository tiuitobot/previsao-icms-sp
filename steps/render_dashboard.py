"""Render interactive dashboard HTML with Plotly charts and KPIs."""
import json
import os
from pathlib import Path


def _load(od: Path, name: str) -> dict:
    f = od / f"{name}.json"
    return json.loads(f.read_text()) if f.exists() else {}


def main(*, output_dir: str = "", template_name: str = "", **kwargs) -> dict:
    """Render dashboard HTML."""
    od = Path(output_dir)
    report_dir = od / "report"
    report_dir.mkdir(exist_ok=True)

    sarimax = _load(od, "run_sarimax_models")
    charts = _load(od, "generate_charts")
    qualitative = _load(od, "qualitative_analysis")

    plotly_charts = charts.get("plotly_charts", {})
    annual_totals = sarimax.get("annual_totals", {}).get("ensemble", {})
    best_model = sarimax.get("best_model", "N/A")
    diagnostics = sarimax.get("diagnostics", {})
    best_aic = diagnostics.get(best_model, {}).get("aic", "N/A") if best_model != "N/A" else "N/A"

    # Load Plotly JS inline (no CDN dependency)
    try:
        import plotly
        plotly_js_path = os.path.join(os.path.dirname(plotly.__file__), "package_data", "plotly.min.js")
        plotly_js = Path(plotly_js_path).read_text(encoding="utf-8")
    except Exception:
        plotly_js = "/* plotly not available */"

    # Build Plotly script includes
    plotly_scripts = []
    for chart_id, chart_data in plotly_charts.items():
        if isinstance(chart_data, dict) and "error" not in chart_data:
            plotly_scripts.append(f"""
            <div id="{chart_id}" style="width:100%;margin:20px 0;"></div>
            <script>
                Plotly.newPlot('{chart_id}', {json.dumps(chart_data.get('data', []))}, {json.dumps(chart_data.get('layout', {}))}, {{responsive: true}});
            </script>
            """)

    # KPIs
    kpi_html = ""
    for year, value in sorted(annual_totals.items()):
        kpi_html += f"""
        <div class="kpi-card">
            <div class="kpi-value">R$ {value:.1f}B</div>
            <div class="kpi-label">ICMS-SP {year}</div>
        </div>
        """

    # Qualitative section
    qual_html = ""
    if qualitative and qualitative.get("status") == "ok":
        exec_summary = qualitative.get("executive_summary", "")
        qual_html = f"""
        <section class="qualitative">
            <h2>Analise Qualitativa</h2>
            <div class="markdown-content">{exec_summary}</div>
        </section>
        """

    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Dashboard — Previsao ICMS-SP</title>
    <script>{plotly_js}</script>
    <style>
        :root {{
            --primary: #1a365d;
            --accent: #2b6cb0;
            --bg: #f7fafc;
            --card-bg: #ffffff;
            --text: #2d3748;
            --border: #e2e8f0;
        }}
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: 'Inter', -apple-system, sans-serif; background: var(--bg); color: var(--text); }}
        header {{
            background: linear-gradient(135deg, var(--primary), var(--accent));
            color: white; padding: 2rem 3rem;
        }}
        header h1 {{ font-size: 1.8rem; font-weight: 700; }}
        header p {{ opacity: 0.85; margin-top: 0.5rem; }}
        .kpi-row {{
            display: flex; gap: 1.5rem; padding: 1.5rem 3rem; flex-wrap: wrap;
        }}
        .kpi-card {{
            background: var(--card-bg); border-radius: 12px; padding: 1.5rem 2rem;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1); flex: 1; min-width: 200px; text-align: center;
        }}
        .kpi-value {{ font-size: 2rem; font-weight: 700; color: var(--primary); }}
        .kpi-label {{ font-size: 0.9rem; color: #718096; margin-top: 0.3rem; }}
        .content {{ padding: 0 3rem 3rem; }}
        section {{ background: var(--card-bg); border-radius: 12px; padding: 2rem; margin-bottom: 1.5rem;
                   box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
        h2 {{ color: var(--primary); margin-bottom: 1rem; font-size: 1.3rem; }}
        .info-row {{ display: flex; gap: 1rem; margin-bottom: 1.5rem; flex-wrap: wrap; }}
        .info-badge {{
            background: #ebf8ff; color: var(--accent); padding: 0.4rem 1rem;
            border-radius: 20px; font-size: 0.85rem; font-weight: 600;
        }}
        footer {{ text-align: center; padding: 2rem; color: #a0aec0; font-size: 0.8rem; }}
    </style>
</head>
<body>
    <header>
        <h1>Previsao de Arrecadacao ICMS-SP</h1>
        <p>SEFAZ — Assessoria de Economia e Financas Publicas</p>
    </header>

    <div class="kpi-row">
        {kpi_html}
        <div class="kpi-card">
            <div class="kpi-value" style="font-size:1.3rem;">{best_model}</div>
            <div class="kpi-label">Melhor modelo (AIC: {best_aic})</div>
        </div>
    </div>

    <div class="content">
        <section>
            <h2>Projecoes por Modelo</h2>
            <div class="info-row">
                <span class="info-badge">{sarimax.get('n_models_fitted', 0)} modelos ajustados</span>
                <span class="info-badge">Ensemble = media dos modelos</span>
            </div>
            {''.join(plotly_scripts)}
        </section>

        {qual_html}
    </div>

    <footer>
        Pipeline Engine v1 — Gerado automaticamente
    </footer>
</body>
</html>"""

    html_path = report_dir / "dashboard.html"
    html_path.write_text(html, encoding="utf-8")

    result = {
        "html_path": str(html_path),
        "status": "ok"
    }

    out_file = od / "render_dashboard.json"
    out_file.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    return result

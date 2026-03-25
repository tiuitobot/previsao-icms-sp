"""Render academic-style HTML report with methodology and diagnostics."""
import json
from pathlib import Path


def _load(od: Path, name: str) -> dict:
    f = od / f"{name}.json"
    return json.loads(f.read_text()) if f.exists() else {}


def main(*, output_dir: str = "", template_name: str = "", **kwargs) -> dict:
    """Render academic report HTML."""
    od = Path(output_dir)
    report_dir = od / "report"
    report_dir.mkdir(exist_ok=True)

    sarimax = _load(od, "run_sarimax_models")
    charts = _load(od, "generate_charts")
    validation = _load(od, "validate_forecasts")

    static_charts = charts.get("static_charts", {})
    models = sarimax.get("models", {})
    diagnostics = sarimax.get("diagnostics", {})
    adf = sarimax.get("adf_test", {})
    annual_totals = sarimax.get("annual_totals", {})

    # Model specification table
    model_table_rows = ""
    for name, model in models.items():
        if "error" in model:
            continue
        spec = model.get("specification", "")
        cols = ", ".join(model.get("exog_cols", []))
        diag = diagnostics.get(name, {})
        aic = diag.get("aic", "—")
        bic = diag.get("bic", "—")
        lb_p = diag.get("ljung_box_p", "—")
        model_table_rows += f"""
        <tr>
            <td><strong>{name}</strong></td>
            <td>{spec}</td>
            <td>{cols}</td>
            <td>{aic}</td>
            <td>{bic}</td>
            <td>{lb_p}</td>
        </tr>"""

    # Annual forecast table
    annual_rows = ""
    if annual_totals:
        years = sorted(set(y for m in annual_totals.values() for y in m.keys()))
        for year in years:
            row = f"<tr><td><strong>{year}</strong></td>"
            for model_name in list(annual_totals.keys()):
                val = annual_totals[model_name].get(year, "—")
                if isinstance(val, (int, float)):
                    row += f"<td>R$ {val:.2f}B</td>"
                else:
                    row += f"<td>{val}</td>"
            row += "</tr>"
            annual_rows += row
        model_headers = "".join(f"<th>{n}</th>" for n in annual_totals.keys())
    else:
        model_headers = ""

    # Chart images (base64 or paths)
    chart_imgs = ""
    for chart_name, chart_path in static_charts.items():
        if isinstance(chart_path, str) and not chart_path.startswith("error"):
            chart_imgs += f"""
            <figure>
                <img src="{chart_path}" alt="{chart_name}" style="max-width:100%;">
                <figcaption>{chart_name.replace('_', ' ').title()}</figcaption>
            </figure>"""

    # Validation results
    validation_html = ""
    checks = validation.get("checks", []) if isinstance(validation, dict) else []
    if checks:
        validation_rows = ""
        for check in checks:
            icon = "pass" if check.get("passed") else "FAIL"
            color = "#38a169" if check.get("passed") else "#e53e3e"
            validation_rows += f"""
            <tr>
                <td style="color:{color};font-weight:bold;">{icon}</td>
                <td>{check.get('name', '')}</td>
                <td>{check.get('detail', '')}</td>
            </tr>"""
        validation_html = f"""
        <section>
            <h2>5. Validacao</h2>
            <table>
                <tr><th></th><th>Teste</th><th>Resultado</th></tr>
                {validation_rows}
            </table>
        </section>"""

    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <title>Previsao ICMS-SP — Relatorio Tecnico</title>
    <style>
        body {{
            font-family: 'Georgia', 'Times New Roman', serif;
            max-width: 900px; margin: 0 auto; padding: 2rem;
            line-height: 1.7; color: #1a202c;
        }}
        h1 {{ text-align: center; font-size: 1.6rem; margin-bottom: 0.5rem; }}
        .subtitle {{ text-align: center; color: #718096; margin-bottom: 2rem; }}
        h2 {{ color: #2d3748; border-bottom: 2px solid #e2e8f0; padding-bottom: 0.3rem; margin-top: 2rem; }}
        table {{ width: 100%; border-collapse: collapse; margin: 1rem 0; font-size: 0.9rem; }}
        th, td {{ border: 1px solid #e2e8f0; padding: 0.5rem 0.8rem; text-align: left; }}
        th {{ background: #f7fafc; font-weight: 600; }}
        figure {{ margin: 1.5rem 0; text-align: center; }}
        figcaption {{ font-size: 0.85rem; color: #718096; margin-top: 0.5rem; font-style: italic; }}
        .abstract {{ background: #f7fafc; padding: 1.5rem; border-left: 4px solid #2b6cb0; margin: 1.5rem 0; }}
        section {{ margin-bottom: 2rem; }}
        footer {{ text-align: center; color: #a0aec0; font-size: 0.8rem; margin-top: 3rem; border-top: 1px solid #e2e8f0; padding-top: 1rem; }}
    </style>
</head>
<body>
    <h1>Previsao de Arrecadacao do ICMS-SP</h1>
    <p class="subtitle">AEFP — Assessoria de Economia e Financas Publicas<br>Relatorio Tecnico — Anexo Metodologico</p>

    <div class="abstract">
        <strong>Resumo:</strong> Este anexo documenta a especificacao e diagnosticos dos 5 modelos SARIMAX utilizados para
        previsao da arrecadacao mensal do ICMS no Estado de Sao Paulo. Variaveis exogenas incluem IBC-BR (BCB), IGP-DI (IPEA),
        dias uteis e dummies estruturais. Melhor modelo: <strong>{sarimax.get('best_model', 'N/A')}</strong> por criterio AIC.
    </div>

    <section>
        <h2>1. Teste de Estacionariedade</h2>
        <p>Teste Augmented Dickey-Fuller sobre log(ICMS_SP) em primeira diferenca:</p>
        <table>
            <tr><th>Estatistica ADF</th><th>p-valor</th><th>Resultado</th></tr>
            <tr>
                <td>{adf.get('statistic', '—')}</td>
                <td>{adf.get('p_value', '—')}</td>
                <td>{'Estacionario' if adf.get('stationary') else 'Nao estacionario'}</td>
            </tr>
        </table>
    </section>

    <section>
        <h2>2. Especificacao dos Modelos</h2>
        <table>
            <tr><th>Modelo</th><th>Especificacao</th><th>Variaveis Exogenas</th><th>AIC</th><th>BIC</th><th>Ljung-Box p</th></tr>
            {model_table_rows}
        </table>
    </section>

    <section>
        <h2>3. Previsoes Anuais</h2>
        <table>
            <tr><th>Ano</th>{model_headers}</tr>
            {annual_rows}
        </table>
    </section>

    <section>
        <h2>4. Graficos</h2>
        {chart_imgs}
    </section>

    {validation_html}

    <section>
        <h2>6. Referencias</h2>
        <ul>
            <li>BCB — Sistema Gerenciador de Series Temporais (SGS), serie 24363 (IBC-BR)</li>
            <li>IPEA Data — IGP-DI mensal (IGP12_IGPDI12)</li>
            <li>BCB — Sistema de Expectativas de Mercado (Focus)</li>
            <li>Hamilton, J.D. (1994). Time Series Analysis. Princeton University Press.</li>
            <li>Hyndman, R.J. & Athanasopoulos, G. (2021). Forecasting: Principles and Practice, 3rd ed.</li>
        </ul>
    </section>

    <footer>
        Pipeline Engine v1 — Gerado automaticamente
    </footer>
</body>
</html>"""

    html_path = report_dir / "academic_report.html"
    html_path.write_text(html, encoding="utf-8")

    result = {
        "html_path": str(html_path),
        "status": "ok"
    }

    out_file = od / "render_academic.json"
    out_file.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    return result

"""Render interactive dashboard HTML with Plotly charts, KPIs, diagnostics, and scenarios."""
import json
import os
from datetime import datetime, date
from pathlib import Path


def _load(od: Path, name: str) -> dict:
    f = od / f"{name}.json"
    return json.loads(f.read_text()) if f.exists() else {}


def _fmt_brl(value_raw: float, unit: str = "bi") -> str:
    """Format a number as R$ with thousands separators.

    *value_raw* is in the unit specified by *unit*:
      - 'bi'  → already in billions  (e.g. 225.37)
      - 'raw' → in reais             (e.g. 2.2537e11)
    Returns e.g. 'R$ 225,37 bi' or 'R$ 22.537.000.000'.
    """
    if unit == "bi":
        formatted = f"{value_raw:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        return f"R$ {formatted} bi"
    else:
        formatted = f"{value_raw:,.0f}".replace(",", "X").replace(".", ",").replace("X", ".")
        return f"R$ {formatted}"


def _fmt_pct(value: float, decimals: int = 2) -> str:
    return f"{value:.{decimals}f}%"


def _freshness_color(last_date_str: str | None) -> tuple[str, str]:
    """Return (css_class, label) based on data age."""
    if not last_date_str:
        return "freshness-red", "sem dados"
    try:
        last = datetime.strptime(last_date_str[:10], "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return "freshness-red", "data invalida"
    age_days = (date.today() - last).days
    if age_days < 45:
        return "freshness-green", f"{age_days}d atras"
    elif age_days < 100:
        return "freshness-yellow", f"{age_days}d atras"
    else:
        return "freshness-red", f"{age_days}d atras"


def _build_monthly_forecast_table(sarimax: dict) -> str:
    """Expandable table: monthly forecasts per model + ensemble + CI."""
    forecasts = sarimax.get("forecasts", {})
    ensemble = sarimax.get("ensemble_mean", [])
    ci = sarimax.get("confidence_intervals", {})
    ci_intervals = ci.get("intervals", [])

    model_names = sorted([k for k in forecasts if isinstance(forecasts[k], list)])
    if not model_names and not ensemble:
        return ""

    # Build date-indexed lookup
    dates = []
    if ensemble:
        dates = [e["data"] for e in ensemble]
    elif model_names:
        dates = [e["data"] for e in forecasts[model_names[0]]]

    if not dates:
        return ""

    # Build CI lookup by date
    ci_by_date = {}
    for entry in ci_intervals:
        ci_by_date[entry["data"]] = entry

    # Build model lookups by date
    model_by_date = {}
    for m in model_names:
        model_by_date[m] = {}
        for entry in forecasts[m]:
            model_by_date[m][entry["data"]] = entry

    # Ensemble lookup
    ens_by_date = {}
    for entry in ensemble:
        ens_by_date[entry["data"]] = entry

    # Header
    header_cells = "<th>Data</th>"
    for m in model_names:
        short = m.replace("Modelo ", "M")
        header_cells += f"<th>{short}</th>"
    header_cells += "<th>Ensemble</th><th>IC Inf</th><th>IC Sup</th>"

    rows = ""
    for d in dates:
        month_label = f"{d[5:7]}/{d[:4]}"
        cells = f"<td>{month_label}</td>"
        for m in model_names:
            entry = model_by_date[m].get(d, {})
            val = entry.get("forecast", 0)
            cells += f'<td class="number">{_fmt_brl(val / 1e9)}</td>'
        ens = ens_by_date.get(d, {})
        ens_val = ens.get("forecast", 0)
        cells += f'<td class="number ensemble-col">{_fmt_brl(ens_val / 1e9)}</td>'
        ci_entry = ci_by_date.get(d, {})
        ci_lo = ci_entry.get("ci_lower", 0)
        ci_hi = ci_entry.get("ci_upper", 0)
        cells += f'<td class="number">{_fmt_brl(ci_lo / 1e9)}</td>'
        cells += f'<td class="number">{_fmt_brl(ci_hi / 1e9)}</td>'
        rows += f"<tr>{cells}</tr>\n"

    return f"""
    <section>
        <h2>Previsoes Mensais por Modelo</h2>
        <details>
            <summary>Expandir tabela completa ({len(dates)} meses)</summary>
            <div class="table-scroll">
                <table class="data-table">
                    <thead><tr>{header_cells}</tr></thead>
                    <tbody>{rows}</tbody>
                </table>
            </div>
        </details>
    </section>
    """


def _build_diagnostics_card(sarimax: dict) -> str:
    """Card with model diagnostics table: AIC, BIC, MAPE, Ljung-Box, verdict."""
    diagnostics = sarimax.get("diagnostics", {})
    best_model = sarimax.get("best_model")

    if not diagnostics:
        return ""

    rows = ""
    for name in sorted(diagnostics.keys()):
        diag = diagnostics[name]
        if "error" in diag:
            rows += f"""<tr class="diag-error"><td>{name}</td>
                <td colspan="5">Erro: {diag['error']}</td></tr>"""
            continue

        aic = diag.get("aic", "—")
        bic = diag.get("bic", "—")
        lb_p = diag.get("ljung_box_p")
        lb_pass = diag.get("ljung_box_pass")

        lb_display = f"{lb_p:.4f}" if lb_p is not None else "N/A"
        if lb_pass is True:
            verdict_icon = '<span class="verdict-pass">&#10003; OK</span>'
        elif lb_pass is False:
            verdict_icon = '<span class="verdict-fail">&#10007; Falhou</span>'
        else:
            verdict_icon = '<span class="verdict-warn">? N/A</span>'

        row_class = "best-model-row" if name == best_model else ""
        best_tag = ' <span class="best-tag">MELHOR</span>' if name == best_model else ""
        desc = diag.get("description", "")
        n_obs = diag.get("n_obs", "—")

        rows += f"""<tr class="{row_class}">
            <td>{name}{best_tag}<br><small class="desc-text">{desc}</small></td>
            <td class="number">{aic}</td>
            <td class="number">{bic}</td>
            <td class="number">{n_obs}</td>
            <td class="number">{lb_display}</td>
            <td>{verdict_icon}</td>
        </tr>"""

    return f"""
    <section>
        <h2>Diagnosticos dos Modelos</h2>
        <table class="data-table diagnostics-table">
            <thead>
                <tr>
                    <th>Modelo</th>
                    <th>AIC</th>
                    <th>BIC</th>
                    <th>N Obs</th>
                    <th>Ljung-Box p</th>
                    <th>Veredicto</th>
                </tr>
            </thead>
            <tbody>{rows}</tbody>
        </table>
    </section>
    """


def _build_ci_summary(sarimax: dict) -> str:
    """Per-year confidence interval summary with uncertainty width indicator."""
    annual_totals = sarimax.get("annual_totals", {})
    forecasts = sarimax.get("forecasts", {})
    ci_data = sarimax.get("confidence_intervals", {})
    ci_intervals = ci_data.get("intervals", [])

    # Compute per-year aggregates from individual model forecasts
    # For each year: ensemble point estimate, min across models, max across models,
    # and CI lower/upper from the best model
    years = sorted(annual_totals.get("ensemble", {}).keys())
    if not years:
        return ""

    # Aggregate CI intervals by year
    ci_by_year = {}
    for entry in ci_intervals:
        year = entry["data"][:4]
        ci_by_year.setdefault(year, {"lowers": [], "uppers": []})
        ci_by_year[year]["lowers"].append(entry.get("ci_lower", 0))
        ci_by_year[year]["uppers"].append(entry.get("ci_upper", 0))

    # Min/max from individual models by year
    model_range_by_year = {}
    for model_name, model_fc in forecasts.items():
        if not isinstance(model_fc, list):
            continue
        for entry in model_fc:
            year = entry["data"][:4]
            model_range_by_year.setdefault(year, [])
            model_range_by_year[year].append(entry.get("forecast", 0))

    rows = ""
    for year in years:
        ens_val = annual_totals.get("ensemble", {}).get(year, 0)  # already in billions

        # Model spread (50% range proxy: interquartile from models)
        model_vals = model_range_by_year.get(year, [])
        # Aggregate to annual per model
        model_annual = {}
        for model_name, model_fc in forecasts.items():
            if not isinstance(model_fc, list):
                continue
            annual_sum = sum(e["forecast"] for e in model_fc if e["data"][:4] == year)
            model_annual[model_name] = annual_sum / 1e9
        model_annual_vals = sorted(model_annual.values())

        if len(model_annual_vals) >= 4:
            q1 = model_annual_vals[1]  # ~25th percentile
            q3 = model_annual_vals[-2]  # ~75th percentile
        elif len(model_annual_vals) >= 2:
            q1 = model_annual_vals[0]
            q3 = model_annual_vals[-1]
        else:
            q1 = ens_val
            q3 = ens_val

        # 95% CI from best model
        ci_year = ci_by_year.get(year, {"lowers": [], "uppers": []})
        ci_lower_sum = sum(ci_year["lowers"]) / 1e9 if ci_year["lowers"] else ens_val * 0.9
        ci_upper_sum = sum(ci_year["uppers"]) / 1e9 if ci_year["uppers"] else ens_val * 1.1

        # Uncertainty width as percentage of point estimate
        uncertainty_pct = ((ci_upper_sum - ci_lower_sum) / ens_val * 100) if ens_val > 0 else 0
        bar_width = min(uncertainty_pct * 2, 100)  # Scale for visual bar

        if uncertainty_pct < 10:
            bar_color = "var(--success)"
        elif uncertainty_pct < 25:
            bar_color = "var(--warning)"
        else:
            bar_color = "var(--danger)"

        rows += f"""<tr>
            <td><strong>{year}</strong></td>
            <td class="number">{_fmt_brl(ens_val)}</td>
            <td class="number">{_fmt_brl(q1)} — {_fmt_brl(q3)}</td>
            <td class="number">{_fmt_brl(ci_lower_sum)} — {_fmt_brl(ci_upper_sum)}</td>
            <td>
                <div class="uncertainty-bar">
                    <div class="uncertainty-fill" style="width:{bar_width:.0f}%;background:{bar_color};"></div>
                </div>
                <small>{uncertainty_pct:.1f}%</small>
            </td>
        </tr>"""

    return f"""
    <section>
        <h2>Intervalos de Confianca</h2>
        <p class="section-desc">Estimativa pontual (ensemble), faixa entre modelos e IC 95% do melhor modelo.</p>
        <table class="data-table">
            <thead>
                <tr>
                    <th>Ano</th>
                    <th>Estimativa Pontual</th>
                    <th>Faixa entre Modelos</th>
                    <th>IC 95%</th>
                    <th>Incerteza</th>
                </tr>
            </thead>
            <tbody>{rows}</tbody>
        </table>
    </section>
    """


def _build_scenario_summary(sarimax: dict) -> str:
    """Scenario cards: pessimistic (5th pct), base (median), optimistic (95th pct)."""
    annual_totals = sarimax.get("annual_totals", {})
    forecasts = sarimax.get("forecasts", {})
    ci_data = sarimax.get("confidence_intervals", {})
    ci_intervals = ci_data.get("intervals", [])

    years = sorted(annual_totals.get("ensemble", {}).keys())
    if not years:
        return ""

    # Aggregate CI by year
    ci_by_year = {}
    for entry in ci_intervals:
        year = entry["data"][:4]
        ci_by_year.setdefault(year, {"lowers": [], "uppers": []})
        ci_by_year[year]["lowers"].append(entry.get("ci_lower", 0))
        ci_by_year[year]["uppers"].append(entry.get("ci_upper", 0))

    year_cards = ""
    for year in years:
        ens_val = annual_totals.get("ensemble", {}).get(year, 0)
        ci_year = ci_by_year.get(year, {"lowers": [], "uppers": []})
        pessimistic = sum(ci_year["lowers"]) / 1e9 if ci_year["lowers"] else ens_val * 0.9
        optimistic = sum(ci_year["uppers"]) / 1e9 if ci_year["uppers"] else ens_val * 1.1

        year_cards += f"""
        <div class="scenario-year">
            <h3>{year}</h3>
            <div class="scenario-grid">
                <div class="scenario-card scenario-pessimistic">
                    <div class="scenario-icon">&#9660;</div>
                    <div class="scenario-label">Pessimista (P5)</div>
                    <div class="scenario-value">{_fmt_brl(pessimistic)}</div>
                </div>
                <div class="scenario-card scenario-base">
                    <div class="scenario-icon">&#9654;</div>
                    <div class="scenario-label">Base (Mediana)</div>
                    <div class="scenario-value">{_fmt_brl(ens_val)}</div>
                </div>
                <div class="scenario-card scenario-optimistic">
                    <div class="scenario-icon">&#9650;</div>
                    <div class="scenario-label">Otimista (P95)</div>
                    <div class="scenario-value">{_fmt_brl(optimistic)}</div>
                </div>
            </div>
        </div>
        """

    return f"""
    <section>
        <h2>Cenarios de Arrecadacao</h2>
        <p class="section-desc">Baseado nos intervalos de confianca do melhor modelo e dispersao entre modelos.</p>
        {year_cards}
    </section>
    """


def _build_freshness_indicator(macro: dict, sefaz: dict) -> str:
    """Data freshness indicator with color-coded status."""
    freshness = macro.get("data_freshness", {})
    icms_last = sefaz.get("last_observed_date")

    sources = [
        ("IBC-BR (BCB)", freshness.get("ibc_br_last"), "Indice de Atividade Economica"),
        ("IGP-DI (IPEA)", freshness.get("igp_di_last"), "Indice de Precos"),
        ("ICMS-SP (SEFAZ)", icms_last, "Arrecadacao Historica"),
    ]

    cards = ""
    for name, last_date, desc in sources:
        css_class, label = _freshness_color(last_date)
        date_display = last_date[:10] if last_date else "—"
        cards += f"""
        <div class="freshness-card {css_class}">
            <div class="freshness-source">{name}</div>
            <div class="freshness-date">{date_display}</div>
            <div class="freshness-age">{label}</div>
            <div class="freshness-desc">{desc}</div>
        </div>
        """

    return f"""
    <section>
        <h2>Atualidade dos Dados</h2>
        <div class="freshness-grid">{cards}</div>
    </section>
    """


def _build_validation_card(validation: dict) -> str:
    """Validation results summary with check/fail icons."""
    checks = validation.get("checks", [])
    warnings_list = validation.get("warnings", [])
    verdict = validation.get("verdict", "unknown")
    passed = validation.get("passed", 0)
    failed = validation.get("failed", 0)

    if not checks:
        return ""

    verdict_class = {
        "pass": "verdict-pass-card",
        "warn": "verdict-warn-card",
        "fail": "verdict-fail-card",
    }.get(verdict, "verdict-warn-card")

    verdict_label = {
        "pass": "&#10003; Todas as verificacoes OK",
        "warn": "&#9888; Atencao: verificacoes com ressalvas",
        "fail": "&#10007; Falhas detectadas",
    }.get(verdict, "Status desconhecido")

    check_rows = ""
    for check in checks:
        icon = '<span class="verdict-pass">&#10003;</span>' if check.get("passed") else '<span class="verdict-fail">&#10007;</span>'
        check_rows += f"""<tr>
            <td>{icon}</td>
            <td>{check.get('name', '—')}</td>
            <td>{check.get('detail', '—')}</td>
        </tr>"""

    warnings_html = ""
    if warnings_list:
        items = "".join(f"<li>{w}</li>" for w in warnings_list)
        warnings_html = f"""
        <details class="warnings-detail">
            <summary>&#9888; {len(warnings_list)} aviso(s)</summary>
            <ul>{items}</ul>
        </details>
        """

    return f"""
    <section>
        <h2>Validacao das Previsoes</h2>
        <div class="verdict-banner {verdict_class}">
            {verdict_label}
            <span class="verdict-stats">{passed} passou, {failed} falhou</span>
        </div>
        <table class="data-table validation-table">
            <thead><tr><th></th><th>Verificacao</th><th>Detalhe</th></tr></thead>
            <tbody>{check_rows}</tbody>
        </table>
        {warnings_html}
    </section>
    """


def _build_methodology_section(sarimax: dict) -> str:
    """Collapsible methodology section."""
    adf = sarimax.get("adf_test", {})
    n_models = sarimax.get("n_models_fitted", 0)
    ci_data = sarimax.get("confidence_intervals", {})
    ci_model = ci_data.get("model", "N/A")

    return f"""
    <section>
        <h2>Metodologia</h2>
        <details>
            <summary>Expandir descricao metodologica</summary>
            <div class="methodology-content">
                <h3>Modelos SARIMAX</h3>
                <p>Foram ajustados <strong>{n_models} modelos</strong> SARIMAX (Seasonal AutoRegressive Integrated Moving Average with eXogenous regressors)
                com diferentes especificacoes de ordem autorregressiva, diferenciacao e media movel, alem de variaveis exogenas distintas.</p>

                <h3>Variaveis Exogenas</h3>
                <ul>
                    <li><strong>IBC-BR:</strong> Indice de Atividade Economica do Banco Central (proxy do PIB mensal)</li>
                    <li><strong>IGP-DI:</strong> Indice Geral de Precos (captura efeito inflacionario na base tributavel)</li>
                    <li><strong>Dias uteis:</strong> Controle para efeito calendario</li>
                    <li><strong>Dummies:</strong> LS2008NOV (crise financeira), TC2020APR04 (COVID), TC2022OUT05 (ajuste fiscal)</li>
                </ul>

                <h3>Teste de Estacionariedade (ADF)</h3>
                <p>Augmented Dickey-Fuller sobre a primeira diferenca da serie em log:
                   estatistica = <code>{adf.get('statistic', 'N/A')}</code>,
                   p-valor = <code>{adf.get('p_value', 'N/A')}</code>
                   &mdash; {"Serie estacionaria" if adf.get('stationary') else "Nao-estacionaria"}.</p>

                <h3>Selecao do Melhor Modelo</h3>
                <p>O modelo com menor AIC (Akaike Information Criterion) foi selecionado como referencia para os intervalos de confianca.
                   A previsao pontual utiliza o <em>ensemble</em> (media aritmetica de todos os modelos validos).</p>

                <h3>Intervalos de Confianca</h3>
                <p>IC 95% derivados do modelo <strong>{ci_model}</strong> via previsao fora da amostra (<code>get_forecast</code>).
                   A transformacao exponencial e aplicada apos a previsao em log para retornar a escala original.</p>

                <h3>Diagnosticos</h3>
                <ul>
                    <li><strong>AIC / BIC:</strong> Criterios de informacao para comparacao entre modelos (menor = melhor)</li>
                    <li><strong>Ljung-Box:</strong> Teste de autocorrelacao dos residuos (p > 0.05 = residuos nao autocorrelacionados)</li>
                </ul>

                <h3>Cenarios</h3>
                <p><strong>Pessimista:</strong> Limite inferior do IC 95% (percentil ~2.5%). <br>
                   <strong>Base:</strong> Ensemble mean dos modelos. <br>
                   <strong>Otimista:</strong> Limite superior do IC 95% (percentil ~97.5%).</p>
            </div>
        </details>
    </section>
    """


CSS = """
    :root {
        --primary: #1a365d;
        --primary-light: #2b6cb0;
        --accent: #3182ce;
        --bg: #f7fafc;
        --card-bg: #ffffff;
        --text: #2d3748;
        --text-light: #718096;
        --border: #e2e8f0;
        --success: #38a169;
        --warning: #d69e2e;
        --danger: #e53e3e;
        --info: #3182ce;
    }
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body {
        font-family: 'Inter', 'Segoe UI', -apple-system, sans-serif;
        background: var(--bg);
        color: var(--text);
        line-height: 1.6;
    }

    /* Header */
    header {
        background: linear-gradient(135deg, var(--primary), var(--primary-light));
        color: white;
        padding: 2.5rem 3rem;
    }
    header h1 { font-size: 1.8rem; font-weight: 700; letter-spacing: -0.02em; }
    header p { opacity: 0.85; margin-top: 0.5rem; font-size: 0.95rem; }
    .header-meta {
        display: flex;
        gap: 2rem;
        margin-top: 1rem;
        font-size: 0.85rem;
        opacity: 0.75;
    }

    /* KPI row */
    .kpi-row {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
        gap: 1.25rem;
        padding: 1.5rem 3rem;
    }
    .kpi-card {
        background: var(--card-bg);
        border-radius: 12px;
        padding: 1.5rem 2rem;
        box-shadow: 0 1px 3px rgba(0,0,0,0.08), 0 1px 2px rgba(0,0,0,0.06);
        text-align: center;
        transition: transform 0.15s, box-shadow 0.15s;
    }
    .kpi-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(0,0,0,0.12);
    }
    .kpi-value { font-size: 1.9rem; font-weight: 700; color: var(--primary); }
    .kpi-label { font-size: 0.85rem; color: var(--text-light); margin-top: 0.3rem; }

    /* Content area */
    .content {
        display: grid;
        grid-template-columns: 1fr;
        gap: 1.25rem;
        padding: 0 3rem 3rem;
    }

    /* Section cards */
    section {
        background: var(--card-bg);
        border-radius: 12px;
        padding: 2rem;
        box-shadow: 0 1px 3px rgba(0,0,0,0.08), 0 1px 2px rgba(0,0,0,0.06);
    }
    h2 {
        color: var(--primary);
        margin-bottom: 1rem;
        font-size: 1.25rem;
        font-weight: 600;
        border-left: 4px solid var(--accent);
        padding-left: 0.75rem;
    }
    .section-desc {
        color: var(--text-light);
        font-size: 0.9rem;
        margin-bottom: 1rem;
    }

    /* Info badges */
    .info-row { display: flex; gap: 0.75rem; margin-bottom: 1.5rem; flex-wrap: wrap; }
    .info-badge {
        background: #ebf8ff;
        color: var(--accent);
        padding: 0.35rem 0.85rem;
        border-radius: 20px;
        font-size: 0.8rem;
        font-weight: 600;
    }

    /* Tables */
    .table-scroll { overflow-x: auto; }
    .data-table {
        width: 100%;
        border-collapse: collapse;
        margin: 1rem 0;
        font-size: 0.88rem;
    }
    .data-table thead th {
        background: linear-gradient(135deg, var(--primary), var(--primary-light));
        color: white;
        padding: 0.75rem 1rem;
        text-align: left;
        font-weight: 600;
        white-space: nowrap;
        position: sticky;
        top: 0;
    }
    .data-table tbody td {
        padding: 0.6rem 1rem;
        border-bottom: 1px solid var(--border);
    }
    .data-table tbody tr:nth-child(even) {
        background: #f8fafc;
    }
    .data-table tbody tr:hover {
        background: #edf2f7;
    }
    .number {
        text-align: right;
        font-family: 'JetBrains Mono', 'Fira Code', 'Consolas', monospace;
        font-size: 0.84rem;
    }
    .ensemble-col { font-weight: 600; color: var(--primary); }

    /* Diagnostics */
    .diagnostics-table .best-model-row {
        background: #f0fff4 !important;
    }
    .diagnostics-table .best-model-row:hover {
        background: #e6ffed !important;
    }
    .best-tag {
        background: var(--success);
        color: white;
        font-size: 0.65rem;
        padding: 0.15rem 0.45rem;
        border-radius: 4px;
        margin-left: 0.4rem;
        vertical-align: middle;
        font-weight: 700;
    }
    .desc-text {
        color: var(--text-light);
        font-size: 0.78rem;
    }
    .verdict-pass { color: var(--success); font-weight: 600; }
    .verdict-fail { color: var(--danger); font-weight: 600; }
    .verdict-warn { color: var(--warning); font-weight: 600; }
    .diag-error td { color: var(--danger); font-style: italic; }

    /* Uncertainty bar */
    .uncertainty-bar {
        width: 100%;
        height: 8px;
        background: #edf2f7;
        border-radius: 4px;
        overflow: hidden;
        margin-bottom: 0.2rem;
    }
    .uncertainty-fill {
        height: 100%;
        border-radius: 4px;
        transition: width 0.3s ease;
    }

    /* Scenarios */
    .scenario-year { margin-bottom: 1.5rem; }
    .scenario-year h3 {
        color: var(--primary);
        font-size: 1.1rem;
        margin-bottom: 0.75rem;
    }
    .scenario-grid {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 1rem;
    }
    .scenario-card {
        border-radius: 10px;
        padding: 1.25rem;
        text-align: center;
    }
    .scenario-pessimistic {
        background: linear-gradient(135deg, #fff5f5, #fed7d7);
        border: 1px solid #feb2b2;
    }
    .scenario-base {
        background: linear-gradient(135deg, #ebf8ff, #bee3f8);
        border: 1px solid #90cdf4;
    }
    .scenario-optimistic {
        background: linear-gradient(135deg, #f0fff4, #c6f6d5);
        border: 1px solid #9ae6b4;
    }
    .scenario-icon { font-size: 1.4rem; margin-bottom: 0.3rem; }
    .scenario-label {
        font-size: 0.78rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.04em;
        color: var(--text-light);
        margin-bottom: 0.4rem;
    }
    .scenario-value {
        font-size: 1.15rem;
        font-weight: 700;
        color: var(--text);
        font-family: 'JetBrains Mono', 'Fira Code', 'Consolas', monospace;
    }

    /* Freshness */
    .freshness-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
        gap: 1rem;
    }
    .freshness-card {
        border-radius: 10px;
        padding: 1.25rem;
        text-align: center;
        border: 2px solid var(--border);
    }
    .freshness-green { border-color: var(--success); background: #f0fff4; }
    .freshness-yellow { border-color: var(--warning); background: #fffff0; }
    .freshness-red { border-color: var(--danger); background: #fff5f5; }
    .freshness-source { font-weight: 600; font-size: 0.95rem; margin-bottom: 0.3rem; }
    .freshness-date {
        font-family: 'JetBrains Mono', 'Consolas', monospace;
        font-size: 0.9rem;
        color: var(--text);
    }
    .freshness-age { font-size: 0.8rem; font-weight: 600; margin-top: 0.2rem; }
    .freshness-green .freshness-age { color: var(--success); }
    .freshness-yellow .freshness-age { color: var(--warning); }
    .freshness-red .freshness-age { color: var(--danger); }
    .freshness-desc { font-size: 0.75rem; color: var(--text-light); margin-top: 0.3rem; }

    /* Validation */
    .verdict-banner {
        padding: 1rem 1.5rem;
        border-radius: 8px;
        margin-bottom: 1rem;
        font-weight: 600;
        font-size: 1rem;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    .verdict-pass-card { background: #f0fff4; color: var(--success); border: 1px solid #9ae6b4; }
    .verdict-warn-card { background: #fffff0; color: var(--warning); border: 1px solid #ecc94b; }
    .verdict-fail-card { background: #fff5f5; color: var(--danger); border: 1px solid #feb2b2; }
    .verdict-stats { font-size: 0.85rem; font-weight: 400; }
    .validation-table { margin-bottom: 1rem; }
    .warnings-detail {
        background: #fffff0;
        border: 1px solid #ecc94b;
        border-radius: 8px;
        padding: 0.75rem 1rem;
    }
    .warnings-detail summary {
        cursor: pointer;
        font-weight: 600;
        color: var(--warning);
    }
    .warnings-detail ul {
        margin-top: 0.5rem;
        padding-left: 1.5rem;
        font-size: 0.88rem;
    }
    .warnings-detail li { margin-bottom: 0.3rem; }

    /* Methodology */
    .methodology-content {
        padding: 1rem 0;
        font-size: 0.92rem;
        line-height: 1.7;
    }
    .methodology-content h3 {
        color: var(--primary);
        margin-top: 1.25rem;
        margin-bottom: 0.5rem;
        font-size: 1rem;
    }
    .methodology-content ul {
        padding-left: 1.5rem;
        margin-bottom: 0.75rem;
    }
    .methodology-content li { margin-bottom: 0.3rem; }
    .methodology-content code {
        background: #edf2f7;
        padding: 0.15rem 0.4rem;
        border-radius: 4px;
        font-size: 0.85rem;
    }

    /* Qualitative section */
    .qualitative .markdown-content {
        font-size: 0.95rem;
        line-height: 1.7;
        white-space: pre-wrap;
    }

    /* Details / summary */
    details {
        cursor: default;
    }
    details summary {
        cursor: pointer;
        font-weight: 600;
        color: var(--accent);
        padding: 0.5rem 0;
        user-select: none;
    }
    details summary:hover {
        color: var(--primary);
    }

    /* Two-column layout for side-by-side sections */
    .two-col {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 1.25rem;
    }

    /* Footer */
    footer {
        text-align: center;
        padding: 2rem;
        color: #a0aec0;
        font-size: 0.8rem;
    }

    /* Responsive */
    @media (max-width: 900px) {
        header, .kpi-row, .content { padding-left: 1.5rem; padding-right: 1.5rem; }
        .scenario-grid { grid-template-columns: 1fr; }
        .two-col { grid-template-columns: 1fr; }
        .kpi-row { grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); }
    }
    @media (max-width: 600px) {
        header, .kpi-row, .content { padding-left: 1rem; padding-right: 1rem; }
        .kpi-value { font-size: 1.4rem; }
    }

    /* Print */
    @media print {
        body { background: white; }
        header { background: var(--primary) !important; -webkit-print-color-adjust: exact; }
        .kpi-card, section { box-shadow: none; border: 1px solid #ddd; }
        details[open] summary ~ * { display: block; }
    }
"""


def main(*, output_dir: str = "", template_name: str = "", **kwargs) -> dict:
    """Render dashboard HTML."""
    od = Path(output_dir)
    report_dir = od / "report"
    report_dir.mkdir(exist_ok=True)

    # Load all data sources
    sarimax = _load(od, "run_sarimax_models")
    charts = _load(od, "generate_charts")
    qualitative = _load(od, "qualitative_analysis")
    validation = _load(od, "validate_forecasts")
    macro = _load(od, "fetch_macro_data")
    sefaz = _load(od, "load_sefaz_data")

    plotly_charts = charts.get("plotly_charts", {})
    annual_totals = sarimax.get("annual_totals", {}).get("ensemble", {})
    best_model = sarimax.get("best_model", "N/A")
    diagnostics = sarimax.get("diagnostics", {})
    best_aic = diagnostics.get(best_model, {}).get("aic", "N/A") if best_model != "N/A" else "N/A"
    n_models = sarimax.get("n_models_fitted", 0)

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
            <div id="{chart_id}" style="width:100%;margin:1rem 0;"></div>
            <script>
                Plotly.newPlot('{chart_id}', {json.dumps(chart_data.get('data', []))}, {json.dumps(chart_data.get('layout', {}))}, {{responsive: true}});
            </script>
            """)

    # KPIs
    kpi_html = ""
    for year, value in sorted(annual_totals.items()):
        kpi_html += f"""
        <div class="kpi-card">
            <div class="kpi-value">{_fmt_brl(value)}</div>
            <div class="kpi-label">ICMS-SP {year}</div>
        </div>
        """

    # Best model KPI
    kpi_html += f"""
    <div class="kpi-card">
        <div class="kpi-value" style="font-size:1.3rem;">{best_model}</div>
        <div class="kpi-label">Melhor modelo (AIC: {best_aic})</div>
    </div>
    """

    # Validation verdict KPI
    verdict = validation.get("verdict", "—")
    v_passed = validation.get("passed", 0)
    v_failed = validation.get("failed", 0)
    verdict_color = {"pass": "var(--success)", "warn": "var(--warning)", "fail": "var(--danger)"}.get(verdict, "var(--text-light)")
    verdict_display = {"pass": "OK", "warn": "Atencao", "fail": "Falha"}.get(verdict, "—")
    kpi_html += f"""
    <div class="kpi-card">
        <div class="kpi-value" style="font-size:1.3rem; color:{verdict_color};">{verdict_display}</div>
        <div class="kpi-label">Validacao ({v_passed}/{v_passed + v_failed} checks)</div>
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

    # Build all new sections
    monthly_table = _build_monthly_forecast_table(sarimax)
    diagnostics_card = _build_diagnostics_card(sarimax)
    ci_summary = _build_ci_summary(sarimax)
    scenario_summary = _build_scenario_summary(sarimax)
    freshness_indicator = _build_freshness_indicator(macro, sefaz)
    validation_card = _build_validation_card(validation)
    methodology = _build_methodology_section(sarimax)

    now_str = datetime.now().strftime("%d/%m/%Y %H:%M")

    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Dashboard &mdash; Previsao ICMS-SP</title>
    <script>{plotly_js}</script>
    <style>{CSS}</style>
</head>
<body>
    <header>
        <h1>Previsao de Arrecadacao ICMS-SP</h1>
        <p>SEFAZ &mdash; Assessoria de Economia e Financas Publicas</p>
        <div class="header-meta">
            <span>Gerado em: {now_str}</span>
            <span>{n_models} modelos SARIMAX</span>
            <span>Melhor: {best_model} (AIC {best_aic})</span>
        </div>
    </header>

    <div class="kpi-row">
        {kpi_html}
    </div>

    <div class="content">
        {scenario_summary}

        <section>
            <h2>Projecoes por Modelo</h2>
            <div class="info-row">
                <span class="info-badge">{n_models} modelos ajustados</span>
                <span class="info-badge">Ensemble = media dos modelos</span>
            </div>
            {''.join(plotly_scripts)}
        </section>

        {diagnostics_card}

        {ci_summary}

        {monthly_table}

        <div class="two-col">
            {validation_card}
            {freshness_indicator}
        </div>

        {qual_html}

        {methodology}
    </div>

    <footer>
        Pipeline Engine v1 &mdash; SEFAZ ICMS-SP &mdash; Gerado automaticamente em {now_str}
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

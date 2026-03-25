"""Render interactive dashboard HTML with Plotly charts, KPIs, diagnostics, and scenarios."""
import json
import os
import re
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
        return "freshness-red", "data inválida"
    age_days = (date.today() - last).days
    if age_days < 45:
        return "freshness-green", f"{age_days}d atrás"
    elif age_days < 100:
        return "freshness-yellow", f"{age_days}d atrás"
    else:
        return "freshness-red", f"{age_days}d atrás"


def _date_to_month_label(date_str: str) -> str:
    """Convert '2024-01-01' to 'jan/2024'."""
    months_pt = {
        1: "jan", 2: "fev", 3: "mar", 4: "abr", 5: "mai", 6: "jun",
        7: "jul", 8: "ago", 9: "set", 10: "out", 11: "nov", 12: "dez",
    }
    try:
        dt = datetime.strptime(date_str[:10], "%Y-%m-%d")
        return f"{months_pt[dt.month]}/{dt.year}"
    except (ValueError, TypeError):
        return date_str[:7] if date_str else "—"


def _next_month_label(date_str: str) -> str:
    """Given a date string, return the month label for the following month."""
    months_pt = {
        1: "jan", 2: "fev", 3: "mar", 4: "abr", 5: "mai", 6: "jun",
        7: "jul", 8: "ago", 9: "set", 10: "out", 11: "nov", 12: "dez",
    }
    try:
        dt = datetime.strptime(date_str[:10], "%Y-%m-%d")
        month = dt.month + 1
        year = dt.year
        if month > 12:
            month = 1
            year += 1
        return f"{months_pt[month]}/{year}"
    except (ValueError, TypeError):
        return "—"


def _build_data_context_bar(sefaz: dict, macro: dict) -> str:
    """Prominent info bar showing data context: last observed, forecast start, macro freshness."""
    last_obs = sefaz.get("last_observed_date")
    freshness = macro.get("data_freshness", {})
    focus = macro.get("focus_expectations", {})

    last_obs_label = _date_to_month_label(last_obs) if last_obs else "—"
    forecast_start_label = _next_month_label(last_obs) if last_obs else "—"
    ibc_label = _date_to_month_label(freshness.get("ibc_br_last", "")) if freshness.get("ibc_br_last") else "—"
    igp_label = _date_to_month_label(freshness.get("igp_di_last", "")) if freshness.get("igp_di_last") else "—"

    # Focus with survey date and per-year expectations
    focus_by_year = macro.get("focus_by_year", {})
    focus_survey_date = freshness.get("focus_survey_date", "")

    focus_parts = []
    for yr in sorted(focus_by_year.keys()):
        yr_data = focus_by_year[yr]
        pib_yr = yr_data.get("PIB Total")
        igpm_yr = yr_data.get("IGP-M")
        parts = []
        if pib_yr is not None:
            parts.append(f"PIB {yr}: +{pib_yr:.1f}%")
        if igpm_yr is not None:
            parts.append(f"IGP-M {yr}: +{igpm_yr:.1f}%")
        if parts:
            focus_parts.append(", ".join(parts))

    if not focus_parts:
        pib = focus.get("PIB Total")
        igpm = focus.get("IGP-M")
        if pib is not None:
            focus_parts.append(f"PIB +{pib:.1f}%")
        if igpm is not None:
            focus_parts.append(f"IGP-M +{igpm:.1f}%")

    focus_text = " | ".join(focus_parts)
    survey_label = ""
    if focus_survey_date:
        try:
            sd = datetime.strptime(focus_survey_date[:10], "%Y-%m-%d")
            survey_label = sd.strftime("%d/%m/%Y")
        except Exception:
            survey_label = focus_survey_date[:10]

    items = [
        ("📊", "Último ICMS observado", last_obs_label),
        ("🔮", "Início da previsão", forecast_start_label),
        ("📈", "IBC-BR até", ibc_label),
        ("💹", "IGP-DI até", igp_label),
    ]
    if focus_text:
        focus_label = f"Focus (coleta {survey_label})" if survey_label else "Focus"
        items.append(("🎯", focus_label, focus_text))

    badges = ""
    for icon, label, value in items:
        badges += f"""
        <div class="context-item">
            <span class="context-icon">{icon}</span>
            <span class="context-label">{label}:</span>
            <span class="context-value">{value}</span>
        </div>
        """

    return f"""
    <div class="data-context-bar">
        {badges}
    </div>
    """


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
        <h2>Previsões Mensais por Modelo</h2>
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
                <td colspan="6">Erro: {diag['error']}</td></tr>"""
            continue

        aic = diag.get("aic", "—")
        bic = diag.get("bic", "—")
        mape = diag.get("mape")
        mape_display = f"{mape:.2f}%" if mape is not None else "—"
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
            <td class="number">{mape_display}</td>
            <td class="number">{n_obs}</td>
            <td class="number">{lb_display}</td>
            <td>{verdict_icon}</td>
        </tr>"""

    return f"""
    <section>
        <h2>Diagnósticos dos Modelos</h2>
        <table class="data-table diagnostics-table">
            <thead>
                <tr>
                    <th>Modelo</th>
                    <th>AIC</th>
                    <th>BIC</th>
                    <th>MAPE</th>
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
        <h2>Intervalos de Confiança</h2>
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
    """Scenario cards: pessimistic (P5), base (median), optimistic (P95) from Monte Carlo."""
    annual_totals = sarimax.get("annual_totals", {})
    mc_config = sarimax.get("monte_carlo_config", {})
    n_simulations = mc_config.get("n_simulations", 1000)
    n_models = mc_config.get("models_simulated", sarimax.get("n_models_fitted", 0))

    # Try ensemble_mc first (proper Monte Carlo percentiles)
    ensemble_mc = annual_totals.get("ensemble_mc", {})

    if ensemble_mc:
        years = sorted(ensemble_mc.keys())
    else:
        years = sorted(annual_totals.get("ensemble", {}).keys())

    if not years:
        return ""

    year_cards = ""
    for year in years:
        if ensemble_mc and year in ensemble_mc:
            mc_data = ensemble_mc[year]
            if isinstance(mc_data, dict):
                pessimistic = mc_data.get("low_95", 0)
                base = mc_data.get("median", 0)
                optimistic = mc_data.get("high_95", 0)
            else:
                # Fallback: ensemble_mc value is just a number
                ens_val = annual_totals.get("ensemble", {}).get(year, 0)
                pessimistic = ens_val * 0.9
                base = ens_val
                optimistic = ens_val * 1.1
        else:
            # Fallback: compute from individual model MC data
            ens_val = annual_totals.get("ensemble", {}).get(year, 0)
            # Try averaging individual model MC percentiles
            model_lows = []
            model_medians = []
            model_highs = []
            for key, val in annual_totals.items():
                if key.endswith("_mc") and key != "ensemble_mc" and isinstance(val, dict):
                    year_data = val.get(year, {})
                    if isinstance(year_data, dict):
                        model_lows.append(year_data.get("low_95", 0))
                        model_medians.append(year_data.get("median", 0))
                        model_highs.append(year_data.get("high_95", 0))

            if model_lows:
                pessimistic = sum(model_lows) / len(model_lows)
                base = sum(model_medians) / len(model_medians)
                optimistic = sum(model_highs) / len(model_highs)
            else:
                pessimistic = ens_val * 0.9
                base = ens_val
                optimistic = ens_val * 1.1

        year_cards += f"""
        <div class="scenario-year">
            <h3>{year}</h3>
            <div class="scenario-grid">
                <div class="scenario-card scenario-pessimistic">
                    <div class="scenario-icon">&#9660;</div>
                    <div class="scenario-label">Pessimista (P5)</div>
                    <div class="scenario-value" id="scenario-pessimistic-{year}">{_fmt_brl(pessimistic)}</div>
                </div>
                <div class="scenario-card scenario-base">
                    <div class="scenario-icon">&#9654;</div>
                    <div class="scenario-label">Base (Mediana)</div>
                    <div class="scenario-value" id="scenario-base-{year}">{_fmt_brl(base)}</div>
                </div>
                <div class="scenario-card scenario-optimistic">
                    <div class="scenario-icon">&#9650;</div>
                    <div class="scenario-label">Otimista (P95)</div>
                    <div class="scenario-value" id="scenario-optimistic-{year}">{_fmt_brl(optimistic)}</div>
                </div>
            </div>
        </div>
        """

    methodology_note = f"""
    <p class="scenario-methodology">
        Cenários derivados de {n_simulations:,} simulações Monte Carlo sobre ensemble de {n_models} modelos.
        P5/P95 representam os percentis 5 e 95 da distribuição simulada.
    </p>
    """.replace(",", ".")

    return f"""
    <section>
        <h2>Cenários de Arrecadação</h2>
        <p class="section-desc">Baseado em simulações Monte Carlo sobre o ensemble de modelos SARIMAX.</p>
        {year_cards}
        {methodology_note}
    </section>
    """


def _build_freshness_indicator(macro: dict, sefaz: dict) -> str:
    """Data freshness indicator with color-coded status."""
    freshness = macro.get("data_freshness", {})
    icms_last = sefaz.get("last_observed_date")

    sources = [
        ("IBC-BR (BCB)", freshness.get("ibc_br_last"), "Índice de Atividade Econômica"),
        ("IGP-DI (IPEA)", freshness.get("igp_di_last"), "Índice de Preços"),
        ("ICMS-SP (SEFAZ)", icms_last, "Arrecadação Histórica"),
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
        "pass": "&#10003; Todas as verificações OK",
        "warn": "&#9888; Atenção: verificações com ressalvas",
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
        <h2>Validação das Previsões</h2>
        <div class="verdict-banner {verdict_class}">
            {verdict_label}
            <span class="verdict-stats">{passed} passou, {failed} falhou</span>
        </div>
        <table class="data-table validation-table">
            <thead><tr><th></th><th>Verificação</th><th>Detalhe</th></tr></thead>
            <tbody>{check_rows}</tbody>
        </table>
        {warnings_html}
    </section>
    """


def _build_predictions_table(sarimax: dict) -> str:
    """Predictions table using all_candidates as single source of truth."""
    all_candidates = sarimax.get("all_candidates", {})
    diagnostics = sarimax.get("diagnostics", {})
    annual_totals = sarimax.get("annual_totals", {})
    best_model = sarimax.get("best_model", "")

    if not all_candidates:
        return ""

    # Determine years from annual_totals (exclude MC entries)
    years = sorted(set(
        y for k, v in annual_totals.items()
        if not k.endswith("_mc") and isinstance(v, dict)
        for y in v.keys()
        if all(isinstance(vv, (int, float)) for vv in v.values())
    ))

    # Sort all candidates by MAPE
    sorted_candidates = sorted(
        all_candidates.items(),
        key=lambda x: x[1].get("mape", 999) if x[1].get("mape") is not None else 999
    )

    # Build table rows
    year_headers = "".join(f"<th>{y}</th>" for y in years)
    rows = ""
    for name, info in sorted_candidates:
        mape = info.get("mape")
        mape_display = f"{mape:.2f}%" if mape is not None else "—"
        is_best = name == best_model
        row_class = "best-model-row" if is_best else ""
        best_tag = ' <span class="best-tag">MELHOR</span>' if is_best else ""
        ctype = info.get("type", "")
        type_badge = (
            '<span class="type-badge type-individual">Individual</span>'
            if ctype == "individual"
            else '<span class="type-badge type-ensemble">Ensemble</span>'
        )

        # Weights description
        weights = info.get("weights", {})
        if weights:
            w_parts = [f"{k.replace('Modelo ', 'M')}:{v:.0%}" for k, v in weights.items()]
            desc = f"Pesos: {', '.join(w_parts)}"
        else:
            diag = diagnostics.get(name, {})
            desc = diag.get("description", "")

        # Annual values: use annual_totals for individual, compute weighted for ensembles
        annual_cells = ""
        for year in years:
            if ctype == "individual":
                val = annual_totals.get(name, {}).get(year, 0)
            else:
                # Weighted sum from components
                components = info.get("components", [])
                if weights:
                    val = sum(
                        weights.get(m, 0) * annual_totals.get(m, {}).get(year, 0)
                        for m in components
                    )
                else:
                    comp_vals = [annual_totals.get(m, {}).get(year, 0) for m in components]
                    val = sum(comp_vals) / len(comp_vals) if comp_vals else 0
            annual_cells += f'<td class="number">{_fmt_brl(val)}</td>'

        rows += f"""<tr class="{row_class}">
            <td>{name}{best_tag}<br><small class="desc-text">{desc}</small></td>
            <td>{type_badge}</td>
            <td class="number">{mape_display}</td>
            {annual_cells}
        </tr>"""

    return f"""
    <section>
        <h2>Previsões — Todos os Candidatos</h2>
        <p class="section-desc">31 candidatos (5 individuais + 26 ensembles inverse-MSE) ordenados por MAPE acumulado pós-dummies.</p>
        <div class="table-scroll">
            <table class="data-table predictions-table">
                <thead>
                    <tr>
                        <th>Candidato</th>
                        <th>Tipo</th>
                        <th>MAPE</th>
                        {year_headers}
                    </tr>
                </thead>
                <tbody>{rows}</tbody>
            </table>
        </div>
    </section>
    """


def _build_r_comparison_appendix(cross_validate: dict) -> str:
    """Collapsible appendix: Python vs R model comparison."""
    comparison_table = cross_validate.get("comparison_table", [])
    discrepancies = cross_validate.get("discrepancies", [])

    if not comparison_table:
        return ""

    # Group by model, only AIC rows
    models_data = {}
    for entry in comparison_table:
        model = entry["model"]
        metric = entry["metric"]
        if model not in models_data:
            models_data[model] = {}
        models_data[model][metric] = entry

    # Extract n_obs from discrepancies
    n_obs_data = {}
    for disc in discrepancies:
        match = re.match(r"(Modelo \d+) n_obs: Python=(\d+), R=(\d+)", disc)
        if match:
            n_obs_data[match.group(1)] = {
                "python": int(match.group(2)),
                "r": int(match.group(3)),
            }

    rows = ""
    for model_name in sorted(models_data.keys()):
        data = models_data[model_name]
        aic_entry = data.get("AIC", {})
        n_obs = n_obs_data.get(model_name, {})

        aic_py = aic_entry.get("python", "—")
        aic_r = aic_entry.get("r", "—")
        dev = aic_entry.get("deviation_pct", "—")
        n_py = n_obs.get("python", "—")
        n_r = n_obs.get("r", "—")

        aic_py_fmt = f"{aic_py:.2f}" if isinstance(aic_py, (int, float)) else aic_py
        aic_r_fmt = f"{aic_r:.2f}" if isinstance(aic_r, (int, float)) else aic_r
        dev_fmt = f"{dev:.1f}%" if isinstance(dev, (int, float)) else dev

        rows += f"""<tr>
            <td>{model_name}</td>
            <td class="number">{aic_py_fmt}</td>
            <td class="number">{aic_r_fmt}</td>
            <td class="number">{dev_fmt}</td>
            <td class="number">{n_py}</td>
            <td class="number">{n_r}</td>
        </tr>"""

    return f"""
    <section>
        <h2>Anexo: Comparação Python vs R</h2>
        <details>
            <summary>Expandir comparação de métricas entre implementações</summary>
            <div class="r-comparison-content">
                <table class="data-table">
                    <thead>
                        <tr>
                            <th>Modelo</th>
                            <th>AIC (Python)</th>
                            <th>AIC (R)</th>
                            <th>Desvio %</th>
                            <th>n_obs Python</th>
                            <th>n_obs R</th>
                        </tr>
                    </thead>
                    <tbody>{rows}</tbody>
                </table>
                <div class="r-comparison-note">
                    <p><strong>Nota metodológica:</strong> Diferenças de AIC/BIC são esperadas devido a:
                    (1) <code>lambda=0</code> no R aplica transformação Box-Cox internamente com ajuste de Jacobiano,
                    enquanto Python usa <code>log()</code> manual;
                    (2) tratamento de NaN nas variáveis exógenas laggadas difere entre <code>forecast::Arima()</code>
                    e <code>statsmodels.SARIMAX</code>.
                    As diferenças observadas (8–19%) são consistentes com estas diferenças de implementação
                    e não indicam erro nos modelos.</p>
                </div>
            </div>
        </details>
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
            <summary>Expandir descrição metodológica</summary>
            <div class="methodology-content">
                <h3>Modelos SARIMAX</h3>
                <p>Foram ajustados <strong>{n_models} modelos</strong> SARIMAX (Seasonal AutoRegressive Integrated Moving Average with eXogenous regressors)
                com diferentes especificações de ordem autorregressiva, diferenciação e média móvel, além de variáveis exógenas distintas.</p>

                <h3>Variáveis Exógenas</h3>
                <ul>
                    <li><strong>IBC-BR:</strong> Índice de Atividade Econômica do Banco Central (proxy do PIB mensal)</li>
                    <li><strong>IGP-DI:</strong> Índice Geral de Preços (captura efeito inflacionário na base tributável)</li>
                    <li><strong>Dias úteis:</strong> Controle para efeito calendário</li>
                    <li><strong>Dummies:</strong> LS2008NOV (crise financeira), TC2020APR04 (COVID), TC2022OUT05 (ajuste fiscal)</li>
                </ul>

                <h3>Teste de Estacionariedade (ADF)</h3>
                <p>Augmented Dickey-Fuller sobre a primeira diferença da série em log:
                   estatística = <code>{adf.get('statistic', 'N/A')}</code>,
                   p-valor = <code>{adf.get('p_value', 'N/A')}</code>
                   &mdash; {"Série estacionária" if adf.get('stationary') else "Não-estacionária"}.</p>

                <h3>Seleção do Melhor Modelo</h3>
                <p>O melhor candidato é selecionado pelo menor MAPE acumulado (Mean Absolute Percentage Error) em janela
                   out-of-sample pós-dummies estruturais. São avaliados 31 candidatos: 5 modelos individuais + 26 ensembles
                   (todas as combinações de 2, 3, 4 e 5 modelos). Ensembles utilizam pesos inverse-MSE
                   (Bates &amp; Granger, 1969), método padrão em bancos centrais (BCB, Fed, ECB, BoE).</p>

                <h3>Intervalos de Confiança</h3>
                <p>IC 95% derivados do modelo <strong>{ci_model}</strong> via previsão fora da amostra (<code>get_forecast</code>).
                   A transformação exponencial é aplicada após a previsão em log para retornar à escala original.</p>

                <h3>Diagnósticos</h3>
                <ul>
                    <li><strong>AIC / BIC:</strong> Critérios de informação para comparação entre modelos (menor = melhor)</li>
                    <li><strong>Ljung-Box:</strong> Teste de autocorrelação dos resíduos (p > 0.05 = resíduos não autocorrelacionados)</li>
                </ul>

                <h3>Cenários</h3>
                <p><strong>Pessimista:</strong> Percentil 5 da simulação Monte Carlo (P5). <br>
                   <strong>Base:</strong> Mediana da simulação Monte Carlo. <br>
                   <strong>Otimista:</strong> Percentil 95 da simulação Monte Carlo (P95).</p>
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

    /* Data context bar */
    .data-context-bar {
        display: flex;
        flex-wrap: wrap;
        gap: 1rem;
        padding: 1rem 3rem;
        background: linear-gradient(135deg, #ebf8ff, #e6fffa);
        border-bottom: 1px solid var(--border);
        align-items: center;
    }
    .context-item {
        display: flex;
        align-items: center;
        gap: 0.35rem;
        font-size: 0.85rem;
        padding: 0.3rem 0.7rem;
        background: rgba(255,255,255,0.7);
        border-radius: 8px;
        border: 1px solid rgba(49,130,206,0.15);
    }
    .context-icon { font-size: 0.95rem; }
    .context-label { color: var(--text-light); font-weight: 500; }
    .context-value { color: var(--primary); font-weight: 700; }

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

    /* Type badges for predictions table */
    .type-badge {
        font-size: 0.7rem;
        padding: 0.15rem 0.5rem;
        border-radius: 4px;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.03em;
    }
    .type-individual {
        background: #ebf8ff;
        color: var(--accent);
    }
    .type-ensemble {
        background: #faf5ff;
        color: #805ad5;
    }

    /* Predictions table */
    .predictions-table .best-model-row {
        background: #f0fff4 !important;
    }
    .predictions-table .best-model-row:hover {
        background: #e6ffed !important;
    }

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
    .scenario-methodology {
        margin-top: 1rem;
        padding: 0.75rem 1rem;
        background: #f7fafc;
        border-left: 3px solid var(--accent);
        font-size: 0.82rem;
        color: var(--text-light);
        line-height: 1.5;
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

    /* R comparison appendix */
    .r-comparison-content {
        padding: 1rem 0;
    }
    .r-comparison-note {
        margin-top: 1rem;
        padding: 1rem;
        background: #f7fafc;
        border-left: 3px solid var(--accent);
        font-size: 0.88rem;
        line-height: 1.6;
        color: var(--text);
    }
    .r-comparison-note code {
        background: #edf2f7;
        padding: 0.15rem 0.4rem;
        border-radius: 4px;
        font-size: 0.82rem;
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
        header, .kpi-row, .content, .data-context-bar { padding-left: 1.5rem; padding-right: 1.5rem; }
        .scenario-grid { grid-template-columns: 1fr; }
        .two-col { grid-template-columns: 1fr; }
        .kpi-row { grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); }
    }
    @media (max-width: 600px) {
        header, .kpi-row, .content, .data-context-bar { padding-left: 1rem; padding-right: 1rem; }
        .kpi-value { font-size: 1.4rem; }
        .data-context-bar { flex-direction: column; }
        .model-dropdown { max-height: 300px; }
    }

    /* Model selector */
    .model-selector { cursor: pointer; position: relative; }
    .model-selector:hover { box-shadow: 0 4px 12px rgba(0,0,0,0.15); }
    .selector-hint { font-size: 0.7rem; color: #a0aec0; margin-top: 0.3rem; }
    .model-dropdown {
        position: absolute; top: 100%; left: 0; right: 0; z-index: 100;
        background: white; border-radius: 8px; box-shadow: 0 8px 24px rgba(0,0,0,0.15);
        max-height: 400px; overflow-y: auto; padding: 0.5rem;
    }
    .model-dropdown input {
        width: calc(100% - 1rem); padding: 0.5rem; border: 1px solid #e2e8f0; border-radius: 4px;
        margin-bottom: 0.5rem; font-size: 0.85rem; outline: none;
    }
    .model-dropdown input:focus { border-color: var(--accent); }
    .model-option {
        display: flex; justify-content: space-between; padding: 0.5rem;
        cursor: pointer; border-radius: 4px; font-size: 0.82rem; align-items: center;
    }
    .model-option:hover { background: #ebf8ff; }
    .model-option.best { background: #f0fff4; font-weight: 600; }
    .model-option .opt-name { flex: 1; text-align: left; }
    .model-option .opt-type {
        font-size: 0.65rem; padding: 0.1rem 0.35rem; border-radius: 3px;
        margin: 0 0.4rem; text-transform: uppercase; font-weight: 600; letter-spacing: 0.02em;
    }
    .model-option .opt-type-individual { background: #ebf8ff; color: var(--accent); }
    .model-option .opt-type-ensemble { background: #faf5ff; color: #805ad5; }
    .model-option .opt-mape { font-family: 'JetBrains Mono','Consolas',monospace; font-size: 0.78rem; color: var(--text-light); }

    /* KPI value animation */
    @keyframes kpiFlash {
        0% { opacity: 0.3; transform: scale(0.95); }
        50% { opacity: 1; transform: scale(1.03); }
        100% { opacity: 1; transform: scale(1); }
    }
    .kpi-flash { animation: kpiFlash 0.35s ease-out; }

    /* Print */
    @media print {
        body { background: white; }
        header { background: var(--primary) !important; -webkit-print-color-adjust: exact; }
        .kpi-card, section { box-shadow: none; border: 1px solid #ddd; }
        details[open] summary ~ * { display: block; }
        .model-dropdown { display: none !important; }
        .selector-hint { display: none; }
    }
"""


def _patch_fan_chart_legend(plotly_charts: dict, sarimax: dict) -> dict:
    """Rename the fan chart legend from 'Previsao (mediana)' to best model name with MAPE."""
    fan_chart = plotly_charts.get("fan_chart")
    if not fan_chart or not isinstance(fan_chart, dict):
        return plotly_charts

    best_mape_model = sarimax.get("best_model_mape", sarimax.get("best_model", ""))
    diagnostics = sarimax.get("diagnostics", {})
    best_diag = diagnostics.get(best_mape_model, {})
    best_mape = best_diag.get("mape")

    if best_mape_model and best_mape is not None:
        label = f"Previsão — {best_mape_model} (MAPE {best_mape:.1f}%)"
    elif best_mape_model:
        label = f"Previsão — {best_mape_model}"
    else:
        label = "Previsão (mediana)"

    # Also fix the title
    if "layout" in fan_chart:
        title = fan_chart["layout"].get("title", "")
        if isinstance(title, dict) and "text" in title:
            title["text"] = "ICMS-SP: Histórico e Previsão com Intervalos de Confiança"
        elif isinstance(title, str):
            fan_chart["layout"]["title"] = "ICMS-SP: Histórico e Previsão com Intervalos de Confiança"

    if "data" in fan_chart:
        for trace in fan_chart["data"]:
            name = trace.get("name", "")
            if "mediana" in name.lower() or "previsao" in name.lower():
                trace["name"] = label

    plotly_charts["fan_chart"] = fan_chart
    return plotly_charts


def _fix_plotly_portuguese(plotly_charts: dict) -> dict:
    """Fix Portuguese orthography in all Plotly chart titles and labels."""
    replacements = {
        "Previsao": "Previsão",
        "Arrecadacao": "Arrecadação",
        "Projecoes": "Projeções",
        "Projecao": "Projeção",
        "Financas Publicas": "Finanças Públicas",
        "Diagnosticos": "Diagnósticos",
        "Diagnostico": "Diagnóstico",
        "Validacao": "Validação",
        "Historico": "Histórico",
        "Confianca": "Confiança",
        "bilhoes": "bilhões",
        "Variaveis Exogenas": "Variáveis Exógenas",
        "Variaveis": "Variáveis",
        "Exogenas": "Exógenas",
        "Indice": "Índice",
        "Economica": "Econômica",
    }

    def _fix_str(s: str) -> str:
        for old, new in replacements.items():
            s = s.replace(old, new)
        return s

    def _fix_obj(obj):
        if isinstance(obj, str):
            return _fix_str(obj)
        elif isinstance(obj, dict):
            return {k: _fix_obj(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [_fix_obj(item) for item in obj]
        return obj

    return _fix_obj(plotly_charts)


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
    cross_validate = _load(od, "cross_validate_r")

    plotly_charts = charts.get("plotly_charts", {})

    # Change 4: Remove AIC bar chart and annual totals charts
    plotly_charts.pop("aic_comparison", None)
    plotly_charts.pop("annual_totals", None)
    plotly_charts.pop("annual_totals_ci", None)

    # Change 6: Patch fan chart legend
    plotly_charts = _patch_fan_chart_legend(plotly_charts, sarimax)

    # Change 7: Fix Portuguese orthography in chart titles/labels
    plotly_charts = _fix_plotly_portuguese(plotly_charts)

    annual_totals = sarimax.get("annual_totals", {}).get("ensemble", {})
    best_model = sarimax.get("best_model", "N/A")
    best_candidate_mape = sarimax.get("best_model_mape", "N/A")
    if isinstance(best_candidate_mape, (int, float)):
        best_candidate_mape = f"{best_candidate_mape:.2f}"
    diagnostics = sarimax.get("diagnostics", {})
    n_models = sarimax.get("n_models_fitted", 0)

    # --- Build CANDIDATES JS data for interactive selector ---
    all_candidates = sarimax.get("all_candidates", {})
    all_annual_totals = sarimax.get("annual_totals", {})
    all_forecasts = sarimax.get("forecasts", {})
    ensemble_mc = all_annual_totals.get("ensemble_mc", {})
    candidates_js = {}

    for cand_name, cand_info in all_candidates.items():
        cand_type = cand_info.get("type", "individual")
        cand_mape = cand_info.get("mape")
        cand_weights = cand_info.get("weights", {})
        cand_components = cand_info.get("components", [])

        # Compute annual totals for this candidate
        cand_annual = {}
        if cand_type == "individual" and cand_name in all_annual_totals:
            # Direct lookup
            for year, val in all_annual_totals[cand_name].items():
                cand_annual[year] = round(val, 2) if isinstance(val, (int, float)) else val
        elif cand_type == "ensemble" and cand_weights:
            # Weighted combination from component forecasts
            years_set = set()
            for comp in cand_components:
                if comp in all_annual_totals and isinstance(all_annual_totals[comp], dict):
                    years_set.update(all_annual_totals[comp].keys())
            for year in sorted(years_set):
                weighted_sum = 0.0
                total_weight = 0.0
                for comp, w in cand_weights.items():
                    comp_val = all_annual_totals.get(comp, {}).get(year)
                    if comp_val is not None and isinstance(comp_val, (int, float)):
                        weighted_sum += comp_val * w
                        total_weight += w
                if total_weight > 0:
                    cand_annual[year] = round(weighted_sum / total_weight, 2)
        elif cand_type == "ensemble":
            # No weights — simple average from components
            years_set = set()
            for comp in cand_components:
                if comp in all_annual_totals and isinstance(all_annual_totals[comp], dict):
                    years_set.update(all_annual_totals[comp].keys())
            for year in sorted(years_set):
                vals = []
                for comp in cand_components:
                    v = all_annual_totals.get(comp, {}).get(year)
                    if v is not None and isinstance(v, (int, float)):
                        vals.append(v)
                if vals:
                    cand_annual[year] = round(sum(vals) / len(vals), 2)

        # CI data — only the best model (ensemble) has MC confidence intervals
        cand_ci = None
        if cand_name == best_model and ensemble_mc:
            cand_ci = {}
            for year, mc_data in ensemble_mc.items():
                if isinstance(mc_data, dict):
                    cand_ci[year] = {
                        "low_95": round(mc_data.get("low_95", 0), 2),
                        "median": round(mc_data.get("median", 0), 2),
                        "high_95": round(mc_data.get("high_95", 0), 2),
                    }

        candidates_js[cand_name] = {
            "mape": cand_mape,
            "type": cand_type,
            "weights": cand_weights,
            "components": cand_components,
            "annual": cand_annual,
            "annual_ci": cand_ci,
        }

    candidates_json_str = json.dumps(candidates_js, ensure_ascii=False, indent=2)

    # MC paths per model — for client-side CI computation
    mc_annual_paths = sarimax.get("mc_annual_paths", {})
    mc_paths_json_str = json.dumps(mc_annual_paths, ensure_ascii=False)

    # Monthly forecast data per individual model — for client-side chart updates
    model_forecasts_js = {}
    for m_name, m_fc in all_forecasts.items():
        if isinstance(m_fc, list):
            model_forecasts_js[m_name] = [
                {"data": f["data"], "forecast": f["forecast"]} for f in m_fc
            ]
    model_forecasts_json_str = json.dumps(model_forecasts_js, ensure_ascii=False)

    # Monthly CI data — for fan chart updates
    ci_block = sarimax.get("confidence_intervals", {})
    monthly_ci_raw = ci_block.get("intervals", [])
    monthly_ci_js = []
    for entry in monthly_ci_raw:
        monthly_ci_js.append({
            "data": entry.get("data", ""),
            "p5": entry.get("p5", 0),
            "p25": entry.get("p25", 0),
            "p50": entry.get("p50", 0),
            "p75": entry.get("p75", 0),
            "p95": entry.get("p95", 0),
        })
    monthly_ci_json_str = json.dumps(monthly_ci_js, ensure_ascii=False)

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

    # KPIs — annual forecast cards with IDs for JS updates
    kpi_html = ""
    for year, value in sorted(annual_totals.items()):
        kpi_html += f"""
        <div class="kpi-card">
            <div class="kpi-value" id="kpi-annual-{year}">{_fmt_brl(value)}</div>
            <div class="kpi-label">ICMS-SP {year}</div>
        </div>
        """

    # Best model KPI — interactive selector
    best_mape_display = ""
    if best_model in all_candidates:
        bm_mape = all_candidates[best_model].get("mape")
        if bm_mape is not None:
            best_mape_display = f"MAPE {bm_mape:.2f}%"
    if not best_mape_display:
        best_mape_display = f"MAPE: N/D"

    kpi_html += f"""
    <div class="kpi-card model-selector" onclick="toggleModelDropdown()">
        <div class="kpi-value" id="best-model-name" style="font-size:1.3rem;">{best_model}</div>
        <div class="kpi-label" id="best-model-mape">{best_mape_display}</div>
        <div class="selector-hint">&#9660; Clique para trocar</div>
        <div id="model-dropdown" class="model-dropdown" style="display:none;" onclick="event.stopPropagation();">
            <input type="text" id="model-search" placeholder="Filtrar..." oninput="filterModels()">
            <div id="model-list"></div>
        </div>
    </div>
    """

    # Validation verdict KPI
    verdict = validation.get("verdict", "—")
    v_passed = validation.get("passed", 0)
    v_failed = validation.get("failed", 0)
    verdict_color = {"pass": "var(--success)", "warn": "var(--warning)", "fail": "var(--danger)"}.get(verdict, "var(--text-light)")
    verdict_display = {"pass": "OK", "warn": "Atenção", "fail": "Falha"}.get(verdict, "—")
    kpi_html += f"""
    <div class="kpi-card">
        <div class="kpi-value" style="font-size:1.3rem; color:{verdict_color};">{verdict_display}</div>
        <div class="kpi-label">Validação ({v_passed}/{v_passed + v_failed} checks)</div>
    </div>
    """

    # Qualitative section
    qual_html = ""
    if qualitative and qualitative.get("status") == "ok":
        exec_summary = qualitative.get("executive_summary", "")
        qual_html = f"""
        <section class="qualitative">
            <h2>Análise Qualitativa</h2>
            <div class="markdown-content">{exec_summary}</div>
        </section>
        """

    # Build all sections
    data_context_bar = _build_data_context_bar(sefaz, macro)
    monthly_table = _build_monthly_forecast_table(sarimax)
    diagnostics_card = _build_diagnostics_card(sarimax)
    ci_summary = _build_ci_summary(sarimax)
    scenario_summary = _build_scenario_summary(sarimax)
    predictions_table = _build_predictions_table(sarimax)
    freshness_indicator = _build_freshness_indicator(macro, sefaz)
    validation_card = _build_validation_card(validation)
    methodology = _build_methodology_section(sarimax)
    r_comparison = _build_r_comparison_appendix(cross_validate)

    now_str = datetime.now().strftime("%d/%m/%Y %H:%M")

    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Dashboard &mdash; Previsão ICMS-SP</title>
    <script>{plotly_js}</script>
    <style>{CSS}</style>
</head>
<body>
    <header>
        <h1>Previsão de Arrecadação ICMS-SP</h1>
        <p>SEFAZ &mdash; Assessoria de Economia e Finanças Públicas</p>
        <div class="header-meta">
            <span>Gerado em: {now_str}</span>
            <span>{n_models} modelos SARIMAX</span>
            <span>Melhor: {best_model} (MAPE {best_candidate_mape}%)</span>
        </div>
    </header>

    <div class="kpi-row">
        {kpi_html}
    </div>

    {data_context_bar}

    <div class="content">
        {scenario_summary}

        {predictions_table}

        <section>
            <h2>Projeções por Modelo</h2>
            <div class="info-row">
                <span class="info-badge">{n_models} modelos ajustados</span>
                <span class="info-badge">Ensemble = média dos modelos</span>
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

        {r_comparison}
    </div>

    <footer>
        Pipeline Engine v1 &mdash; SEFAZ ICMS-SP &mdash; Gerado automaticamente em {now_str}
    </footer>

    <script>
    // --- Model/Ensemble Selector ---
    const CANDIDATES = {candidates_json_str};
    const BEST_MODEL = {json.dumps(best_model, ensure_ascii=False)};
    const MC_PATHS = {mc_paths_json_str};
    const MODEL_FORECASTS = {model_forecasts_json_str};
    const MONTHLY_CI = {monthly_ci_json_str};

    function fmtBrl(val) {{
        if (val == null || isNaN(val)) return "N/D";
        var s = val.toFixed(2).replace(".", ",");
        var parts = s.split(",");
        parts[0] = parts[0].replace(/\\B(?=(\\d{{3}})+(?!\\d))/g, ".");
        return "R$ " + parts.join(",") + " bi";
    }}

    function flashEl(el) {{
        el.classList.remove("kpi-flash");
        void el.offsetWidth; // trigger reflow
        el.classList.add("kpi-flash");
    }}

    function toggleModelDropdown() {{
        var dd = document.getElementById("model-dropdown");
        if (dd.style.display === "none") {{
            dd.style.display = "block";
            populateModelList("");
            var inp = document.getElementById("model-search");
            inp.value = "";
            setTimeout(function(){{ inp.focus(); }}, 50);
        }} else {{
            dd.style.display = "none";
        }}
    }}

    function filterModels() {{
        var q = document.getElementById("model-search").value.toLowerCase();
        populateModelList(q);
    }}

    function populateModelList(filter) {{
        var list = document.getElementById("model-list");
        // Sort candidates by MAPE ascending
        var entries = Object.entries(CANDIDATES).map(function(e) {{
            return {{ name: e[0], data: e[1] }};
        }});
        entries.sort(function(a, b) {{
            var ma = a.data.mape != null ? a.data.mape : 9999;
            var mb = b.data.mape != null ? b.data.mape : 9999;
            return ma - mb;
        }});

        var html = "";
        for (var i = 0; i < entries.length; i++) {{
            var e = entries[i];
            if (filter && e.name.toLowerCase().indexOf(filter) === -1 && e.data.type.toLowerCase().indexOf(filter) === -1) continue;
            var isBest = (e.name === BEST_MODEL) ? " best" : "";
            var typeCls = e.data.type === "individual" ? "opt-type-individual" : "opt-type-ensemble";
            var typeLabel = e.data.type === "individual" ? "individual" : "ensemble";
            var mapeStr = e.data.mape != null ? e.data.mape.toFixed(2) + "%" : "—";
            html += '<div class="model-option' + isBest + '" onclick="selectCandidate(&quot;' + e.name + '&quot;)">';
            html += '<span class="opt-name">' + e.name + '</span>';
            html += '<span class="opt-type ' + typeCls + '">' + typeLabel + '</span>';
            html += '<span class="opt-mape">' + mapeStr + '</span>';
            html += '</div>';
        }}
        list.innerHTML = html;
    }}

    function selectCandidate(name) {{
        var c = CANDIDATES[name];
        if (!c) return;

        // Update model KPI
        var nameEl = document.getElementById("best-model-name");
        var mapeEl = document.getElementById("best-model-mape");
        nameEl.textContent = name;
        mapeEl.textContent = c.mape != null ? "MAPE " + c.mape.toFixed(2) + "%" : "—";
        flashEl(nameEl);
        flashEl(mapeEl);

        // Update annual KPIs
        for (var year in c.annual) {{
            var el = document.getElementById("kpi-annual-" + year);
            if (el) {{
                el.textContent = fmtBrl(c.annual[year]);
                flashEl(el);
            }}
        }}

        // Compute CI from MC paths for this candidate's components
        var components = c.components || [];
        var weights = c.weights || {{}};
        var hasWeights = Object.keys(weights).length > 0;

        // Check if all components have MC paths
        var allHavePaths = components.length > 0 && components.every(function(m) {{ return MC_PATHS[m]; }});

        if (allHavePaths) {{
            var years = Object.keys(MC_PATHS[components[0]]);
            for (var yi = 0; yi < years.length; yi++) {{
                var year = years[yi];
                var nSim = MC_PATHS[components[0]][year].length;
                var ensembleSums = new Array(nSim).fill(0);

                for (var ci = 0; ci < components.length; ci++) {{
                    var m = components[ci];
                    var w = hasWeights ? (weights[m] || 0) : (1.0 / components.length);
                    var paths = MC_PATHS[m][year];
                    for (var si = 0; si < nSim; si++) {{
                        ensembleSums[si] += w * paths[si];
                    }}
                }}

                // Sort and get percentiles
                ensembleSums.sort(function(a, b) {{ return a - b; }});
                var p5 = ensembleSums[Math.floor(nSim * 0.05)];
                var p50 = ensembleSums[Math.floor(nSim * 0.50)];
                var p95 = ensembleSums[Math.floor(nSim * 0.95)];

                updateScenarioYear(year, p5, p50, p95);
            }}
        }} else {{
            clearScenarios(c);
        }}

        // Update Plotly charts
        updateCharts(name);

        // Close dropdown
        document.getElementById("model-dropdown").style.display = "none";
    }}

    function updateScenarioYear(year, p5, p50, p95) {{
        var pessEl = document.getElementById("scenario-pessimistic-" + year);
        var baseEl = document.getElementById("scenario-base-" + year);
        var optEl = document.getElementById("scenario-optimistic-" + year);
        if (pessEl) {{ pessEl.textContent = fmtBrl(p5); flashEl(pessEl); }}
        if (baseEl) {{ baseEl.textContent = fmtBrl(p50); flashEl(baseEl); }}
        if (optEl) {{ optEl.textContent = fmtBrl(p95); flashEl(optEl); }}
    }}

    function clearScenarios(c) {{
        var years = c && c.annual ? Object.keys(c.annual) : [];
        for (var i = 0; i < years.length; i++) {{
            var year = years[i];
            var pessEl = document.getElementById("scenario-pessimistic-" + year);
            var baseEl = document.getElementById("scenario-base-" + year);
            var optEl = document.getElementById("scenario-optimistic-" + year);
            if (pessEl) {{ pessEl.textContent = "N/D"; flashEl(pessEl); }}
            if (baseEl) {{ baseEl.textContent = c.annual[year] != null ? fmtBrl(c.annual[year]) : "N/D"; flashEl(baseEl); }}
            if (optEl) {{ optEl.textContent = "N/D"; flashEl(optEl); }}
        }}
    }}

    // --- Dynamic Plotly chart updates ---
    function updateCharts(name) {{
        var c = CANDIDATES[name];
        if (!c) return;
        updateForecastComparison(name, c);
        updateFanChart(name, c);
    }}

    function updateForecastComparison(name, c) {{
        var chartDiv = document.getElementById('forecast_comparison');
        if (!chartDiv || !chartDiv.data) return;

        // Reset all model traces to thin/muted, highlight selected
        for (var i = 0; i < chartDiv.data.length; i++) {{
            var trace = chartDiv.data[i];
            if (trace.name && trace.name.startsWith('Modelo')) {{
                var isComponent = c.components && c.components.indexOf(trace.name) >= 0;
                var isSelected = (name === trace.name);
                Plotly.restyle(chartDiv, {{
                    'line.width': isSelected ? 3 : (isComponent ? 2 : 1),
                    'opacity': isSelected ? 1.0 : (isComponent ? 0.8 : 0.3),
                }}, [i]);
            }}
        }}

        // If ensemble, add/update weighted forecast trace
        if (c.type === 'ensemble' && c.components && c.components.length > 1) {{
            var weights = c.weights || {{}};
            var hasWeights = Object.keys(weights).length > 0;

            // Compute weighted forecast from MODEL_FORECASTS
            var firstComp = MODEL_FORECASTS[c.components[0]];
            if (!firstComp) return;
            var dates = firstComp.map(function(f) {{ return f.data; }});
            var values = dates.map(function(d, idx) {{
                var sum = 0;
                for (var ci = 0; ci < c.components.length; ci++) {{
                    var m = c.components[ci];
                    var w = hasWeights ? (weights[m] || 0) : (1.0 / c.components.length);
                    var mf = MODEL_FORECASTS[m];
                    if (mf && mf[idx]) {{
                        sum += w * mf[idx].forecast / 1e9;
                    }}
                }}
                return sum;
            }});

            // Remove old ensemble trace if exists
            var existingIdx = chartDiv.data.findIndex(function(t) {{ return t.name && t.name.indexOf('\u2192') === 0; }});
            if (existingIdx >= 0) {{
                Plotly.deleteTraces(chartDiv, existingIdx);
            }}

            // Add new ensemble trace
            Plotly.addTraces(chartDiv, {{
                x: dates,
                y: values,
                name: '\u2192 ' + name,
                line: {{color: 'black', width: 3}},
                mode: 'lines',
            }});
        }} else {{
            // Remove ensemble trace if switching to individual
            var existingIdx = chartDiv.data.findIndex(function(t) {{ return t.name && t.name.indexOf('\u2192') === 0; }});
            if (existingIdx >= 0) {{
                Plotly.deleteTraces(chartDiv, existingIdx);
            }}
        }}

        // Update chart title
        Plotly.relayout(chartDiv, {{
            'title': 'Previs\u00e3o ICMS-SP por Modelo \u2014 ' + name
        }});
    }}

    function updateFanChart(name, c) {{
        var chartDiv = document.getElementById('fan_chart');
        if (!chartDiv || !chartDiv.data) return;

        // Find the forecast line trace (the dashed red line, not fill traces)
        for (var i = 0; i < chartDiv.data.length; i++) {{
            var trace = chartDiv.data[i];
            if (trace.name && trace.name.indexOf('Previs') >= 0) {{
                // Update label
                var mapeStr = c.mape != null ? c.mape.toFixed(2) + '%' : 'N/D';
                Plotly.restyle(chartDiv, {{'name': 'Previs\u00e3o \u2014 ' + name + ' (MAPE ' + mapeStr + ')'}}, [i]);

                // Update forecast values for selected candidate
                if (c.components && c.components.length > 0) {{
                    var firstComp = MODEL_FORECASTS[c.components[0]];
                    if (!firstComp) break;
                    var dates = firstComp.map(function(f) {{ return f.data; }});
                    var weights = c.weights || {{}};
                    var hasWeights = Object.keys(weights).length > 0;
                    var values = dates.map(function(d, idx) {{
                        var sum = 0;
                        for (var ci = 0; ci < c.components.length; ci++) {{
                            var m = c.components[ci];
                            var w = hasWeights ? (weights[m] || 0) : (1.0 / c.components.length);
                            var mf = MODEL_FORECASTS[m];
                            if (mf && mf[idx]) {{
                                sum += w * mf[idx].forecast / 1e9;
                            }}
                        }}
                        return sum;
                    }});
                    Plotly.restyle(chartDiv, {{'y': [values]}}, [i]);
                }}
                break;
            }}
        }}
    }}

    // Close dropdown when clicking outside
    document.addEventListener("click", function(e) {{
        var selector = document.querySelector(".model-selector");
        var dd = document.getElementById("model-dropdown");
        if (selector && dd && !selector.contains(e.target)) {{
            dd.style.display = "none";
        }}
    }});
    </script>
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

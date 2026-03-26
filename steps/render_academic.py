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

    horizon_key = kwargs.get("horizon", "short")

    sarimax = _load(od, "run_sarimax_models")
    charts = _load(od, "generate_charts")
    validation = _load(od, "validate_forecasts")

    # If horizons exist, overlay horizon-specific fields on top of sarimax
    hz_data = sarimax.get("horizons", {}).get(horizon_key, {})

    static_charts = charts.get("static_charts", {})
    models = sarimax.get("models", {})
    diagnostics = sarimax.get("diagnostics", {})
    adf = sarimax.get("adf_test", {})
    annual_totals = hz_data.get("annual_totals", sarimax.get("annual_totals", {}))
    ensemble_weighting = hz_data.get("ensemble_weighting", sarimax.get("ensemble_weighting", {}))
    best_model = hz_data.get("best_model", sarimax.get("best_model", "N/A"))
    best_mape = hz_data.get("best_model_mape", sarimax.get("best_model_mape", "—"))
    all_candidates = hz_data.get("all_candidates", sarimax.get("all_candidates", {}))
    horizon = hz_data.get("forecast_horizon", sarimax.get("forecast_horizon", {}))
    mc_config = sarimax.get("monte_carlo_config", {})
    realized = annual_totals.get("_realized", {})

    # Model specification table with MAPE
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
        mape = diag.get("mape", "—")
        oos = diag.get("oos_validation", {})
        mape_std = oos.get("mape_std", "—")
        model_table_rows += f"""
        <tr>
            <td><strong>{name}</strong></td>
            <td>{spec}</td>
            <td>{cols}</td>
            <td>{aic}</td>
            <td>{bic}</td>
            <td>{lb_p}</td>
            <td>{mape}%</td>
            <td>{mape_std}%</td>
        </tr>"""

    # OOS expanding window detail table
    oos_window_rows = ""
    sample_oos = diagnostics.get("Modelo 2", {}).get("oos_validation", {})
    n_windows = sample_oos.get("n_windows", 0)
    oos_horizon = sample_oos.get("oos_horizon_months", 12)
    first_window = sample_oos.get("first_window_train_end", "—")
    last_window = sample_oos.get("last_window_train_end", "—")

    for name in models:
        diag = diagnostics.get(name, {})
        oos = diag.get("oos_validation", {})
        windows = oos.get("windows", [])
        for w in windows:
            oos_window_rows += f"""
            <tr>
                <td>{name}</td>
                <td>{w.get('train_end', '—')}</td>
                <td>{w.get('mape', w.get('mape_12m', '—'))}%</td>
            </tr>"""

    # Annual forecast table (point estimates only, skip _realized and *_mc)
    annual_rows = ""
    display_models = [k for k in annual_totals if not k.startswith("_") and not k.endswith("_mc")]
    if display_models:
        years = sorted(set(
            y for k in display_models
            for y in annual_totals[k].keys()
            if isinstance(annual_totals[k].get(y), (int, float))
        ))
        for year in years:
            row = f"<tr><td><strong>{year}</strong></td>"
            for model_name in display_models:
                val = annual_totals[model_name].get(year, "—")
                if isinstance(val, (int, float)):
                    row += f"<td>R$ {val:.2f}B</td>"
                else:
                    row += f"<td>—</td>"
            row += "</tr>"
            annual_rows += row
        model_headers = "".join(f"<th>{n}</th>" for n in display_models)
    else:
        model_headers = ""

    # Ensemble top 5 table
    top5 = sarimax.get("top5_ensembles", [])
    top5_rows = ""
    for ens in top5:
        comps = ", ".join(ens.get("components", []))
        weights_dict = ens.get("weights", {})
        weights_str = ", ".join(f"{k}: {v:.1%}" for k, v in weights_dict.items()) if weights_dict else "—"
        top5_rows += f"""
        <tr>
            <td><strong>{ens.get('name', '—')}</strong></td>
            <td>{comps}</td>
            <td>{weights_str}</td>
            <td>{ens.get('mape', '—')}%</td>
        </tr>"""

    # Best ensemble detail
    best_info = all_candidates.get(best_model, {})
    best_weights = best_info.get("weights", {})
    best_weights_str = ", ".join(f"{k}: {v:.1%}" for k, v in best_weights.items()) if best_weights else "—"
    best_components = ", ".join(best_info.get("components", []))

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
            <h2>8. Validacao</h2>
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
        h3 {{ color: #4a5568; margin-top: 1.5rem; }}
        table {{ width: 100%; border-collapse: collapse; margin: 1rem 0; font-size: 0.9rem; }}
        th, td {{ border: 1px solid #e2e8f0; padding: 0.5rem 0.8rem; text-align: left; }}
        th {{ background: #f7fafc; font-weight: 600; }}
        figure {{ margin: 1.5rem 0; text-align: center; }}
        figcaption {{ font-size: 0.85rem; color: #718096; margin-top: 0.5rem; font-style: italic; }}
        .abstract {{ background: #f7fafc; padding: 1.5rem; border-left: 4px solid #2b6cb0; margin: 1.5rem 0; }}
        .formula {{ background: #f7fafc; padding: 1rem 1.5rem; border-radius: 4px; font-family: 'Courier New', monospace; margin: 1rem 0; font-size: 0.95rem; }}
        section {{ margin-bottom: 2rem; }}
        footer {{ text-align: center; color: #a0aec0; font-size: 0.8rem; margin-top: 3rem; border-top: 1px solid #e2e8f0; padding-top: 1rem; }}
    </style>
</head>
<body>
    <h1>Previsao de Arrecadacao do ICMS-SP</h1>
    <p class="subtitle">AEFP — Assessoria de Economia e Financas Publicas<br>Relatorio Tecnico — Anexo Metodologico</p>

    <div class="abstract">
        <strong>Resumo:</strong> Este anexo documenta a metodologia de previsao da arrecadacao mensal do ICMS no Estado de Sao Paulo.
        Cinco modelos SARIMAX sao estimados com variaveis exogenas (IBC-BR, IGP-DI, dias uteis, dummies estruturais) e combinados
        em 31 ensembles via pesos inverse-MSE (Bates &amp; Granger, 1969). A selecao do melhor modelo/ensemble usa validacao
        fora da amostra com <strong>expanding window</strong> e horizonte de 12 meses a frente ({n_windows} janelas).
        Melhor candidato: <strong>{best_model}</strong> (MAPE medio = {best_mape}%).
        Intervalos de confianca sao obtidos por simulacao Monte Carlo ({mc_config.get('n_simulations', 1000)} trajetorias).
    </div>

    <section>
        <h2>1. Teste de Estacionariedade</h2>
        <p>Teste Augmented Dickey-Fuller sobre &Delta;log(ICMS_SP):</p>
        <table>
            <tr><th>Estatistica ADF</th><th>p-valor</th><th>Resultado</th></tr>
            <tr>
                <td>{adf.get('statistic', '—')}</td>
                <td>{adf.get('p_value', '—')}</td>
                <td>{'Estacionario (rejeita H0 de raiz unitaria)' if adf.get('stationary') else 'Nao estacionario'}</td>
            </tr>
        </table>
        <p>A serie log(ICMS_SP) em primeira diferenca e estacionaria, validando o uso de modelos ARIMA com d=1.</p>
    </section>

    <section>
        <h2>2. Especificacao dos Modelos Individuais</h2>
        <p>Cinco especificacoes SARIMAX sao estimadas sobre log(ICMS_SP), diferindo em ordens ARIMA/SARIMA
        e variaveis exogenas. A estimacao usa maxima verossimilhanca (MLE) sem restricoes de estacionariedade
        ou invertibilidade.</p>
        <table>
            <tr><th>Modelo</th><th>Especificacao</th><th>Variaveis Exogenas</th><th>AIC</th><th>BIC</th><th>Ljung-Box p</th><th>MAPE</th><th>MAPE std</th></tr>
            {model_table_rows}
        </table>
        <p><strong>Dummies estruturais:</strong></p>
        <ul>
            <li><em>LS2008NOV:</em> Level shift a partir de novembro/2008 (crise financeira global)</li>
            <li><em>TC2020APR04:</em> Transitory change abril-julho/2020 (pandemia COVID-19)</li>
            <li><em>TC2022OUT05:</em> Transitory change outubro/2022-maio/2023 (reforma tributaria estadual)</li>
        </ul>
    </section>

    <section>
        <h2>3. Validacao Fora da Amostra: Expanding Window</h2>

        <h3>3.1. Metodologia</h3>
        <p>A validacao out-of-sample (OOS) utiliza o metodo de <strong>expanding window com horizonte fixo de 12 meses</strong>.
        O procedimento garante que todas as dummies estruturais estejam estimadas no conjunto de treino:</p>
        <ol>
            <li>A primeira janela treina ate {first_window} (fim da ultima dummy estrutural TC2022OUT05)</li>
            <li>Cada janela subsequente expande o treino em 1 mes, mantendo o teste sempre nos proximos 12 meses</li>
            <li>A ultima janela treina ate {last_window}, testando nos 12 meses seguintes ate o ultimo dado observado</li>
            <li>Para cada janela, calcula-se o MAPE acumulado de 12 meses: |&Sigma;real - &Sigma;previsto| / &Sigma;real</li>
            <li>O MAPE final do modelo e a <strong>media dos MAPEs de todas as janelas</strong></li>
        </ol>
        <div class="formula">
            MAPE<sub>janela</sub> = |&Sigma;<sub>t=1..12</sub> y<sub>t</sub> - &Sigma;<sub>t=1..12</sub> &#375;<sub>t</sub>| / &Sigma;<sub>t=1..12</sub> y<sub>t</sub> &times; 100<br><br>
            MAPE<sub>modelo</sub> = (1/N) &times; &Sigma;<sub>j=1..N</sub> MAPE<sub>janela j</sub><br><br>
            N = {n_windows} janelas, horizonte = {oos_horizon} meses
        </div>
        <p>O desvio-padrao (std) entre janelas indica a <strong>estabilidade</strong> do modelo: std alto sugere
        desempenho preditivo variavel ao longo do tempo.</p>

        <h3>3.2. Resultados por Janela (amostra)</h3>
        <p>Tabela completa com MAPE de 12 meses por janela de treino, para cada modelo individual:</p>
        <details>
            <summary>Expandir tabela de janelas ({n_windows} janelas &times; {len(models)} modelos)</summary>
            <table>
                <tr><th>Modelo</th><th>Treino ate</th><th>MAPE 12m</th></tr>
                {oos_window_rows}
            </table>
        </details>
    </section>

    <section>
        <h2>4. Combinacao de Previsoes: Ensembles Inverse-MSE</h2>

        <h3>4.1. Metodo</h3>
        <p>As previsoes individuais sao combinadas em ensembles usando pesos inverse-MSE,
        conforme proposto por Bates &amp; Granger (1969). O metodo e padrao em bancos centrais
        (BCB, Fed, ECB, Bank of England) para combinacao de previsoes macroeconomicas.</p>
        <div class="formula">
            w<sub>i</sub> = (1 / MSE<sub>i</sub>) / &Sigma;<sub>j</sub> (1 / MSE<sub>j</sub>)<br><br>
            &#375;<sub>ensemble</sub> = &Sigma;<sub>i</sub> w<sub>i</sub> &times; &#375;<sub>i</sub>
        </div>
        <p>Onde MSE<sub>i</sub> e o erro quadratico medio do modelo <em>i</em> na janela de teste OOS.
        <strong>Os pesos sao recalculados em cada janela do expanding window</strong> — o ensemble e
        re-otimizado a cada mes, nao fixo. O MAPE reportado e a media dos MAPEs de 12 meses
        do ensemble ponderado em cada janela.</p>

        <h3>4.2. Todas as Combinacoes</h3>
        <p>Sao avaliadas todas as {len(all_candidates) - len(models)} combinacoes possiveis dos 5 modelos
        (pares, tripletos, quadrupletos e quintupleto), totalizando 31 ensembles.
        Os 5 melhores por MAPE OOS:</p>
        <table>
            <tr><th>Ensemble</th><th>Componentes</th><th>Pesos (ultima janela)</th><th>MAPE medio</th></tr>
            {top5_rows}
        </table>

        <h3>4.3. Modelo Selecionado</h3>
        <p>O candidato com menor MAPE medio nas {n_windows} janelas e:</p>
        <ul>
            <li><strong>{best_model}</strong></li>
            <li>Componentes: {best_components}</li>
            <li>Pesos (ultima janela): {best_weights_str}</li>
            <li>MAPE medio: {best_mape}%</li>
        </ul>
    </section>

    <section>
        <h2>5. Intervalos de Confianca: Monte Carlo</h2>
        <p>Os intervalos de confianca sao obtidos por simulacao Monte Carlo com
        {mc_config.get('n_simulations', 1000)} trajetorias. Para cada modelo componente do ensemble:</p>
        <ol>
            <li>Simula-se <code>nsimulations</code> trajetorias futuras usando <code>model.simulate()</code></li>
            <li>Cada trajetoria e convertida de log-escala para escala real (exp)</li>
            <li>As trajetorias dos componentes sao combinadas com pesos inverse-MSE</li>
            <li>Percentis (5, 25, 50, 75, 95) sao extraidos das trajetorias do ensemble</li>
        </ol>
        <p>Para totais anuais, as trajetorias mensais sao somadas por ano antes de calcular os percentis,
        preservando a correlacao temporal intra-ano.</p>
    </section>

    <section>
        <h2>6. Previsoes Anuais</h2>
        <p>Totais anuais em R$ bilhoes. Para {realized.get('year', '—')}, o total inclui
        <strong>{realized.get('months', '—')} meses realizados</strong> (R$ {realized.get('total_brl_bi', '—')}B)
        + {12 - realized.get('months', 0)} meses projetados.</p>
        <table>
            <tr><th>Ano</th>{model_headers}</tr>
            {annual_rows}
        </table>
    </section>

    <section>
        <h2>7. Graficos</h2>
        {chart_imgs}
    </section>

    {validation_html}

    <section>
        <h2>9. Referencias</h2>
        <ul>
            <li>Bates, J.M. &amp; Granger, C.W.J. (1969). The Combination of Forecasts. <em>Operational Research Quarterly</em>, 20(4), 451-468.</li>
            <li>Timmermann, A. (2006). Forecast Combinations. In: Elliott, G., Granger, C.W.J. &amp; Timmermann, A. (eds.), <em>Handbook of Economic Forecasting</em>, Vol. 1, Ch. 4.</li>
            <li>Hamilton, J.D. (1994). <em>Time Series Analysis</em>. Princeton University Press.</li>
            <li>Hyndman, R.J. &amp; Athanasopoulos, G. (2021). <em>Forecasting: Principles and Practice</em>, 3rd ed.</li>
            <li>BCB — Sistema Gerenciador de Series Temporais (SGS), serie 24363 (IBC-BR)</li>
            <li>IPEA Data — IGP-DI mensal (IGP12_IGPDI12)</li>
            <li>BCB — Sistema de Expectativas de Mercado (Focus)</li>
        </ul>
    </section>

    <footer>
        Horizonte: {horizon.get('forecast_start', '—')} a {horizon.get('forecast_end', '—')} ({horizon.get('n_months', '—')} meses) |
        OOS: {n_windows} janelas expanding window, {oos_horizon}m ahead |
        MC: {mc_config.get('n_simulations', '—')} simulacoes |
        Pipeline Engine v1 — Gerado automaticamente
    </footer>
</body>
</html>"""

    suffix = f"_{horizon_key}" if horizon_key != "short" else ""
    html_path = report_dir / f"academic_report{suffix}.html"
    html_path.write_text(html, encoding="utf-8")

    result = {
        "html_path": str(html_path),
        "status": "ok"
    }

    out_file = od / "render_academic.json"
    out_file.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    return result

# previsao-icms-sp

Previsao de arrecadacao ICMS-SP usando 5 modelos SARIMAX com dados reais de APIs publicas (BCB, IPEA, Focus) e historico SEFAZ. Produz dashboard interativo e relatorio academico com diagnosticos, intervalos de confianca via Monte Carlo e validacao out-of-sample.

## Pipeline DAG

```
fetch_macro_data ──┐
  [python, $0]     ├── prepare_base ── run_sarimax_models ─┬── cross_validate_r (opt)
load_sefaz_data ───┘     [python]      [python, checkpoint] │     [python]
                                                            │
                                          ┌─────────────────┼── validate_forecasts
                                          │                 │       [python]
                                          │                 │
                                          │    qualitative_analysis (opt, non-blocking)
                                          │      [copilot_cli, gpt-5.4]
                                          │                 │
                                          │    generate_charts
                                          │      [python]   │
                                          │                 │
                                          ├── render_dashboard (short) ──┐
                                          ├── render_dashboard (long)  ──┤
                                          ├── render_academic (short)  ──┤── regression_tracker
                                          └── render_academic (long)  ──┘    [python, non-blocking]
```

## Steps

| Step | Executor | O que faz |
|------|----------|-----------|
| `fetch_macro_data` | python | Busca IBC-BR (BCB SGS), IGP-DI (IPEA), expectativas Focus |
| `load_sefaz_data` | python | Carrega historico ICMS-SP do Excel SEFAZ |
| `prepare_base` | python | Merge macro + SEFAZ, cria lags, dummies, projecoes |
| `run_sarimax_models` | python | Ajusta 5 modelos SARIMAX, forecasts, Monte Carlo, diagnosticos |
| `cross_validate_r` | python | Cross-check com modelo R original (opcional) |
| `validate_forecasts` | python | Validacao deterministica dos forecasts |
| `qualitative_analysis` | copilot_cli (gpt-5.4) | Analise qualitativa/narrativa dos resultados (opt-in) |
| `generate_charts` | python | Graficos Plotly (interativos) e matplotlib (estaticos) |
| `render_dashboard` | python | Dashboard HTML interativo (Jinja2), por horizonte |
| `render_academic` | python | Relatorio academico HTML com metodologia e diagnosticos |
| `regression_tracker` | python | Compara run atual com anteriores para detectar regressoes |

## Custo por execucao

- **Sem analise qualitativa (default):** $0.00 — pipeline 100% deterministico
- **Com analise qualitativa:** ~$0.30 — um unico step LLM via Copilot CLI

## Pipeline dinamico

O pipeline aceita requests em linguagem natural. Um interpreter LLM (`gpt-4.1-mini`) analisa o pedido e configura os steps:

```bash
python run.py                                          # defaults (todos os modelos, sem qualitativa)
python run.py "cenario otimista com PIB +3.5%"         # override de cenario macro
python run.py "apenas modelos 3 e 4, horizonte 2027"   # selecao de modelos
python run.py "incluir analise qualitativa"            # opt-in no step LLM
python run.py "incluir cross-check com R"              # ativa cross_validate_r
python run.py --dry-run "test"                         # preview sem executar
python run.py --resume <run-id>                        # retomar de checkpoint
python run.py --last                                   # re-rodar ultimo config
```

### Steps condicionais

| Step | Default | Ativa quando |
|------|---------|-------------|
| `qualitative_analysis` | skip | usuario pede analise qualitativa/narrativa |
| `cross_validate_r` | skip | usuario pede cross-check com R |
| `render_academic` | active | sempre, exceto se usuario pedir so dashboard |
| `render_dashboard` | active | sempre, exceto se usuario pedir so academico |

### Parametros configuraveis

| Step | Parametro | Default |
|------|-----------|---------|
| `prepare_base` | `pib_growth_override` | consenso Focus |
| `prepare_base` | `inflation_override` | consenso Focus |
| `prepare_base` | `horizon_end` | 2026 |
| `run_sarimax_models` | `models_to_run` | todos (1-5) |
| `run_sarimax_models` | `n_simulations` | 1000 |

## Setup

```bash
pip install -r requirements-runtime.txt
# Copiar .env.example para .env e preencher API keys (so necessario se usar qualitative_analysis)
```

### Dados de entrada

- `data/dados_sefaz.xlsx` — historico de arrecadacao ICMS-SP (SEFAZ)
- APIs publicas (fetch automatico): BCB SGS (IBC-BR), IPEA (IGP-DI), Focus (expectativas)
- `data/r_original/modelo_previsao_29_10.Rmd` — modelo R original (para cross-check)

## Output

Outputs em `workspace/outputs/runs/{run_id}/`:

| Arquivo | Descricao |
|---------|-----------|
| `report/dashboard_short.html` | Dashboard interativo — horizonte curto |
| `report/dashboard_long.html` | Dashboard interativo — horizonte longo |
| `report/academic_short.html` | Relatorio academico — horizonte curto |
| `report/academic_long.html` | Relatorio academico — horizonte longo |
| `run_sarimax_models.json` | Forecasts, diagnosticos, Monte Carlo paths |
| `validate_forecasts.json` | Resultados da validacao deterministica |
| `regression_tracker.json` | Comparacao com runs anteriores |
| `manifest.json` | Metadata do run |
| `ledger.jsonl` | Event stream de cada step |

## Estrutura do repo

```
previsao-icms-sp/
├── pipelines/v1.json          # DAG definition
├── pipelines/v1.config.json   # Dynamic pipeline config (interpreter rules)
├── steps/                     # Step scripts (Python)
├── contracts/steps/           # Step contracts (inputs, outputs, executor)
├── contracts/schemas/         # JSON schemas para validacao de output
├── templates/pages/           # Jinja2 templates (dashboard_premium, academic_report)
├── data/                      # Input data (SEFAZ Excel, R original)
├── config/                    # Pipeline config
├── run.py                     # Entry point
├── lib/                       # Pipeline engine runtime (nao modificar)
└── workspace/outputs/         # Run outputs (gitignored)
```

## Built with

[Pipeline Engine](https://github.com/your-org/pipeline-engine) — DAG runner com executor plugins, checkpointing e cost tracking.

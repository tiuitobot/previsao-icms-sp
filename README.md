# previsao-icms-sp

Previsao de arrecadacao ICMS-SP usando 5 modelos SARIMAX com dados reais de APIs publicas (BCB, IPEA, Focus) e historico SEFAZ. Produz dashboard interativo e relatorio academico com diagnosticos, intervalos de confianca via Monte Carlo e validacao out-of-sample.

## Quick Start

### 1. Abra o projeto no VS Code

Abra o VS Code, va em **File > Open Folder** e selecione a pasta `previsao-icms-sp`.

Para abrir o terminal integrado, pressione **Ctrl + `** (crase). Todos os comandos abaixo devem ser digitados nesse terminal.

### 2. Instale Python e as dependencias

Instale o [Python 3.12+](https://www.python.org/downloads/) se ainda nao tiver. Na instalacao, marque a opcao **"Add Python to PATH"**.

Depois, no terminal do VS Code:

```bash
pip install -r requirements-runtime.txt
```

Se `pip` nao for reconhecido, tente `py -m pip install -r requirements-runtime.txt`.

### 3. Coloque o arquivo SEFAZ

Copie o arquivo `dados_sefaz.xlsx` para a pasta `data/` do projeto. Voce pode arrastar o arquivo direto para a pasta no explorador do VS Code.

### 4. Rode o pipeline

```bash
python run.py
```

O pipeline busca dados macro automaticamente via APIs publicas (BCB, IPEA, Focus). O unico arquivo que voce precisa fornecer e o Excel da SEFAZ.

### 5. Veja o resultado

Quando terminar, o terminal mostra o caminho do output, por exemplo:

```
Output: workspace/outputs/runs/20260327-161500/
```

Para abrir o dashboard, clique com botao direito no arquivo HTML no explorador do VS Code e selecione **Open with Live Server** (se tiver a extensao) ou **Reveal in File Explorer**, e abra o arquivo `.html` no navegador (Chrome, Edge, etc.).

### Exemplos de uso (digite no terminal do VS Code)

```bash
# Rodar com defaults (todos os modelos, custo $0)
python run.py

# Rodar com cenario customizado
python run.py "cenario otimista com PIB +3.5%"

# Rodar apenas modelos especificos
python run.py "apenas modelos 3 e 4, horizonte 2027"

# Incluir analise qualitativa (usa LLM, ~$0.30)
python run.py "incluir analise qualitativa"

# Preview sem executar (ver os steps sem gastar nada)
python run.py --dry-run
```

### (Opcional) Configurar .env para analise qualitativa

So e necessario se voce quiser usar o step de analise qualitativa via LLM:

```bash
copy .env.example .env
# Abra .env no VS Code e preencha as API keys
```

## Como usar

```bash
# Rodar com defaults (todos os modelos, sem analise qualitativa)
python run.py

# Rodar com cenario customizado (aciona interpreter LLM via Copilot CLI)
python run.py "cenario otimista com PIB +3.5%"
python run.py "apenas modelos 3 e 4, horizonte 2027"
python run.py "incluir analise qualitativa"
python run.py "incluir cross-check com R"

# Preview sem executar
python run.py --dry-run

# Retomar run interrompido
python run.py --resume <run-id>

# Re-rodar com ultimo config
python run.py --last
```

Sem argumento de texto, o pipeline roda 100% deterministico ($0). Com texto, um interpreter LLM (Copilot CLI, gpt-5.4) analisa o pedido e configura os steps automaticamente.

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

- **Sem argumento de texto (default):** $0.00 — pipeline 100% deterministico
- **Com argumento de texto:** ~$0.01 — interpreter LLM resolve o pedido
- **Com analise qualitativa:** ~$0.30 — step LLM via Copilot CLI

## Steps condicionais

| Step | Default | Ativa quando |
|------|---------|-------------|
| `qualitative_analysis` | skip | usuario pede analise qualitativa/narrativa |
| `cross_validate_r` | skip | usuario pede cross-check com R |
| `render_academic` | active | sempre, exceto se usuario pedir so dashboard |
| `render_dashboard` | active | sempre, exceto se usuario pedir so academico |

## Parametros configuraveis

| Step | Parametro | Default |
|------|-----------|---------|
| `prepare_base` | `pib_growth_override` | consenso Focus |
| `prepare_base` | `inflation_override` | consenso Focus |
| `prepare_base` | `horizon_end` | 2026 |
| `run_sarimax_models` | `models_to_run` | todos (1-5) |
| `run_sarimax_models` | `n_simulations` | 1000 |

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
├── run.py                     # Entry point
├── pipelines/v1.json          # DAG definition
├── pipelines/v1.config.json   # Dynamic pipeline config (interpreter rules)
├── steps/                     # Step scripts (Python)
├── contracts/steps/           # Step contracts (inputs, outputs, executor)
├── contracts/schemas/         # JSON schemas para validacao de output
├── templates/pages/           # Jinja2 templates (dashboard_premium, academic_report)
├── data/                      # Input data (SEFAZ Excel)
├── config/                    # Pipeline config
├── lib/                       # Pipeline engine runtime (nao modificar)
└── workspace/outputs/         # Run outputs (gitignored)
```

## Requisitos

- Python 3.12+
- Pacotes: `pandas`, `numpy`, `statsmodels`, `requests`, `openpyxl`, `plotly`, `matplotlib`, `jsonschema`, `rich`
- Arquivo `data/dados_sefaz.xlsx` (historico ICMS-SP da SEFAZ)
- (Opcional) Copilot CLI instalado para analise qualitativa e interpreter

# previsao-icms-sp-v1

> Pipeline completo para relatorios analiticos com narrativa executiva e auditoria. Domain: previsao-icms-sp. Objective: project deliverable.

![Pipeline Status](https://img.shields.io/badge/status-active-brightgreen) ![Cost per Run](https://img.shields.io/badge/cost%20per%20run-%240.00-blue) ![Steps](https://img.shields.io/badge/steps-11-informational) ![Last Updated](https://img.shields.io/badge/updated-2026-03-25-lightgrey)

---

## What This Pipeline Does

Pipeline completo para relatorios analiticos com narrativa executiva e auditoria. Domain: previsao-icms-sp. Objective: project deliverable.

## Architecture

### Pipeline DAG

```
┌─────────────────┐
│  data_ingester  │
└─────────────────┘
   gpt-4.1, $0.00
         │
         └┬──────────────┬───────┐
          │              │       │
┌───────────────────┐    │       │
│ domain_specialist │    │       │
└───────────────────┘    │       │
    gpt-4.1, $0.00       │       │
          │              │       │
         ┌┴──────────────┘
         │                       │
┌─────────────────┐              │
│   data_auditor  │              │
└─────────────────┘              │
   gpt-4.1, $0.00                │
         │                       │
         └┬────────────────┬─┐
          │                │ │   │
┌───────────────────┐      │ │   │
│  insight_explorer │      │ │   │
└───────────────────┘      │ │   │
    gpt-4.1, $0.00         │ │   │
          │                │ │   │
          ┼────────────────┴─┼─┐
          │                  │ │ │
┌───────────────────┐        │ │ │
│  executive_writer │        │ │ │
└───────────────────┘        │ │ │
    gpt-4.1, $0.00           │ │ │
          │                  │ │ │
          ┼──────────────────┴─┴─┼─┬───────────┐
          │                      │ │           │
┌───────────────────┐            │ │           │
│  technical_writer │            │ │           │
└───────────────────┘            │ │           │
    gpt-4.1, $0.00               │ │           │
          │                      │ │           │
          ┼──────────────────────┴─┴───────────┼─┐
          │                                    │ │
┌───────────────────┐                          │ │
│  output_validator │                          │ │
└───────────────────┘                          │ │
    gpt-4.1, $0.00                             │ │
          │                                    │ │
          └────┬───────────────────────────────┴─┘
               │
┌─────────────────────────────┐
│      report_synthesizer     │
└─────────────────────────────┘
   gpt-4.1, $0.00, checkpoint
               │
         ┌─────┴─────────────────┐
         │                       │
┌─────────────────┐    ┌───────────────────┐
│  html_renderer  │    │  external_auditor │
└─────────────────┘    └───────────────────┘
   gpt-4.1, $0.00          gpt-4.1, $0.00
         │
         └──┐
            │
┌───────────────────────┐
│  html_quality_checker │
└───────────────────────┘
      gpt-4.1, $0.00
```

### Step Breakdown

| # | Step | Type | Executor | Model | Est. Cost | Description |
|---|------|------|----------|-------|-----------|-------------|
| 0 | **Data Ingester** | deterministic | `python` | gpt-4.1 | $0.00 | Load and normalize input data from all declared sources. |
| 1 | **Domain Specialist** | llm | `openai_api` | gpt-4.1 | $0.00 | Evaluate context and propose execution strategy based on ingested data. |
| 2 | **Data Auditor** | llm | `openai_api` | gpt-4.1 | $0.00 | Build factsheet from source data with traceable keys. |
| 3 | **Insight Explorer** | llm | `openai_api` | gpt-4.1 | $0.00 | Identify ranked insights and implications. |
| 4 | **Executive Writer** | llm | `openai_api` | gpt-4.1 | $0.00 | Draft the executive narrative with implications. |
| 5 | **Technical Writer** | llm | `openai_api` | gpt-4.1 | $0.00 | Write detailed technical sections with references. |
| 6 | **Output Validator** | deterministic | `python` | gpt-4.1 | $0.00 | Cross-check all LLM outputs against source data. Flag numeric mismatches and unsupported claims. |
| 7 | **Report Synthesizer** | llm | `openai_api` | gpt-4.1 | $0.00 | Compile final report, resolve validation issues, structure for template. |
| 8 | **HTML Renderer** | deterministic | `python` | gpt-4.1 | $0.00 | Render final report to HTML using Jinja2 template. |
| 9 | **HTML Quality Checker** | deterministic | `python` | gpt-4.1 | $0.00 | Validate HTML: no markdown artifacts, correct lang, no mixed languages, professional appearance. |
| 10 | **External Auditor** | llm | `openai_api` | gpt-4.1 | $0.00 | Independent cold audit of the final deliverable. Score accuracy, completeness, consistency. |

**Total estimated cost per run:** $0.00
**Typical execution time:** varies by data size

### Data Flow

```
Input (JSON)
  → Data Ingester [deterministic, python]
  → Domain Specialist [llm, openai_api]
  → Data Auditor [llm, openai_api]
  → Insight Explorer [llm, openai_api]
  → Executive Writer [llm, openai_api]
  → Technical Writer [llm, openai_api]
  → Output Validator [deterministic, python]
  → Report Synthesizer [llm, openai_api]
  → HTML Renderer [deterministic, python]
  → HTML Quality Checker [deterministic, python]
  → External Auditor [llm, openai_api]
  → Output (JSON)
```

## Quick Start

### Prerequisites

- Python 3.12+
- API keys for your chosen LLM provider (see `.env.example`)

### Setup

```bash
# Clone the repo
git clone <repo-url>
cd previsao-icms-sp-v1

# Configure environment
cp .env.example .env
# Fill in your API keys in .env

# Install dependencies
pip install -r requirements-runtime.txt
```

### Run

```bash
# Preview the pipeline DAG (no API calls, no cost)
python3 -m lib.runner --pipeline pipelines/v1.json --dry-run

# Execute the full pipeline
python3 -m lib.runner --pipeline pipelines/v1.json --data-dir data/

# Resume from a checkpoint or after failure
python3 -m lib.runner --pipeline pipelines/v1.json --run-id <run-id> --resume
```

### Output

Outputs are written to `workspace/outputs/runs/{run_id}/`:

| File | Description |
|------|-------------|
| `manifest.json` | Run metadata (pipeline version, timestamps, config) |
| `ledger.jsonl` | Append-only event stream for every step transition |
| `run_state.json` | Per-step status, timing, and error details |
| `external_audit.json` | **The final deliverable** |

## Pipeline Design

### Why This Architecture

This pipeline decomposes the problem into discrete, auditable steps. Each step has a single responsibility and a clear contract defining expected inputs and outputs. Deterministic steps handle data loading and assembly, while LLM steps handle analysis and generation. Checkpoints pause execution for human review at critical junctures.

### Quality Controls

| Control | Steps | Purpose |
|---------|-------|---------|
| Schema validation | HTML Quality Checker, HTML Renderer, Data Ingester, Output Validator, Report Synthesizer, Domain Specialist, External Auditor, Technical Writer, Insight Explorer, Data Auditor, Executive Writer | Ensures step outputs conform to expected structure |
| Checkpoints | Report Synthesizer | Pauses for human review before proceeding |
| Fixups | None configured | Deterministic corrections applied automatically |

### Contracts

LLM steps are guided by **contracts** — structured prompts that define exactly what the model should do, what inputs it receives, and what output schema it must follow.

| Step | Contract | Model | Purpose |
|------|----------|-------|---------|
| Domain Specialist | `contracts/steps/domain_specialist.json` | gpt-4.1 | Evaluate context and propose execution strategy based on ingested data. |
| Data Auditor | `contracts/steps/data_auditor.json` | gpt-4.1 | Build factsheet from source data with traceable keys. |
| Insight Explorer | `contracts/steps/insight_explorer.json` | gpt-4.1 | Identify ranked insights and implications. |
| Executive Writer | `contracts/steps/executive_writer.json` | gpt-4.1 | Draft the executive narrative with implications. |
| Technical Writer | `contracts/steps/technical_writer.json` | gpt-4.1 | Write detailed technical sections with references. |
| Report Synthesizer | `contracts/steps/report_synthesizer.json` | gpt-4.1 | Compile final report, resolve validation issues, structure for template. |
| External Auditor | `contracts/steps/external_auditor.json` | gpt-4.1 | Independent cold audit of the final deliverable. Score accuracy, completeness, c |

## Iterating

After the first run, review outputs and iterate:

1. **Inspect outputs** in `workspace/outputs/runs/{run_id}/`
2. **Edit contracts** in `contracts/v1/` to refine LLM behavior
3. **Re-run** with `--resume` to skip completed deterministic steps
4. **Log changes** in `docs/ITERATIONS.md` to maintain a decision trail

<details>
<summary>Iteration tips</summary>

- Start by reviewing the final output for quality issues
- Trace problems back to the responsible step using `ledger.jsonl`
- Adjust the contract for that step (prompt, schema, acceptance criteria)
- Use `--dry-run` to validate the pipeline structure before spending on API calls
- Each iteration builds on checkpointed state — you only re-run what changed

</details>

## Built With

- **[Pipeline Engine](https://github.com/your-org/pipeline-engine)** — DAG-based pipeline runner with executor plugins, checkpointing, and cost tracking
- **Archetype:** `custom`

## Cost Breakdown

| Component | Est. Cost |
|-----------|-----------|
| Data Ingester | $0.00 |
| Domain Specialist | $0.00 |
| Data Auditor | $0.00 |
| Insight Explorer | $0.00 |
| Executive Writer | $0.00 |
| Technical Writer | $0.00 |
| Output Validator | $0.00 |
| Report Synthesizer | $0.00 |
| HTML Renderer | $0.00 |
| HTML Quality Checker | $0.00 |
| External Auditor | $0.00 |
| **Total per run** | **$0.00** |

## Project Structure

```
previsao-icms-sp-v1/
├── pipelines/          # Pipeline DAG definitions (JSON)
├── contracts/
│   ├── steps/          # Step definitions (inputs, outputs, executor)
│   └── schemas/        # JSON schemas for step output validation
├── data/               # Input data
├── lib/                # Pipeline engine runtime
├── workspace/outputs/  # Run outputs (gitignored)
└── docs/               # Design decisions and iteration log
```

## License

See LICENSE file.

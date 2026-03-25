# Executors

Auto-generated. [[_index|<- Back to catalog]]
Full documentation: see `docs/EXECUTORS.md`.

## Quick check: what's available?

```bash
python3 scripts/check_executors.py
```

## Decision guide

Use this order of preference when choosing `base_executor` and per-step executors:

| Priority | Executor | Type | Cost | Schema output | Web search | When to use |
|---|---|---|---|---|---|---|
| 1 | `python` | Local | $0 | N/A | N/A | **Always first.** Anything that doesn't need LLM judgment: data fetching, validation, rendering, transforms. |
| 2 | `azure_openai` | API | Tracked | Yes | Yes | **Primary API.** Use when you need schema output, web search, or cost tracking. Responses API. |
| 3 | `openai_api` | API | Tracked | Yes | Via tools | **Fallback if no Azure.** Direct OpenAI Responses API. |
| 4 | `anthropic_api` | API | Tracked | No | No | **Claude via API.** Use when you need Claude models. No schema output — use prompt-based JSON. |
| 5 | `codex_cli` | CLI | Not tracked | Yes (`--output-schema`) | Yes | **CLI with schema.** Good for mechanical tasks. File access. |
| 6 | `claude_cli` | CLI | Not tracked | No | Yes | **Claude CLI.** Web search + file access. |
| 7 | `kimi_api` | API | Partial | No | No | **Budget.** Kimi K2.5 via Azure AI Foundry. |
| 8 | `copilot_cli` | CLI | Not tracked | No | Yes | **GitHub Copilot.** Needs GITHUB_TOKEN. |

## Environment requirements

| Executor | Env vars / binaries needed |
|---|---|
| `python` | Always available |
| `azure_openai` | `AZURE_OPENAI_API_KEY` + `AZURE_OPENAI_ENDPOINT` |
| `openai_api` | `OPENAI_API_KEY` (without `AZURE_OPENAI_ENDPOINT`) |
| `anthropic_api` | `ANTHROPIC_API_KEY` |
| `kimi_api` | `KIMI_API_KEY` + `KIMI_ENDPOINT` (or `AZURE_KIMI_*`) |
| `codex_cli` | `codex` binary in PATH |
| `claude_cli` | `claude` binary in PATH |
| `copilot_cli` | `copilot` binary in PATH + `GITHUB_TOKEN` |

## Source files

| Executor | File |
|---|---|
| `python` | `lib/executors/python.py` |
| `azure_openai` | `lib/executors/azure_openai.py` |
| `openai_api` | `lib/executors/openai_api.py` |
| `anthropic_api` | `lib/executors/anthropic_api.py` |
| `kimi_api` | `lib/executors/kimi_api.py` |
| `codex_cli` | `lib/executors/codex_cli.py` |
| `claude_cli` | `lib/executors/claude_cli.py` |
| `copilot_cli` | `lib/executors/copilot_cli.py` |

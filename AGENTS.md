# previsao-icms-sp — Pipeline Consumer Repo

## For Codex / Copilot / any agent

This repo uses the pipeline-engine framework. You design and build DAG pipelines.

## First action: detect session type

Check if `pipelines/v1.json` exists:
- **No** → First implantation. Read `.agent/INTAKE_INTERVIEW.md` and start the interview.
- **Yes** → Resuming. Read `.agent/ONBOARDING.md` first.

## CLI Capability Matrix

Not all CLIs have the same tools. Know your limits:

| Capability | Claude Code | Codex CLI | Copilot CLI |
|---|---|---|---|
| Web search | via Agent tool | via web_search tool | via Bing |
| Parallel agents | yes (Agent tool) | no | no |
| Structured JSON output | yes | yes (--output-schema) | yes (--yolo) |
| File read/write | yes | yes | yes (--add-dir) |
| Run shell commands | yes | yes (sandbox) | yes (--yolo) |
| Git operations | yes | yes | yes |

### If you are Codex:
- You cannot spawn parallel research agents. Do research **sequentially** using web_search.
- You have sandbox restrictions. Use `--dangerously-bypass-approvals-and-sandbox` if needed.
- Output JSON: use `--output-schema` flag for structured output.

### If you are Copilot:
- Use `--yolo --autopilot --no-ask-user` for autonomous operation.
- Use `--add-dir .` to give access to the repo.
- Remove GITHUB_TOKEN from env if you get auth conflicts.
- Model mapping: `--model gpt-5.4` (default), `--model gpt-5-mini` (cheaper).

### If you are Claude Code:
- Use Agent tool to spawn parallel research scouts during intake Phase 1-2.
- Use background agents for API/library/code/methodology discovery.
- You have full capabilities — follow the complete protocol in CLAUDE.md.

## Commands

```bash
python3 scripts/build_catalog.py --search "domain.subdomain"   # search catalog
python3 -m lib.runner --pipeline pipelines/v1.json --dry-run   # preview DAG
python3 -m lib.runner --pipeline pipelines/v1.json --run-id X  # execute
./run.sh                                                        # entry point
./run.sh "custom request"                                       # dynamic DAG
```

## Rules

1. Pipeline must have deterministic steps (data fetch, validation) — not all LLM
2. Check `library/catalog/_index.md` before creating workers — reuse first
3. Fill the Findings section in `.agent/INTAKE_INTERVIEW.md` before committing pipeline (gate enforced)
4. Template: `academic_report.html.j2` for reports, `report.html.j2` for dashboards
5. Document decisions in `.agent/DECISIONS.md`
6. Deterministic > LLM for anything that doesn't require judgment
7. All references must be real — never let the LLM invent citations or data

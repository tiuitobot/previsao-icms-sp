#!/usr/bin/env bash
# Pipeline runner — single entry point
# Template: {PIPELINE_NAME} consumer repo
#
# Usage:
#   ./run.sh                                    # run with defaults
#   ./run.sh "análise focada em renda fixa"     # run with user request
#   ./run.sh --data path/to/file.xlsx           # run with input file
#   ./run.sh --resume <run-id>                  # resume a paused run
#   ./run.sh --last                             # re-run with last config
#   ./run.sh --dry-run "my request"             # preview without executing
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
PIPELINE="pipelines/v1.json"
CONFIG="${PIPELINE%.json}.config.json"
RUN_ID="$(date +%Y%m%d-%H%M%S)"
DATA_DIR="data"
REQUEST=""
RESUME=""
DRY_RUN=""
EXTRA_ARGS=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --data) DATA_DIR="$2"; shift 2;;
    --pipeline) PIPELINE="$2"; CONFIG="${PIPELINE%.json}.config.json"; shift 2;;
    --run-id) RUN_ID="$2"; shift 2;;
    --resume) RESUME="$2"; shift 2;;
    --last)
      LAST=$(tail -1 "$ROOT/workspace/outputs/runs/index.jsonl" 2>/dev/null | python3 -c "import json,sys; print(json.load(sys.stdin)['run_id'])" 2>/dev/null || echo "")
      if [ -z "$LAST" ]; then echo "No previous runs found"; exit 1; fi
      RUN_ID="$LAST"; RESUME="$LAST"; shift;;
    --dry-run) DRY_RUN="--dry-run"; shift;;
    --no-ui) EXTRA_ARGS="$EXTRA_ARGS --no-ui"; shift;;
    -*) echo "Unknown flag: $1"; exit 1;;
    *) REQUEST="$1"; shift;;
  esac
done

cd "$ROOT"

# Handle resume
if [ -n "$RESUME" ]; then
  echo "Resuming run: $RESUME"
  python3 -m lib.runner --pipeline "$PIPELINE" --run-id "$RESUME" --resume $EXTRA_ARGS
  exit $?
fi

# Save user request
if [ -n "$REQUEST" ]; then
  mkdir -p "$DATA_DIR"
  python3 -c "
import json
from datetime import datetime
json.dump({
    'user_request': '''$REQUEST''',
    'timestamp': datetime.now().isoformat()
}, open('$DATA_DIR/user_request.json', 'w'), ensure_ascii=False, indent=2)
"
  echo "Request: $REQUEST"
fi

# Handle file input
if [ -f "$DATA_DIR" ]; then
  FILE="$DATA_DIR"
  DATA_DIR="data"
  mkdir -p "$DATA_DIR"
  cp "$FILE" "$DATA_DIR/"
  echo "Input file copied to data/"
fi

# Check if pipeline has a config (dynamic DAG)
if [ -f "$CONFIG" ] && [ -z "$DRY_RUN" ]; then
  echo "Dynamic pipeline detected — running interpreter..."

  # Stage 1: Run interpreter to resolve the pipeline
  INTERP_DIR="workspace/outputs/runs/$RUN_ID"
  mkdir -p "$INTERP_DIR"

  # Call interpreter LLM to analyze request and produce interpretation
  python3 -c "
import json, sys
sys.path.insert(0, '.')
from lib.executors import get_executor

# Load inputs
request = ''
try:
    request = json.load(open('$DATA_DIR/user_request.json')).get('user_request', '')
except: pass

config = json.load(open('$CONFIG'))
pipeline = json.load(open('$PIPELINE'))

# Build prompt for interpreter
step_descriptions = []
for s in pipeline['steps']:
    step_descriptions.append(f'- {s[\"id\"]}: {s.get(\"type\", \"normal\")}, executor={s.get(\"executor\", \"inherited\")}')

prompt = f'''User request: {request}

Pipeline config:
{json.dumps(config, indent=2, ensure_ascii=False)}

Available steps:
{chr(10).join(step_descriptions)}

Based on the user request and config, produce the interpretation JSON.'''

contract = '''You are a pipeline interpreter. Read the user request and pipeline config, then decide:
1. skip_steps: step IDs to deactivate (only if explicitly conditional in config)
2. step_params: parameters to inject into specific steps
3. user_context: 1-3 sentence summary of user intent for LLM steps
Respond in valid JSON only.'''

try:
    executor = get_executor('azure_openai')
    interp_model = config.get('interpreter_model', 'gpt-4.1-mini')
    result = executor.run(prompt=prompt, system_prompt=contract, model=interp_model)
    content = result.content.strip()
    if content.startswith('\`\`\`'):
        lines = content.splitlines()
        content = '\\n'.join(lines[1:-1] if lines[-1].strip() == '\`\`\`' else lines[1:])
    interpretation = json.loads(content)
except Exception as e:
    print(f'Interpreter failed ({e}), using defaults', file=sys.stderr)
    interpretation = {'original_request': request, 'skip_steps': [], 'step_params': {}, 'user_context': request}

# Save interpretation
json.dump(interpretation, open('$INTERP_DIR/interpretation.json', 'w'), ensure_ascii=False, indent=2)

# Resolve pipeline
from lib.workers.interpreter import resolve_pipeline
resolved = resolve_pipeline(pipeline, config, interpretation)
json.dump(resolved, open('$INTERP_DIR/pipeline.resolved.json', 'w'), ensure_ascii=False, indent=2)

print(f'Interpreted: skip={interpretation.get(\"skip_steps\", [])}, params={list(interpretation.get(\"step_params\", {}).keys())}')
print(f'Resolved pipeline: {len(resolved[\"steps\"])} steps')
"

  # Stage 2: Run the resolved pipeline
  RESOLVED="$INTERP_DIR/pipeline.resolved.json"
  if [ -f "$RESOLVED" ]; then
    python3 -m lib.runner --pipeline "$RESOLVED" --run-id "$RUN_ID" --data-dir "$DATA_DIR" $EXTRA_ARGS
  else
    echo "Pipeline resolution failed, running original"
    python3 -m lib.runner --pipeline "$PIPELINE" --run-id "$RUN_ID" --data-dir "$DATA_DIR" $EXTRA_ARGS
  fi
else
  # Static pipeline (no config) — run directly
  python3 -m lib.runner --pipeline "$PIPELINE" --run-id "$RUN_ID" --data-dir "$DATA_DIR" $DRY_RUN $EXTRA_ARGS
fi

# Show result
echo ""
echo "Output: workspace/outputs/runs/$RUN_ID/"
[ -f "workspace/outputs/runs/$RUN_ID/report/report.html" ] && echo "Report: workspace/outputs/runs/$RUN_ID/report/report.html"
[ -f "workspace/outputs/runs/$RUN_ID/report/report.pdf" ] && echo "PDF:    workspace/outputs/runs/$RUN_ID/report/report.pdf"

#!/usr/bin/env python3
"""Pipeline runner — single entry point.

Usage:
    python run.py                                    # run with defaults
    python run.py "análise focada em renda fixa"     # run with user request
    python run.py --data path/to/file.xlsx           # run with input file
    python run.py --resume <run-id>                  # resume a paused run
    python run.py --last                             # re-run with last config
    python run.py --dry-run "my request"             # preview without executing
"""
import argparse
import json
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PIPELINE_DEFAULT = "pipelines/v1.json"
DATA_DIR_DEFAULT = "data"


def parse_args():
    parser = argparse.ArgumentParser(description="Pipeline runner — single entry point")
    parser.add_argument("request", nargs="?", default="", help="User request text")
    parser.add_argument("--data", default=DATA_DIR_DEFAULT, help="Data directory or input file")
    parser.add_argument("--pipeline", default=PIPELINE_DEFAULT, help="Pipeline JSON path")
    parser.add_argument("--run-id", default=None, help="Custom run ID")
    parser.add_argument("--resume", default=None, metavar="RUN_ID", help="Resume a paused run")
    parser.add_argument("--last", action="store_true", help="Re-run with last config")
    parser.add_argument("--dry-run", action="store_true", help="Preview without executing")
    parser.add_argument("--no-ui", action="store_true", help="Run without UI")
    return parser.parse_args()


def get_last_run_id():
    index_path = ROOT / "workspace" / "outputs" / "runs" / "index.jsonl"
    if not index_path.exists():
        return None
    lines = index_path.read_text().strip().splitlines()
    if not lines:
        return None
    try:
        return json.loads(lines[-1])["run_id"]
    except (json.JSONDecodeError, KeyError):
        return None


def save_user_request(data_dir: Path, request: str):
    data_dir.mkdir(parents=True, exist_ok=True)
    req_file = data_dir / "user_request.json"
    json.dump(
        {"user_request": request, "timestamp": datetime.now().isoformat()},
        req_file.open("w"),
        ensure_ascii=False,
        indent=2,
    )
    print(f"Request: {request}")


def handle_file_input(data_arg: str) -> Path:
    """If --data points to a file, copy it into data/ and return the data dir."""
    p = Path(data_arg)
    if p.is_file():
        data_dir = ROOT / "data"
        data_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, data_dir / p.name)
        print("Input file copied to data/")
        return data_dir
    return Path(data_arg)


def run_interpreter(pipeline_path: str, config_path: str, data_dir: Path, run_id: str):
    """Run the interpreter LLM to resolve a dynamic pipeline."""
    interp_dir = ROOT / "workspace" / "outputs" / "runs" / run_id
    interp_dir.mkdir(parents=True, exist_ok=True)

    sys.path.insert(0, str(ROOT))
    from lib.executors import get_executor
    from lib.workers.interpreter import resolve_pipeline

    # Load inputs
    request = ""
    req_file = data_dir / "user_request.json"
    if req_file.exists():
        try:
            request = json.loads(req_file.read_text()).get("user_request", "")
        except Exception:
            pass

    config = json.loads(Path(config_path).read_text())
    pipeline = json.loads(Path(pipeline_path).read_text())

    # Build prompt for interpreter
    step_descriptions = [
        f'- {s["id"]}: {s.get("type", "normal")}, executor={s.get("executor", "inherited")}'
        for s in pipeline["steps"]
    ]

    prompt = (
        f"User request: {request}\n\n"
        f"Pipeline config:\n{json.dumps(config, indent=2, ensure_ascii=False)}\n\n"
        f"Available steps:\n" + "\n".join(step_descriptions) + "\n\n"
        f"Based on the user request and config, produce the interpretation JSON."
    )

    contract = (
        "You are a pipeline interpreter. Read the user request and pipeline config, then decide:\n"
        "1. skip_steps: step IDs to deactivate (only if explicitly conditional in config)\n"
        "2. step_params: parameters to inject into specific steps\n"
        "3. user_context: 1-3 sentence summary of user intent for LLM steps\n"
        "Respond in valid JSON only."
    )

    try:
        executor = get_executor("azure_openai")
        interp_model = config.get("interpreter_model", "gpt-4.1-mini")
        result = executor.run(prompt=prompt, system_prompt=contract, model=interp_model)
        content = result.content.strip()
        if content.startswith("```"):
            lines = content.splitlines()
            content = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
        interpretation = json.loads(content)
    except Exception as e:
        print(f"Interpreter failed ({e}), using defaults", file=sys.stderr)
        interpretation = {
            "original_request": request,
            "skip_steps": [],
            "step_params": {},
            "user_context": request,
        }

    # Save interpretation
    json.dump(
        interpretation,
        (interp_dir / "interpretation.json").open("w"),
        ensure_ascii=False,
        indent=2,
    )

    # Resolve pipeline
    resolved = resolve_pipeline(pipeline, config, interpretation)
    resolved_path = interp_dir / "pipeline.resolved.json"
    json.dump(resolved, resolved_path.open("w"), ensure_ascii=False, indent=2)

    print(f'Interpreted: skip={interpretation.get("skip_steps", [])}, params={list(interpretation.get("step_params", {}).keys())}')
    print(f"Resolved pipeline: {len(resolved['steps'])} steps")

    return str(resolved_path) if resolved_path.exists() else None


def run_pipeline(pipeline: str, run_id: str, data_dir: str, extra_args: list[str]):
    cmd = [
        sys.executable, "-m", "lib.runner",
        "--pipeline", pipeline,
        "--run-id", run_id,
        "--data-dir", str(data_dir),
        *extra_args,
    ]
    result = subprocess.run(cmd, cwd=str(ROOT))
    return result.returncode


def main():
    args = parse_args()

    pipeline = args.pipeline
    config_path = pipeline.replace(".json", ".config.json")
    run_id = args.run_id or datetime.now().strftime("%Y%m%d-%H%M%S")
    data_dir = handle_file_input(args.data)

    extra_args = []
    if args.dry_run:
        extra_args.append("--dry-run")
    if args.no_ui:
        extra_args.append("--no-ui")

    # Handle --last
    if args.last:
        last_id = get_last_run_id()
        if not last_id:
            print("No previous runs found")
            sys.exit(1)
        run_id = last_id
        args.resume = last_id

    # Handle resume
    if args.resume:
        print(f"Resuming run: {args.resume}")
        cmd = [
            sys.executable, "-m", "lib.runner",
            "--pipeline", pipeline,
            "--run-id", args.resume,
            "--resume",
            *extra_args,
        ]
        result = subprocess.run(cmd, cwd=str(ROOT))
        sys.exit(result.returncode)

    # Save user request
    if args.request:
        save_user_request(Path(data_dir), args.request)

    # Dynamic pipeline (config exists) — interpret then run
    if Path(config_path).exists() and not args.dry_run:
        print("Dynamic pipeline detected — running interpreter...")
        resolved_path = run_interpreter(pipeline, config_path, Path(data_dir), run_id)
        if resolved_path:
            rc = run_pipeline(resolved_path, run_id, data_dir, extra_args)
        else:
            print("Pipeline resolution failed, running original")
            rc = run_pipeline(pipeline, run_id, data_dir, extra_args)
    else:
        # Static pipeline or dry-run
        rc = run_pipeline(pipeline, run_id, data_dir, extra_args)

    # Show result
    output_dir = ROOT / "workspace" / "outputs" / "runs" / run_id
    print(f"\nOutput: {output_dir}/")
    report = output_dir / "report" / "report.html"
    if report.exists():
        print(f"Report: {report}")
    pdf = output_dir / "report" / "report.pdf"
    if pdf.exists():
        print(f"PDF:    {pdf}")

    sys.exit(rc)


if __name__ == "__main__":
    main()

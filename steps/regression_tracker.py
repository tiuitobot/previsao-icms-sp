"""Compare current SARIMAX run against previous runs to detect regressions."""
import json
from pathlib import Path


def _load_json(path: Path) -> dict | None:
    """Load JSON file, return None if missing or invalid."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def _find_previous_runs(consumer_root: Path, current_output_dir: Path) -> list[Path]:
    """Find all previous run directories that contain SARIMAX output."""
    runs_dir = consumer_root / "workspace" / "outputs" / "runs"
    if not runs_dir.exists():
        return []

    current_resolved = current_output_dir.resolve()
    previous = []
    for entry in sorted(runs_dir.iterdir()):
        if not entry.is_dir():
            continue
        # Skip symlinks like "latest"
        if entry.is_symlink():
            continue
        # Skip current run
        if entry.resolve() == current_resolved:
            continue
        sarimax_file = entry / "run_sarimax_models.json"
        if sarimax_file.exists():
            previous.append(sarimax_file)

    return previous


def _pct_change(current: float, previous: float) -> float:
    """Percentage change from previous to current. Returns 0 if previous is 0."""
    if previous == 0:
        return 0.0
    return ((current - previous) / abs(previous)) * 100


def _compare_runs(current: dict, previous: dict, prev_run_id: str) -> dict:
    """Compare two SARIMAX outputs and flag regressions."""
    flags = []
    details = {}

    # 1. Compare AIC values per model (flag if changed by >5%)
    cur_diag = current.get("diagnostics", {})
    prev_diag = previous.get("diagnostics", {})
    aic_changes = {}
    for model_name in set(list(cur_diag.keys()) + list(prev_diag.keys())):
        cur_aic = cur_diag.get(model_name, {}).get("aic")
        prev_aic = prev_diag.get(model_name, {}).get("aic")
        if cur_aic is not None and prev_aic is not None:
            pct = _pct_change(cur_aic, prev_aic)
            aic_changes[model_name] = {
                "current": cur_aic,
                "previous": prev_aic,
                "pct_change": round(pct, 2),
            }
            if abs(pct) > 5:
                flags.append(f"AIC changed by {pct:+.1f}% for {model_name}")
        elif cur_aic is None and prev_aic is not None:
            aic_changes[model_name] = {"current": None, "previous": prev_aic, "pct_change": None}
            flags.append(f"{model_name} failed in current run but succeeded previously")
        elif cur_aic is not None and prev_aic is None:
            aic_changes[model_name] = {"current": cur_aic, "previous": None, "pct_change": None}
    details["aic_changes"] = aic_changes

    # 2. Compare annual forecast totals (flag if changed by >10%)
    cur_totals = current.get("annual_totals", {})
    prev_totals = previous.get("annual_totals", {})
    forecast_changes = {}
    for source_name in set(list(cur_totals.keys()) + list(prev_totals.keys())):
        cur_years = cur_totals.get(source_name, {})
        prev_years = prev_totals.get(source_name, {})
        for year in set(list(cur_years.keys()) + list(prev_years.keys())):
            cur_val = cur_years.get(year)
            prev_val = prev_years.get(year)
            if not isinstance(cur_val, (int, float)) or not isinstance(prev_val, (int, float)):
                continue
            if cur_val is not None and prev_val is not None:
                pct = _pct_change(cur_val, prev_val)
                key = f"{source_name}_{year}"
                forecast_changes[key] = {
                    "current": cur_val,
                    "previous": prev_val,
                    "pct_change": round(pct, 2),
                }
                if abs(pct) > 10:
                    flags.append(
                        f"Annual total for {source_name} ({year}) changed by {pct:+.1f}%"
                    )
    details["forecast_changes"] = forecast_changes

    # 3. Compare best model (flag if different)
    cur_best = current.get("best_model")
    prev_best = previous.get("best_model")
    details["best_model"] = {"current": cur_best, "previous": prev_best}
    if cur_best != prev_best:
        flags.append(f"Best model changed: {prev_best} -> {cur_best}")

    # 4. Compare number of models fitted (flag if fewer)
    cur_n = current.get("n_models_fitted", 0)
    prev_n = previous.get("n_models_fitted", 0)
    details["n_models_fitted"] = {"current": cur_n, "previous": prev_n}
    if cur_n < prev_n:
        flags.append(f"Fewer models fitted: {prev_n} -> {cur_n}")

    return {
        "compared_to_run": prev_run_id,
        "flags": flags,
        "regression_detected": len(flags) > 0,
        "details": details,
    }


def main(*, output_dir: str = "", **kwargs) -> dict:
    """Compare current SARIMAX output against previous runs."""
    od = Path(output_dir)

    # Load current run's SARIMAX output
    current_file = od / "run_sarimax_models.json"
    current = _load_json(current_file)
    if current is None:
        return {
            "status": "error",
            "verdict": "missing_input",
            "message": f"run_sarimax_models.json not found in {od}",
            "comparisons": [],
        }

    # Find consumer root by walking up from output_dir
    # output_dir is typically <consumer_root>/workspace/outputs/runs/<run_id>
    consumer_root = od
    for _ in range(5):
        if (consumer_root / "workspace").exists():
            break
        consumer_root = consumer_root.parent
    else:
        # Fallback: try 4 levels up from output_dir (standard layout)
        consumer_root = od.parent.parent.parent.parent

    previous_files = _find_previous_runs(consumer_root, od)

    if not previous_files:
        return {
            "status": "ok",
            "verdict": "first_run",
            "comparisons": [],
        }

    # Compare against each previous run (most recent last)
    comparisons = []
    for prev_file in previous_files:
        prev_data = _load_json(prev_file)
        if prev_data is None:
            continue
        prev_run_id = prev_file.parent.name
        comparison = _compare_runs(current, prev_data, prev_run_id)
        comparisons.append(comparison)

    # Overall verdict based on most recent previous run
    latest_comparison = comparisons[-1] if comparisons else None
    if latest_comparison and latest_comparison["regression_detected"]:
        verdict = "regression"
    else:
        verdict = "stable"

    result = {
        "status": "ok",
        "verdict": verdict,
        "n_previous_runs": len(comparisons),
        "comparisons": comparisons,
    }

    # Write output
    out_file = od / "regression_tracker.json"
    out_file.write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    return result

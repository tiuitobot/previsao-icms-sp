"""Cross-validate Python SARIMAX results against R original."""
import json
import shutil
import subprocess
from pathlib import Path


def _load(od: Path, name: str) -> dict:
    f = od / f"{name}.json"
    return json.loads(f.read_text()) if f.exists() else {}


def _find_project_root(output_dir: Path) -> Path:
    """Walk up from output_dir to find the project root (has pipelines/ dir)."""
    candidate = output_dir.resolve()
    for _ in range(10):
        if (candidate / "pipelines").is_dir():
            return candidate
        candidate = candidate.parent
    # Fallback: assume CWD is project root
    return Path.cwd()


def main(*, output_dir: str = "", rmd_path: str = "", **kwargs) -> dict:
    """Run R cross-validation if R is available."""
    od = Path(output_dir)
    project_root = _find_project_root(od)

    # Check if R is available
    if not shutil.which("Rscript"):
        result = {
            "comparison_table": [],
            "discrepancies": [],
            "max_deviation_pct": None,
            "verdict": "skipped",
            "status": "ok",
            "reason": "Rscript not found in PATH"
        }
        out_file = od / "cross_validate_r.json"
        out_file.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        return result

    sarimax = _load(od, "run_sarimax_models")

    # Resolve baseline metrics path relative to project root
    r_metrics_path = project_root / "data" / "r_original" / "metricas_modelos_r.json"

    if not r_metrics_path.exists():
        # Try running extract_metrics.R to generate the baseline
        extract_script = project_root / "data" / "r_original" / "extract_metrics.R"
        if extract_script.exists():
            try:
                r_result = subprocess.run(
                    ["Rscript", str(extract_script)],
                    capture_output=True, text=True, timeout=300,
                    cwd=str(project_root)
                )
                if r_result.returncode != 0:
                    result = {
                        "comparison_table": [],
                        "discrepancies": [f"R extract_metrics.R failed: {r_result.stderr[:500]}"],
                        "max_deviation_pct": None,
                        "verdict": "error",
                        "status": "ok"
                    }
                    out_file = od / "cross_validate_r.json"
                    out_file.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
                    return result
            except (subprocess.TimeoutExpired, FileNotFoundError) as e:
                result = {
                    "comparison_table": [],
                    "discrepancies": [str(e)],
                    "max_deviation_pct": None,
                    "verdict": "error",
                    "status": "ok"
                }
                out_file = od / "cross_validate_r.json"
                out_file.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
                return result
        else:
            result = {
                "comparison_table": [],
                "discrepancies": ["R baseline not found and extract_metrics.R missing"],
                "max_deviation_pct": None,
                "verdict": "error",
                "status": "ok"
            }
            out_file = od / "cross_validate_r.json"
            out_file.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
            return result

    # Compare Python vs R diagnostics
    comparison = []
    discrepancies = []
    max_dev = 0.0

    if r_metrics_path.exists():
        r_metrics = json.loads(r_metrics_path.read_text(encoding="utf-8"))
        py_diagnostics = sarimax.get("diagnostics", {})

        # Metrics to compare: AIC, BIC, log-likelihood
        metrics_to_compare = [
            ("aic", "AIC"),
            ("bic", "BIC"),
            ("loglik", "LogLik"),
        ]

        for model_name in py_diagnostics:
            py = py_diagnostics[model_name]
            r = r_metrics.get(model_name, {})

            for metric_key, metric_label in metrics_to_compare:
                if metric_key in py and metric_key in r:
                    r_val = r[metric_key]
                    py_val = py[metric_key]
                    # Use absolute values for percentage deviation to handle negative metrics
                    if abs(r_val) > 1e-10:
                        dev = abs(py_val - r_val) / abs(r_val) * 100
                    else:
                        dev = abs(py_val - r_val) * 100  # fallback for near-zero
                    max_dev = max(max_dev, dev)
                    entry = {
                        "model": model_name,
                        "metric": metric_label,
                        "python": py_val,
                        "r": r_val,
                        "deviation_pct": round(dev, 2)
                    }
                    comparison.append(entry)
                    if dev > 1.0:
                        discrepancies.append(
                            f"{model_name} {metric_label}: Python={py_val}, R={r_val} ({dev:.1f}% deviation)"
                        )

            # Also compare n_obs if available
            if "n_obs" in py and "n_obs" in r:
                if py["n_obs"] != r["n_obs"]:
                    discrepancies.append(
                        f"{model_name} n_obs: Python={py['n_obs']}, R={r['n_obs']}"
                    )

    # Verdict thresholds:
    # - AIC/BIC will differ between R (lambda=0 adjusts likelihood) and Python (manual log)
    # - <5% is expected, <10% is acceptable, >10% needs investigation
    if not comparison:
        verdict = "no_data"
    elif max_dev < 5.0:
        verdict = "pass"
    elif max_dev < 10.0:
        verdict = "warn"
    else:
        verdict = "fail"

    # Note about expected differences
    notes = []
    if max_dev > 1.0:
        notes.append(
            "R's Arima with lambda=0 applies a Box-Cox log transform and adjusts "
            "the likelihood for the transformation Jacobian. Python's statsmodels "
            "SARIMAX with manual np.log() does not apply this adjustment, so "
            "AIC/BIC values are expected to differ. The key comparison is relative "
            "model ranking (which model is best) rather than absolute values."
        )

    result = {
        "comparison_table": comparison,
        "discrepancies": discrepancies,
        "max_deviation_pct": round(max_dev, 2) if comparison else None,
        "verdict": verdict,
        "notes": notes,
        "r_baseline_path": str(r_metrics_path),
        "status": "ok"
    }

    out_file = od / "cross_validate_r.json"
    out_file.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    return result

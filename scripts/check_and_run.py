#!/usr/bin/env python3
"""Check if web data sources have updates and run the pipeline if so.

Designed for Windows Task Scheduler (daily cron).
Checks BCB IBC-BR, IPEA IGP-DI, and Focus survey dates against
the last successful run. If any source has new data, runs the pipeline.

Usage:
    python scripts/check_and_run.py           # check and run if updated
    python scripts/check_and_run.py --force    # run regardless of updates
    python scripts/check_and_run.py --check    # only check, don't run
"""
import argparse
import json
import logging
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
STATE_FILE = ROOT / "workspace" / "last_data_state.json"
LOG_FILE = ROOT / "workspace" / "cron.log"


def setup_logging():
    ROOT.joinpath("workspace").mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(message)s",
        datefmt="%Y-%m-%d %H:%M",
        handlers=[
            logging.FileHandler(LOG_FILE, encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )


def fetch_latest_dates() -> dict:
    """Fetch the most recent data point date from each source."""
    dates = {}

    # IBC-BR: last available data point
    try:
        resp = requests.get(
            "https://api.bcb.gov.br/dados/serie/bcdata.sgs.24363/dados/ultimos/1?formato=json",
            timeout=15,
        )
        resp.raise_for_status()
        raw = resp.json()
        if raw:
            dates["ibc_br"] = raw[-1]["data"]  # dd/mm/yyyy
    except Exception as e:
        logging.warning(f"IBC-BR check failed: {e}")

    # IGP-DI: last available data point
    try:
        resp = requests.get(
            "http://www.ipeadata.gov.br/api/odata4/ValoresSerie(SERCODIGO='IGP12_IGPDI12')"
            "?$orderby=VALDATA%20desc&$top=1",
            timeout=15,
        )
        resp.raise_for_status()
        values = resp.json().get("value", [])
        if values:
            dates["igp_di"] = values[0]["VALDATA"][:10]
    except Exception as e:
        logging.warning(f"IGP-DI check failed: {e}")

    # Focus: latest survey date
    try:
        year = datetime.now().year
        resp = requests.get(
            f"https://olinda.bcb.gov.br/olinda/servico/Expectativas/versao/v1/odata/"
            f"ExpectativasMercadoAnuais?$filter=DataReferencia%20eq%20'{year}'"
            f"&$orderby=Data%20desc&$top=1&$format=json",
            timeout=15,
        )
        resp.raise_for_status()
        values = resp.json().get("value", [])
        if values:
            dates["focus"] = str(values[0]["Data"])[:10]
    except Exception as e:
        logging.warning(f"Focus check failed: {e}")

    return dates


def load_previous_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return {}


def save_state(dates: dict):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    state = {
        "last_check": datetime.now().isoformat(),
        "dates": dates,
    }
    STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def run_pipeline():
    logging.info("Running pipeline...")
    result = subprocess.run(
        [sys.executable, "run.py"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        logging.info("Pipeline completed successfully")
        # Log output path
        for line in result.stdout.splitlines():
            if "Output:" in line or "Report:" in line:
                logging.info(line.strip())
    else:
        logging.error(f"Pipeline failed (exit {result.returncode})")
        if result.stderr:
            logging.error(result.stderr[-500:])
    return result.returncode


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="Run regardless of updates")
    parser.add_argument("--check", action="store_true", help="Only check, don't run")
    args = parser.parse_args()

    setup_logging()
    logging.info("=" * 40)
    logging.info("Checking for data updates...")

    current = fetch_latest_dates()
    previous = load_previous_state().get("dates", {})

    if not current:
        logging.warning("Could not fetch any data source. Skipping.")
        return

    # Compare
    changes = []
    for source, date in current.items():
        prev = previous.get(source)
        if prev != date:
            changes.append(f"{source}: {prev} -> {date}")

    if changes:
        for c in changes:
            logging.info(f"  UPDATE: {c}")
    else:
        logging.info("No updates found.")

    if args.check:
        save_state(current)
        return

    if changes or args.force:
        if args.force and not changes:
            logging.info("Force run requested.")
        rc = run_pipeline()
        if rc == 0:
            save_state(current)
    else:
        logging.info("Skipping pipeline run.")
        save_state(current)


if __name__ == "__main__":
    main()

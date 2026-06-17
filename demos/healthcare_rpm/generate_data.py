"""
Generate 100% synthetic remote-patient-monitoring (RPM) data and load it
into ClickHouse. No real patients, no PHI.

Defaults to ~10M vitals rows (10,000 patients x 5 metrics x 200 readings).
A small cohort is made to "deteriorate" over the last few days so the agent
has a real, hidden risk pattern to discover.

Usage:
    python demos/healthcare_rpm/generate_data.py            # ~10M rows
    python demos/healthcare_rpm/generate_data.py --quick    # ~2M rows (fast)
    python demos/healthcare_rpm/generate_data.py --patients 20000 --timepoints 300
"""
import argparse
import pathlib
import sys
from datetime import datetime, timedelta

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src.core.db import exec_script, get_client  # noqa: E402

CONDITIONS = ["Healthy", "Hypertension", "Diabetes", "COPD", "CHF"]
CONDITION_P = [0.40, 0.20, 0.18, 0.12, 0.10]
REGIONS = ["Dublin", "London", "Berlin", "Madrid", "Toronto", "New York"]
METRICS = ["heart_rate", "spo2", "systolic_bp", "glucose", "steps"]

# base mean/std per metric, plus per-condition offsets to make cohorts realistic
BASE = {
    "heart_rate":  {"mean": 72,  "std": 7,   "offset": {"COPD": 6,  "CHF": 11}},
    "spo2":        {"mean": 97,  "std": 1.1, "offset": {"COPD": -3, "CHF": -2}},
    "systolic_bp": {"mean": 120, "std": 9,   "offset": {"Hypertension": 22, "CHF": 9}},
    "glucose":     {"mean": 95,  "std": 11,  "offset": {"Diabetes": 48}},
    "steps":       {"mean": 240, "std": 110, "offset": {"CHF": -120, "COPD": -85}},
}
# direction of "getting worse" for the deteriorating cohort
DETERIORATION = {"heart_rate": +1, "spo2": -1, "systolic_bp": +1, "glucose": +1, "steps": -1}
DETERIORATION_MAG = {"heart_rate": 28, "spo2": 7, "systolic_bp": 35, "glucose": 90, "steps": 160}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--patients", type=int, default=10_000)
    ap.add_argument("--timepoints", type=int, default=200)
    ap.add_argument("--quick", action="store_true", help="shortcut for a ~2M-row dataset")
    ap.add_argument("--deteriorating-pct", type=float, default=0.03)
    args = ap.parse_args()
    if args.quick:
        args.timepoints = 40

    n_p, n_t = args.patients, args.timepoints
    rng = np.random.default_rng(42)
    client = get_client()

    print(f"Creating schema in ClickHouse...")
    exec_script(client, (pathlib.Path(__file__).parent / "schema.sql").read_text())
    client.command("TRUNCATE TABLE IF EXISTS patients")
    client.command("TRUNCATE TABLE IF EXISTS vitals")

    # ---- patients dimension ----
    print(f"Generating {n_p:,} patients...")
    conditions = rng.choice(CONDITIONS, size=n_p, p=CONDITION_P)
    ages = rng.integers(28, 90, size=n_p, dtype=np.uint8)
    sexes = rng.choice([1, 2], size=n_p).astype("int8")
    regions = rng.choice(REGIONS, size=n_p)
    enrolled = [datetime(2026, 1, 1).date() + timedelta(days=int(d))
                for d in rng.integers(0, 120, size=n_p)]
    client.insert(
        "patients",
        [np.arange(n_p, dtype=np.uint32), ages, sexes, conditions, regions, enrolled],
        column_names=["patient_id", "age", "sex", "condition", "region", "enrolled_at"],
        column_oriented=True,
    )

    # who deteriorates, and over how many of the most-recent readings
    det_mask = np.zeros(n_p, dtype=bool)
    det_ids = rng.choice(n_p, size=int(n_p * args.deteriorating_pct), replace=False)
    det_mask[det_ids] = True
    recent_window = max(8, n_t // 12)
    print(f"  ({det_mask.sum():,} patients will deteriorate over their last {recent_window} readings)")

    # time axis: last 30 days, evenly spaced
    end = datetime.now().replace(microsecond=0)
    interval = timedelta(days=30) / n_t
    time_offsets = np.array([np.datetime64(end - interval * (n_t - 1 - t)) for t in range(n_t)],
                            dtype="datetime64[s]")

    patient_index = np.repeat(np.arange(n_p), n_t)           # row -> patient
    timepoint_index = np.tile(np.arange(n_t), n_p)           # row -> reading #
    event_time = np.tile(time_offsets, n_p)
    severity = np.clip((timepoint_index - (n_t - recent_window)) / recent_window, 0, 1)

    total_rows = n_p * n_t * len(METRICS)
    print(f"Generating + loading {total_rows:,} vitals rows ({len(METRICS)} metrics)...")

    for metric in METRICS:
        spec = BASE[metric]
        per_patient_offset = np.zeros(n_p, dtype=np.float32)
        for cond, off in spec["offset"].items():
            per_patient_offset[conditions == cond] = off
        row_mean = spec["mean"] + per_patient_offset[patient_index]
        values = rng.normal(row_mean, spec["std"]).astype(np.float32)

        # apply deterioration to the recent window of the at-risk cohort
        det_rows = det_mask[patient_index]
        bump = DETERIORATION[metric] * DETERIORATION_MAG[metric] * severity
        values = values + (det_rows * bump).astype(np.float32)

        if metric == "spo2":
            values = np.clip(values, 70, 100)
        elif metric == "steps":
            values = np.clip(values, 0, None)

        device_id = (patient_index + 100000).astype(np.uint32)
        metric_col = np.full(len(values), metric)

        # insert in chunks to keep memory flat
        chunk = 500_000
        for i in range(0, len(values), chunk):
            sl = slice(i, i + chunk)
            client.insert(
                "vitals",
                [event_time[sl].tolist(), patient_index[sl].astype(np.uint32),
                 metric_col[sl], values[sl], device_id[sl]],
                column_names=["event_time", "patient_id", "metric", "value", "device_id"],
                column_oriented=True,
            )
        print(f"  loaded {metric}")

    n = client.query("SELECT count() FROM vitals").result_rows[0][0]
    print(f"\nDone. vitals row count = {n:,}")


if __name__ == "__main__":
    main()

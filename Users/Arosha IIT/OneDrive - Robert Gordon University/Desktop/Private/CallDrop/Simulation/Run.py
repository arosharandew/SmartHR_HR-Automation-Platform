#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Master script to run the full call drop prediction pipeline:
1. Simulation (add one new call)
2. Feature engineering (aggregate features)
3. Prediction (classify the latest call and update raw CSV)
"""

import subprocess
import sys
import os
import pandas as pd   # <-- added for post-processing

# Configuration: script names (adjust if needed)
SIMULATION_SCRIPT = "Simulation.py"
FEATURE_SCRIPT = "Feature_Engineering.py"
PREDICTION_SCRIPT = "Prediction.py"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def run_script(script_name):
    """Run a Python script and wait for it to finish, handling encoding errors."""
    script_path = os.path.join(BASE_DIR, script_name)
    if not os.path.exists(script_path):
        print(f"❌ Error: {script_path} not found.")
        return False
    print(f"\n🚀 Running {script_name} ...")

    try:
        result = subprocess.run(
            [sys.executable, script_path],
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace'
        )
    except UnicodeDecodeError:
        result = subprocess.run(
            [sys.executable, script_path],
            capture_output=True,
            text=False
        )
        stdout = result.stdout.decode('utf-8', errors='replace')
        stderr = result.stderr.decode('utf-8', errors='replace')
        print(stdout)
        if stderr:
            print("Errors/Warnings:\n", stderr)
        return result.returncode == 0

    print(result.stdout)
    if result.stderr:
        print("Errors/Warnings:\n", result.stderr)
    if result.returncode != 0:
        print(f"❌ {script_name} failed with exit code {result.returncode}")
        return False
    print(f"✅ {script_name} completed successfully.")
    return True


def ensure_int_column(csv_path, col_name='is_drop'):
    """Convert specified column to integer (0/1) in a CSV file."""
    if not os.path.exists(csv_path):
        print(f"⚠️ {csv_path} not found, skipping integer conversion.")
        return
    df = pd.read_csv(csv_path)
    if col_name in df.columns:
        df[col_name] = df[col_name].fillna(0).astype(int)
        df.to_csv(csv_path, index=False)
        print(f"✅ Converted '{col_name}' to integer in {csv_path}")
    else:
        print(f"ℹ️ Column '{col_name}' not found in {csv_path}, nothing to convert.")


if __name__ == "__main__":
    print("=" * 60)
    print("CALL DROP PREDICTION PIPELINE")
    print("=" * 60)

    if not run_script(SIMULATION_SCRIPT):
        sys.exit(1)
    if not run_script(FEATURE_SCRIPT):
        sys.exit(1)
    if not run_script(PREDICTION_SCRIPT):
        sys.exit(1)

    # ------------------------------------------------------------------
    # Post-processing: ensure 'is_drop' is integer in both CSVs
    # ------------------------------------------------------------------
    # Try to locate the CSV files (first in Simulation/Data/, then fallback to Data/)
    data_dir = os.path.join(BASE_DIR, "Simulation", "Data")
    eng_csv = os.path.join(data_dir, "Engineered.csv")
    raw_csv = os.path.join(data_dir, "telecom_call_drop.csv")

    if not os.path.exists(eng_csv):
        fallback_dir = os.path.join(BASE_DIR, "Data")
        eng_csv = os.path.join(fallback_dir, "Engineered.csv")
        raw_csv = os.path.join(fallback_dir, "telecom_call_drop.csv")

    ensure_int_column(eng_csv)
    ensure_int_column(raw_csv)

    print("\n🎉 Full pipeline executed successfully.")
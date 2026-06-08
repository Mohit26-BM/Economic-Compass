"""
Pre-compute Prophet calibration results for all series.
Retrains Prophet with a 2023-01-01 cutoff and measures forecast accuracy
against actual data from 2023 onward.

Takes ~3-5 minutes to run.
"""
from dotenv import load_dotenv

load_dotenv()

from ml.calibration.backtester import calibrate_series

SERIES = ["GDP", "CPIAUCSL", "UNRATE", "FEDFUNDS", "HOUST", "RSXFS", "T10Y2Y"]

print("Running calibration backtests (cutoff: 2023-01-01) ...\n")
for series_id in SERIES:
    try:
        r = calibrate_series(series_id)
        coverage_flag = "OK " if r["actual_coverage"] >= 0.80 else "LOW"
        print(
            f"[{coverage_flag}] {series_id:8s} "
            f"coverage={r['actual_coverage']:.0%} (expected 95%)  "
            f"MAE={r['mae']:.2f}  MAPE={r['mape']:.2f}%  "
            f"n={r['n_test']}"
        )
    except Exception as e:
        print(f"[FAIL] {series_id:8s} {e}")

print("\nArtifacts saved to ml/artifacts/calibration_*.json")
print("Serve via GET /analysis/calibration/{series_id}")

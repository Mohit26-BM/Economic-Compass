"""
Pre-compute the forecast backtests for every forecast series (rolling origin, 12-month horizon).

Measures the Holt-Winters forecasts the API actually serves: how often the 95% interval contains
the real value, and whether the forecast beats "nothing changes". Takes about a minute.
"""
from dotenv import load_dotenv

load_dotenv()

from ml.calibration.backtester import calibrate_series

SERIES = ["GDP", "CPIAUCSL", "UNRATE", "FEDFUNDS", "HOUST", "RSXFS", "T10Y2Y"]

print("Running rolling-origin backtests ...\n")
for series_id in SERIES:
    try:
        r = calibrate_series(series_id)
        verdict = "beats" if r["mae_vs_naive"] is not None and r["mae_vs_naive"] < 1 else "does NOT beat"
        print(
            f"{series_id:8s} coverage={r['actual_coverage']:.0%} (expected 95%)  "
            f"MAE={r['mae']:.2f} vs naive {r['naive_mae']:.2f}  {verdict} 'no change'  "
            f"origins={r['n_origins']} n={r['n_test']}"
        )
    except Exception as e:
        print(f"[FAIL] {series_id:8s} {e}")

print("\nArtifacts saved to ml/artifacts/calibration_*.json")
print("Served via GET /analysis/calibration/{series_id}")

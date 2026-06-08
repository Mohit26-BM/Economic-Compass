import numpy as np
import pandas as pd
from loguru import logger


def population_stability_index(
    expected: pd.Series,
    actual: pd.Series,
    bins: int = 10,
) -> float:
    """
    Normalized PSI.

    Both windows are z-scored using the REFERENCE mean and std before binning,
    then fixed equal-width bins are placed from -4 to +4 (standard deviations).

    Why this matters for macro monthly data
    ----------------------------------------
    Percentile-bin PSI requires large samples (100+ per window).  With 6-12
    monthly observations in the current window, most bins end up empty and the
    1e-4 epsilon substitution produces PSI ≈ 6-9 even for nearly identical
    distributions.  Normalizing first puts both windows on the same scale,
    bounds outliers, and ensures the bin grid is always fully covered by the
    reference distribution.

    A score of 0 means no distributional shift from the reference.
    Standard thresholds still apply on the normalized scale:
        < 0.10  — no meaningful drift
        0.10–0.25 — moderate, worth monitoring
        > 0.25  — significant
        > 1.0   — near-complete distribution shift
    """
    exp_clean = expected.dropna()
    act_clean = actual.dropna()

    if len(exp_clean) < bins or len(act_clean) < 2:
        return float("nan")  # insufficient data — don't fabricate a number

    ref_mean = float(exp_clean.mean())
    ref_std  = float(exp_clean.std())

    if ref_std < 1e-10:
        # Constant reference distribution.
        # Any shift in current mean = definite drift; otherwise stable.
        return 0.0 if abs(float(act_clean.mean()) - ref_mean) < 1e-10 else 1.0

    # Standardize both windows with REFERENCE statistics
    z_ref = ((exp_clean - ref_mean) / ref_std).clip(-4.0, 4.0)
    z_cur = ((act_clean - ref_mean) / ref_std).clip(-4.0, 4.0)

    # Fixed grid on the standardized scale — always fully covered by reference
    edges = np.linspace(-4.0, 4.0, bins + 1)

    def bucket(z: pd.Series) -> np.ndarray:
        counts, _ = np.histogram(z, bins=edges)
        # Laplace smoothing: add 0.5 pseudo-count to every bin.
        # With 12 current observations and 10 bins the old 1e-4 epsilon
        # produced log(ref_pct / 1e-4) ≈ 9 per empty bin × 8 empty bins = ~72
        # of artificial PSI before any real signal was counted.
        # 0.5 / (n + K/2) ≈ 0.029 for n=12, K=10, which is proportionate.
        smoothed = counts + 0.5
        return smoothed / smoothed.sum()

    e_pct = bucket(z_ref)
    a_pct = bucket(z_cur)
    psi = float(np.sum((e_pct - a_pct) * np.log(e_pct / a_pct)))
    return round(max(psi, 0.0), 6)


def _severity(psi) -> str:
    if psi != psi:  # NaN
        return "insufficient_data"
    if psi < 0.10:
        return "stable"
    if psi < 0.25:
        return "minor"
    if psi < 1.0:
        return "moderate"
    return "high"


def detect_drift(
    reference: pd.DataFrame,
    current: pd.DataFrame,
    feature_col: str = "value",
    threshold: float = 0.25,
    series_id: str = "",
) -> dict:
    psi = population_stability_index(reference[feature_col], current[feature_col])
    sev = _severity(psi)
    drifted = bool(psi > threshold) if psi == psi else False  # NaN → not flagged

    if drifted:
        logger.warning(f"Drift on '{series_id or feature_col}': PSI={psi:.4f}")

    ref_vals = reference[feature_col].dropna()
    cur_vals = current[feature_col].dropna()

    return {
        "feature":   feature_col,
        "series_id": series_id,
        "psi":       psi if psi == psi else None,
        "threshold": threshold,
        "drifted":   drifted,
        "severity":  sev,
        "reference": {
            "n":     int(len(ref_vals)),
            "mean":  round(float(ref_vals.mean()), 4) if len(ref_vals) else None,
            "std":   round(float(ref_vals.std()), 4)  if len(ref_vals) else None,
            "start": str(reference["observation_date"].min().date()) if "observation_date" in reference.columns else None,
            "end":   str(reference["observation_date"].max().date()) if "observation_date" in reference.columns else None,
        },
        "current": {
            "n":     int(len(cur_vals)),
            "mean":  round(float(cur_vals.mean()), 4) if len(cur_vals) else None,
            "std":   round(float(cur_vals.std()), 4)  if len(cur_vals) else None,
            "start": str(current["observation_date"].min().date()) if "observation_date" in current.columns else None,
            "end":   str(current["observation_date"].max().date()) if "observation_date" in current.columns else None,
        },
    }

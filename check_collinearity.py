"""
Quick multicollinearity check for the recession model features.
Prints correlation matrix and VIF for all features.
"""
import joblib
import numpy as np
import pandas as pd

try:
    from statsmodels.stats.outliers_influence import variance_inflation_factor
    HAS_STATSMODELS = True
except ImportError:
    HAS_STATSMODELS = False

import duckdb
import os
from dotenv import load_dotenv
load_dotenv()

sys_path_hack = __import__("sys"); sys_path_hack.path.insert(0, ".")
from ml.recession.model import _load_all_series, _to_monthly_panel, _build_features

# ── Load features ────────────────────────────────────────────────────────────
df      = _load_all_series()
monthly = _to_monthly_panel(df)
feats   = _build_features(monthly).dropna()

artifact     = joblib.load("ml/artifacts/recession_model.joblib")
feature_cols = artifact["feature_cols"]
feats        = feats[feature_cols]

print(f"Feature matrix: {feats.shape[0]} rows x {feats.shape[1]} cols\n")

# ── Correlation matrix ───────────────────────────────────────────────────────
corr = feats.corr().round(3)

print("=== Pearson Correlation Matrix ===")
print(corr.to_string())
print()

# Highlight pairs with |r| > 0.5
print("=== High-correlation pairs  (|r| > 0.50) ===")
found = False
cols = corr.columns.tolist()
for i, c1 in enumerate(cols):
    for c2 in cols[i+1:]:
        r = corr.loc[c1, c2]
        if abs(r) > 0.50:
            flag = "**" if abs(r) > 0.80 else "  "
            print(f"  {flag} {c1:25s}  x  {c2:25s}  r = {r:+.3f}")
            found = True
if not found:
    print("  None found.")
print()

# Focus on the two variables in question
print("=== GDP YoY vs CPI YoY ===")
r_gdp_cpi = corr.loc["gdp_yoy", "cpi_yoy"] if "gdp_yoy" in corr.index and "cpi_yoy" in corr.index else None
if r_gdp_cpi is not None:
    print(f"  r = {r_gdp_cpi:+.3f}")
    if abs(r_gdp_cpi) < 0.30:
        print("  Low correlation — both features are carrying independent signal.")
    elif abs(r_gdp_cpi) < 0.60:
        print("  Moderate correlation — some overlap but both features add value.")
    else:
        print("  High correlation — multicollinearity risk; large coefficients may be unstable.")
print()

# ── VIF ──────────────────────────────────────────────────────────────────────
if HAS_STATSMODELS:
    print("=== Variance Inflation Factor (VIF) ===")
    print("  VIF > 5 = moderate concern   VIF > 10 = high concern")
    X = feats.values.astype(float)
    vifs = []
    for i, col in enumerate(feature_cols):
        try:
            vif = variance_inflation_factor(X, i)
        except Exception:
            vif = float("nan")
        vifs.append((col, round(vif, 2)))
    vifs.sort(key=lambda x: x[1] if not np.isnan(x[1]) else 0, reverse=True)
    for col, vif in vifs:
        flag = "  **" if vif > 10 else ("  * " if vif > 5 else "    ")
        print(f"  {flag} {col:25s}  VIF = {vif:.2f}")
else:
    print("statsmodels not installed — skipping VIF.")
    print("Install with: pip install statsmodels")

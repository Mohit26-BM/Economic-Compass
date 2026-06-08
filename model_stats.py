import joblib

a = joblib.load("ml/artifacts/recession_model.joblib")
oos = a["oos_metrics"]

print("=== OOS Metrics (trained pre-2001, tested 2001-present) ===")
print(f"  AUC       : {oos['auc']}")
print(f"  Brier     : {oos['brier']}")
print(f"  Precision : {oos['precision']}")
print(f"  Recall    : {oos['recall']}")
print(f"  F1        : {oos['f1']}")
print(f"  Test rows : {oos['n_test']}  ({oos['n_recession_months']} recession months)")
print()
print("=== Feature Importances (standardized coefficients) ===")
for f in a["feature_importances"]:
    bar = "+" * int(abs(f["coefficient"]) * 5)
    sign = "+" if f["coefficient"] > 0 else "-"
    print(f"  {f['feature']:25s}  {sign}{abs(f['coefficient']):.4f}  {bar}")

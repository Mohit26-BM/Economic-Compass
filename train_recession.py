from dotenv import load_dotenv

load_dotenv()

from ml.recession.model import train_recession_model

try:
    result = train_recession_model()
    oos = result["oos_metrics"]
    print(f"OK  Recession model trained on {result['training_rows']} rows")
    print(f"    In-sample AUC : {result['in_sample_auc']}")
    print(f"    OOS AUC       : {oos['auc']}  (trained pre-2001, tested {oos['test_period']})")
    print(f"    OOS Brier     : {oos['brier']}")
    print(f"    OOS Precision : {oos['precision']}")
    print(f"    OOS Recall    : {oos['recall']}")
    print(f"    Test recessions covered: 2001, 2008-09, 2020")
    print()
    print("Top features by importance:")
    for f in result["feature_importances"][:5]:
        direction = "+ risk" if f["coefficient"] > 0 else "- risk (inverted)"
        print(f"    {f['feature']:25s} {f['coefficient']:+.4f}  {direction}")
except ValueError as e:
    print(f"FAIL: {e}")
    print()
    print("Make sure USREC is ingested first:")
    print("  python -m pipeline.flows.ingest_flow")

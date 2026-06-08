import duckdb
from dotenv import load_dotenv
from ml.train.trainer import train_prophet

load_dotenv()

con = duckdb.connect("./data/warehouse.duckdb")
df = con.execute("SELECT * FROM raw.economic_indicators WHERE value IS NOT NULL").fetchdf()
con.close()

for series in ["GDP", "CPIAUCSL", "UNRATE", "FEDFUNDS", "HOUST", "RSXFS", "T10Y2Y"]:
    try:
        r = train_prophet(df, series)
        print(f"OK  {series}: {r['training_rows']} rows trained")
    except Exception as e:
        print(f"FAIL {series}: {e}")

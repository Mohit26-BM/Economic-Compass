import duckdb
import pandas as pd

SAHM_THRESHOLD = 0.5  # pp — original Claudia Sahm (2019) threshold


def _load_panel(db_path: str = "./data/warehouse.duckdb") -> pd.DataFrame:
    con = duckdb.connect(db_path, read_only=True)
    df = con.execute("""
        SELECT series_id, observation_date, value
        FROM raw.economic_indicators
        WHERE series_id IN ('UNRATE', 'PAYEMS', 'USREC') AND value IS NOT NULL
        ORDER BY observation_date
    """).fetchdf()
    con.close()

    df["observation_date"] = pd.to_datetime(df["observation_date"])
    pivot = df.pivot_table(
        index="observation_date", columns="series_id", values="value", aggfunc="mean"
    )
    return pivot.resample("MS").mean().ffill(limit=3)


def compute_sahm(db_path: str = "./data/warehouse.duckdb") -> dict:
    monthly = _load_panel(db_path)

    if "UNRATE" not in monthly.columns:
        raise ValueError("UNRATE series required for Sahm Rule")

    unrate = monthly["UNRATE"]

    # Sahm Rule: 3-month avg UNRATE minus 12-month rolling minimum of UNRATE
    # When this crosses +0.5pp, the rule signals a recession has started.
    unrate_3m = unrate.rolling(3, min_periods=3).mean()
    unrate_12m_min = unrate.rolling(12, min_periods=12).min()
    sahm = (unrate_3m - unrate_12m_min).dropna()

    # Payrolls: month-over-month change (thousands of jobs) and 3-month avg
    payems_mom = None
    payems_3m = None
    if "PAYEMS" in monthly.columns:
        payems_mom = monthly["PAYEMS"].diff()        # raw MoM change in thousands
        payems_3m  = payems_mom.rolling(3).mean()   # smoothed 3-month average

    usrec = monthly.get("USREC", pd.Series(dtype=float))

    # Build history — align all series on the Sahm index
    history = []
    for idx in sahm.index:
        row: dict = {
            "date":   idx.strftime("%Y-%m-%d"),
            "sahm":   round(float(sahm[idx]), 4),
            "unrate": round(float(unrate[idx]), 4) if idx in unrate.index and not pd.isna(unrate[idx]) else None,
        }
        if payems_mom is not None and idx in payems_mom.index and not pd.isna(payems_mom[idx]):
            row["payems_mom"] = round(float(payems_mom[idx]), 1)
        if payems_3m is not None and idx in payems_3m.index and not pd.isna(payems_3m[idx]):
            row["payems_3m"] = round(float(payems_3m[idx]), 1)
        if idx in usrec.index and not pd.isna(usrec[idx]):
            row["recession"] = int(usrec[idx])
        else:
            row["recession"] = 0
        history.append(row)

    current = history[-1]
    current_sahm = current["sahm"]

    if current_sahm >= SAHM_THRESHOLD:
        signal = "recession"
        signal_label = f"Sahm indicator at {current_sahm:.2f}pp — above {SAHM_THRESHOLD}pp threshold, rule has fired"
    elif current_sahm >= 0.3:
        signal = "warning"
        signal_label = f"Sahm indicator at {current_sahm:.2f}pp — approaching {SAHM_THRESHOLD}pp threshold, monitor closely"
    else:
        signal = "clear"
        signal_label = f"Sahm indicator at {current_sahm:.2f}pp — well below threshold, labour market not signalling recession"

    # Payrolls YoY (current only — for metrics row)
    payems_yoy = None
    if "PAYEMS" in monthly.columns:
        p = monthly["PAYEMS"]
        yoy = p.pct_change(12, fill_method=None) * 100
        last_yoy = yoy.dropna()
        if len(last_yoy):
            payems_yoy = round(float(last_yoy.iloc[-1]), 2)

    # Add payems_yoy to history rows
    if "PAYEMS" in monthly.columns:
        payems_yoy_series = monthly["PAYEMS"].pct_change(12, fill_method=None) * 100
        for row in history:
            idx = pd.Timestamp(row["date"])
            if idx in payems_yoy_series.index and not pd.isna(payems_yoy_series[idx]):
                row["payems_yoy"] = round(float(payems_yoy_series[idx]), 2)

    # Historical accuracy: each distinct firing episode vs NBER recession windows.
    # A "correct signal" = episode start falls within 3 months before or 6 months
    # after an NBER recession began.  Everything else = false positive.
    since_1970 = sahm[sahm.index >= pd.Timestamp("1970-01-01")]
    usrec_1970 = usrec.reindex(since_1970.index).fillna(0)

    firing_changes = (since_1970 >= SAHM_THRESHOLD).astype(int).diff().fillna(0)
    episode_starts = since_1970.index[firing_changes == 1].tolist()

    n_correct = 0
    n_false_positives = 0
    for start in episode_starts:
        window_s = start - pd.DateOffset(months=3)
        window_e = start + pd.DateOffset(months=9)
        window_usrec = usrec_1970[
            (usrec_1970.index >= window_s) & (usrec_1970.index <= window_e)
        ]
        if not window_usrec.empty and window_usrec.max() >= 1:
            n_correct += 1
        else:
            n_false_positives += 1

    n_recession_episodes_since_1970 = int(
        (usrec_1970.diff().fillna(0) == 1).sum()
    )

    # Update current with payems_yoy
    if payems_yoy is not None:
        current["payems_yoy"] = payems_yoy

    return {
        "history":        history,
        "current":        current,
        "signal":         signal,
        "signal_label":   signal_label,
        "threshold":      SAHM_THRESHOLD,
        "n_threshold_crossings": len(episode_starts),
        "n_correct_signals":     n_correct,
        "n_false_positives":     n_false_positives,
        "n_recession_episodes":  n_recession_episodes_since_1970,
        "has_payems":     "PAYEMS" in monthly.columns,
    }

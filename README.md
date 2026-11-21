# Economic Compass

A data engineering and analysis platform for U.S. macroeconomic data. It pulls nine series from the Federal Reserve (FRED), stores them in an embedded DuckDB warehouse, transforms them with dbt, runs seven analytical models, and serves everything through a read-only FastAPI backend and a React dashboard.

It is built to show how the data and the models behave, and where they stop being reliable. Every model page carries its own caveats, and the [review section](#what-the-review-found-and-fixed) lists what was wrong and what changed.

> **Not financial or economic advice.** The outputs are descriptive and educational. None of them is a forecast you should trade or plan around (see [Limitations](#limitations)).

---

## What it does

- **Ingestion** — pulls nine FRED series (about 20,000 rows, some going back to 1854) with retries; each series is replaced in a single transaction, and an empty answer from FRED never wipes stored history.
- **Transformation** — dbt staging view and a trends table (lags, rolling average, month-on-month and year-on-year change, lagged by date so quarterly and daily series are handled correctly).
- **Seven analyses** — recession risk score, regime detection, Taylor Rule, Sahm Rule, conditions index, cross-series correlation and Granger tests, and a scenario simulator.
- **Trend extrapolation** — a 12-month Holt-Winters projection per series, with a rolling-origin backtest that is compared against "nothing changes".
- **Drift check** — population stability index (PSI) of each series' recent window against the previous five years.
- **Lineage** — a graph of how data moves from FRED to each endpoint.
- **Dashboard** — React pages for each of the above, with sliders and preset scenarios for the simulator.

## Tech stack

| Layer           | Technology                         | Purpose                                         |
| --------------- | ---------------------------------- | ----------------------------------------------- |
| Orchestration   | Prefect (2.19+)                    | Run and retry the ingestion flow                |
| Warehouse       | DuckDB                             | Embedded analytical database, one file          |
| Transformations | dbt + dbt-duckdb                   | Staging and trend models                        |
| Models          | scikit-learn, statsmodels, SciPy   | Logistic regression, K-means, Holt-Winters, Granger |
| API             | FastAPI + Uvicorn                  | Read-only JSON API with generated docs at `/docs` |
| Dashboard       | React 18, Vite, Recharts, React Router 7 | Charts, sliders, lineage graph            |
| Data source     | FRED API (St. Louis Fed)           | Free macroeconomic series                       |

## Series tracked

| Series ID | Name                          | Frequency | Used by                                            |
| --------- | ----------------------------- | --------- | -------------------------------------------------- |
| GDP       | Gross Domestic Product (**nominal**) | Quarterly | Taylor Rule, Conditions, Recession, Simulator |
| CPIAUCSL  | Consumer Price Index          | Monthly   | Taylor Rule, Conditions, Recession, Simulator      |
| UNRATE    | Unemployment Rate             | Monthly   | Sahm Rule, Recession, Conditions, Simulator        |
| FEDFUNDS  | Federal Funds Rate            | Monthly   | Taylor Rule, Recession, Conditions, Simulator      |
| T10Y2Y    | 10-Year minus 2-Year Treasury | Daily     | Recession, Conditions, Simulator                   |
| HOUST     | Housing Starts                | Monthly   | Recession, Conditions, Simulator                   |
| RSXFS     | Advance Retail Sales (ex-food services) | Monthly | Conditions, Simulator                    |
| PAYEMS    | Nonfarm Payrolls              | Monthly   | Sahm chart, Conditions                             |
| USREC     | NBER Recession Indicator      | Monthly   | Ground truth for validation only                   |

Everything is put on a monthly grid first (quarterly GDP is carried forward up to three months, daily values are averaged within the month).

---

## The analyses, and how far to trust each

### 1. Recession risk score

Logistic regression on 14 features (yield curve level, change and months inverted; unemployment level and 3/6-month change; Fed funds level and changes; housing; CPI and GDP growth). The target is whether the NBER indicator is 1 in **any of the next 12 months**.

Validation is honest and the result is modest:

| Out-of-sample test (trained to Dec 1999, tested 2001 onward, 12-month gap) | Result |
| --- | --- |
| AUC (ranking risky months above calm ones) | **0.84** |
| Brier score vs always quoting the training base rate | 0.149 vs 0.148 (skill ≈ 0) |
| 2001 recession | warned 3 months ahead |
| 2008 recession | warned 12 months ahead |
| 2020 recession | **missed** (a pandemic shock; nothing in these series foresaw it) |
| False alarms (signal on, no recession within 12 months) | 3 (2006, 2022, 2024) |

What that means: the model ranks months by risk reasonably well, but its percentages are **not calibrated probabilities** and it was trained on only **three recessions** (1980, 1981–82, 1990; the yield-curve series starts in 1976). Treat the figure as a risk score. The regularisation strength was picked after looking at the 2001-onward results, so even these numbers are slightly flattering.

The history chart shows the production model fitted on all data, so it is in-sample.

### 2. Regime detection

K-means (k = 4) on growth rates and levels of nine series, labelled Expansion / Tightening / Recession / Recovery (an extreme cluster can be labelled Crisis). The recession cluster is **named using the NBER indicator**, so its overlap with NBER months is partly by construction. The model is fitted on the full history, which makes it a description of the past, not a real-time classifier.

### 3. Taylor Rule

`rate = 2 + π + 0.5 (π − 2) + 0.5 × output gap`, the 1993 formula. Inflation is CPI less a fixed 0.5pp (a rough CPI-to-PCE adjustment). The output gap comes from a Hodrick-Prescott filter on CPI-deflated GDP. A second line uses 5-year average inflation; it is smoothed past inflation, **not** a forward-looking expectation.

Sanity checks the tests pin: the rule tracks the actual rate within 1pp in 2000 and 2007, and shows policy far below it in 1979 and 2021, which matches the usual reading of those episodes. See [Limitations](#limitations) for why it runs high today.

### 4. Sahm Rule

The 3-month average unemployment rate minus its lowest value in the previous 12 months; at 0.5pp the rule signals a recession has started. It reproduces the published FRED value for August 2024 (0.57). Since 1970 it crossed the threshold 10 times: 8 coincided with an NBER recession and 2 did not (2003 and 2024). It is a **confirmation** tool; by design it fires after a recession has begun.

### 5. Conditions index

Five categories (growth, labour, inflation, financial, housing), each a weighted average of 10-year rolling z-scores, averaged into a composite (clipped at ±3.5 so one shock month cannot dominate). Expansion months average +0.05 and NBER recession months −0.82. Because each reading is judged against the last ten years, a long-lasting shock gradually becomes the "normal" it is measured against.

### 6. Correlation and Granger tests

Lagged correlations (either series may lead) on growth rates, plus Granger tests on **stationary** versions (YoY growth for trending series, first differences for rates), with a Bonferroni adjustment for choosing the best of six lags. Granger causality means "helps predict", not "causes", and monthly growth rates that overlap by eleven months overstate how independent the observations are. Read the p-values as a ranking.

### 7. Scenario simulator

Seven sliders feed all of the above for a hypothetical economy. Rules worth knowing: the Taylor rate uses the same formula as the Taylor page but takes its output gap from unemployment (Okun's law, NAIRU 4.4%); a change to a level (say unemployment) is also applied to that series' 3/6-month change features; the "closest historical months" compare the scenario against each past month's z-score; the regime label is a transparent rule, not the K-means model. The GDP slider is **nominal** growth. Presets are illustrative, not calibrated forecasts.

### Trend extrapolation and its backtest

The series pages continue the last ten years' trend and seasonal pattern (Holt-Winters). Every six months since 2012 the model is refitted on what was known then, forecast 12 months ahead, and scored against what happened:

| Series | 95% interval actually contained the outcome | Forecast error vs "nothing changes" |
| --- | --- | --- |
| GDP | 84% | 0.46× (better) |
| CPI | 81% | 0.53× (better) |
| Retail sales | 92% | 0.82× (better) |
| Unemployment | 95% | 1.07× (no better) |
| Housing starts | 99% | 1.01× (no better) |
| Fed funds | 68% | 1.22× (worse) |
| 10Y–2Y spread | 80% | 1.23× (worse) |

For trending series the extrapolation helps; for rates and spreads, which turn on policy decisions, it adds nothing, and the dashboard says so next to each chart.

---

## What the review found and fixed

The platform was reviewed model by model against how each would be used in practice (check the numbers, then check whether they mean what the page says). Findings that changed behaviour:

| Area | Problem | Real-life consequence | Fix |
| --- | --- | --- | --- |
| Recession target | The 12-month "forward" label was backward-looking (it was 0 in the year before the 2008 recession and 1 for months after it ended) | The model learned "a recession just happened" and its validation numbers were meaningless | Forward label; last 12 unlabelled months excluded; 12-month purge before the test period |
| Recession validation | Only AUC and Brier were reported; no baseline | A Brier score near the base rate looked good | Baseline Brier, skill score, warning lead times and false alarms reported |
| Sahm Rule | Used the lowest *monthly* unemployment rate instead of the lowest 3-month average of the previous 12 months | Missed the August 2024 trigger (0.47 vs the published 0.57) | Official definition; test pins the published value |
| Granger tests | Run on raw levels, though the page said growth rates | Spurious "causal" links from shared trends | Stationary inputs, Bonferroni adjustment |
| Cross-correlation | Only checked whether the first-listed series leads | "Fed funds leads unemployment" could not be found | Both directions searched |
| Taylor Rule | HP filter on nominal GDP; 5-year trailing average called "forward-looking" | Steady inflation looked like a boom; the label overstated what the line is | CPI-deflated GDP; relabelled "smoothed" |
| Simulator | Output gap = GDP growth − 2.5 (a growth gap, not a level gap); unemployment jumps left momentum features unchanged; optional sliders crashed the regime rule | Scenarios gave inconsistent or no answers | Okun gap, same PCE wedge as Taylor page, momentum pass-through, defaults for omitted sliders |
| Regime | "GDP growth" was a 4-month change; analogue years listed every year in a range | Wrong feature, wrong analogues | 12-month growth; years that really had the regime |
| Forecast calibration | Calibration measured Prophet; the API served Holt-Winters | The accuracy panel described a different model | One model; rolling-origin backtest vs a naive benchmark; Prophet removed |
| dbt mart | Lags counted rows, not time | "12 rows back" was 3 years for GDP and 12 days for T10Y2Y | Lags by date (ASOF join) |
| API | CORS `*` for everything, exception text returned to clients, `/health` listed the working directory and every table, unbounded parameters, the simulator accepted `NaN` and refitted K-means on every call | Information leak and an easy way to keep the server busy | See [Security](#security-and-reliability) |
| Ingestion | Delete-then-insert without a transaction; empty FRED answer replaced a series with nothing; failures still exited 0 | A bad run could empty a series silently | Transactional replace, skip on empty, non-zero exit |
| Docker | Dashboard image referenced a missing `nginx.conf`; `.env` could be copied into the image; an unused Postgres and Prefect server | Build failure and a secret-leak risk | Fixed, `.dockerignore`, non-root user, slimmer compose |
| Dependencies | 14 npm advisories | Dev-server and router vulnerabilities | React Router 7 and Vite 8; `npm audit` reports 0 |

## Security and reliability

- Public, read-only API with no logins or cookies. `ALLOWED_ORIGINS` can restrict browser access to your dashboard.
- Every parameter is bounded and every series id is checked against the known list; scenario inputs must lie within the slider ranges and cannot be `NaN` or infinite.
- Errors are logged in full and returned as short generic messages. `/health` only says whether the database and model exist.
- Per-visitor rate limits (30 scenario runs and 120 reads per minute by default). `X-Forwarded-For` is trusted only when `TRUSTED_PROXY_HOPS` is set, so visitors cannot invent addresses to dodge the limit.
- Analyses are cached until the warehouse or model file changes, and the heavy ones are warmed up in the background at start-up.
- Security headers on API responses; the dashboard container runs nginx with the same headers. The API container runs as an unprivileged user.

## API

Base URL `http://localhost:8000`, interactive docs at `/docs`.

| Method | Endpoint | Description |
| --- | --- | --- |
| GET | `/health` | Liveness, database and model present |
| GET | `/pipeline/series`, `/pipeline/series/{id}?limit=` | Series list and recent observations |
| GET | `/metrics/forecast/{id}?horizon=` | 12-month trend extrapolation (1–36) |
| GET | `/metrics/drift`, `/metrics/drift/{id}` | PSI drift report |
| GET | `/analysis/recession` `regime` `taylor` `sahm` `conditions` `correlation` | The six analyses |
| GET | `/analysis/simulate-defaults` | Current values for the sliders |
| POST | `/analysis/simulate` | Run all models on a scenario |
| GET | `/analysis/calibration/{id}` | Forecast backtest results |
| GET | `/lineage/graph` | Pipeline graph |

## Environment

Copy `.env.example` to `.env`. The committed warehouse already holds the data, so a key is only needed to refresh it.

| Variable | Default | Used by | Notes |
| --- | --- | --- | --- |
| `FRED_API_KEY` | none | ingestion | Free key from FRED. Never sent anywhere else. |
| `DUCKDB_PATH` | `./data/warehouse.duckdb` | everything | Warehouse file. |
| `MODEL_ARTIFACTS_PATH` | `./ml/artifacts` | models, API | Trained model and backtest files. |
| `ALLOWED_ORIGINS` | any site | API | Comma-separated list to restrict browser access. |
| `TRUSTED_PROXY_HOPS` | `0` | API | Reverse proxies in front of the API (Render counts as 1). |
| `SIMULATE_RATE_PER_MIN` / `READ_RATE_PER_MIN` | `30` / `120` | API | Per visitor. |
| `WARMUP` | `1` | API | Set `0` to skip start-up pre-computation. |
| `VITE_API_URL` | `http://localhost:8000` | dashboard (build time) | Address the browser uses to reach the API. |

## Running locally

Python 3.11+ and Node 20+.

```bash
python -m venv .venv && .venv\Scripts\activate        # source .venv/bin/activate on macOS/Linux
pip install -r requirements.txt
uvicorn api.main:app --port 8000                      # API (docs at /docs)

cd dashboard && npm install && npm run dev             # dashboard at http://localhost:5173
```

Refreshing the data and models (needs `FRED_API_KEY`):

```bash
python -m pipeline.flows.ingest_flow                   # fetch the nine series
dbt run --project-dir transform --profiles-dir transform
python train_recession.py                              # retrain the recession model
python calibrate_all.py                                # recompute the forecast backtests (about a minute)
```

Docker: `docker compose up --build` serves the API on 8000 and the dashboard on 5173. Set `TRUSTED_PROXY_HOPS` and `ALLOWED_ORIGINS` in `docker-compose.yml` when you put it behind a proxy.

## Limitations

- **Revised data, not real-time data.** FRED returns today's revised values (GDP and payrolls are revised for years). Every historical result, including the validation above, is "what the data says now", not "what a forecaster knew then". A real-time study needs vintage data (ALFRED).
- **GDP is nominal.** The warehouse holds nominal GDP, so "GDP growth" includes inflation. Real GDP (GDPC1) and CBO potential GDP would give a proper output gap.
- **Publication lag.** GDP arrives about a month after the quarter, payrolls and unemployment a week after the month, and NBER dates a year or more later. The monthly panel lines series up by the period they describe, not by when they were published.
- **Few recessions.** Only about twelve recessions since 1948 and three in the recession model's training period. Any model of recessions has very little to learn from.
- **The Taylor Rule is a benchmark, not the Fed's rule.** It uses headline CPI, a 1993 neutral rate of 2% (modern estimates are about 0.5–1%) and an HP filter that is revised as data arrives. The gap it shows is context, not a prediction.
- **The extrapolation is a trend, not a forecast.** It cannot anticipate a turning point and, for rates and spreads, does not beat "nothing changes".
- **Single-country, monthly.** Nothing here covers other economies, daily markets, credit spreads, or surveys of expectations.
- **In-memory rate limits.** Each API process counts separately and restarting resets them.
- **No automated test suite in this repository.** The checks run during the review (79 tests across the models, API, ingestion and SQL) are kept outside the repository.

## Possible improvements

- Ingest vintage data (ALFRED) and rebuild the validation in real time.
- Add real GDP (GDPC1), potential GDP (GDPPOT), core PCE and inflation-expectation series; use them in the Taylor Rule and the output gap.
- Add credit spreads, initial claims and term-premium series to the recession model, and test a model that does not rely on levels from the 1980s.
- Quantify uncertainty for the risk score (bootstrap or Bayesian) and show it on the page.
- Replace the single-origin regime fit with a rolling or expanding fit so the label is available in real time.
- Move the rate limit to a shared store; run ingestion on a schedule with alerting on failed series.
- Schema tests in dbt (not-null, accepted series, freshness) and a freshness banner on the dashboard.

## Project layout

```text
ingestion/    FRED client and row schema
pipeline/     Prefect flow and tasks (transactional load)
transform/    dbt project (staging view, trends table)
ml/           recession, regime, taylor, sahm, conditions, correlation, simulator,
              inference (Holt-Winters), calibration (backtest), cache helper
monitoring/   PSI drift detector, lineage graph
api/          FastAPI app, routers, guards (limits, cache, safe errors)
dashboard/    React app
docker/       API and dashboard images
data/         warehouse.duckdb (committed so the app runs without a key)
```

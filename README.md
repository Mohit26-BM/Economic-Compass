# Economic Compass

An end-to-end data engineering and machine learning platform that ingests real U.S. macroeconomic data from the Federal Reserve (FRED API), transforms it through a dbt pipeline, runs seven analytical models, and serves everything through a FastAPI backend and React dashboard.

---

## What This Project Does

Most portfolio projects stop at training a model in a notebook. This project builds the full production-grade stack around those models:

- **Automated ingestion** — pulls live economic data from the Federal Reserve on a schedule
- **Data transformation** — cleans, types, and engineers features using dbt (the industry standard for SQL transformations)
- **Seven analytical models** — recession probability, regime detection, Taylor Rule, Sahm Rule, correlation analysis, conditions index, and an interactive scenario simulator
- **Data lineage** — tracks the full journey of every data point from API call to dashboard output
- **REST API** — FastAPI backend serving all model outputs and historical data
- **Interactive dashboard** — React frontend with charts, live what-if sliders, and historical analogue finder

---

## Tech Stack

| Layer           | Technology                          | Purpose                                           |
| --------------- | ----------------------------------- | ------------------------------------------------- |
| Orchestration   | Prefect 3                           | Schedule and monitor pipeline runs                |
| Data warehouse  | DuckDB                              | Embedded analytical database (no server needed)   |
| Transformations | dbt + dbt-duckdb                    | SQL-based data modeling (staging → marts)         |
| ML models       | scikit-learn, Prophet, custom logic | Recession model, regime clustering, forecasting   |
| API             | FastAPI + Uvicorn                   | Async REST API with auto-generated docs           |
| Dashboard       | React + Vite + Recharts             | Interactive charts, sliders, lineage graph        |
| Data source     | FRED API (St. Louis Fed)            | 800,000+ free macroeconomic series                |

---

## Project Structure

```text
data-pipeline-platform/
├── ingestion/                      # Data ingestion layer
│   ├── sources/
│   │   └── fred.py                 # Async FRED API client with retry logic
│   └── schemas/
│       └── raw.py                  # Pydantic models for raw observations
│
├── pipeline/                       # Prefect orchestration
│   ├── flows/
│   │   └── ingest_flow.py          # Main ingestion flow (fetch → load)
│   └── tasks/
│       └── common.py               # Reusable Prefect tasks
│
├── transform/                      # dbt project
│   ├── models/
│   │   ├── staging/
│   │   │   ├── sources.yml                    # DuckDB source definition
│   │   │   └── stg_economic_indicators.sql    # Cleans raw data
│   │   └── marts/
│   │       └── mart_indicator_trends.sql      # Lag features + YoY/MoM %
│   ├── dbt_project.yml
│   └── profiles.yml
│
├── ml/                             # Machine learning layer
│   ├── recession/
│   │   └── model.py                # Logistic regression, OOS validation, Brier score
│   ├── regime/
│   │   └── detector.py             # K-means (k=4) regime clustering
│   ├── taylor/
│   │   └── rule.py                 # Taylor Rule (HP-filtered, forward/backward variants)
│   ├── sahm/
│   │   └── indicator.py            # Sahm Rule + accuracy metrics vs NBER
│   ├── conditions/
│   │   └── index.py                # 5-category conditions index (10yr rolling z-scores)
│   ├── simulator/
│   │   └── engine.py               # Scenario simulator engine + historical analogues
│   ├── features/
│   │   └── engineering.py          # Shared feature engineering (YoY transforms, etc.)
│   ├── train/
│   │   └── trainer.py              # Prophet training + artifact saving
│   ├── inference/
│   │   └── predictor.py            # Load artifact and generate forecasts
│   └── artifacts/                  # Saved .joblib model files (gitignored)
│
├── monitoring/                     # Observability layer
│   └── lineage/
│       └── tracker.py              # Pipeline lineage graph (nodes + edges)
│
├── api/                            # FastAPI backend
│   ├── main.py                     # App entry point + CORS config
│   ├── routers/
│   │   ├── pipeline.py             # GET /pipeline/series endpoints
│   │   ├── metrics.py              # GET /metrics/forecast
│   │   ├── lineage.py              # GET /lineage/graph
│   │   └── analysis.py             # All analytical model endpoints
│   └── schemas/
│       └── responses.py            # Pydantic response models
│
├── dashboard/                      # React frontend (Vite)
│   └── src/
│       ├── pages/
│       │   ├── OverviewPage.jsx        # Series cards + analysis tool index
│       │   ├── SeriesPage.jsx          # Historical + forecast chart
│       │   ├── LineagePage.jsx         # Interactive pipeline DAG
│       │   ├── RecessionPage.jsx       # Recession probability gauge + history
│       │   ├── RegimesPage.jsx         # K-means cluster chart + current regime
│       │   ├── CorrelationPage.jsx     # Granger causality + cross-correlation matrix
│       │   ├── TaylorPage.jsx          # Taylor Rule prescribed vs actual rate
│       │   ├── SahmPage.jsx            # Sahm Rule chart + accuracy metrics
│       │   ├── ConditionsPage.jsx      # Composite index + 5 category sub-indices
│       │   └── SimulatorPage.jsx       # Interactive scenario simulator
│       ├── services/
│       │   └── api.js                  # Axios API client
│       └── components/
│           └── layout/Layout.jsx       # Collapsible sidebar navigation
│
├── data/
│   ├── raw/                        # Gitignored
│   └── processed/                  # Gitignored
│
├── docker/
│   ├── api.Dockerfile
│   └── dashboard.Dockerfile
├── docker-compose.yml
├── train_recession.py              # Train logistic regression recession model
├── train_all.py                    # Train all Prophet forecast models
├── requirements.txt
├── pyproject.toml
└── .env.example
```

---

## Economic Series Tracked

| Series ID | Full Name                            | Category        | Frequency | Use in models                                |
| --------- | ------------------------------------ | --------------- | --------- | -------------------------------------------- |
| GDP       | Gross Domestic Product               | Growth          | Quarterly | Taylor Rule, Conditions Index, Simulator     |
| CPIAUCSL  | Consumer Price Index                 | Inflation       | Monthly   | Taylor Rule, Conditions Index, Simulator     |
| UNRATE    | Unemployment Rate                    | Labour Market   | Monthly   | Sahm Rule, Recession model, Conditions Index |
| FEDFUNDS  | Federal Funds Rate                   | Monetary Policy | Monthly   | Taylor Rule, Conditions Index, Simulator     |
| T10Y2Y    | 10Y–2Y Treasury Spread               | Financial       | Daily     | Recession model, Conditions Index, Simulator |
| HOUST     | New Housing Starts                   | Housing         | Monthly   | Conditions Index, Simulator                  |
| RSXFS     | Advance Retail Sales (ex-food)       | Consumer        | Monthly   | Conditions Index, Simulator                  |
| PAYEMS    | Nonfarm Payrolls                     | Labour Market   | Monthly   | Sahm Rule (payrolls YoY chart)               |
| USREC     | NBER Recession Indicator             | Reference       | Monthly   | Ground truth for all model validation        |

**Total: ~23,000 rows of real economic data spanning up to 80 years.**

---

## Data Pipeline Architecture

```text
FRED API (9 series)
   │
   ▼  [Prefect Flow — ingest_flow.py]
raw.economic_indicators               ← DuckDB raw schema, ~23k rows
   │
   ▼  [dbt — stg_economic_indicators.sql]
main_staging.stg_economic_indicators  ← Cleaned: nulls removed, types cast, FRED
                                         missing-value sentinel '.' → NULL
   │
   ▼  [dbt — mart_indicator_trends.sql]
main_marts.mart_indicator_trends      ← Lag features (1m, 3m, 12m),
                                         rolling 12m average, MoM/YoY % change
   │
   ├──▶ [ML Models]                   ← recession, regimes, Taylor, Sahm,
   │                                     conditions, simulator, correlation
   │
   ├──▶ [Prophet Trainer]  →  ml/artifacts/*.joblib
   │
   └──▶ [Lineage Tracker]  →  nodes + edges graph
              │
              ▼
         FastAPI (port 8000)
              │
              ▼
         React Dashboard (port 5173)
```

### dbt Transformation Layers

**Staging (`stg_economic_indicators`)** — materialised as a VIEW:

- Filters FRED missing values (`'.'` → NULL)
- Casts `observation_date` to DATE, `value` to DOUBLE
- Standardises column names across all series

**Marts (`mart_indicator_trends`)** — materialised as a TABLE:

- Lag features: `value_lag_1m`, `value_lag_3m`, `value_lag_12m`
- Rolling 12-month average
- Month-over-month % change (`mom_pct_change`)
- Year-over-year % change (`yoy_pct_change`)

---

## Data Lineage

The platform tracks the complete transformation journey from FRED API call to dashboard output. Each node in the lineage graph has a `type` (source / transform / model / output) and each edge carries a `transform` label describing what happened at that step.

```text
FRED API
  └─[fetch]──▶ raw.economic_indicators
                  └─[dbt staging]──▶ stg_economic_indicators
                                        └─[dbt mart]──▶ mart_indicator_trends
                                                           │
                                              ┌────────────┼────────────────────┐
                                              ▼            ▼                    ▼
                                        recession_    conditions_          taylor_rule
                                        model         index                calculator
                                              │            │                    │
                                              └────────────┴──────────┬─────────┘
                                                                       ▼
                                                               React Dashboard
```

The lineage API endpoint (`GET /lineage/graph`) returns a node/edge JSON structure that the dashboard renders as an interactive DAG. Each series has its own lineage path — if FRED silently changes how it reports a series, the lineage graph immediately shows which downstream models are affected.

**Why lineage matters for debugging:**

1. Forecast looks wrong → check lineage to identify which transform step changed
2. Conditions Index score unexpected → trace back through mart_indicator_trends to the raw series
3. Regime label flipped → lineage shows whether the cause was a data issue or a model issue

---

## Analytical Models

### 1. Recession Probability

Logistic regression trained on yield curve, unemployment momentum, and Fed Funds rate features. Outputs a 12-month forward recession probability.

- **Validation:** Out-of-sample across three recessions (2001, 2008–09, 2020)
- **Metric:** Brier score — measures calibration, not just directional accuracy
- **Key feature:** T10Y2Y (yield curve inversion) — every U.S. recession since 1955 was preceded by an inverted yield curve

### 2. Economic Regime Detection

K-means clustering (k=4) on growth-rate transformed features. Identifies four recurring economic environments: Expansion, Tightening, Recession, Recovery.

- Labels are validated against NBER recession dates
- Silhouette score measures within-cluster cohesion
- Current regime is identified by classifying the most recent data point

### 3. Taylor Rule

Classic Taylor Rule prescription using HP-filtered output gap and CPI inflation. Two variants:

- **Backward-looking** — uses current CPI
- **Forward-looking** — uses trailing 5-year CPI average (captures inflation expectations)

The gap between the prescribed rate and the actual Fed Funds rate shows whether policy is tight or accommodative. When they diverge by more than 1pp, it's historically significant.

### 4. Sahm Rule

The Sahm Rule fires when the 3-month average unemployment rate rises 0.5pp above its 12-month low. Designed by Claudia Sahm (former Fed economist) to identify recessions in real time using only publicly available data.

**Accuracy metrics (validated vs NBER, since 1970):**

| Metric              | Value                                             |
| ------------------- | ------------------------------------------------- |
| Threshold crossings | Tracked per episode, not raw months               |
| Correct signals     | Episodes overlapping ±3 months of NBER recession  |
| False positives     | Episodes with no overlapping NBER recession       |
| Payrolls YoY        | Supplementary chart showing momentum context      |

### 5. Conditions Index

A composite index inspired by the Chicago Fed National Activity Index (CFNAI). Five category sub-indices — Growth, Labor Market, Inflation, Financial Conditions, Housing — each computed as a weighted average of 10-year rolling z-scores.

**Why 10-year rolling z-scores:**
The 1970s–80s inflation and rate environment was structurally different from today. Using a rolling window means the score reflects conditions relative to the recent regime, not against historical extremes that are no longer comparable.

**Z-score clipping at ±3.5:**
Prevents any single shock month (e.g. April 2020 COVID) from dominating the composite.

| Composite Score | Label            |
| --------------- | ---------------- |
| < −1.0          | Contraction      |
| −1.0 to −0.5    | Slowdown         |
| −0.5 to −0.25   | Below Trend      |
| −0.25 to +0.25  | Neutral          |
| +0.25 to +0.75  | Moderate Growth  |
| > +0.75         | Expansion        |

**Validation:** In-sample separation — expansion months average ~+0.05, recession months average ~−0.84. A meaningful separation confirms the index discriminates between regimes.

### 6. Cross-Series Correlation

Granger causality tests and lagged cross-correlations on growth-rate transformed series. Identifies which indicators statistically lead or lag others, with p-values.

**Why growth-rate transforms:** Most economic series are non-stationary in levels (they trend upward over time). Applying YoY transforms makes them stationary, which is a prerequisite for valid Granger causality tests.

### 7. Economic Scenario Simulator

An interactive "macroeconomic laboratory" — seven sliders drive all models simultaneously.

**Inputs (sliders):**

| Slider         | Range                | Step   |
| -------------- | -------------------- | ------ |
| Fed Funds Rate | 0% to 10%            | 0.25pp |
| CPI Inflation  | -2% to 12% (YoY)     | 0.1pp  |
| GDP Growth     | -8% to 10% (YoY)     | 0.1pp  |
| Unemployment   | 2% to 12%            | 0.1pp  |
| 10Y-2Y Spread  | -3pp to +3.5pp       | 0.05pp |
| Housing Starts | -50% to +60% (YoY)   | 1pp    |
| Retail Sales   | -15% to +20% (YoY)   | 0.5pp  |

**Outputs:**

- Taylor Rule: prescribed vs actual rate, policy gap, plain-English explanation
- Recession Risk: probability bar, signal color, reason
- Conditions Index: composite label + 5 category chips
- Economic Regime: rule-based label + explanation
- Historical Analogues: top 5 closest real months by Euclidean distance in z-score space

**Preset scenarios:** Soft Landing, Fed Pivot, 1970s Inflation, 2008 Crisis, COVID Shock, Goldilocks — clicking a preset moves all sliders to historically-calibrated values.

**Scenario Interpretation panel:** Automatically generates a positive/negative signal breakdown and a plain-English net assessment for any combination of slider values.

**Simulation limitation (prominently displayed):**
Only current levels are adjusted. Historical momentum features (3m/6m/12m changes) remain anchored to actual data. Results are directional signals, not precise forecasts.

---

## API Endpoints

Base URL: `http://localhost:8000`

### Pipeline

| Method | Endpoint                | Description                                       |
| ------ | ----------------------- | ------------------------------------------------- |
| GET    | `/health`               | Health check                                      |
| GET    | `/pipeline/series`      | List all 9 series with row counts and date ranges |
| GET    | `/pipeline/series/{id}` | Historical observations for a single series       |

### Metrics

| Method | Endpoint                 | Description                                      |
| ------ | ------------------------ | ------------------------------------------------ |
| GET    | `/metrics/forecast/{id}` | 12-month Prophet forecast with confidence bounds |

### Analysis

| Method | Endpoint                      | Description                                        |
| ------ | ----------------------------- | -------------------------------------------------- |
| GET    | `/analysis/recession`         | Recession probability + feature importance         |
| GET    | `/analysis/regime`            | Current regime + cluster history                   |
| GET    | `/analysis/taylor`            | Taylor Rule prescribed rate + policy gap history   |
| GET    | `/analysis/sahm`              | Sahm Rule value + accuracy metrics vs NBER         |
| GET    | `/analysis/correlation`       | Granger causality matrix + lagged correlations     |
| GET    | `/analysis/conditions`        | Conditions index composite + 5 category scores     |
| GET    | `/analysis/simulate-defaults` | Current real values for simulator slider init      |
| POST   | `/analysis/simulate`          | Run all models against a hypothetical input set    |
| GET    | `/analysis/calibration/{id}`  | Forecast calibration for a series                  |

### Lineage

| Method | Endpoint         | Description                                   |
| ------ | ---------------- | --------------------------------------------- |
| GET    | `/lineage/graph` | Full pipeline lineage as nodes + edges JSON   |
| GET    | `/docs`          | Auto-generated interactive API documentation  |

---

## Setup & Running

### Prerequisites

- Python 3.11+
- Node.js 20+
- A free [FRED API key](https://fredaccount.stlouisfed.org/apikeys)

### 1. Clone and install dependencies

```bash
git clone <repo-url>
cd data-pipeline-platform
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS/Linux
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env and add your FRED_API_KEY
```

### 3. Run the ingestion pipeline

```bash
python -m pipeline.flows.ingest_flow
```

Fetches ~23,000 rows across 9 series into `data/warehouse.duckdb`.

### 4. Run dbt transformations

```bash
dbt run --project-dir transform --profiles-dir transform
```

Builds the staging view and marts table in DuckDB.

### 5. Train the recession model

```bash
python train_recession.py
```

Trains logistic regression on yield curve + labour market features. Saves to `ml/artifacts/recession_model.joblib`.

### 6. Train Prophet forecast models (optional)

```bash
python train_all.py
```

Trains Prophet on all series (~30 seconds). Required only for the individual series forecast charts.

### 7. Start the API

```bash
uvicorn api.main:app --reload --port 8000
```

API available at `http://localhost:8000`. Interactive docs at `http://localhost:8000/docs`.

### 8. Start the dashboard

```bash
cd dashboard
npm install
npm run dev
```

Dashboard available at `http://localhost:5173`.

---

## Key Engineering Decisions

**Why DuckDB instead of PostgreSQL?**
DuckDB is an embedded analytical database — it runs in-process with no server, stores data in a single file, and is optimised for columnar analytical queries. For a single-machine project it eliminates infrastructure overhead while still supporting full SQL, schemas, and dbt integration. The entire warehouse is a single `.duckdb` file.

**Why Prefect instead of Airflow?**
Prefect 3 has a much simpler local development experience — flows are just Python functions decorated with `@flow` and `@task`. No DAG configuration files, no XML, no scheduler process required. It runs in local mode automatically and provides observability for free.

**Why logistic regression for recession prediction (not LSTM)?**
Economic data is low-frequency (monthly), with limited labelled recession months (~80 since 1970). A logistic regression is interpretable, fast to retrain, and produces calibrated probability outputs. Deep learning would overfit on this sample size and produce opaque predictions. The Brier score measures calibration explicitly — probability outputs should actually reflect observed frequencies.

**Why 10-year rolling z-scores for the Conditions Index?**
The 1970s–80s was a structurally different economic regime (persistent high inflation, very different rate levels). Using full-history z-scores would make today's 3% CPI look "near normal" by comparison. A 10-year rolling window means the score reflects conditions relative to the recent regime — which is what's actually useful for a forward-looking decision.

**Why rule-based regime classification in the Simulator?**
The Simulator needs to classify a single hypothetical data point, not a time series. Re-running K-means on a single point would require the full historical panel as context. A rule-based classifier using explicit thresholds on inputs (CPI > 4% and Fed Funds > 3% → Tightening; GDP < 0 with 3+ stress signals → Recession; etc.) is deterministic, transparent, and avoids the chicken-and-egg problem of retraining.

---

## Data Lineage in Detail

The lineage tracker (`monitoring/lineage/tracker.py`) maintains a directed acyclic graph where:

- **Nodes** represent data artifacts: raw tables, staging models, mart models, ML model outputs
- **Edges** represent transformations: fetch, dbt-stage, dbt-mart, train, infer, aggregate

The API serialises this graph as `{ nodes: [...], edges: [...] }` which the `LineagePage.jsx` dashboard renders as an interactive visualization.

**Node schema:**

```json
{
  "id": "mart_indicator_trends",
  "label": "mart_indicator_trends",
  "type": "transform",
  "description": "Lag features, rolling averages, YoY/MoM changes"
}
```

**Edge schema:**

```json
{
  "source": "stg_economic_indicators",
  "target": "mart_indicator_trends",
  "transform": "dbt mart — adds lag_1m, lag_3m, lag_12m, rolling_12m_avg, mom_pct_change, yoy_pct_change"
}
```

**Full lineage path for a recession probability output:**

```text
FRED API
  └─[fetch via Prefect]──────────────▶ raw.economic_indicators
                                            │
                                  [dbt staging: type cast,
                                   null filter, rename]
                                            │
                                            ▼
                               stg_economic_indicators
                                            │
                                  [dbt mart: lag features,
                                   rolling avg, YoY/MoM]
                                            │
                                            ▼
                               mart_indicator_trends
                                            │
                              [feature engineering: inversion
                               flag, momentum delta, spread]
                                            │
                                            ▼
                               recession_model (logistic regression)
                                            │
                                 [inference: predict_proba]
                                            │
                                            ▼
                               GET /analysis/recession
                                            │
                                            ▼
                               RecessionPage.jsx (dashboard)
```

---

## Interview Talking Points

**On the pipeline architecture:**

> "I built a full data engineering pipeline: Prefect orchestrates the ingestion from FRED, dbt handles staging and mart transformations in DuckDB, and FastAPI serves everything downstream. Each layer is independently testable — I can run dbt without the API, and I can call the API without the dashboard."

**On the analytical models:**

> "The project runs seven distinct analytical models on the same underlying data. They're not independent charts — they're interconnected. The Scenario Simulator demonstrates this directly: move one slider and the Taylor Rule, recession probability, conditions index, and regime all update simultaneously. That's the whole point of building a platform rather than a collection of notebooks."

**On the Conditions Index design:**

> "I used 10-year rolling z-scores rather than full-history z-scores because economic regimes are non-stationary. The 1970s inflation environment isn't comparable to today. A rolling window gives scores that are meaningful relative to the current regime, and I clip at ±3.5 to prevent single shocks like April 2020 from dominating the composite."

**On the recession model calibration:**

> "I measure the recession model with a Brier score, not just accuracy. A model that outputs 70% probability for every month would have OK accuracy but terrible calibration. Brier score penalises confident wrong predictions — which is what actually matters for a probability forecast."

**On data lineage:**

> "If a forecast looks wrong, I can trace it back through the lineage graph: the dashboard gets data from the API, which calls the model, which was trained on mart_indicator_trends, which was built from stg_economic_indicators, which came from raw.economic_indicators, which was fetched from FRED. If FRED silently changes how they report a series, the lineage tells me exactly which downstream models are affected."

**On the Scenario Simulator:**

> "The Simulator was a deliberate design choice to make the platform accessible to non-economists. 'What if inflation fell to 2%?' is a question anyone can ask. The answer — Taylor Rule says cut rates to X, recession probability drops to Y%, conditions move to Moderate Growth, the closest historical analogue is 1996 — turns abstract models into concrete, interpretable outputs. I also added a prominent limitation warning explaining that momentum features are held fixed, so a user can't over-interpret a single-point simulation as a precise forecast."

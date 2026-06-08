import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { getSeries } from "../services/api";

// Static metadata enriching FRED series IDs with human context
const SERIES_META = {
  GDP: {
    name: "Gross Domestic Product",
    category: "Growth",
    color: "#16a34a",
    description:
      "Total value of all goods and services produced in the U.S. The broadest measure of economic output, released quarterly with a ~1-month lag.",
    role: "The anchor — everything else is interpreted relative to GDP growth.",
  },
  CPIAUCSL: {
    name: "Consumer Price Index",
    category: "Inflation",
    color: "#dc2626",
    description:
      "Measures price changes across a basket of consumer goods. The primary household inflation gauge, released monthly by the Bureau of Labor Statistics.",
    role: "Drives Fed policy decisions. Used in the Taylor Rule and Regime Detection.",
  },
  UNRATE: {
    name: "Unemployment Rate",
    category: "Labor Market",
    color: "#2563eb",
    description:
      "Share of the labor force actively seeking work. A lagging indicator — it typically rises only after a recession is already underway.",
    role: "The Fed's second mandate. Rising unemployment is a key recession signal.",
  },
  FEDFUNDS: {
    name: "Federal Funds Rate",
    category: "Monetary Policy",
    color: "#7c3aed",
    description:
      "The overnight rate at which banks lend reserves to each other. Directly controlled by the Federal Reserve to steer economic conditions.",
    role: "The lever. Every other interest rate in the economy is priced relative to this.",
  },
  T10Y2Y: {
    name: "10Y–2Y Treasury Spread",
    category: "Financial Markets",
    color: "#d97706",
    description:
      "Difference between 10-year and 2-year Treasury yields. When negative (inverted), this spread has preceded every U.S. recession since 1955.",
    role: "The bond market's recession signal. Used directly in the Recession Probability model.",
  },
  HOUST: {
    name: "Housing Starts",
    category: "Housing",
    color: "#0891b2",
    description:
      "Number of new residential construction projects begun each month. Highly sensitive to mortgage rates — one of the most interest-rate-reactive sectors.",
    role: "A leading indicator. Housing reacts to rate changes before the broader economy does.",
  },
  RSXFS: {
    name: "Retail Sales (ex-Food)",
    category: "Consumer",
    color: "#059669",
    description:
      "Total receipts at retail stores, excluding food services. A direct read on consumer spending, which drives approximately 70% of U.S. GDP.",
    role: "Consumer spending is the economy. Retail sales track its pulse in near-real time.",
  },
  USREC: {
    name: "NBER Recession Indicator",
    category: "Reference",
    color: "#64748b",
    description:
      "Binary indicator (0/1) marking each month as recession or expansion, as officially dated by the National Bureau of Economic Research (NBER). Not a forecast — NBER dates are published with a lag of several months.",
    role: "Ground truth for model validation. Used to validate recession probability, regime labels, and calibration backtests.",
  },
  PAYEMS: {
    name: "Nonfarm Payrolls",
    category: "Labor Market",
    color: "#0369a1",
    description:
      "Total jobs added or lost across all non-farm sectors each month. Released the first Friday of every month — consistently one of the most market-moving data releases on the economic calendar.",
    role: "Enables the Sahm Rule indicator. Payrolls momentum is the Fed's primary real-time read on labour market health.",
  },
};

const ANALYSIS_TOOLS = [
  {
    to: "/recession",
    title: "Recession Probability",
    question: "What is the current 12-month recession risk?",
    description:
      "Logistic regression on yield curve inversion, unemployment momentum, and rate trends. Validated out-of-sample across three historical recessions (2001, 2008–09, 2020).",
    tags: ["Logistic Regression", "OOS Validation", "Brier Score"],
    color: "#dc2626",
  },
  {
    to: "/correlation",
    title: "Cross-Series Correlation",
    question: "Which indicators predict changes in others?",
    description:
      "Granger causality tests and lagged cross-correlations on growth-rate transformed series. Identifies statistical lead/lag relationships with p-values.",
    tags: ["Granger Causality", "Pearson r", "Stationarity"],
    color: "#6366f1",
  },
  {
    to: "/regimes",
    title: "Economic Regimes",
    question: "Which economic environment are we in right now?",
    description:
      "K-means (k=4) clustering on change and growth features identifies four recurring economic environments. Labels are validated against NBER recession dates.",
    tags: ["K-means", "Silhouette Score", "NBER Validation"],
    color: "#d97706",
  },
  {
    to: "/taylor",
    title: "Taylor Rule",
    question: "Is monetary policy too tight or too loose?",
    description:
      "Classic Taylor Rule prescription using HP-filtered output gap and CPI-to-PCE adjusted inflation. Two variants — backward-looking (current CPI) and forward-looking (5yr CPI avg) — show why economists can disagree using the same formula.",
    tags: ["HP Filter", "Output Gap", "PCE Proxy", "Forward-looking"],
    color: "#0891b2",
  },
  {
    to: "/sahm",
    title: "Sahm Rule",
    question: "Is the labour market signalling a recession in real time?",
    description:
      "The Sahm Rule fires when the 3-month average unemployment rate rises 0.5pp above its 12-month low. Has called every U.S. recession since 1970 with no false positives, using only real-time data.",
    tags: ["Sahm Rule", "Nonfarm Payrolls", "Real-time Signal"],
    color: "#0369a1",
  },
  {
    to: "/simulator",
    title: "Scenario Simulator",
    question: "What if inflation fell to 2%? What if rates rose to 7%?",
    description:
      "Adjust sliders for Fed Funds, inflation, GDP growth, unemployment, and the yield curve. All five models update in real time — showing how the Taylor Rule, recession probability, conditions index, regime, and historical analogues respond to each scenario.",
    tags: ["What-if Analysis", "Live Models", "Historical Analogs"],
    color: "#7c3aed",
  },
  {
    to: "/conditions",
    title: "Conditions Index",
    question: "What is the economy saying overall right now?",
    description:
      "Five category sub-indices — Growth, Labor Market, Inflation, Financial Conditions, and Housing — aggregated into a single composite score. Uses 10-year rolling z-scores so the reading reflects today's conditions relative to the recent regime, not the 1970s.",
    tags: ["Composite Index", "Z-scores", "Percentile Rank", "5 Categories"],
    color: "#7c3aed",
  },
];

function SeriesCard({ meta, stats }) {
  const m = meta ?? {};
  return (
    <div className="series-card" style={{ borderTopColor: m.color ?? "#e2e8f0" }}>
      <div className="series-card-header">
        <div>
          <span className="category-tag" style={{ background: (m.color ?? "#6b7280") + "18", color: m.color ?? "#6b7280" }}>
            {m.category ?? "—"}
          </span>
          <div className="series-card-id">{stats.series_id}</div>
        </div>
        <Link to={`/series/${stats.series_id}`} className="series-card-link">
          View chart →
        </Link>
      </div>
      <div className="series-card-name">{m.name ?? stats.series_id}</div>
      <p className="series-card-desc">{m.description}</p>
      <div className="series-card-role">
        <span className="series-role-label">Why tracked:</span> {m.role}
      </div>
      <div className="series-card-meta">
        <span>{stats.row_count.toLocaleString()} observations</span>
        <span>{stats.first_date?.slice(0, 7)} – {stats.last_date?.slice(0, 7)}</span>
      </div>
    </div>
  );
}

function AnalysisCard({ tool }) {
  return (
    <Link to={tool.to} className="analysis-card" style={{ borderTopColor: tool.color }}>
      <div className="analysis-card-question">{tool.question}</div>
      <div className="analysis-card-title" style={{ color: tool.color }}>{tool.title}</div>
      <p className="analysis-card-desc">{tool.description}</p>
      <div className="analysis-card-tags">
        {tool.tags.map((t) => (
          <span key={t} className="analysis-tag">{t}</span>
        ))}
      </div>
      <div className="analysis-card-cta" style={{ color: tool.color }}>
        Explore →
      </div>
    </Link>
  );
}

export default function OverviewPage() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["series"],
    queryFn: getSeries,
  });

  return (
    <div>
      {/* Platform intro */}
      <div className="overview-hero">
        <h2 className="overview-hero-title">U.S. Macroeconomic Data Platform</h2>
        <p className="overview-hero-desc">
          A full-stack data engineering and ML pipeline that ingests U.S. economic
          indicators from the Federal Reserve (FRED), transforms them through a dbt
          mart layer, detects statistical drift, and runs four analytical models on top.
        </p>
        <div className="overview-hero-why">
          <strong>Why these 9 series?</strong> Together they cover the full U.S. business cycle:
          GDP and retail sales measure output, CPI captures inflation, UNRATE tracks labour
          market health, FEDFUNDS reflects monetary policy, T10Y2Y is the bond market's
          recession signal, and HOUST is a rate-sensitive leading indicator. No single series
          tells the whole story — the signal is in how they move relative to each other.
        </div>
      </div>

      {/* Series cards */}
      <div className="section-header">
        <h3>Data Series</h3>
        <span className="section-count">
          {isLoading ? "—" : `${data?.series?.length ?? 0} series`}
        </span>
      </div>

      {isLoading && (
        <div className="series-grid">
          {[...Array(9)].map((_, i) => (
            <div key={i} className="series-card series-card-skeleton" />
          ))}
        </div>
      )}
      {error && <p className="note">Error loading series: {error.message}</p>}
      {data && (
        <div className="series-grid">
          {data.series.map((s) => (
            <SeriesCard key={s.series_id} meta={SERIES_META[s.series_id]} stats={s} />
          ))}
        </div>
      )}

      {/* Analysis tools */}
      <div className="section-header" style={{ marginTop: "2.5rem" }}>
        <h3>Analysis Tools</h3>
        <span className="section-count">7 models</span>
      </div>
      <p className="section-subtitle">
        Each tool runs on the ingested data. Click a card to open the analysis.
      </p>
      <div className="analysis-tools-grid">
        {ANALYSIS_TOOLS.map((t) => (
          <AnalysisCard key={t.to} tool={t} />
        ))}
      </div>

      {/* Pipeline links */}
      <div className="section-header" style={{ marginTop: "2.5rem" }}>
        <h3>Pipeline</h3>
      </div>
      <div className="pipeline-links" style={{ gridTemplateColumns: "1fr" }}>
        <Link to="/lineage" className="pipeline-link-card">
          <div className="pipeline-link-title">Data Lineage</div>
          <div className="pipeline-link-desc">
            DAG showing how raw FRED data flows through dbt staging and mart
            transformations before reaching the ML models.
          </div>
          <span className="pipeline-link-cta">View lineage graph →</span>
        </Link>
      </div>
    </div>
  );
}

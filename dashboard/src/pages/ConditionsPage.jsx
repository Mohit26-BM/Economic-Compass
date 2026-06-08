import { useQuery } from "@tanstack/react-query";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ReferenceArea,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { getConditions } from "../services/api";

const STATUS_COLORS = { green: "#16a34a", yellow: "#d97706", red: "#dc2626" };

function getRecessionBands(history) {
  const bands = [];
  let start = null;
  for (const d of history) {
    if (d.recession === 1 && start === null) start = d.date;
    if (d.recession === 0 && start !== null) { bands.push({ start, end: d.date }); start = null; }
  }
  if (start !== null) bands.push({ start, end: history[history.length - 1]?.date });
  return bands;
}

function StatusDot({ status }) {
  return (
    <span
      style={{
        display: "inline-block",
        width: 10,
        height: 10,
        borderRadius: "50%",
        background: STATUS_COLORS[status] ?? "#6b7280",
        marginRight: 6,
        flexShrink: 0,
      }}
    />
  );
}

function CategoryCard({ cat }) {
  const borderColor = STATUS_COLORS[cat.status] ?? "#e2e8f0";
  return (
    <div
      className="chart-card"
      style={{ borderTop: `3px solid ${borderColor}`, padding: "1rem" }}
    >
      <div style={{ display: "flex", alignItems: "center", marginBottom: "0.25rem" }}>
        <StatusDot status={cat.status} />
        <span style={{ fontSize: "0.7rem", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.06em", color: "#94a3b8" }}>
          {cat.name}
        </span>
      </div>
      <div style={{ fontSize: "1.1rem", fontWeight: 700, color: borderColor, marginBottom: "0.2rem" }}>
        {cat.label}
      </div>
      <div style={{ fontSize: "0.78rem", color: "#6b7280", marginBottom: "0.75rem" }}>
        {cat.description}
      </div>

      {/* Score + percentile */}
      <div style={{ display: "flex", gap: "1rem", marginBottom: "0.75rem" }}>
        <div>
          <div style={{ fontSize: "0.68rem", color: "#94a3b8" }}>Score</div>
          <div style={{ fontSize: "0.95rem", fontWeight: 600, color: borderColor }}>
            {cat.score > 0 ? "+" : ""}{cat.score.toFixed(2)}
          </div>
        </div>
        {cat.percentile != null && (
          <div>
            <div style={{ fontSize: "0.68rem", color: "#94a3b8" }}>Percentile</div>
            <div style={{ fontSize: "0.95rem", fontWeight: 600 }}>{cat.percentile}th</div>
          </div>
        )}
      </div>

      {/* Indicator chips */}
      <div style={{ display: "flex", flexDirection: "column", gap: "0.3rem" }}>
        {cat.indicators.map((ind) => (
          <div
            key={ind.series}
            style={{
              display: "flex",
              justifyContent: "space-between",
              fontSize: "0.75rem",
              background: "#f8fafc",
              borderRadius: 4,
              padding: "0.2rem 0.4rem",
            }}
          >
            <span style={{ color: "#475569" }}>{ind.label}</span>
            <span style={{ fontWeight: 600, color: ind.z_score == null ? "#94a3b8" : ind.z_score > 0 ? "#16a34a" : "#dc2626" }}>
              {ind.raw_value != null
                ? `${ind.raw_value > 0 && ind.unit === "%" ? "+" : ""}${ind.raw_value.toFixed(1)}${ind.unit}`
                : "—"}
              {ind.z_score != null && (
                <span style={{ color: "#94a3b8", fontWeight: 400, marginLeft: 4 }}>
                  (z={ind.z_score > 0 ? "+" : ""}{ind.z_score.toFixed(2)})
                </span>
              )}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

const CAT_COLORS = {
  growth: "#16a34a",
  labor_market: "#2563eb",
  inflation: "#dc2626",
  financial_conditions: "#d97706",
  housing: "#0891b2",
};

const CAT_KEYS = ["growth", "labor_market", "inflation", "financial_conditions", "housing"];
const CAT_DISPLAY = {
  growth: "Growth",
  labor_market: "Labor Market",
  inflation: "Inflation",
  financial_conditions: "Financial",
  housing: "Housing",
};

export default function ConditionsPage() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["conditions"],
    queryFn: getConditions,
    staleTime: 5 * 60_000,
  });

  if (isLoading) return <p>Computing conditions index…</p>;
  if (error) return (
    <div>
      <h2>Economic Conditions Index</h2>
      <p className="note">Error: {error.message}</p>
    </div>
  );

  const { composite, categories, history, validation } = data;
  const recBands = getRecessionBands(history);

  return (
    <div>
      <h2>Economic Conditions Index</h2>
      <p className="page-subtitle">
        Five category sub-indices — Growth, Labor Market, Inflation, Financial Conditions,
        and Housing — each built from 10-year rolling z-scores of their constituent FRED
        series. A score of 0 means average historical conditions; positive means above
        average; negative means below.
      </p>

      {/* Headline */}
      <div
        style={{
          background: composite.color + "12",
          border: `1.5px solid ${composite.color}`,
          borderRadius: 10,
          padding: "1.25rem 1.5rem",
          marginBottom: "1.75rem",
          display: "flex",
          alignItems: "center",
          gap: "2rem",
          flexWrap: "wrap",
        }}
      >
        <div>
          <div style={{ fontSize: "0.7rem", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.07em", color: "#94a3b8", marginBottom: 2 }}>
            Current Economic Conditions
          </div>
          <div style={{ fontSize: "1.6rem", fontWeight: 800, color: composite.color }}>
            {composite.label}
          </div>
        </div>
        <div style={{ display: "flex", gap: "1.5rem", flexWrap: "wrap" }}>
          <div className="metric-chip">
            <span className="metric-label">Composite Score</span>
            <span className="metric-value" style={{ color: composite.color }}>
              {composite.score > 0 ? "+" : ""}{composite.score.toFixed(2)}
            </span>
          </div>
          <div className="metric-chip">
            <span className="metric-label">Historical Percentile</span>
            <span className="metric-value">{composite.percentile}th</span>
          </div>
          <div className="metric-chip">
            <span className="metric-label">Since</span>
            <span className="metric-value" style={{ fontSize: "0.82rem", color: "#6b7280" }}>1990</span>
          </div>
        </div>
        <div style={{ fontSize: "0.78rem", color: "#6b7280", maxWidth: 320 }}>
          Better than <strong>{composite.percentile}%</strong> of months since 1990.
          Composite separates expansion avg ({validation.expansion_avg > 0 ? "+" : ""}{validation.expansion_avg.toFixed(2)}) from
          recession avg ({validation.recession_avg.toFixed(2)}) by{" "}
          <strong>{validation.separation.toFixed(2)} units</strong>.
        </div>
      </div>

      {/* Category grid */}
      <div style={{ fontSize: "0.7rem", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.06em", color: "#94a3b8", marginBottom: "0.6rem" }}>
        Category Breakdown
      </div>
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))",
          gap: "1rem",
          marginBottom: "2rem",
        }}
      >
        {categories.map((cat) => (
          <CategoryCard key={cat.name} cat={cat} />
        ))}
      </div>

      {/* Composite time series */}
      <div className="chart-card" style={{ marginBottom: "1.5rem" }}>
        <div style={{ padding: "1rem 1rem 0.25rem" }}>
          <h3>Composite Score — History</h3>
          <p style={{ fontSize: "0.82rem", color: "#6b7280" }}>
            Monthly composite of all five category scores. Gray shading = NBER recessions.
            Dashed line at 0 = historical average. Each category line shown below.
          </p>
        </div>
        <ResponsiveContainer width="100%" height={300}>
          <LineChart data={history} margin={{ top: 10, right: 30, left: 0, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
            <XAxis dataKey="date" tick={{ fontSize: 10 }} interval={Math.floor(history.length / 14)} />
            <YAxis tick={{ fontSize: 11 }} tickFormatter={(v) => (v > 0 ? `+${v.toFixed(1)}` : v.toFixed(1))} width={42} />
            <Tooltip
              formatter={(v, name) => [
                v != null ? (v > 0 ? `+${v.toFixed(3)}` : v.toFixed(3)) : "—",
                name,
              ]}
            />
            {recBands.map((b, i) => (
              <ReferenceArea key={i} x1={b.start} x2={b.end} fill="#94a3b8" fillOpacity={0.2} />
            ))}
            <ReferenceLine y={0} stroke="#64748b" strokeDasharray="4 3" strokeWidth={1} />
            <Line type="monotone" dataKey="composite" stroke="#1e293b" strokeWidth={2.5} dot={false} name="Composite" />
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* Category lines chart */}
      <div className="chart-card" style={{ marginBottom: "1.5rem" }}>
        <div style={{ padding: "1rem 1rem 0.25rem" }}>
          <h3>Category Scores — History</h3>
          <p style={{ fontSize: "0.82rem", color: "#6b7280" }}>
            Each line = one category sub-index. Divergence between categories often
            precedes recessions (e.g., Financial Conditions drops before Labor Market).
          </p>
        </div>
        <ResponsiveContainer width="100%" height={320}>
          <LineChart data={history} margin={{ top: 10, right: 30, left: 0, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
            <XAxis dataKey="date" tick={{ fontSize: 10 }} interval={Math.floor(history.length / 14)} />
            <YAxis tick={{ fontSize: 11 }} tickFormatter={(v) => (v > 0 ? `+${v.toFixed(1)}` : v.toFixed(1))} width={42} />
            <Tooltip
              formatter={(v, name) => [
                v != null ? (v > 0 ? `+${v.toFixed(2)}` : v.toFixed(2)) : "—",
                name,
              ]}
            />
            <Legend />
            {recBands.map((b, i) => (
              <ReferenceArea key={i} x1={b.start} x2={b.end} fill="#94a3b8" fillOpacity={0.15} />
            ))}
            <ReferenceLine y={0} stroke="#64748b" strokeDasharray="4 3" strokeWidth={1} />
            {CAT_KEYS.map((key) => (
              <Line
                key={key}
                type="monotone"
                dataKey={key}
                stroke={CAT_COLORS[key]}
                strokeWidth={1.5}
                dot={false}
                name={CAT_DISPLAY[key]}
                connectNulls
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* Validation table */}
      <div className="chart-card" style={{ marginBottom: "1rem" }}>
        <div style={{ padding: "1rem 1rem 0.5rem" }}>
          <h3>Index Validation</h3>
          <p style={{ fontSize: "0.82rem", color: "#6b7280" }}>
            Average composite score by economic period (NBER-dated). A well-constructed
            index should show clearly negative scores in recessions.
          </p>
        </div>
        <div style={{ padding: "0 1rem 1rem", overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.83rem" }}>
            <thead>
              <tr style={{ borderBottom: "1px solid #e2e8f0" }}>
                <th style={{ textAlign: "left", padding: "0.4rem 0.6rem", color: "#64748b" }}>Period</th>
                <th style={{ textAlign: "right", padding: "0.4rem 0.6rem", color: "#64748b" }}>Avg Composite Score</th>
                <th style={{ textAlign: "right", padding: "0.4rem 0.6rem", color: "#64748b" }}>Interpretation</th>
              </tr>
            </thead>
            <tbody>
              <tr style={{ borderBottom: "1px solid #f1f5f9" }}>
                <td style={{ padding: "0.4rem 0.6rem", fontWeight: 500 }}>Expansion (USREC = 0)</td>
                <td style={{ padding: "0.4rem 0.6rem", textAlign: "right", color: "#16a34a", fontWeight: 600 }}>
                  {validation.expansion_avg > 0 ? "+" : ""}{validation.expansion_avg.toFixed(3)}
                </td>
                <td style={{ padding: "0.4rem 0.6rem", textAlign: "right", color: "#6b7280" }}>Above-average conditions</td>
              </tr>
              <tr>
                <td style={{ padding: "0.4rem 0.6rem", fontWeight: 500 }}>Recession (USREC = 1)</td>
                <td style={{ padding: "0.4rem 0.6rem", textAlign: "right", color: "#dc2626", fontWeight: 600 }}>
                  {validation.recession_avg.toFixed(3)}
                </td>
                <td style={{ padding: "0.4rem 0.6rem", textAlign: "right", color: "#6b7280" }}>
                  {validation.separation.toFixed(2)}-unit separation from expansion
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <div className="note">
        <strong>Methodology:</strong> Each indicator is converted to a stationary form
        (YoY % change for trending series; level for rates and spreads), then z-scored
        against a 10-year rolling window so the score reflects conditions <em>relative
        to the recent regime</em>. Inverted indicators (unemployment, CPI, Fed Funds)
        are sign-flipped so that positive always means "better conditions." Category
        scores are weighted averages of their constituents; the composite is the simple
        mean of all five category scores.
      </div>
    </div>
  );
}

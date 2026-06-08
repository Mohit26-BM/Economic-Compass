import { useQuery } from "@tanstack/react-query";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ReferenceLine,
  ReferenceArea,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  Bar,
  BarChart,
  Cell,
} from "recharts";
import { getSahm } from "../services/api";

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

export default function SahmPage() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["sahm"],
    queryFn: getSahm,
    staleTime: 5 * 60_000,
  });

  if (isLoading) return <p>Computing Sahm Rule indicator...</p>;
  if (error) return (
    <div>
      <h2>Sahm Rule &amp; Labour Market</h2>
      <p className="note">
        {error.response?.data?.detail?.includes("UNRATE")
          ? "UNRATE series missing. Re-run ingestion: python -m pipeline.flows.ingest_flow"
          : `Error: ${error.message}`}
      </p>
    </div>
  );

  const {
    current, signal, signal_label, history, threshold,
    n_correct_signals, n_false_positives, n_recession_episodes,
    has_payems,
  } = data;
  const signalColor =
    signal === "recession" ? "#dc2626" : signal === "warning" ? "#d97706" : "#16a34a";

  const recessionBands = getRecessionBands(history);
  const displayHistory = history.filter((d) => d.date >= "1970-01-01");

  return (
    <div>
      <h2>Sahm Rule &amp; Labour Market</h2>
      <p className="page-subtitle">
        The <strong>Sahm Rule</strong> (Claudia Sahm, 2019) fires when the 3-month average
        unemployment rate rises 0.5pp or more above its 12-month low. It has correctly
        identified the start of every U.S. recession since 1970 with no false positives
        in real time. Nonfarm payrolls provide a complementary leading read on labour
        market momentum.
      </p>

      {/* Signal banner */}
      <div
        className="signal-banner"
        style={{ background: signalColor + "18", borderColor: signalColor, marginBottom: "1.5rem" }}
      >
        <span style={{ color: signalColor, fontWeight: 600 }}>{signal_label}</span>
      </div>

      {/* Real-time metrics */}
      <div style={{ marginBottom: "0.5rem", fontSize: "0.75rem", fontWeight: 600, color: "#94a3b8", textTransform: "uppercase", letterSpacing: "0.05em" }}>
        Real-time indicators
      </div>
      <div className="metric-row" style={{ marginBottom: "1rem" }}>
        <div className="metric-chip">
          <span className="metric-label">Sahm Indicator</span>
          <span className="metric-value" style={{ color: signalColor }}>
            {current.sahm.toFixed(2)}pp
          </span>
        </div>
        <div className="metric-chip">
          <span className="metric-label">Threshold</span>
          <span className="metric-value">{threshold.toFixed(1)}pp</span>
        </div>
        <div className="metric-chip">
          <span className="metric-label">Unemployment Rate</span>
          <span className="metric-value">{current.unrate?.toFixed(1)}%</span>
        </div>
        {current.payems_mom != null && (
          <div className="metric-chip">
            <span className="metric-label">Payrolls last month</span>
            <span className="metric-value" style={{ color: current.payems_mom > 0 ? "#16a34a" : "#dc2626" }}>
              {current.payems_mom > 0 ? "+" : ""}{Math.round(current.payems_mom)}k
            </span>
          </div>
        )}
        {current.payems_3m != null && (
          <div className="metric-chip">
            <span className="metric-label">Payrolls 3m avg</span>
            <span className="metric-value" style={{ color: current.payems_3m > 0 ? "#16a34a" : "#dc2626" }}>
              {current.payems_3m > 0 ? "+" : ""}{Math.round(current.payems_3m)}k/mo
            </span>
          </div>
        )}
        {current.payems_yoy != null && (
          <div className="metric-chip">
            <span className="metric-label">Payrolls YoY</span>
            <span className="metric-value" style={{ color: current.payems_yoy > 0 ? "#16a34a" : "#dc2626" }}>
              {current.payems_yoy > 0 ? "+" : ""}{current.payems_yoy.toFixed(1)}%
            </span>
          </div>
        )}
      </div>

      {/* Historical accuracy */}
      <div style={{ marginBottom: "0.5rem", fontSize: "0.75rem", fontWeight: 600, color: "#94a3b8", textTransform: "uppercase", letterSpacing: "0.05em" }}>
        Historical accuracy (since 1970)
      </div>
      <div className="metric-row" style={{ marginBottom: "1.5rem" }}>
        <div className="metric-chip">
          <span className="metric-label">Recessions detected</span>
          <span className="metric-value" style={{ color: "#16a34a" }}>
            {n_correct_signals} / {n_recession_episodes}
          </span>
        </div>
        <div className="metric-chip">
          <span className="metric-label">False positives</span>
          <span className="metric-value" style={{ color: n_false_positives === 0 ? "#16a34a" : "#dc2626" }}>
            {n_false_positives}
          </span>
        </div>
        <div className="metric-chip">
          <span className="metric-label">What counts?</span>
          <span className="metric-value" style={{ fontSize: "0.72rem", color: "#6b7280", fontWeight: 400 }}>
            Rule fired ≤ 3mo before recession start
          </span>
        </div>
      </div>

      {/* Sahm indicator chart */}
      <div className="chart-card">
        <div style={{ padding: "1rem 1rem 0.25rem" }}>
          <h3>Sahm Rule Indicator</h3>
          <p style={{ fontSize: "0.82rem", color: "#6b7280" }}>
            3-month avg UNRATE minus 12-month minimum UNRATE.
            Red dashed line = 0.5pp firing threshold. Gray shading = NBER recession periods.
          </p>
        </div>
        <ResponsiveContainer width="100%" height={300}>
          <LineChart data={displayHistory} margin={{ top: 10, right: 30, left: 0, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
            <XAxis dataKey="date" tick={{ fontSize: 10 }} interval={Math.floor(displayHistory.length / 14)} />
            <YAxis tickFormatter={(v) => `${v.toFixed(1)}pp`} tick={{ fontSize: 11 }} width={50} domain={[0, "auto"]} />
            <Tooltip formatter={(v) => [`${v.toFixed(3)}pp`, "Sahm Indicator"]} />
            {recessionBands.map((b, i) => (
              <ReferenceArea key={i} x1={b.start} x2={b.end} fill="#94a3b8" fillOpacity={0.2} />
            ))}
            <ReferenceLine y={threshold} stroke="#dc2626" strokeDasharray="5 3" strokeWidth={1.5} label={{ value: `Threshold ${threshold}pp`, position: "insideTopLeft", fontSize: 10, fill: "#dc2626" }} />
            <ReferenceLine y={0.3} stroke="#d97706" strokeDasharray="3 3" strokeOpacity={0.5} />
            <Line type="monotone" dataKey="sahm" stroke="#6366f1" dot={false} strokeWidth={2} name="Sahm Indicator" />
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* Payrolls chart */}
      {has_payems && (
        <div className="chart-card" style={{ marginTop: "1.5rem" }}>
          <div style={{ padding: "1rem 1rem 0.25rem" }}>
            <h3>Nonfarm Payrolls — Monthly Change</h3>
            <p style={{ fontSize: "0.82rem", color: "#6b7280" }}>
              Bars = monthly jobs added or lost (thousands). Purple line = 3-month rolling average.
              Gray shading = NBER recessions.
            </p>
          </div>
          <ResponsiveContainer width="100%" height={280}>
            <LineChart
              data={displayHistory.filter((d) => d.payems_mom != null)}
              margin={{ top: 10, right: 30, left: 0, bottom: 5 }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
              <XAxis dataKey="date" tick={{ fontSize: 10 }} interval={Math.floor(displayHistory.length / 14)} />
              <YAxis tickFormatter={(v) => `${v > 0 ? "+" : ""}${Math.round(v)}k`} tick={{ fontSize: 11 }} width={58} />
              <Tooltip formatter={(v, name) => [`${v > 0 ? "+" : ""}${Math.round(v)}k`, name]} />
              <Legend />
              {recessionBands.map((b, i) => (
                <ReferenceArea key={i} x1={b.start} x2={b.end} fill="#94a3b8" fillOpacity={0.2} />
              ))}
              <ReferenceLine y={0} stroke="#64748b" strokeWidth={1} />
              <Line type="monotone" dataKey="payems_mom" stroke="#cbd5e1" dot={false} strokeWidth={1} name="MoM change" />
              <Line type="monotone" dataKey="payems_3m" stroke="#6366f1" dot={false} strokeWidth={2} name="3-month avg" />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      <div className="note" style={{ marginTop: "1rem" }}>
        <strong>How to read this page.</strong> The Sahm indicator (top chart) measures how
        much the 3-month average unemployment rate has risen above its 12-month low. When
        it crosses 0.5pp (red dashed line), the rule fires — Claudia Sahm's original paper
        found this threshold caught every NBER recession since 1970 with no false positives
        in real time. <em>A "correct signal"</em> here means the rule fired within 3 months of
        an NBER recession start. <em>A "false positive"</em> means it fired when no recession
        began within the following 9 months.{" "}
        <strong>Payrolls caveat:</strong> the pandemic spike (April 2020 reached 11pp — seven
        times the threshold) was structurally different from prior recessions. Post-2020
        readings should be interpreted alongside the payrolls chart for context.
      </div>
    </div>
  );
}

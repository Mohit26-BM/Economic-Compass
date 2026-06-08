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
import { getTaylorRule } from "../services/api";

function getBehindCurvePeriods(history) {
  const periods = [];
  let start = null;
  for (const d of history) {
    if (d.gap < -0.75 && start === null) start = d.date;
    if (d.gap >= -0.75 && start !== null) {
      periods.push({ start, end: d.date });
      start = null;
    }
  }
  if (start !== null) periods.push({ start, end: history[history.length - 1]?.date });
  return periods;
}

// Small info icon with native tooltip — no library dependency needed
function InfoTip({ text }) {
  return (
    <span
      title={text}
      style={{
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        width: 15,
        height: 15,
        borderRadius: "50%",
        background: "#cbd5e1",
        color: "#475569",
        fontSize: "0.6rem",
        fontWeight: 700,
        cursor: "help",
        marginLeft: "0.3rem",
        verticalAlign: "middle",
        flexShrink: 0,
      }}
    >
      i
    </span>
  );
}

export default function TaylorPage() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["taylor"],
    queryFn: getTaylorRule,
    staleTime: 10 * 60_000,
  });

  if (isLoading) return <p>Computing Taylor Rule...</p>;
  if (error) return <p>Error: {error.message}</p>;

  const { current, signal, signal_label, history } = data;
  const signalColor =
    signal === "behind_curve" ? "#d97706" : signal === "ahead_curve" ? "#dc2626" : "#16a34a";

  const behindPeriods = getBehindCurvePeriods(history);
  const displayHistory = history.filter((d) => d.date >= "1990-01-01");
  const hasForward = displayHistory.some((d) => d.taylor_forward != null);

  return (
    <div>
      <h2>Taylor Rule vs Actual Fed Funds Rate</h2>
      <p className="page-subtitle">
        The Taylor Rule estimates where the Fed <em>should</em> set rates given inflation and
        the output gap. Two variants are shown: a <strong>backward-looking</strong> version
        using current inflation and a <strong>forward-looking</strong> version using the
        5-year rolling average of CPI as a proxy for medium-term inflation expectations.
        The gap between variants illustrates why economists can disagree while using the
        same formula.
      </p>

      {/* Signal banner */}
      <div
        className="signal-banner"
        style={{ background: signalColor + "18", borderColor: signalColor, marginBottom: "1.5rem" }}
      >
        <span style={{ color: signalColor, fontWeight: 600 }}>{signal_label}</span>
      </div>

      {/* Current numbers */}
      <div className="metric-row" style={{ marginBottom: "1.5rem" }}>
        <div className="metric-chip">
          <span className="metric-label">Actual FEDFUNDS</span>
          <span className="metric-value" style={{ color: "#2563eb" }}>
            {current.actual.toFixed(2)}%
          </span>
        </div>
        <div className="metric-chip">
          <span className="metric-label">Backward-looking Taylor</span>
          <span className="metric-value" style={{ color: "#f59e0b" }}>
            {current.taylor.toFixed(2)}%
          </span>
        </div>
        {current.taylor_forward != null && (
          <div className="metric-chip">
            <span className="metric-label">Forward-looking Taylor</span>
            <span className="metric-value" style={{ color: "#10b981" }}>
              {current.taylor_forward.toFixed(2)}%
            </span>
          </div>
        )}
        <div className="metric-chip">
          <span className="metric-label">Policy Gap (backward)</span>
          <span className="metric-value" style={{ color: signalColor }}>
            {current.gap > 0 ? "+" : ""}{current.gap.toFixed(2)}pp
          </span>
        </div>
        <div className="metric-chip">
          <span className="metric-label">CPI YoY (raw)</span>
          <span className="metric-value">{current.cpi_yoy.toFixed(2)}%</span>
        </div>
        <div className="metric-chip">
          <span className="metric-label" style={{ display: "flex", alignItems: "center" }}>
            PCE proxy (−0.5pp)
            <InfoTip text="Core PCE inflation (the Fed's actual target measure) has historically run 0.3–0.7pp below CPI. This dashboard applies a fixed −0.5pp adjustment as a conservative approximation. The true wedge varies over time." />
          </span>
          <span className="metric-value">{current.pi_adjusted?.toFixed(2)}%</span>
        </div>
        <div className="metric-chip">
          <span className="metric-label">Output Gap (HP filter)</span>
          <span className="metric-value">{current.output_gap.toFixed(2)}%</span>
        </div>
      </div>

      {/* Main chart */}
      <div className="chart-card">
        <div style={{ padding: "1rem 1rem 0.25rem" }}>
          <h3>Actual FEDFUNDS vs Taylor Rule Variants (1990–present)</h3>
          <p style={{ fontSize: "0.82rem", color: "#6b7280" }}>
            <strong style={{ color: "#f59e0b" }}>Orange dashed</strong> = backward-looking (current CPI).{" "}
            {hasForward && <><strong style={{ color: "#10b981" }}>Green dashed</strong> = forward-looking (5yr CPI average, ≈ medium-term expectations).{" "}</>}
            Orange shading = periods Fed was &gt;0.75pp below the backward-looking Taylor rate.
          </p>
        </div>
        <ResponsiveContainer width="100%" height={380}>
          <LineChart data={displayHistory} margin={{ top: 10, right: 30, left: 0, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
            <XAxis
              dataKey="date"
              tick={{ fontSize: 10 }}
              interval={Math.floor(displayHistory.length / 14)}
            />
            <YAxis
              tickFormatter={(v) => `${v.toFixed(0)}%`}
              tick={{ fontSize: 11 }}
              width={44}
              domain={["auto", "auto"]}
            />
            <Tooltip formatter={(v, name) => [v != null ? `${v.toFixed(2)}%` : "—", name]} />
            <Legend />
            <ReferenceLine y={0} stroke="#e2e8f0" />
            {behindPeriods.map((p, i) => (
              <ReferenceArea key={i} x1={p.start} x2={p.end} fill="#f59e0b" fillOpacity={0.12} />
            ))}
            <Line
              type="monotone"
              dataKey="actual"
              stroke="#2563eb"
              dot={false}
              strokeWidth={2}
              name="Actual FEDFUNDS"
            />
            <Line
              type="monotone"
              dataKey="taylor"
              stroke="#f59e0b"
              dot={false}
              strokeWidth={1.5}
              strokeDasharray="5 3"
              name="Taylor (backward-looking)"
            />
            {hasForward && (
              <Line
                type="monotone"
                dataKey="taylor_forward"
                stroke="#10b981"
                dot={false}
                strokeWidth={1.5}
                strokeDasharray="3 3"
                name="Taylor (forward-looking)"
                connectNulls={false}
              />
            )}
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* Variant comparison callout */}
      <div className="note" style={{ marginTop: "1rem", display: "flex", gap: "1.5rem", flexWrap: "wrap" }}>
        <div style={{ flex: 1, minWidth: 220 }}>
          <strong>Backward-looking specification</strong><br />
          Uses current CPI YoY − 0.5pp as the inflation input. Responds immediately to
          inflation spikes, which is why it showed 7–9% implied rates in 2022. Appropriate
          if you believe the Fed should react to current conditions.
        </div>
        <div style={{ flex: 1, minWidth: 220 }}>
          <strong>Forward-looking specification</strong><br />
          Uses a 5-year rolling CPI average − 0.5pp. Approximates medium-term inflation
          expectations — the Fed sets rates for where inflation will be in 12–18 months,
          not where it is today. Typically produces a rate 1–2pp lower during inflation spikes.
        </div>
      </div>

      {/* Policy gap chart */}
      <div className="chart-card" style={{ marginTop: "1.5rem" }}>
        <div style={{ padding: "1rem 1rem 0.25rem" }}>
          <h3>Policy Gap (Actual − Backward-looking Taylor Rate)</h3>
          <p style={{ fontSize: "0.82rem", color: "#6b7280" }}>
            Positive = Fed is more restrictive than this specification suggests.
            Negative = more accommodative.
          </p>
        </div>
        <ResponsiveContainer width="100%" height={220}>
          <LineChart data={displayHistory} margin={{ top: 5, right: 30, left: 0, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
            <XAxis
              dataKey="date"
              tick={{ fontSize: 10 }}
              interval={Math.floor(displayHistory.length / 14)}
            />
            <YAxis tickFormatter={(v) => `${v.toFixed(0)}pp`} tick={{ fontSize: 11 }} width={48} />
            <Tooltip formatter={(v) => [`${v.toFixed(2)}pp`, "Policy Gap"]} />
            <ReferenceLine y={0} stroke="#64748b" strokeWidth={1.5} />
            <ReferenceLine y={0.75} stroke="#dc2626" strokeDasharray="4 3" strokeOpacity={0.4} />
            <ReferenceLine y={-0.75} stroke="#d97706" strokeDasharray="4 3" strokeOpacity={0.4} />
            <Line type="monotone" dataKey="gap" stroke="#6366f1" dot={false} strokeWidth={1.5} name="Policy Gap" />
          </LineChart>
        </ResponsiveContainer>
      </div>

      <div className="note" style={{ marginTop: "1rem" }}>
        <strong>Formula:</strong> Taylor Rate = 2% (r*) + π + 0.5×(π − 2%) + 0.5×output gap.
        Backward-looking: π = CPI YoY − 0.5pp. Forward-looking: π = 5yr rolling CPI avg − 0.5pp.
        Output gap: Hodrick-Prescott filter (λ=1600) on quarterly nominal GDP.
        The r* = 2% neutral rate is a fixed assumption; some estimates place it at 0.5–1.5% post-GFC,
        which would lower both implied rates by 0.5–1.5pp.
      </div>
    </div>
  );
}

import { useQuery } from "@tanstack/react-query";
import {
  Legend,
  PolarAngleAxis,
  PolarGrid,
  PolarRadiusAxis,
  Radar,
  RadarChart,
  ResponsiveContainer,
  Tooltip,
} from "recharts";
import { getRegime } from "../services/api";

const DEFAULT_COLORS = {
  Expansion: "#16a34a",
  Tightening: "#d97706",
  Recession: "#dc2626",
  Recovery: "#2563eb",
  Crisis:    "#7c3aed",
};

function getColor(regime, colors) {
  return colors?.[regime] ?? DEFAULT_COLORS[regime] ?? "#6b7280";
}

function toSegments(timeline) {
  if (!timeline?.length) return [];
  const segs = [];
  let cur = { regime: timeline[0].regime, start: timeline[0].date, count: 1 };
  for (let i = 1; i < timeline.length; i++) {
    const d = timeline[i];
    if (d.regime === cur.regime) {
      cur.count++;
    } else {
      segs.push(cur);
      cur = { regime: d.regime, start: d.date, count: 1 };
    }
  }
  segs.push(cur);
  return segs;
}

function rateColor(regime, rate) {
  if (regime === "Recession") {
    return rate >= 0.5 ? "#16a34a" : rate >= 0.3 ? "#d97706" : "#dc2626";
  }
  if (regime === "Crisis") {
    return rate >= 0.3 ? "#16a34a" : rate >= 0.15 ? "#d97706" : "#dc2626";
  }
  // Expansion, Tightening, Recovery — lower is better
  return rate <= 0.10 ? "#16a34a" : rate <= 0.25 ? "#d97706" : "#dc2626";
}

function ValidationRow({ regime, stats, color }) {
  const rateDisplay = `${(stats.recession_rate * 100).toFixed(1)}%`;
  const expected =
    regime === "Recession"
      ? "≥50%"
      : regime === "Crisis"
      ? "≥30%"
      : regime === "Expansion"
      ? "≤25%"
      : regime === "Tightening"
      ? "≤25%"
      : "≤30%";

  return (
    <tr>
      <td>
        <span style={{ display: "inline-flex", alignItems: "center", gap: "0.4rem" }}>
          <span style={{ width: 10, height: 10, borderRadius: "50%", background: color, display: "inline-block" }} />
          <strong>{regime}</strong>
        </span>
      </td>
      <td>{stats.total_months}</td>
      <td>{stats.recession_months}</td>
      <td>
        <span style={{ fontWeight: 600, color: rateColor(regime, stats.recession_rate) }}>{rateDisplay}</span>
      </td>
      <td style={{ color: "#94a3b8", fontSize: "0.82rem" }}>{expected}</td>
      <td>
        <span
          className="badge"
          style={{
            background: stats.label_valid ? "#dcfce7" : "#fee2e2",
            color: stats.label_valid ? "#15803d" : "#dc2626",
          }}
        >
          {stats.label_valid ? "Valid" : "Suspect"}
        </span>
      </td>
    </tr>
  );
}

export default function RegimesPage() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["regime"],
    queryFn: getRegime,
    staleTime: 10 * 60_000,
  });

  if (isLoading) return <p>Running K-means regime detection...</p>;
  if (error) return <p>Error: {error.message}</p>;

  const segments = toSegments(data.timeline);
  const total = segments.reduce((s, c) => s + c.count, 0);
  const colors = data.regime_colors ?? DEFAULT_COLORS;
  const currentColor = getColor(data.current_regime, colors);
  const radarSeries = data.profiles?.map((p) => p.name) ?? [];

  const sil = data.silhouette_score;
  const silColor = sil > 0.5 ? "#16a34a" : sil > 0.25 ? "#d97706" : "#dc2626";

  const hasValidation = data.usrec_validation && Object.keys(data.usrec_validation).length > 0;
  const allValid = hasValidation && Object.values(data.usrec_validation).every((v) => v.label_valid);

  return (
    <div>
      <h2>Economic Regime Detection</h2>
      <p className="page-subtitle">
        K-means (k=4) on <strong>change and growth features</strong> — CPI YoY, GDP growth, unemployment
        change, FEDFUNDS level + 12m change, T10Y2Y. Using rates of change prevents era-level clustering
        (where 1970s and 2022 land in the same bucket because both have high nominal CPI).
      </p>

      {/* Current regime */}
      <div
        className="signal-banner"
        style={{ background: currentColor + "18", borderColor: currentColor, marginBottom: "1.25rem" }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", flexWrap: "wrap" }}>
          <div style={{ width: 14, height: 14, borderRadius: "50%", background: currentColor, flexShrink: 0 }} />
          <div>
            <span style={{ color: currentColor, fontWeight: 700, fontSize: "1.05rem" }}>
              Current Regime: {data.current_regime}
            </span>
            <span style={{ color: "#6b7280", marginLeft: "1rem", fontSize: "0.85rem" }}>
              as of {data.current_date}
            </span>
            {data.historical_analogues?.length > 0 && (
              <span style={{ color: "#6b7280", marginLeft: "1rem", fontSize: "0.85rem" }}>
                · Analogues: {data.historical_analogues.join(", ")}
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Model quality metrics */}
      <div className="metric-row" style={{ marginBottom: "1.25rem" }}>
        <div className="metric-chip">
          <span className="metric-label">Silhouette Score</span>
          <span className="metric-value" style={{ color: silColor }}>{sil?.toFixed(3)}</span>
        </div>
        <div className="metric-chip">
          <span className="metric-label">Interpretation</span>
          <span style={{ fontSize: "0.82rem", color: "#475569", display: "block", marginTop: "0.1rem" }}>
            {data.silhouette_interpretation}
          </span>
        </div>
        <div className="metric-chip">
          <span className="metric-label">Feature set</span>
          <span style={{ fontSize: "0.82rem", color: "#475569", display: "block", marginTop: "0.1rem" }}>
            Change/growth rates
          </span>
        </div>
        {hasValidation && (
          <div className="metric-chip">
            <span className="metric-label">Label validity</span>
            <span className="metric-value" style={{ color: allValid ? "#16a34a" : "#dc2626", fontSize: "0.95rem" }}>
              {allValid ? "All labels valid" : "Some labels suspect"}
            </span>
          </div>
        )}
      </div>

      <div className="analysis-grid">
        {/* Radar chart */}
        <div className="chart-card" style={{ padding: "1.25rem" }}>
          <h3 style={{ marginBottom: "0.25rem" }}>Regime Profiles (Z-scores)</h3>
          <p style={{ fontSize: "0.82rem", color: "#6b7280", marginBottom: "0.75rem" }}>
            Each axis = average normalized value for that feature within the regime.
            ±1σ from mean is a meaningful signal.
          </p>
          <ResponsiveContainer width="100%" height={300}>
            <RadarChart data={data.radar_data} margin={{ top: 10, right: 30, bottom: 10, left: 30 }}>
              <PolarGrid stroke="#e2e8f0" />
              <PolarAngleAxis dataKey="series" tick={{ fontSize: 10 }} />
              <PolarRadiusAxis angle={30} domain={[-2.5, 2.5]} tick={{ fontSize: 9 }} />
              {radarSeries.map((name) => (
                <Radar
                  key={name}
                  name={name}
                  dataKey={name}
                  stroke={getColor(name, colors)}
                  fill={getColor(name, colors)}
                  fillOpacity={0.12}
                  strokeWidth={1.5}
                />
              ))}
              <Legend />
              <Tooltip formatter={(v) => (typeof v === "number" ? v.toFixed(2) : v)} />
            </RadarChart>
          </ResponsiveContainer>
        </div>

        {/* Regime stats + centroid table */}
        <div className="chart-card" style={{ padding: "1.25rem" }}>
          <h3 style={{ marginBottom: "0.75rem" }}>Time Spent per Regime</h3>
          {data.profiles?.map((p) => {
            const color = getColor(p.name, colors);
            const pct = Math.round((p.count / total) * 100);
            return (
              <div key={p.id} style={{ marginBottom: "1.1rem" }}>
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "0.3rem" }}>
                  <span style={{ fontWeight: 600, color }}>{p.name}</span>
                  <span style={{ fontSize: "0.82rem", color: "#6b7280" }}>
                    {p.count} months ({pct}%)
                  </span>
                </div>
                <div style={{ height: 8, borderRadius: 4, background: "#e2e8f0", overflow: "hidden" }}>
                  <div style={{ height: "100%", width: `${pct}%`, background: color, borderRadius: 4 }} />
                </div>
                {/* Centroid in original units — much more readable than z-scores */}
                {p.centroid && (
                  <div style={{ display: "flex", flexWrap: "wrap", gap: "0.35rem", marginTop: "0.45rem" }}>
                    {Object.entries(p.centroid)
                      .sort((a, b) => {
                        // Sort by absolute z-score so most distinctive features are first
                        const za = Math.abs(p.features[a[0]] ?? 0);
                        const zb = Math.abs(p.features[b[0]] ?? 0);
                        return zb - za;
                      })
                      .slice(0, 5)
                      .map(([key, f]) => {
                        const val = f.value;
                        const positive = val >= 0;
                        const isNeutral = Math.abs(p.features[key] ?? 0) < 0.3;
                        return (
                          <span
                            key={key}
                            title={f.label}
                            style={{
                              fontSize: "0.72rem",
                              padding: "0.1rem 0.4rem",
                              borderRadius: "4px",
                              background: isNeutral ? "#f1f5f9" : positive ? "#dcfce7" : "#fee2e2",
                              color: isNeutral ? "#94a3b8" : positive ? "#15803d" : "#dc2626",
                              fontWeight: 500,
                            }}
                          >
                            {f.label}: {val >= 0 ? "+" : ""}{val}{f.unit}
                          </span>
                        );
                      })}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* USREC validation cross-tab */}
      {hasValidation && (
        <div className="chart-card" style={{ marginTop: "1.5rem", padding: "1.25rem" }}>
          <h3 style={{ marginBottom: "0.25rem" }}>Regime Label Validation (vs NBER Recession Dates)</h3>
          <p style={{ fontSize: "0.82rem", color: "#6b7280", marginBottom: "0.75rem" }}>
            Cross-tabulation of regime clusters against the USREC binary indicator.
            A "Recession" label is only meaningful if ≥50% of its months were actual recessions.
          </p>
          <table className="table">
            <thead>
              <tr>
                <th>Regime</th>
                <th>Total Months</th>
                <th>Recession Months</th>
                <th>Recession Rate</th>
                <th>Expected</th>
                <th>Label</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(data.usrec_validation).map(([regime, stats]) => (
                <ValidationRow
                  key={regime}
                  regime={regime}
                  stats={stats}
                  color={getColor(regime, colors)}
                />
              ))}
            </tbody>
          </table>
          <p style={{ fontSize: "0.78rem", color: "#94a3b8", marginTop: "0.5rem" }}>
            "Suspect" means the cluster's actual recession rate is inconsistent with its label —
            the K-means geometry didn't align with economic reality for that regime.
            Consider increasing k or adjusting features if multiple regimes are suspect.
          </p>
        </div>
      )}

      {/* Timeline */}
      <div className="chart-card" style={{ marginTop: "1.5rem", padding: "1.25rem" }}>
        <h3 style={{ marginBottom: "0.75rem" }}>Economic Regime Timeline</h3>
        <div style={{ display: "flex", height: 40, borderRadius: 6, overflow: "hidden" }}>
          {segments.map((seg, i) => (
            <div
              key={i}
              style={{
                width: `${(seg.count / total) * 100}%`,
                background: getColor(seg.regime, colors),
                opacity: 0.85,
                minWidth: seg.count > 2 ? undefined : 0,
              }}
              title={`${seg.regime} — ${seg.start} (${seg.count} months)`}
            />
          ))}
        </div>
        <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.75rem", color: "#94a3b8", marginTop: "0.3rem" }}>
          <span>{data.timeline?.[0]?.date?.slice(0, 7)}</span>
          <span>{data.current_date?.slice(0, 7)}</span>
        </div>
        <div style={{ display: "flex", gap: "1.25rem", marginTop: "0.75rem", flexWrap: "wrap" }}>
          {Object.entries(colors).map(([name, color]) => (
            <div key={name} style={{ display: "flex", alignItems: "center", gap: "0.4rem" }}>
              <div style={{ width: 12, height: 12, borderRadius: 2, background: color }} />
              <span style={{ fontSize: "0.82rem", color: "#475569" }}>{name}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

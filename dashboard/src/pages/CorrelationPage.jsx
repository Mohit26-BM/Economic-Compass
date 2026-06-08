import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import {
  CartesianGrid,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { getCorrelation } from "../services/api";

const SERIES_ORDER = ["GDP", "CPIAUCSL", "UNRATE", "FEDFUNDS", "T10Y2Y", "HOUST", "RSXFS"];

function corrColor(corr, significant) {
  if (!significant) return "#f8fafc";  // non-significant: near-white, no color
  const abs = Math.abs(corr);
  const intensity = Math.round(abs * 180);
  if (corr > 0) return `rgb(${255 - intensity}, ${255 - intensity}, 255)`;
  return `rgb(255, ${255 - intensity}, ${255 - intensity})`;
}

function textColor(corr, significant) {
  if (!significant) return "#94a3b8";
  return Math.abs(corr) > 0.5 ? "#fff" : "#1e293b";
}

export default function CorrelationPage() {
  const [selectedPair, setSelectedPair] = useState(0);

  const { data, isLoading, error } = useQuery({
    queryKey: ["correlation"],
    queryFn: getCorrelation,
    staleTime: 10 * 60_000,
  });

  if (isLoading) return <p>Computing cross-series correlations and Granger tests...</p>;
  if (error) return <p>Error: {error.message}</p>;

  const series = data.series ?? SERIES_ORDER.filter((s) => data.series?.includes(s));

  // Build 7×7 lookup
  const corrMap = {};
  for (const s of series) {
    corrMap[s] = {};
    series.forEach((t) => {
      corrMap[s][t] = s === t ? { correlation: 1, lag: 0 } : { correlation: 0, lag: 0 };
    });
  }
  for (const c of data.cross_correlations ?? []) {
    const entry = { correlation: c.correlation, lag: c.best_lag, p_value: c.p_value, significant: c.significant };
    corrMap[c.series_a][c.series_b] = entry;
    corrMap[c.series_b][c.series_a] = entry;
  }

  const scatterPair = data.scatter_pairs?.[selectedPair];

  return (
    <div>
      <h2>Cross-Series Correlation Analysis</h2>
      <p className="page-subtitle">
        Trending series (GDP, CPI, RSXFS, HOUST) are converted to <strong>YoY growth rates</strong> before
        correlation to avoid spurious near-1.0 values driven by shared long-run trends.
        FEDFUNDS, UNRATE, T10Y2Y kept as levels (already stationary/spread measures).
        Optimal lag searched 0–12 months. <strong>Faded cells</strong> have p &gt; 0.01
        (conservative threshold given the lag search).
      </p>

      {/* Heatmap */}
      <div className="chart-card" style={{ padding: "1.25rem", overflowX: "auto" }}>
        <h3 style={{ marginBottom: "0.25rem" }}>Correlation Heatmap (at optimal lag, growth-rate series)</h3>
        <div style={{ display: "flex", gap: "0.75rem", alignItems: "flex-start", marginBottom: "0.75rem", flexWrap: "wrap" }}>
          <p style={{ fontSize: "0.78rem", color: "#94a3b8", flex: 1, minWidth: 220 }}>
            Faded cells: p &gt; 0.01 (not significant after conservative lag-search correction).
            p-values shown in small text. Hover a cell for a plain-English description.
          </p>
          <div style={{ background: "#eff6ff", border: "1px solid #bfdbfe", borderRadius: "6px", padding: "0.45rem 0.7rem", fontSize: "0.76rem", color: "#1d4ed8", flexShrink: 0, maxWidth: 320 }}>
            <strong>What does +12mo mean?</strong><br />
            The row series is most correlated with the column series measured <em>12 months earlier</em>.
            A positive lag means the column series leads — it moves first, and the row series follows.
            Lag 0 means they move together simultaneously.
          </div>
        </div>
        <table style={{ borderCollapse: "collapse", fontSize: "0.8rem" }}>
          <thead>
            <tr>
              <th style={{ padding: "0.4rem 0.6rem", textAlign: "left", background: "#f8fafc" }} />
              {series.map((s) => (
                <th
                  key={s}
                  style={{
                    padding: "0.4rem 0.6rem",
                    textAlign: "center",
                    background: "#f8fafc",
                    fontWeight: 600,
                    minWidth: "72px",
                  }}
                >
                  {s}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {series.map((rowS) => (
              <tr key={rowS}>
                <td style={{ padding: "0.4rem 0.6rem", fontWeight: 600, background: "#f8fafc" }}>
                  {rowS}
                </td>
                {series.map((colS) => {
                  const cell = corrMap[rowS]?.[colS] ?? { correlation: 0, lag: 0, p_value: 1, significant: false };
                  const bg = corrColor(cell.correlation, cell.significant);
                  const fg = textColor(cell.correlation, cell.significant);
                  return (
                    <td
                      key={colS}
                      style={{
                        background: bg,
                        color: fg,
                        padding: "0.4rem 0.5rem",
                        textAlign: "center",
                        border: "1px solid #e2e8f0",
                        cursor: "default",
                        opacity: rowS === colS ? 1 : (cell.significant ? 1 : 0.55),
                      }}
                      title={
                        rowS === colS
                          ? `${rowS} vs itself (always 1.0)`
                          : cell.lag === 0
                          ? `${rowS} ↔ ${colS}: r=${cell.correlation.toFixed(3)}, p=${cell.p_value?.toFixed(4)} — strongest correlation is simultaneous (no lag)`
                          : `${rowS} ↔ ${colS}: r=${cell.correlation.toFixed(3)}, p=${cell.p_value?.toFixed(4)} — strongest when ${colS} leads by ${cell.lag} month${cell.lag !== 1 ? "s" : ""} (${colS} moves first, ${rowS} follows)`
                      }
                    >
                      {rowS === colS ? "—" : (
                        <>
                          <div style={{ fontWeight: 600 }}>{cell.correlation.toFixed(2)}</div>
                          <div style={{ fontSize: "0.68rem", opacity: 0.8 }}>
                            {cell.lag > 0 ? `+${cell.lag}mo` : "lag 0"}
                          </div>
                          {cell.p_value != null && (
                            <div style={{ fontSize: "0.62rem", opacity: 0.7 }}>
                              p={cell.p_value < 0.001 ? "<.001" : cell.p_value.toFixed(3)}
                            </div>
                          )}
                        </>
                      )}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="analysis-grid" style={{ marginTop: "1.5rem" }}>
        {/* Granger causality */}
        <div className="chart-card" style={{ padding: "1.25rem" }}>
          <h3 style={{ marginBottom: "0.75rem" }}>Granger Causality Tests</h3>
          <p style={{ fontSize: "0.82rem", color: "#6b7280", marginBottom: "0.75rem" }}>
            Does knowing series A improve forecasts of series B beyond B's own history?
          </p>
          <table className="table">
            <thead>
              <tr>
                <th>Cause</th>
                <th>Effect</th>
                <th>Best Lag</th>
                <th>p-value</th>
                <th>Verdict</th>
              </tr>
            </thead>
            <tbody>
              {(data.granger_results ?? []).map((g, i) => (
                <tr key={i}>
                  <td>
                    <strong>{g.cause}</strong>
                  </td>
                  <td>{g.effect}</td>
                  <td>{g.best_lag}mo</td>
                  <td>
                    <code>{g.p_value.toFixed(4)}</code>
                  </td>
                  <td>
                    <span
                      className="badge"
                      style={{
                        background: g.significant ? "#dcfce7" : "#f1f5f9",
                        color: g.significant ? "#15803d" : "#64748b",
                      }}
                    >
                      {g.significant ? "Significant" : "Not significant"}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <p style={{ fontSize: "0.78rem", color: "#94a3b8", marginTop: "0.5rem" }}>
            Granger causality does not imply true causality — it measures predictive precedence.
          </p>
        </div>

        {/* Scatter plot */}
        <div className="chart-card" style={{ padding: "1.25rem" }}>
          <h3 style={{ marginBottom: "0.5rem" }}>Lagged Scatter Plot</h3>
          <div style={{ display: "flex", gap: "0.5rem", marginBottom: "0.75rem", flexWrap: "wrap" }}>
            {(data.scatter_pairs ?? []).map((p, i) => (
              <button
                key={i}
                className={`btn-outline ${i === selectedPair ? "btn-active" : ""}`}
                onClick={() => setSelectedPair(i)}
              >
                {p.label}
              </button>
            ))}
          </div>
          {scatterPair && (
            <>
              {/* Stats row */}
              <div style={{ display: "flex", gap: "1rem", marginBottom: "0.5rem", flexWrap: "wrap" }}>
                <div className="metric-chip" style={{ padding: "0.3rem 0.7rem" }}>
                  <span className="metric-label">Pearson r</span>
                  <span className="metric-value" style={{ color: Math.abs(scatterPair.pearson_r) > 0.5 ? "#16a34a" : "#d97706" }}>
                    {scatterPair.pearson_r?.toFixed(3)}
                  </span>
                </div>
                <div className="metric-chip" style={{ padding: "0.3rem 0.7rem" }}>
                  <span className="metric-label">R²</span>
                  <span className="metric-value">{scatterPair.r_squared?.toFixed(3)}</span>
                </div>
                <div className="metric-chip" style={{ padding: "0.3rem 0.7rem" }}>
                  <span className="metric-label">p-value</span>
                  <span className="metric-value" style={{ fontSize: "0.85rem" }}>
                    {scatterPair.p_value < 0.001 ? "<0.001" : scatterPair.p_value?.toFixed(4)}
                  </span>
                </div>
                <div className="metric-chip" style={{ padding: "0.3rem 0.7rem" }}>
                  <span className="metric-label">n</span>
                  <span className="metric-value">{scatterPair.n}</span>
                </div>
              </div>
              <p style={{ fontSize: "0.82rem", color: "#6b7280", marginBottom: "0.5rem" }}>
                Each dot = one month. Dots only — no connecting lines. X-axis is {scatterPair.x_label ?? `${scatterPair.cause} (t−${scatterPair.lag}mo)`}.
              </p>
              <ResponsiveContainer width="100%" height={280}>
                <ScatterChart margin={{ top: 10, right: 20, left: 0, bottom: 20 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                  <XAxis
                    dataKey="x"
                    name={scatterPair.x_label ?? scatterPair.cause}
                    tick={{ fontSize: 11 }}
                    label={{
                      value: scatterPair.x_label ?? `${scatterPair.cause} (t−${scatterPair.lag}mo)`,
                      position: "insideBottom",
                      offset: -10,
                      fontSize: 10,
                    }}
                  />
                  <YAxis
                    dataKey="y"
                    name={scatterPair.y_label ?? scatterPair.effect}
                    tick={{ fontSize: 11 }}
                    label={{
                      value: scatterPair.y_label ?? scatterPair.effect,
                      angle: -90,
                      position: "insideLeft",
                      fontSize: 10,
                    }}
                  />
                  <Tooltip
                    cursor={{ strokeDasharray: "3 3" }}
                    formatter={(v, name) => [v.toFixed(2), name]}
                  />
                  <Scatter
                    data={scatterPair.data}
                    fill="#6366f1"
                    fillOpacity={0.45}
                    r={2.5}
                    line={false}
                    shape="circle"
                  />
                </ScatterChart>
              </ResponsiveContainer>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

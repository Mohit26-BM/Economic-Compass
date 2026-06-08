import { useQuery } from "@tanstack/react-query";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ReferenceArea,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { getRecession } from "../services/api";

function GaugeChart({ probability }) {
  const pct = Math.round(probability * 100);
  const color = pct > 60 ? "#dc2626" : pct > 35 ? "#d97706" : "#16a34a";
  const label = pct > 60 ? "HIGH RISK" : pct > 35 ? "MODERATE" : "LOW RISK";

  const gaugeData = [
    { value: pct, fill: color },
    { value: 100 - pct, fill: "#e2e8f0" },
  ];

  return (
    <div style={{ textAlign: "center" }}>
      <PieChart width={240} height={140}>
        <Pie
          data={gaugeData}
          cx={120}
          cy={125}
          startAngle={180}
          endAngle={0}
          innerRadius={72}
          outerRadius={112}
          paddingAngle={0}
          dataKey="value"
          strokeWidth={0}
        >
          {gaugeData.map((entry, i) => (
            <Cell key={i} fill={entry.fill} />
          ))}
        </Pie>
      </PieChart>
      <div style={{ marginTop: "-48px" }}>
        <div style={{ fontSize: "2.8rem", fontWeight: 700, color, lineHeight: 1 }}>
          {pct}%
        </div>
        <div style={{ fontSize: "0.7rem", fontWeight: 700, letterSpacing: "0.1em", color, marginTop: "0.2rem" }}>
          {label}
        </div>
        <div style={{ fontSize: "0.8rem", color: "#6b7280", marginTop: "0.4rem" }}>
          12-month recession probability
        </div>
      </div>
    </div>
  );
}

function getRecessionBands(history) {
  const bands = [];
  let start = null;
  for (const d of history) {
    if (d.recession === 1 && start === null) start = d.date;
    if (d.recession === 0 && start !== null) {
      bands.push({ start, end: d.date });
      start = null;
    }
  }
  if (start !== null) bands.push({ start, end: history[history.length - 1]?.date });
  return bands;
}

function OOSMetrics({ oos }) {
  if (!oos || !oos.auc) return null;

  const aucColor = oos.auc > 0.85 ? "#16a34a" : oos.auc > 0.75 ? "#d97706" : "#dc2626";
  const brierColor = oos.brier < 0.1 ? "#16a34a" : oos.brier < 0.2 ? "#d97706" : "#dc2626";

  return (
    <div className="chart-card" style={{ padding: "1.25rem", marginTop: "1.5rem" }}>
      <h3 style={{ marginBottom: "0.25rem" }}>
        Out-of-Sample Validation (trained pre-2001, tested 2001–present)
      </h3>
      <p style={{ fontSize: "0.82rem", color: "#6b7280", marginBottom: "1rem" }}>
        Tests cover three distinct recessions: 2001, 2008–09, and 2020.
        AUC &gt;0.75 = genuinely useful signal. Brier &lt;0.15 = well-calibrated probabilities.
      </p>
      <div className="metric-row">
        <div className="metric-chip">
          <span className="metric-label">OOS AUC</span>
          <span className="metric-value" style={{ color: aucColor }}>{oos.auc.toFixed(3)}</span>
        </div>
        <div className="metric-chip">
          <span className="metric-label">Brier Score</span>
          <span className="metric-value" style={{ color: brierColor }}>{oos.brier.toFixed(3)}</span>
        </div>
        <div className="metric-chip">
          <span className="metric-label">Precision</span>
          <span className="metric-value">{(oos.precision * 100).toFixed(1)}%</span>
        </div>
        <div className="metric-chip">
          <span className="metric-label">Recall</span>
          <span className="metric-value">{(oos.recall * 100).toFixed(1)}%</span>
        </div>
        <div className="metric-chip">
          <span className="metric-label">F1</span>
          <span className="metric-value">{oos.f1?.toFixed(3)}</span>
        </div>
        <div className="metric-chip">
          <span className="metric-label">Test period</span>
          <span style={{ fontSize: "0.82rem", color: "#475569", display: "block", marginTop: "0.15rem" }}>
            {oos.test_period}
          </span>
        </div>
      </div>
      <div className="note" style={{ marginTop: "0.75rem" }}>
        <strong>Recall vs Precision trade-off:</strong> Class balancing favours recall — it is more
        costly to miss a recession (false negative) than to give a false alarm (false positive).
        A low-precision / high-recall model is the correct design choice here.
      </div>
    </div>
  );
}

function FeatureImportance({ importances }) {
  if (!importances?.length) return null;

  const top = importances.slice(0, 10);
  const chartData = [...top].reverse(); // show highest at top

  return (
    <div className="chart-card" style={{ padding: "1.25rem", marginTop: "1.5rem" }}>
      <h3 style={{ marginBottom: "0.25rem" }}>Feature Importances (Standardized Coefficients)</h3>
      <p style={{ fontSize: "0.82rem", color: "#6b7280", marginBottom: "0.75rem" }}>
        Because features are z-score normalized, coefficients are directly comparable.
        <strong style={{ color: "#dc2626" }}> Red</strong> = feature predicts higher recession risk when elevated.
        <strong style={{ color: "#2563eb" }}> Blue</strong> = feature predicts higher risk when depressed (e.g. inverted T10Y2Y).
      </p>
      <ResponsiveContainer width="100%" height={top.length * 34 + 20}>
        <BarChart
          data={chartData}
          layout="vertical"
          margin={{ left: 130, right: 30, top: 5, bottom: 5 }}
        >
          <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" horizontal={false} />
          <XAxis type="number" tick={{ fontSize: 11 }} tickFormatter={(v) => v.toFixed(2)} />
          <YAxis dataKey="feature" type="category" tick={{ fontSize: 11 }} width={125} />
          <Tooltip formatter={(v) => [v.toFixed(4), "Coefficient"]} />
          <Bar dataKey="coefficient" name="Coefficient">
            {chartData.map((entry, i) => (
              <Cell key={i} fill={entry.coefficient > 0 ? "#dc2626" : "#2563eb"} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
      <p style={{ fontSize: "0.78rem", color: "#94a3b8", marginTop: "0.5rem" }}>
        Coefficients from logistic regression trained on full dataset.
        GDP growth and CPI are the dominant predictors, followed by the fed funds path and unemployment.
        The yield curve matters more through its rate-of-change than its absolute level.
      </p>
    </div>
  );
}

export default function RecessionPage() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["recession"],
    queryFn: getRecession,
    staleTime: 5 * 60_000,
  });

  if (isLoading) return <p>Running recession probability model...</p>;
  if (error)
    return (
      <div>
        <h2>Recession Probability</h2>
        <p className="note">
          {error.response?.data?.detail?.includes("not trained")
            ? "Model not trained yet. Run: python train_recession.py"
            : error.response?.data?.detail?.includes("USREC")
            ? "USREC series missing. Re-run ingestion: python -m pipeline.flows.ingest_flow"
            : `Error: ${error.message}`}
        </p>
      </div>
    );

  const recessionBands = getRecessionBands(data.history);
  const signalColor =
    data.signal === "high" ? "#dc2626" : data.signal === "medium" ? "#d97706" : "#16a34a";

  return (
    <div>
      <h2>Recession Probability</h2>
      <p className="page-subtitle">
        Logistic regression on GDP growth, CPI, fed funds path, yield curve inversion, unemployment
        momentum, and housing starts. Target: any NBER recession month in the next 12 months.
        Trained on full history; OOS validation uses 2001–present (covers three recessions).
      </p>

      <div className="analysis-grid">
        {/* Gauge + signal */}
        <div className="chart-card" style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", padding: "1.5rem" }}>
          <GaugeChart probability={data.current_probability} />
          <div
            className="signal-banner"
            style={{ background: signalColor + "18", borderColor: signalColor, marginTop: "1.25rem", width: "100%" }}
          >
            <span style={{ color: signalColor, fontWeight: 600 }}>{data.signal_label}</span>
          </div>
        </div>

        {/* Feature table */}
        <div className="chart-card" style={{ padding: "1.25rem" }}>
          <h3 style={{ marginBottom: "0.75rem" }}>Current Leading Indicators</h3>
          <table className="table">
            <thead>
              <tr>
                <th>Feature</th>
                <th>Value</th>
                <th>Signal</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(data.current_features).map(([key, val]) => {
                const bearish =
                  (key === "t10y2y" && val < 0) ||
                  (key === "unrate_6m_chg" && val > 0.3) ||
                  (key === "fedfunds_6m_chg" && val > 0.5) ||
                  (key === "t10y2y_inv_months" && val > 3) ||
                  (key === "houst_6m_pct" && val < -5) ||
                  (key === "unrate_3m_chg" && val > 0.2);
                return (
                  <tr key={key}>
                    <td><code>{key}</code></td>
                    <td>{val}</td>
                    <td>
                      <span
                        className="badge"
                        style={{
                          background: bearish ? "#fee2e2" : "#f1f5f9",
                          color: bearish ? "#dc2626" : "#64748b",
                        }}
                      >
                        {bearish ? "Bearish" : "Neutral"}
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* OOS validation */}
      <OOSMetrics oos={data.oos_metrics} />

      {/* Feature importance */}
      <FeatureImportance importances={data.feature_importances} />

      {/* Probability history */}
      <div className="chart-card" style={{ marginTop: "1.5rem" }}>
        <h3 style={{ padding: "1rem 1rem 0" }}>Historical Recession Probability</h3>
        <p style={{ padding: "0.25rem 1rem 0.75rem", fontSize: "0.82rem", color: "#6b7280" }}>
          Gray shading = NBER recession periods. Probability is from the production model
          (trained on all data). OOS test metrics above use a pre-2001 training split.
        </p>
        <ResponsiveContainer width="100%" height={300}>
          <LineChart data={data.history} margin={{ top: 5, right: 30, left: 0, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
            <XAxis
              dataKey="date"
              tick={{ fontSize: 10 }}
              interval={Math.floor(data.history.length / 12)}
            />
            <YAxis
              domain={[0, 1]}
              tickFormatter={(v) => `${Math.round(v * 100)}%`}
              tick={{ fontSize: 11 }}
              width={48}
            />
            <Tooltip
              formatter={(v, name) =>
                name === "probability"
                  ? [`${(v * 100).toFixed(1)}%`, "Recession Probability"]
                  : [v, name]
              }
            />
            <Legend />
            {recessionBands.map((band, i) => (
              <ReferenceArea
                key={i}
                x1={band.start}
                x2={band.end}
                fill="#94a3b8"
                fillOpacity={0.25}
              />
            ))}
            <Line
              type="monotone"
              dataKey="probability"
              stroke="#dc2626"
              dot={false}
              strokeWidth={1.5}
              name="Recession Probability"
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

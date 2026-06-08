import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useParams } from "react-router-dom";
import {
  Area,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { getCalibration, getForecast, getSeriesData } from "../services/api";

export default function SeriesPage() {
  const { id } = useParams();
  const [showCalibration, setShowCalibration] = useState(false);

  const { data: historical } = useQuery({
    queryKey: ["series", id],
    queryFn: () => getSeriesData(id),
  });

  const { data: forecastData } = useQuery({
    queryKey: ["forecast", id],
    queryFn: () => getForecast(id),
  });

  const { data: calibration, isError: calibError } = useQuery({
    queryKey: ["calibration", id],
    queryFn: () => getCalibration(id),
    retry: false,
    enabled: showCalibration,
  });

  // Main chart: historical actual + forecast with CI bands
  const chartData = [
    ...(historical?.data?.map((d) => ({
      ds: d.observation_date,
      actual: d.value,
      forecast: null,
      ci_upper: null,
      ci_lower: null,
    })) ?? []),
    ...(forecastData?.forecast?.map((d) => ({
      ds: d.ds,
      actual: null,
      forecast: parseFloat(d.yhat.toFixed(4)),
      ci_upper: parseFloat(d.yhat_upper.toFixed(4)),
      ci_lower: parseFloat(d.yhat_lower.toFixed(4)),
    })) ?? []),
  ];

  // Calibration chart: actual vs forecast from backtest
  const calibData = calibration?.calibration_data?.map((d) => ({
    ds: d.ds,
    actual: d.actual,
    forecast: d.forecast,
    ci_upper: d.upper,
    ci_lower: d.lower,
    in_interval: d.in_interval,
  })) ?? [];

  const coverageColor =
    calibration?.actual_coverage >= 0.85
      ? "#16a34a"
      : calibration?.actual_coverage >= 0.65
      ? "#d97706"
      : "#dc2626";

  return (
    <div>
      <h2>{id} — Historical + Forecast</h2>

      <div style={{ marginBottom: "0.75rem", display: "flex", gap: "1rem", alignItems: "center" }}>
        <span style={{ fontSize: "0.85rem", color: "#6b7280" }}>
          Showing last 120 observations + 12-month forecast with 95% confidence interval
        </span>
        <button
          className="btn-outline"
          onClick={() => setShowCalibration((v) => !v)}
        >
          {showCalibration ? "Hide" : "Show"} calibration backtest
        </button>
      </div>

      <div className="chart-card">
        <ResponsiveContainer width="100%" height={380}>
          <ComposedChart data={chartData} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
            <defs>
              <linearGradient id="ciGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#f59e0b" stopOpacity={0.25} />
                <stop offset="100%" stopColor="#f59e0b" stopOpacity={0.05} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
            <XAxis dataKey="ds" tick={{ fontSize: 10 }} interval="preserveStartEnd" />
            <YAxis tick={{ fontSize: 11 }} width={60} />
            <Tooltip
              formatter={(val, name) =>
                val !== null ? [typeof val === "number" ? val.toFixed(2) : val, name] : [null, name]
              }
            />
            <Legend />
            {/* CI band: upper fill, then lower erase with white */}
            <Area
              type="monotone"
              dataKey="ci_upper"
              fill="url(#ciGrad)"
              stroke="none"
              name="95% CI Upper"
              legendType="none"
              activeDot={false}
              connectNulls={false}
            />
            <Area
              type="monotone"
              dataKey="ci_lower"
              fill="white"
              fillOpacity={1}
              stroke="none"
              name="95% CI Lower"
              legendType="none"
              activeDot={false}
              connectNulls={false}
            />
            <Line
              type="monotone"
              dataKey="actual"
              stroke="#2563eb"
              dot={false}
              name="Actual"
              strokeWidth={1.5}
            />
            <Line
              type="monotone"
              dataKey="forecast"
              stroke="#f59e0b"
              dot={false}
              strokeDasharray="6 3"
              name="Forecast"
              strokeWidth={2}
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>

      {showCalibration && (
        <div style={{ marginTop: "1.5rem" }}>
          <h3>Calibration Backtest (trained on data before 2023-01-01)</h3>
          {calibError ? (
            <p className="note">
              No calibration data yet. Run <code>python calibrate_all.py</code> to generate it.
            </p>
          ) : calibration ? (
            <>
              <div className="metric-row" style={{ marginBottom: "1rem" }}>
                <div className="metric-chip">
                  <span className="metric-label">Expected CI coverage</span>
                  <span className="metric-value">95%</span>
                </div>
                <div className="metric-chip">
                  <span className="metric-label">Actual CI coverage</span>
                  <span className="metric-value" style={{ color: coverageColor }}>
                    {(calibration.actual_coverage * 100).toFixed(1)}%
                  </span>
                </div>
                <div className="metric-chip">
                  <span className="metric-label">MAE</span>
                  <span className="metric-value">{calibration.mae.toFixed(2)}</span>
                </div>
                <div className="metric-chip">
                  <span className="metric-label">MAPE</span>
                  <span className="metric-value">{calibration.mape.toFixed(2)}%</span>
                </div>
                <div className="metric-chip">
                  <span className="metric-label">Test periods</span>
                  <span className="metric-value">{calibration.n_test}</span>
                </div>
              </div>
              <p style={{ fontSize: "0.82rem", color: "#6b7280", marginBottom: "0.75rem" }}>
                {calibration.actual_coverage >= 0.85
                  ? "Well-calibrated — the 95% CI captures most actuals as expected."
                  : calibration.actual_coverage >= 0.65
                  ? "Somewhat overconfident — CI is narrower than it should be for this series."
                  : "Overconfident — actual values frequently fall outside the predicted interval. Consider retraining on recent data only."}
              </p>
              <div className="chart-card">
                <ResponsiveContainer width="100%" height={280}>
                  <ComposedChart data={calibData} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
                    <defs>
                      <linearGradient id="calibGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="#6366f1" stopOpacity={0.2} />
                        <stop offset="100%" stopColor="#6366f1" stopOpacity={0.03} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                    <XAxis dataKey="ds" tick={{ fontSize: 10 }} interval="preserveStartEnd" />
                    <YAxis tick={{ fontSize: 11 }} width={60} />
                    <Tooltip />
                    <Legend />
                    <Area
                      type="monotone"
                      dataKey="ci_upper"
                      fill="url(#calibGrad)"
                      stroke="none"
                      legendType="none"
                      activeDot={false}
                    />
                    <Area
                      type="monotone"
                      dataKey="ci_lower"
                      fill="white"
                      fillOpacity={1}
                      stroke="none"
                      legendType="none"
                      activeDot={false}
                    />
                    <Line
                      type="monotone"
                      dataKey="actual"
                      stroke="#2563eb"
                      dot={{ r: 3 }}
                      name="Actual"
                    />
                    <Line
                      type="monotone"
                      dataKey="forecast"
                      stroke="#6366f1"
                      dot={false}
                      strokeDasharray="5 3"
                      name="Backtest Forecast"
                    />
                  </ComposedChart>
                </ResponsiveContainer>
              </div>
            </>
          ) : (
            <p style={{ color: "#6b7280" }}>Loading calibration data...</p>
          )}
        </div>
      )}
    </div>
  );
}

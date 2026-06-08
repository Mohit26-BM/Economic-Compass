import { useQuery, useMutation } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { getSimulateDefaults, runSimulation } from "../services/api";

// ── colour helpers ──────────────────────────────────────────────────────────

const REGIME_COLORS = {
  Expansion:  "#16a34a",
  Tightening: "#d97706",
  Recession:  "#dc2626",
  Recovery:   "#2563eb",
  Balanced:   "#6b7280",
};

function signalColor(signal) {
  return signal === "high" ? "#dc2626" : signal === "medium" ? "#d97706" : "#16a34a";
}

function catStatusColor(status) {
  return status === "green" ? "#16a34a" : status === "yellow" ? "#d97706" : "#dc2626";
}

// ── Preset scenarios ─────────────────────────────────────────────────────────

const PRESETS = [
  {
    label: "Soft Landing",
    desc: "Growth slows gently, inflation returns to target, no recession",
    values: { fedfunds: 3.5, cpi_yoy: 2.5, gdp_yoy: 2.0, unrate: 4.5, t10y2y: 0.5, houst_yoy: -5, rsxfs_yoy: 2.5 },
  },
  {
    label: "Fed Pivot",
    desc: "Fed cuts aggressively as inflation cools, rates fall sharply",
    values: { fedfunds: 2.0, cpi_yoy: 2.2, gdp_yoy: 2.5, unrate: 4.8, t10y2y: 1.2, houst_yoy: 8, rsxfs_yoy: 3.0 },
  },
  {
    label: "1970s Inflation",
    desc: "Entrenched high inflation, aggressive rate hiking cycle",
    values: { fedfunds: 10.0, cpi_yoy: 8.0, gdp_yoy: 1.5, unrate: 7.0, t10y2y: 0.3, houst_yoy: -18, rsxfs_yoy: 1.5 },
  },
  {
    label: "2008 Crisis",
    desc: "Severe recession, financial system stress, housing collapse",
    values: { fedfunds: 1.0, cpi_yoy: 1.0, gdp_yoy: -4.0, unrate: 9.0, t10y2y: -1.5, houst_yoy: -40, rsxfs_yoy: -5.0 },
  },
  {
    label: "COVID Shock",
    desc: "Sudden demand collapse, emergency Fed action, mass layoffs",
    values: { fedfunds: 0.25, cpi_yoy: 1.2, gdp_yoy: -8.0, unrate: 10.0, t10y2y: 0.5, houst_yoy: -25, rsxfs_yoy: -10.0 },
  },
  {
    label: "Goldilocks",
    desc: "Strong growth, low inflation, healthy labour market — ideal",
    values: { fedfunds: 3.5, cpi_yoy: 2.0, gdp_yoy: 3.5, unrate: 3.8, t10y2y: 1.5, houst_yoy: 12, rsxfs_yoy: 5.0 },
  },
];

// ── Scenario interpretation ───────────────────────────────────────────────────

function buildInterpretation(values, result) {
  const positives = [];
  const negatives = [];

  if (values.gdp_yoy >= 2.5) {
    positives.push(`GDP growth above trend (${values.gdp_yoy.toFixed(1)}%)`);
  } else if (values.gdp_yoy < 0) {
    negatives.push(`GDP contracting (${values.gdp_yoy.toFixed(1)}%)`);
  } else {
    negatives.push(`GDP below trend (${values.gdp_yoy.toFixed(1)}%, target 2.5%)`);
  }

  if (values.cpi_yoy <= 2.5) {
    positives.push(`Inflation near or at Fed target (${values.cpi_yoy.toFixed(1)}%)`);
  } else if (values.cpi_yoy > 4.0) {
    negatives.push(`Elevated inflation well above target (${values.cpi_yoy.toFixed(1)}%)`);
  } else {
    negatives.push(`Inflation above 2% Fed target (${values.cpi_yoy.toFixed(1)}%)`);
  }

  if (values.unrate <= 4.5) {
    positives.push(`Labour market healthy (${values.unrate.toFixed(1)}% unemployment)`);
  } else if (values.unrate >= 7.0) {
    negatives.push(`Unemployment severely elevated (${values.unrate.toFixed(1)}%)`);
  } else {
    negatives.push(`Unemployment rising above full employment (${values.unrate.toFixed(1)}%)`);
  }

  if (values.t10y2y > 0.5) {
    positives.push(`Yield curve positively sloped (+${values.t10y2y.toFixed(2)}pp) — no inversion signal`);
  } else if (values.t10y2y < 0) {
    negatives.push(`Yield curve inverted (${values.t10y2y.toFixed(2)}pp) — historical recession signal`);
  } else {
    positives.push(`Yield curve flat but not inverted (${values.t10y2y.toFixed(2)}pp)`);
  }

  const taylorGap = result?.taylor?.policy_gap;
  if (taylorGap != null) {
    if (taylorGap < -1.0) {
      positives.push(`Monetary policy accommodative (${taylorGap.toFixed(1)}pp below Taylor prescription)`);
    } else if (taylorGap > 1.5) {
      negatives.push(`Fed Funds rate significantly restrictive (+${taylorGap.toFixed(1)}pp above Taylor prescription)`);
    } else if (taylorGap > 0.5) {
      negatives.push(`Fed Funds rate moderately restrictive (+${taylorGap.toFixed(1)}pp above Taylor prescription)`);
    } else {
      positives.push("Monetary policy roughly in line with Taylor Rule prescription");
    }
  }

  if (values.houst_yoy != null) {
    if (values.houst_yoy > 5) {
      positives.push(`Housing activity positive (${values.houst_yoy.toFixed(0)}% YoY) — rate-sensitive sector healthy`);
    } else if (values.houst_yoy < -20) {
      negatives.push(`Housing in deep contraction (${values.houst_yoy.toFixed(0)}% YoY)`);
    } else if (values.houst_yoy < -5) {
      negatives.push(`Housing starts declining (${values.houst_yoy.toFixed(0)}% YoY)`);
    }
  }

  if (values.rsxfs_yoy != null) {
    if (values.rsxfs_yoy >= 3) {
      positives.push(`Consumer spending healthy (Retail Sales +${values.rsxfs_yoy.toFixed(1)}% YoY)`);
    } else if (values.rsxfs_yoy < 0) {
      negatives.push(`Consumer spending declining (Retail Sales ${values.rsxfs_yoy.toFixed(1)}% YoY)`);
    }
  }

  const recPct = result?.recession?.probability != null
    ? Math.round(result.recession.probability * 100)
    : null;
  const regime = result?.regime?.regime ?? "—";
  const condLabel = result?.conditions?.composite?.label ?? "—";

  let netResult;
  if (recPct !== null && recPct >= 50) {
    netResult = `High recession probability (${recPct}%) with ${condLabel.toLowerCase()} conditions. The dominant forces here are contractionary — deteriorating leading indicators outweigh any positives.`;
  } else if (recPct !== null && recPct >= 25) {
    netResult = `Elevated recession risk (${recPct}%) with ${condLabel.toLowerCase()} conditions. The economy is under meaningful stress but has not yet tipped into contraction. Watch for further deterioration in leading indicators.`;
  } else if (recPct !== null && recPct >= 10) {
    netResult = `Moderate recession risk (${recPct}%) in a ${regime.toLowerCase()} environment. Conditions are ${condLabel.toLowerCase()} — neither clearly expansionary nor contractionary. The balance of signals is mixed.`;
  } else {
    netResult = `Low recession risk (${recPct ?? "—"}%) with ${condLabel.toLowerCase()} conditions. The ${regime.toLowerCase()} environment is broadly supported by the majority of indicators pointing in a constructive direction.`;
  }

  return { positives, negatives, netResult };
}

// ── Slider component ─────────────────────────────────────────────────────────

function Slider({ id, config, value, onChange }) {
  return (
    <div style={{ marginBottom: "1rem" }}>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "0.3rem" }}>
        <span style={{ fontSize: "0.8rem", fontWeight: 600, color: "#374151" }}>
          {config.label}
        </span>
        <span
          style={{
            fontSize: "0.85rem",
            fontWeight: 700,
            color: "#1e293b",
            background: "#f1f5f9",
            borderRadius: 4,
            padding: "0.05rem 0.4rem",
            minWidth: 52,
            textAlign: "right",
          }}
        >
          {value > 0 && config.unit !== "%" ? "+" : ""}{value.toFixed(config.step < 0.1 ? 2 : 1)}{config.unit}
        </span>
      </div>
      <input
        type="range"
        min={config.min}
        max={config.max}
        step={config.step}
        value={value}
        onChange={(e) => onChange(id, parseFloat(e.target.value))}
        style={{ width: "100%", accentColor: "#6366f1" }}
      />
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.65rem", color: "#94a3b8" }}>
        <span>{config.min}{config.unit}</span>
        <span>{config.max}{config.unit}</span>
      </div>
    </div>
  );
}

// ── Interpretation panel ─────────────────────────────────────────────────────

function InterpretationPanel({ values, result }) {
  if (!result) return null;
  const { positives, negatives, netResult } = buildInterpretation(values, result);
  return (
    <div
      className="chart-card"
      style={{ padding: "1.1rem", marginBottom: "0.75rem", borderLeft: "3px solid #6366f1" }}
    >
      <div
        style={{
          fontSize: "0.65rem",
          fontWeight: 700,
          textTransform: "uppercase",
          letterSpacing: "0.07em",
          color: "#94a3b8",
          marginBottom: "0.6rem",
        }}
      >
        Scenario Interpretation
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.75rem", marginBottom: "0.75rem" }}>
        <div>
          <div style={{ fontSize: "0.72rem", fontWeight: 700, color: "#16a34a", marginBottom: "0.3rem" }}>
            Positive Signals
          </div>
          {positives.length === 0 ? (
            <p style={{ fontSize: "0.75rem", color: "#94a3b8", fontStyle: "italic" }}>None</p>
          ) : (
            positives.map((p, i) => (
              <div key={i} style={{ display: "flex", gap: "0.4rem", marginBottom: "0.25rem", fontSize: "0.78rem", color: "#1e293b" }}>
                <span style={{ color: "#16a34a", fontWeight: 700, flexShrink: 0 }}>✓</span>
                <span>{p}</span>
              </div>
            ))
          )}
        </div>
        <div>
          <div style={{ fontSize: "0.72rem", fontWeight: 700, color: "#dc2626", marginBottom: "0.3rem" }}>
            Negative Signals
          </div>
          {negatives.length === 0 ? (
            <p style={{ fontSize: "0.75rem", color: "#94a3b8", fontStyle: "italic" }}>None</p>
          ) : (
            negatives.map((n, i) => (
              <div key={i} style={{ display: "flex", gap: "0.4rem", marginBottom: "0.25rem", fontSize: "0.78rem", color: "#1e293b" }}>
                <span style={{ color: "#dc2626", fontWeight: 700, flexShrink: 0 }}>✗</span>
                <span>{n}</span>
              </div>
            ))
          )}
        </div>
      </div>
      <div
        style={{
          background: "#f8fafc",
          borderRadius: 6,
          padding: "0.6rem 0.75rem",
          borderLeft: "3px solid #e2e8f0",
        }}
      >
        <div style={{ fontSize: "0.68rem", fontWeight: 700, color: "#6366f1", marginBottom: "0.2rem" }}>
          Net Result
        </div>
        <p style={{ fontSize: "0.8rem", color: "#334155", margin: 0, lineHeight: 1.55 }}>{netResult}</p>
      </div>
    </div>
  );
}

// ── Output panels ─────────────────────────────────────────────────────────────

function TaylorPanel({ taylor }) {
  if (!taylor) return null;
  const gapColor = taylor.policy_gap > 1 ? "#dc2626" : taylor.policy_gap < -1 ? "#16a34a" : "#6b7280";
  return (
    <div className="chart-card" style={{ padding: "1rem", marginBottom: "0.75rem" }}>
      <div style={{ fontSize: "0.65rem", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.07em", color: "#94a3b8", marginBottom: "0.3rem" }}>Taylor Rule</div>
      <div style={{ display: "flex", gap: "1.5rem", flexWrap: "wrap", marginBottom: "0.5rem" }}>
        <div>
          <div style={{ fontSize: "0.68rem", color: "#94a3b8" }}>Prescribed</div>
          <div style={{ fontWeight: 700, fontSize: "1.1rem", color: "#6366f1" }}>{taylor.taylor_rate.toFixed(1)}%</div>
        </div>
        <div>
          <div style={{ fontSize: "0.68rem", color: "#94a3b8" }}>Actual</div>
          <div style={{ fontWeight: 700, fontSize: "1.1rem" }}>{taylor.actual_rate.toFixed(1)}%</div>
        </div>
        <div>
          <div style={{ fontSize: "0.68rem", color: "#94a3b8" }}>Policy gap</div>
          <div style={{ fontWeight: 700, fontSize: "1.1rem", color: gapColor }}>
            {taylor.policy_gap > 0 ? "+" : ""}{taylor.policy_gap.toFixed(1)}pp
          </div>
        </div>
      </div>
      <p style={{ fontSize: "0.75rem", color: "#475569", margin: 0 }}>{taylor.explanation}</p>
      <p style={{ fontSize: "0.68rem", color: "#94a3b8", margin: "0.25rem 0 0" }}>{taylor.note}</p>
    </div>
  );
}

function RecessionPanel({ recession }) {
  if (!recession) return null;
  if (recession.probability == null) return (
    <div className="chart-card" style={{ padding: "1rem", marginBottom: "0.75rem" }}>
      <div style={{ fontSize: "0.65rem", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.07em", color: "#94a3b8" }}>Recession Risk</div>
      <p style={{ fontSize: "0.8rem", color: "#94a3b8" }}>{recession.explanation}</p>
    </div>
  );
  const pct = Math.round(recession.probability * 100);
  const color = signalColor(recession.signal);
  return (
    <div className="chart-card" style={{ padding: "1rem", marginBottom: "0.75rem", borderLeft: `3px solid ${color}` }}>
      <div style={{ fontSize: "0.65rem", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.07em", color: "#94a3b8", marginBottom: "0.3rem" }}>12-month Recession Risk</div>
      <div style={{ display: "flex", alignItems: "baseline", gap: "0.75rem", marginBottom: "0.4rem" }}>
        <span style={{ fontSize: "1.6rem", fontWeight: 800, color }}>{pct}%</span>
        <span style={{ fontSize: "0.8rem", fontWeight: 600, color, textTransform: "capitalize" }}>{recession.signal} risk</span>
      </div>
      <div style={{ height: 6, background: "#f1f5f9", borderRadius: 3, marginBottom: "0.5rem" }}>
        <div style={{ width: `${pct}%`, height: "100%", background: color, borderRadius: 3, transition: "width 0.3s" }} />
      </div>
      <p style={{ fontSize: "0.75rem", color: "#475569", margin: 0 }}>{recession.explanation}</p>
      <p style={{ fontSize: "0.68rem", color: "#94a3b8", margin: "0.25rem 0 0" }}>{recession.note}</p>
    </div>
  );
}

function ConditionsPanel({ conditions }) {
  if (!conditions) return null;
  const { composite, categories } = conditions;
  return (
    <div className="chart-card" style={{ padding: "1rem", marginBottom: "0.75rem" }}>
      <div style={{ fontSize: "0.65rem", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.07em", color: "#94a3b8", marginBottom: "0.3rem" }}>Conditions Index</div>
      <div style={{ display: "flex", alignItems: "baseline", gap: "0.75rem", marginBottom: "0.75rem" }}>
        <span style={{ fontSize: "1.3rem", fontWeight: 800, color: composite.color }}>{composite.label}</span>
        <span style={{ fontSize: "0.85rem", color: composite.color, fontWeight: 600 }}>
          {composite.score > 0 ? "+" : ""}{composite.score.toFixed(2)}
        </span>
      </div>
      <div style={{ display: "flex", flexWrap: "wrap", gap: "0.4rem" }}>
        {categories.map((cat) => (
          <span
            key={cat.name}
            style={{
              fontSize: "0.72rem",
              fontWeight: 600,
              background: catStatusColor(cat.status) + "18",
              color: catStatusColor(cat.status),
              borderRadius: 4,
              padding: "0.1rem 0.5rem",
              border: `1px solid ${catStatusColor(cat.status)}40`,
            }}
          >
            {cat.name}: {cat.label}
          </span>
        ))}
      </div>
    </div>
  );
}

function RegimePanel({ regime }) {
  if (!regime) return null;
  const color = REGIME_COLORS[regime.regime] ?? regime.color ?? "#6b7280";
  return (
    <div className="chart-card" style={{ padding: "1rem", marginBottom: "0.75rem", borderLeft: `3px solid ${color}` }}>
      <div style={{ fontSize: "0.65rem", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.07em", color: "#94a3b8", marginBottom: "0.3rem" }}>Economic Regime</div>
      <div style={{ fontSize: "1.2rem", fontWeight: 800, color, marginBottom: "0.25rem" }}>{regime.regime}</div>
      <p style={{ fontSize: "0.75rem", color: "#475569", margin: 0 }}>{regime.reason}</p>
    </div>
  );
}

function AnaloguesPanel({ analogues }) {
  if (!analogues?.length) return null;
  return (
    <div className="chart-card" style={{ padding: "1rem" }}>
      <div style={{ fontSize: "0.65rem", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.07em", color: "#94a3b8", marginBottom: "0.5rem" }}>
        Closest Historical Periods
      </div>
      <p style={{ fontSize: "0.75rem", color: "#6b7280", margin: "0 0 0.75rem" }}>
        Months in history where conditions (in z-score space) most resembled this scenario.
      </p>
      <div style={{ display: "flex", flexDirection: "column", gap: "0.4rem" }}>
        {analogues.map((a, i) => {
          const rc = REGIME_COLORS[a.regime] ?? "#6b7280";
          return (
            <div
              key={a.date}
              style={{
                display: "flex",
                alignItems: "center",
                gap: "0.75rem",
                fontSize: "0.8rem",
                padding: "0.3rem 0.5rem",
                background: i === 0 ? "#f8fafc" : "white",
                borderRadius: 6,
                border: i === 0 ? "1px solid #e2e8f0" : "none",
              }}
            >
              <span style={{ fontWeight: 700, color: "#374151", minWidth: 36 }}>#{i + 1}</span>
              <span style={{ fontWeight: 600, color: "#1e293b", minWidth: 70 }}>{a.date.slice(0, 7)}</span>
              <span
                style={{
                  fontSize: "0.68rem",
                  fontWeight: 600,
                  color: rc,
                  background: rc + "18",
                  borderRadius: 4,
                  padding: "0.05rem 0.4rem",
                  minWidth: 76,
                  textAlign: "center",
                }}
              >
                {a.regime}
              </span>
              <span style={{ color: "#94a3b8", fontSize: "0.72rem" }}>
                dist {a.distance.toFixed(2)}
              </span>
            </div>
          );
        })}
      </div>
      <p style={{ fontSize: "0.68rem", color: "#94a3b8", margin: "0.5rem 0 0" }}>
        Distance = Euclidean distance in z-score space across all tracked indicators. Lower = more similar conditions.
      </p>
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function SimulatorPage() {
  const { data: defaults, isLoading: loadingDefaults } = useQuery({
    queryKey: ["simulate-defaults"],
    queryFn: getSimulateDefaults,
    staleTime: 10 * 60_000,
  });

  const [values, setValues] = useState(null);
  const [result, setResult] = useState(null);
  const [activePreset, setActivePreset] = useState(null);
  const debounceRef = useRef(null);

  const defaultValues = (src) => ({
    fedfunds:  src?.fedfunds  ?? 4.0,
    cpi_yoy:   src?.cpi_yoy   ?? 3.0,
    gdp_yoy:   src?.gdp_yoy   ?? 2.5,
    unrate:    src?.unrate    ?? 4.5,
    t10y2y:    src?.t10y2y    ?? 0.5,
    houst_yoy: src?.houst_yoy ?? 0.0,
    rsxfs_yoy: src?.rsxfs_yoy ?? 3.0,
  });

  useEffect(() => {
    if (defaults && !values) setValues(defaultValues(defaults));
  }, [defaults, values]);

  const mutation = useMutation({ mutationFn: runSimulation });

  const fire = (next) => {
    clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      mutation.mutate(next, { onSuccess: setResult });
    }, 280);
  };

  const handleChange = (id, val) => {
    const next = { ...values, [id]: val };
    setValues(next);
    setActivePreset(null);
    fire(next);
  };

  const applyPreset = (preset) => {
    const next = preset.values ? { ...defaultValues(defaults), ...preset.values } : defaultValues(defaults);
    setValues(next);
    setActivePreset(preset.label);
    clearTimeout(debounceRef.current);
    mutation.mutate(next, { onSuccess: setResult });
  };

  useEffect(() => {
    if (values && !result && !mutation.isPending) {
      mutation.mutate(values, { onSuccess: setResult });
    }
  }, [values]);

  if (loadingDefaults || !values) {
    return (
      <div>
        <h2>Economic Scenario Simulator</h2>
        <p>Loading current indicator values…</p>
      </div>
    );
  }

  const sliderConfig = defaults?.slider_config ?? {};

  return (
    <div>
      <h2>Economic Scenario Simulator</h2>
      <p className="page-subtitle">
        Adjust the sliders to explore hypothetical economic scenarios. All five models
        update in real time — see how the Taylor Rule, recession probability, conditions
        index, and regime label respond as you change rates, inflation, and growth.
      </p>

      {/* Preset buttons */}
      <div style={{ marginBottom: "1.25rem" }}>
        <div style={{ fontSize: "0.72rem", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.07em", color: "#94a3b8", marginBottom: "0.5rem" }}>
          Preset Scenarios
        </div>
        <div style={{ display: "flex", flexWrap: "wrap", gap: "0.5rem" }}>
          <button
            onClick={() => { setActivePreset("Current Economy"); applyPreset({ label: "Current Economy", values: null }); }}
            style={{
              padding: "0.35rem 0.75rem",
              borderRadius: 6,
              border: `1px solid ${activePreset === "Current Economy" ? "#6366f1" : "#e2e8f0"}`,
              background: activePreset === "Current Economy" ? "#ede9fe" : "white",
              color: activePreset === "Current Economy" ? "#6366f1" : "#374151",
              fontSize: "0.8rem",
              fontWeight: activePreset === "Current Economy" ? 700 : 500,
              cursor: "pointer",
              transition: "all 0.15s",
            }}
            title="Reset to current real indicator values"
          >
            Current Economy
          </button>
          {PRESETS.map((p) => (
            <button
              key={p.label}
              onClick={() => applyPreset(p)}
              title={p.desc}
              style={{
                padding: "0.35rem 0.75rem",
                borderRadius: 6,
                border: `1px solid ${activePreset === p.label ? "#6366f1" : "#e2e8f0"}`,
                background: activePreset === p.label ? "#ede9fe" : "white",
                color: activePreset === p.label ? "#6366f1" : "#374151",
                fontSize: "0.8rem",
                fontWeight: activePreset === p.label ? 700 : 500,
                cursor: "pointer",
                transition: "all 0.15s",
              }}
            >
              {p.label}
            </button>
          ))}
        </div>
        {activePreset && activePreset !== "Current Economy" && (
          <p style={{ fontSize: "0.75rem", color: "#6b7280", marginTop: "0.35rem" }}>
            {PRESETS.find((p) => p.label === activePreset)?.desc}
          </p>
        )}
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "320px 1fr", gap: "1.5rem", alignItems: "start" }}>

        {/* Left — sliders */}
        <div>
          <div
            style={{
              background: "#f8fafc",
              border: "1px solid #e2e8f0",
              borderRadius: 10,
              padding: "1.25rem",
            }}
          >
            <div
              style={{
                fontSize: "0.68rem",
                fontWeight: 700,
                textTransform: "uppercase",
                letterSpacing: "0.07em",
                color: "#94a3b8",
                marginBottom: "1rem",
              }}
            >
              Scenario Inputs
            </div>
            {Object.entries(sliderConfig).map(([id, cfg]) => (
              <Slider
                key={id}
                id={id}
                config={cfg}
                value={values[id] ?? 0}
                onChange={handleChange}
              />
            ))}
            <button
              onClick={() => applyPreset({ label: "Current Economy", values: null })}
              style={{
                width: "100%",
                padding: "0.5rem",
                border: "1px solid #e2e8f0",
                borderRadius: 6,
                background: "white",
                color: "#6b7280",
                fontSize: "0.78rem",
                cursor: "pointer",
                marginTop: "0.5rem",
              }}
            >
              Reset to current real values
            </button>
            {mutation.isPending && (
              <p style={{ fontSize: "0.72rem", color: "#94a3b8", textAlign: "center", margin: "0.5rem 0 0" }}>
                Computing…
              </p>
            )}
          </div>

          {/* Simulation limitation — placed under sliders, prominent */}
          <div
            style={{
              marginTop: "0.75rem",
              background: "#fffbeb",
              border: "1px solid #fbbf24",
              borderRadius: 8,
              padding: "0.85rem 1rem",
            }}
          >
            <div style={{ fontSize: "0.72rem", fontWeight: 700, color: "#92400e", marginBottom: "0.35rem" }}>
              Simulation Limitation
            </div>
            <p style={{ fontSize: "0.75rem", color: "#78350f", margin: 0, lineHeight: 1.55 }}>
              Only current <strong>levels</strong> are adjusted. Historical momentum features
              (3m / 6m / 12m changes) remain anchored to actual data.
            </p>
            <p style={{ fontSize: "0.75rem", color: "#78350f", margin: "0.35rem 0 0", lineHeight: 1.55 }}>
              Results are <strong>directional signals</strong>, not precise forecasts. A sudden
              shock (e.g. unemployment to 9%) won't reflect the momentum deterioration that
              would accompany such a move in reality.
            </p>
          </div>
        </div>

        {/* Right — outputs */}
        <div>
          {result ? (
            <>
              <InterpretationPanel values={values} result={result} />
              <TaylorPanel    taylor={result.taylor} />
              <RecessionPanel recession={result.recession} />
              <ConditionsPanel conditions={result.conditions} />
              <RegimePanel    regime={result.regime} />
              <AnaloguesPanel analogues={result.analogues} />
            </>
          ) : (
            <p style={{ color: "#94a3b8" }}>Move a slider to see results.</p>
          )}
        </div>
      </div>
    </div>
  );
}

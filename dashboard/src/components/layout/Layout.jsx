import { useState } from "react";
import { NavLink, Outlet } from "react-router-dom";

const nav = [
  {
    to: "/",
    label: "Overview",
    sub: "Series & status",
    group: "data",
    end: true,
  },
  {
    to: "/lineage",
    label: "Data Lineage",
    sub: "Pipeline DAG",
    group: "data",
  },
  {
    to: "/recession",
    label: "Recession Risk",
    sub: "12-month probability",
    group: "analysis",
  },
  {
    to: "/correlation",
    label: "Correlation",
    sub: "Lead/lag relationships",
    group: "analysis",
  },
  {
    to: "/regimes",
    label: "Economic Regimes",
    sub: "Current environment",
    group: "analysis",
  },
  {
    to: "/taylor",
    label: "Taylor Rule",
    sub: "Policy stance",
    group: "analysis",
  },
  {
    to: "/sahm",
    label: "Sahm Rule",
    sub: "Labour market signal",
    group: "analysis",
  },
  {
    to: "/conditions",
    label: "Conditions Index",
    sub: "Overall economic health",
    group: "analysis",
  },
  {
    to: "/simulator",
    label: "Scenario Simulator",
    sub: "What-if analysis",
    group: "analysis",
  },
];

function ChevronLeft() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
      <path d="M10 12L6 8l4-4" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  );
}

function ChevronRight() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
      <path d="M6 4l4 4-4 4" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  );
}

export default function Layout() {
  const [collapsed, setCollapsed] = useState(() => {
    try { return localStorage.getItem("sidebar-collapsed") === "true"; } catch { return false; }
  });

  const toggle = () => {
    setCollapsed((v) => {
      const next = !v;
      try { localStorage.setItem("sidebar-collapsed", String(next)); } catch {}
      return next;
    });
  };

  return (
    <div className="app">
      <aside className={`sidebar${collapsed ? " collapsed" : ""}`}>
        <div className="brand">
          <div className="brand-title">Economic Compass</div>
          <div className="brand-sub">U.S. Economic Indicators</div>
        </div>

        <button className="sidebar-toggle" onClick={toggle} title={collapsed ? "Expand sidebar" : "Collapse sidebar"}>
          {collapsed ? <ChevronRight /> : <ChevronLeft />}
          {!collapsed && <span style={{ marginLeft: "0.4rem", fontSize: "0.72rem", color: "#64748b" }}>Collapse</span>}
        </button>

        <nav>
          <div className="nav-section-label">Pipeline</div>
          {nav.filter((n) => n.group === "data").map(({ to, label, sub, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) => (isActive ? "nav-link active" : "nav-link")}
              title={collapsed ? label : undefined}
            >
              <span className="nav-link-label">{label}</span>
              <span className="nav-link-sub">{sub}</span>
            </NavLink>
          ))}
          <div className="nav-section-label" style={{ marginTop: "1.25rem" }}>Analysis</div>
          {nav.filter((n) => n.group === "analysis").map(({ to, label, sub }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) => (isActive ? "nav-link active" : "nav-link")}
              title={collapsed ? label : undefined}
            >
              <span className="nav-link-label">{label}</span>
              <span className="nav-link-sub">{sub}</span>
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-footer">
          <div className="sidebar-footer-text">FRED API · dbt · DuckDB</div>
          <div className="sidebar-footer-text">Prophet · scikit-learn</div>
        </div>
      </aside>
      <main className="content">
        <Outlet />
      </main>
    </div>
  );
}

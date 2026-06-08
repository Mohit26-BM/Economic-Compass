"""
Simulator validation test suite.

Usage:
    python test_simulator.py                  # run against localhost:8000
    python test_simulator.py --url http://... # custom base URL
    python test_simulator.py --scenario 4     # run only scenario 4

Each scenario POSTs to /analysis/simulate and checks that the outputs
are economically sensible.  The final table shows the ordering that matters:
Goldilocks -> Soft Landing -> Tightening -> Stagflation -> 2008 -> COVID
"""

import argparse
import sys

try:
    import requests
except ImportError:
    sys.exit("requests not installed -- run: pip install requests")

# ANSI colours
GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

def col(text, color): return f"{color}{text}{RESET}"

SEP  = "-" * 72
SEP2 = "=" * 72

# ---------------------------------------------------------------------------
# Scenario definitions
# ---------------------------------------------------------------------------

SCENARIOS = [
    {
        "name":  "Test 1 -- Soft Landing",
        "desc":  "Current-ish economy: moderate growth, cooling inflation",
        "inputs": dict(fedfunds=3.5, cpi_yoy=3.0, gdp_yoy=3.0, unrate=4.3,
                       t10y2y=0.5,  houst_yoy=5.0, rsxfs_yoy=4.0),
        "expect": {
            "taylor_rate_min": 4.0,  "taylor_rate_max": 6.0,
            "recession_max":   0.40,
            "regime_ok":       {"Expansion", "Recovery", "Balanced"},
        },
    },
    {
        "name":  "Test 2 -- Fed Overtightening",
        "desc":  "Rates far above Taylor prescription, yield curve inverted",
        "inputs": dict(fedfunds=8.0, cpi_yoy=2.0, gdp_yoy=1.0, unrate=5.0,
                       t10y2y=-1.0, houst_yoy=-10.0, rsxfs_yoy=1.0),
        "expect": {
            "policy_gap_min": 2.0,
            "recession_min":  0.20,
            "regime_ok":      {"Tightening", "Recession", "Balanced"},
        },
    },
    {
        "name":  "Test 3 -- 1970s Inflation",
        "desc":  "High inflation, Fed behind the curve",
        "inputs": dict(fedfunds=5.0, cpi_yoy=10.0, gdp_yoy=2.0, unrate=5.0,
                       t10y2y=1.0,  houst_yoy=0.0, rsxfs_yoy=2.0),
        "expect": {
            "taylor_rate_min": 12.0,
            "policy_gap_max":  -4.0,
            "regime_ok":       {"Tightening", "Expansion", "Balanced"},
        },
    },
    {
        "name":  "Test 4 -- 2008 Financial Crisis",
        "desc":  "Severe recession, housing collapse, inverted curve",
        "inputs": dict(fedfunds=1.0, cpi_yoy=1.0, gdp_yoy=-4.0, unrate=8.0,
                       t10y2y=-0.5, houst_yoy=-25.0, rsxfs_yoy=-10.0),
        "expect": {
            "recession_min":  0.45,
            "composite_max":  -0.5,
            "regime_ok":      {"Recession", "Tightening"},
        },
    },
    {
        "name":  "Test 5 -- COVID Shock",
        "desc":  "Sudden demand collapse, emergency rate cut",
        "inputs": dict(fedfunds=0.25, cpi_yoy=1.0, gdp_yoy=-8.0, unrate=12.0,
                       t10y2y=0.5, houst_yoy=-20.0, rsxfs_yoy=-15.0),
        "expect": {
            "recession_min":  0.55,
            "composite_max":  -0.8,
            "regime_ok":      {"Recession"},
        },
    },
    {
        "name":  "Test 6 -- Goldilocks Economy",
        "desc":  "Strong growth, near-target inflation, healthy labour market",
        "inputs": dict(fedfunds=3.0, cpi_yoy=2.0, gdp_yoy=3.0, unrate=3.5,
                       t10y2y=1.0,  houst_yoy=10.0, rsxfs_yoy=6.0),
        "expect": {
            "recession_max":  0.15,
            "composite_min":  0.2,
            "regime_ok":      {"Expansion", "Recovery", "Balanced"},
        },
    },
    {
        "name":  "Test 7 -- Stagflation",
        "desc":  "High inflation + weak growth -- the worst of both worlds",
        "inputs": dict(fedfunds=4.0, cpi_yoy=8.0, gdp_yoy=0.0, unrate=7.0,
                       t10y2y=-1.0, houst_yoy=-10.0, rsxfs_yoy=0.0),
        "expect": {
            "taylor_rate_min": 10.0,
            "policy_gap_max":  -4.0,
            "recession_min":   0.35,
            "regime_ok":       {"Tightening", "Recession"},
        },
    },
    # Single-slider sanity checks
    {
        "name":  "Sanity A -- Raise CPI only (3->6%)",
        "desc":  "Everything else held at soft-landing baseline",
        "inputs": dict(fedfunds=3.5, cpi_yoy=6.0, gdp_yoy=3.0, unrate=4.3,
                       t10y2y=0.5, houst_yoy=5.0, rsxfs_yoy=4.0),
        "expect": {
            "taylor_rate_min": 7.0,
            "recession_min":   0.05,
        },
    },
    {
        "name":  "Sanity B -- Raise Unemployment only (4.3->7%)",
        "desc":  "Everything else held at soft-landing baseline",
        "inputs": dict(fedfunds=3.5, cpi_yoy=3.0, gdp_yoy=3.0, unrate=7.0,
                       t10y2y=0.5, houst_yoy=5.0, rsxfs_yoy=4.0),
        "expect": {
            "recession_min": 0.10,
        },
    },
    {
        "name":  "Sanity C -- Raise Housing only (0->+20%)",
        "desc":  "Everything else held at soft-landing baseline",
        "inputs": dict(fedfunds=3.5, cpi_yoy=3.0, gdp_yoy=3.0, unrate=4.3,
                       t10y2y=0.5, houst_yoy=20.0, rsxfs_yoy=4.0),
        "expect": {
            "composite_min": -0.1,
        },
    },
    {
        "name":  "Sanity D -- Super-expansion stress test",
        "desc":  "GDP +8%, UNRATE 2%, housing +30%, retail +15% -- must not show recession",
        "inputs": dict(fedfunds=3.0, cpi_yoy=2.5, gdp_yoy=8.0, unrate=2.0,
                       t10y2y=1.5, houst_yoy=30.0, rsxfs_yoy=15.0),
        "expect": {
            "recession_max":  0.20,
            "composite_min":  0.3,
            "regime_ok":      {"Expansion", "Recovery", "Balanced", "Tightening"},
        },
    },
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def pct_bar(prob: float, width: int = 20) -> str:
    filled = round(prob * width)
    bar = "#" * filled + "." * (width - filled)
    pct = f"{prob*100:5.1f}%"
    c = RED if prob >= 0.5 else (YELLOW if prob >= 0.25 else GREEN)
    return f"{col(bar, c)} {col(pct, c)}"


def conditions_color(score: float) -> str:
    if score >= 0.5:    return GREEN
    elif score >= 0:    return CYAN
    elif score >= -0.5: return YELLOW
    else:               return RED


def regime_color(regime: str) -> str:
    return {"Expansion": GREEN, "Recovery": CYAN, "Balanced": CYAN,
            "Tightening": YELLOW, "Recession": RED}.get(regime, RESET)


def gap_str(gap: float) -> str:
    sign = "+" if gap > 0 else ""
    c = RED if gap > 1 else GREEN if gap < -1 else RESET
    return col(f"{sign}{gap:.2f}pp", c)


def catcol(status: str) -> str:
    return GREEN if status == "green" else (YELLOW if status == "yellow" else RED)


def run_scenario(url: str, scenario: dict) -> dict | None:
    try:
        r = requests.post(f"{url}/analysis/simulate",
                          json=scenario["inputs"], timeout=30)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.ConnectionError:
        print(col(f"\n  ERROR: Cannot connect to {url}. Is the API running?", RED))
        return None
    except Exception as e:
        print(col(f"\n  ERROR: {e}", RED))
        return None


def print_scenario(scenario: dict, data: dict) -> dict:
    name   = scenario["name"]
    inputs = scenario["inputs"]
    exp    = scenario.get("expect", {})

    print(f"\n{SEP}")
    print(col(f"  {name}", BOLD))
    print(f"  {scenario['desc']}")
    print()

    # Inputs
    print(col("  Inputs:", BOLD))
    print(f"    Fed Funds {inputs['fedfunds']:.2f}%  |  "
          f"CPI {inputs['cpi_yoy']:.1f}%  |  "
          f"GDP {inputs['gdp_yoy']:.1f}%  |  "
          f"UNRATE {inputs['unrate']:.1f}%  |  "
          f"T10Y2Y {inputs['t10y2y']:+.2f}pp  |  "
          f"Housing {inputs.get('houst_yoy', 0):+.0f}%  |  "
          f"Retail {inputs.get('rsxfs_yoy', 0):+.0f}%")
    print()

    # Taylor Rule
    t   = data.get("taylor", {})
    tr  = t.get("taylor_rate", 0)
    act = t.get("actual_rate", 0)
    gap = t.get("policy_gap", 0)
    print(col("  Taylor Rule:", BOLD))
    print(f"    Prescribed {col(f'{tr:.2f}%', CYAN)}  |  "
          f"Actual {act:.2f}%  |  "
          f"Policy gap {gap_str(gap)}")
    if t.get("explanation"):
        print(f"    {t['explanation']}")
    print()

    # Recession
    rec  = data.get("recession", {})
    prob = rec.get("probability")
    print(col("  Recession Risk:", BOLD))
    if prob is not None:
        print(f"    {pct_bar(prob)}  {rec.get('signal','').upper()}")
        if rec.get("explanation"):
            print(f"    {rec['explanation']}")
    else:
        print(f"    {col('Model not available', YELLOW)}: {rec.get('explanation','')}")
    print()

    # Conditions
    cond      = data.get("conditions", {})
    composite = cond.get("composite", {})
    score     = composite.get("score", 0)
    label     = composite.get("label", "--")
    cats      = cond.get("categories", [])
    print(col("  Conditions Index:", BOLD))
    print(f"    {col(label, conditions_color(score))} {col(f'({score:+.3f})', conditions_color(score))}")
    if cats:
        cat_str = "   ".join(
            f"{c['name'][:4]}: {col(c['label'], catcol(c['status']))}"
            for c in cats
        )
        print(f"    {cat_str}")
    print()

    # Regime
    reg    = data.get("regime", {})
    regime = reg.get("regime", "--")
    print(col("  Regime:", BOLD))
    print(f"    {col(regime, regime_color(regime))}")
    if reg.get("reason"):
        print(f"    {reg['reason']}")
    print()

    # Top analogues
    analogs = data.get("analogues", [])
    if analogs:
        print(col("  Closest Historical Periods:", BOLD))
        for i, a in enumerate(analogs[:3]):
            rc = regime_color(a.get("regime", ""))
            print(f"    #{i+1}  {a['date'][:7]}  "
                  f"{col(a.get('regime','?'), rc):<20}  dist={a['distance']:.3f}")
    print()

    # Checks
    passes, fails = [], []
    results_for_table = {
        "name":      name.split("--")[0].strip(),
        "prob":      prob,
        "regime":    regime,
        "composite": score,
        "all_pass":  True,
    }

    def do_check(label, ok, detail=""):
        mark = col("PASS", GREEN) if ok else col("FAIL", RED)
        line = f"  [{mark}] {label}"
        if detail:
            line += f"  <- {detail}"
        (passes if ok else fails).append(line)
        if not ok:
            results_for_table["all_pass"] = False

    if "taylor_rate_min" in exp:
        do_check(f"Taylor Rate >= {exp['taylor_rate_min']:.1f}%",
                 tr >= exp["taylor_rate_min"], f"got {tr:.2f}%")
    if "taylor_rate_max" in exp:
        do_check(f"Taylor Rate <= {exp['taylor_rate_max']:.1f}%",
                 tr <= exp["taylor_rate_max"], f"got {tr:.2f}%")
    if "policy_gap_min" in exp:
        do_check(f"Policy gap >= {exp['policy_gap_min']:+.1f}pp (actual > Taylor)",
                 gap >= exp["policy_gap_min"], f"got {gap:+.2f}pp")
    if "policy_gap_max" in exp:
        do_check(f"Policy gap <= {exp['policy_gap_max']:+.1f}pp (actual < Taylor)",
                 gap <= exp["policy_gap_max"], f"got {gap:+.2f}pp")
    if "recession_min" in exp and prob is not None:
        do_check(f"Recession probability >= {exp['recession_min']*100:.0f}%",
                 prob >= exp["recession_min"], f"got {prob*100:.1f}%")
    if "recession_max" in exp and prob is not None:
        do_check(f"Recession probability <= {exp['recession_max']*100:.0f}%",
                 prob <= exp["recession_max"], f"got {prob*100:.1f}%")
    if "composite_min" in exp:
        do_check(f"Conditions composite >= {exp['composite_min']:+.2f}",
                 score >= exp["composite_min"], f"got {score:+.3f}")
    if "composite_max" in exp:
        do_check(f"Conditions composite <= {exp['composite_max']:+.2f}",
                 score <= exp["composite_max"], f"got {score:+.3f}")
    if "regime_ok" in exp:
        ok = regime in exp["regime_ok"]
        do_check(f"Regime in {{{', '.join(sorted(exp['regime_ok']))}}}",
                 ok, f"got '{regime}'")

    for line in passes: print(line)
    for line in fails:  print(line)

    total = len(passes) + len(fails)
    if total:
        n_pass = len(passes)
        sc = GREEN if n_pass == total else (YELLOW if n_pass >= total // 2 else RED)
        print(f"\n  {col(f'{n_pass}/{total} checks passed', sc)}")

    return results_for_table


# ---------------------------------------------------------------------------
# Summary table
# ---------------------------------------------------------------------------

def print_summary(rows: list):
    ordered_prefixes = ["Test 6", "Test 1", "Test 2", "Test 7", "Test 4", "Test 5"]
    ordered = []
    for prefix in ordered_prefixes:
        for r in rows:
            if r["name"].startswith(prefix):
                ordered.append(r)
                break

    print(f"\n\n{SEP2}")
    print(col("  ORDERING TABLE  (Goldilocks -> Soft Landing -> Tightening -> Stagflation -> 2008 -> COVID)", BOLD))
    print(SEP2)
    print(f"  {'Scenario':<28}  {'Recession Risk':>14}  {'Regime':<16}  {'Composite':>10}  Result")
    print(f"  {'-'*28}  {'-'*14}  {'-'*16}  {'-'*10}  {'-'*6}")

    prev_prob = -1.0
    ordering_ok = True
    for r in ordered:
        prob  = r["prob"]
        score = r["composite"]
        reg   = r["regime"]

        if prob is not None and prev_prob > prob + 0.05:
            ordering_ok = False
            order_flag = col("WRONG ORDER", RED)
        elif prob is None:
            order_flag = col("N/A", YELLOW)
        else:
            order_flag = col("OK", GREEN)

        prob_str  = f"{prob*100:.1f}%" if prob is not None else "N/A"
        pass_mark = col("PASS", GREEN) if r["all_pass"] else col("FAIL", RED)

        print(f"  {r['name']:<28}  {prob_str:>14}  "
              f"{col(reg, regime_color(reg)):<25}  "
              f"{col(f'{score:+.3f}', conditions_color(score)):>19}  "
              f"{pass_mark}  {order_flag}")

        if prob is not None:
            prev_prob = prob

    print(f"  {'-'*72}")
    verdict = col("Ordering consistent", GREEN) if ordering_ok else col("Ordering violation detected", RED)
    print(f"  {verdict}")

    n_pass = sum(1 for r in rows if r["all_pass"])
    total  = len(rows)
    oc = GREEN if n_pass == total else (YELLOW if n_pass >= total // 2 else RED)
    print(f"\n  {col(f'{n_pass}/{total} scenarios passed all checks', oc)}")
    print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Economic Compass simulator test suite")
    parser.add_argument("--url", default="http://localhost:8000",
                        help="API base URL (default: http://localhost:8000)")
    parser.add_argument("--scenario", type=int, default=None,
                        help="Run only this scenario number (1-based)")
    args = parser.parse_args()

    url = args.url.rstrip("/")

    try:
        requests.get(f"{url}/health", timeout=5)
    except Exception:
        print(col(f"\nCannot reach {url}/health. Start the API:", RED))
        print("  uvicorn api.main:app --reload --port 8000\n")
        sys.exit(1)

    print(col("\n  ECONOMIC COMPASS -- Simulator Test Suite", BOLD))
    print(f"  API: {url}  |  Scenarios: {len(SCENARIOS)}")

    to_run = SCENARIOS
    if args.scenario is not None:
        idx = args.scenario - 1
        if 0 <= idx < len(SCENARIOS):
            to_run = [SCENARIOS[idx]]
        else:
            print(col(f"Scenario {args.scenario} not found (valid: 1-{len(SCENARIOS)})", RED))
            sys.exit(1)

    summary_rows = []
    for scenario in to_run:
        data = run_scenario(url, scenario)
        if data is None:
            break
        summary_rows.append(print_scenario(scenario, data))

    if len(summary_rows) == len(SCENARIOS):
        print_summary(summary_rows)


if __name__ == "__main__":
    main()

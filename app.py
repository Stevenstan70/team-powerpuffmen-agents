"""
Powerpuffmen Research — Prototype dashboard.

Synthetic demo data only. No live market data or brokerage connection.
No AI agent connected. Rule-based summary only.
"""

import sys
import os

import streamlit as st

# ---------------------------------------------------------------------------
# Path setup — allow import of tools/ without installing the package
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.dirname(__file__))

from tools.powerpuffmen_basic_screen import powerpuffmen_basic_screen  # noqa: E402

_screen_fn = powerpuffmen_basic_screen.fn

# ---------------------------------------------------------------------------
# Fictional company definitions (hardcoded, clearly synthetic)
# ---------------------------------------------------------------------------
# Three examples as required:
#   1. "Acme Galactic Ltd"   — passes all four rules
#   2. "Bluebird Ventures"   — fails operating cash flow (negative OCF)
#   3. "Crescent Peak Corp"  — employee count missing; other three rules pass

COMPANIES = {
    "Acme Galactic Ltd (all rules PASS)": {
        "description": (
            "A fictional mid-cap technology conglomerate headquartered on "
            "Planet Synthetix. All four screening inputs are available and "
            "within acceptable ranges."
        ),
        "inputs": {
            "market_cap_usd": 15_000_000_000.0,           # USD 15 B  → within 2B–100B ✓
            "close_price_usd": 42.50,                      # USD 42.50 → >= 10 ✓
            "operating_cash_flow_ttm_usd": 850_000_000.0,  # positive ✓
            "employee_count": 3_200.0,                     # 3,200     → >= 20 ✓
        },
    },
    "Bluebird Ventures (OCF FAIL)": {
        "description": (
            "A fictional early-stage aerospace firm. Market cap, price, and "
            "headcount all pass, but the company is burning cash and reports "
            "a negative trailing-12-month operating cash flow."
        ),
        "inputs": {
            "market_cap_usd": 5_500_000_000.0,             # USD 5.5 B → within 2B–100B ✓
            "close_price_usd": 18.75,                       # USD 18.75 → >= 10 ✓
            "operating_cash_flow_ttm_usd": -120_000_000.0,  # negative → FAIL ✗
            "employee_count": 870.0,                        # 870       → >= 20 ✓
        },
    },
    "Crescent Peak Corp (employees UNVERIFIED)": {
        "description": (
            "A fictional pharmaceutical holding company. Three inputs are "
            "available and passing, but employee headcount data was not "
            "disclosed in the most recent filing."
        ),
        "inputs": {
            "market_cap_usd": 8_200_000_000.0,            # USD 8.2 B → within 2B–100B ✓
            "close_price_usd": 67.00,                      # USD 67.00 → >= 10 ✓
            "operating_cash_flow_ttm_usd": 310_000_000.0,  # positive ✓
            "employee_count": None,                        # not disclosed → UNVERIFIED
        },
    },
}

# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

_STATUS_COLOURS = {
    "PASS": "#1a7f37",
    "FAIL": "#cf222e",
    "UNVERIFIED": "#9a6700",
}

_AGGREGATE_LABELS = {
    "PASS": "✅ PASS",
    "FAIL": "❌ FAIL",
    "UNVERIFIED": "⚠️ UNVERIFIED",
}

# Human-readable labels for each rule key
_RULE_LABELS = {
    "market_cap_range": "Market Cap Range",
    "min_close_price": "Min Close Price",
    "positive_operating_cash_flow": "Positive Operating Cash Flow",
    "min_employee_count": "Min Employee Count",
}

# Which inputs are USD amounts vs. employee counts
_USD_INPUTS = {"market_cap_usd", "close_price_usd", "operating_cash_flow_ttm_usd"}
_INT_INPUTS = {"employee_count"}


def _fmt_usd(v) -> str:
    """Format a USD float for display; None → 'Unknown'."""
    if v is None:
        return "Unknown"
    if abs(v) >= 1_000_000_000:
        return f"${v / 1_000_000_000:,.2f} B"
    if abs(v) >= 1_000_000:
        return f"${v / 1_000_000:,.2f} M"
    return f"${v:,.2f}"


def _fmt_employees(v) -> str:
    """Format an employee count; None → 'Unknown'."""
    if v is None:
        return "Unknown"
    return f"{int(v):,}"


def _fmt_input(key: str, v) -> str:
    """Format a screening input by key for the inputs summary."""
    if key in _USD_INPUTS:
        return _fmt_usd(v)
    if key in _INT_INPUTS:
        return _fmt_employees(v)
    return str(v) if v is not None else "Unknown"


def _fmt_observed(rule_name: str, v) -> str:
    """Format a rule's observed_value based on which rule it is."""
    if v is None:
        return "Unknown"
    if rule_name in ("market_cap_range", "positive_operating_cash_flow"):
        return _fmt_usd(v)
    if rule_name == "min_close_price":
        return f"${v:,.2f}"
    if rule_name == "min_employee_count":
        return _fmt_employees(v)
    return str(v)


def _status_icon(status: str) -> str:
    return {"PASS": "✅ PASS", "FAIL": "❌ FAIL", "UNVERIFIED": "⚠️ UNVERIFIED"}.get(status, status)


def _build_summary(company_name: str, result: dict) -> str:
    """Return a deterministic plain-language explanation of the screen result."""
    lines = []
    agg = result["basic_screen_status"]
    lines.append(f"**Screen result for {company_name}: {_AGGREGATE_LABELS[agg]}**\n")

    for r in result["rules"]:
        status = r["status"]
        name = _RULE_LABELS.get(r["rule_name"], r["rule_name"].replace("_", " ").title())
        obs = _fmt_observed(r["rule_name"], r["observed_value"])
        threshold = r["threshold"]
        explanation = r["explanation"]

        if status == "PASS":
            bullet = f"✅ **{name}** — {explanation} (observed: {obs}; threshold: {threshold})"
        elif status == "FAIL":
            bullet = f"❌ **{name}** — {explanation} (observed: {obs}; threshold: {threshold})"
        else:  # UNVERIFIED
            bullet = (
                f"⚠️ **{name}** — Data not available (observed: {obs}; "
                f"threshold: {threshold}). {explanation}"
            )
        lines.append(bullet)

    lines.append("")
    lines.append(f"*{result['scope_note']}*")
    return "\n\n".join(lines)


# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Powerpuffmen Research — Prototype",
    layout="wide",
)

# ---------------------------------------------------------------------------
# Persistent synthetic-data warning  (always visible, at very top)
# ---------------------------------------------------------------------------
st.warning(
    "⚠️ **SYNTHETIC DEMO DATA** — no live market data or brokerage connection.",
    icon=None,
)

# ---------------------------------------------------------------------------
# Title
# ---------------------------------------------------------------------------
st.title("Powerpuffmen Research — Prototype")

# ---------------------------------------------------------------------------
# Sidebar: company selector
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("Company selector")
    company_name = st.selectbox(
        "Select a fictional company",
        options=list(COMPANIES.keys()),
        key="company_select",
    )
    st.caption(
        "These companies are entirely fictional and exist only "
        "to demonstrate the screening tool."
    )

company = COMPANIES[company_name]
inputs = company["inputs"]

# Session-state key is scoped to the selected company so that switching
# companies never surfaces the previous company's result.
state_key = f"result_{company_name}"

# ---------------------------------------------------------------------------
# Company header + aggregate status (above the two-column split)
# ---------------------------------------------------------------------------
st.subheader(company_name)
st.markdown(company["description"])

if state_key in st.session_state:
    agg = st.session_state[state_key]["basic_screen_status"]
    colour = _STATUS_COLOURS[agg]
    st.markdown(
        f'<p style="font-size:1.25em;font-weight:700;color:{colour};margin-bottom:0.25em;">'
        f"Aggregate screen status: {_AGGREGATE_LABELS[agg]}</p>",
        unsafe_allow_html=True,
    )
else:
    st.caption("Aggregate status: — (run the screen to see results)")

st.divider()

# ---------------------------------------------------------------------------
# Two main columns
# ---------------------------------------------------------------------------
left_col, right_col = st.columns([1, 1], gap="large")

# ── LEFT: screening inputs, run button, compact rule table ──────────────────
with left_col:
    st.markdown("#### Screening inputs")

    _INPUT_LABELS = {
        "market_cap_usd": "Market Cap (USD)",
        "close_price_usd": "Close Price (USD)",
        "operating_cash_flow_ttm_usd": "Operating Cash Flow TTM (USD)",
        "employee_count": "Employee Count",
    }
    for key, label in _INPUT_LABELS.items():
        st.markdown(f"- **{label}:** {_fmt_input(key, inputs[key])}")

    st.markdown("")
    run_pressed = st.button("▶ Run basic screen", type="primary", key="run_btn")

    if run_pressed:
        st.session_state[state_key] = _screen_fn(**inputs)

    if state_key in st.session_state:
        result = st.session_state[state_key]

        st.markdown("#### Rule results")

        # ── Compact rule table ──────────────────────────────────────────────
        table_rows = []
        for r in result["rules"]:
            table_rows.append({
                "Rule": _RULE_LABELS.get(r["rule_name"], r["rule_name"]),
                "Observed value": _fmt_observed(r["rule_name"], r["observed_value"]),
                "Required threshold": r["threshold"],
                "Status": _status_icon(r["status"]),
            })

        st.dataframe(
            table_rows,
            width="stretch",
            hide_index=True,
        )

        # ── Collapsed expander: per-rule explanations ───────────────────────
        with st.expander("Rule explanations", expanded=False):
            for r in result["rules"]:
                name = _RULE_LABELS.get(r["rule_name"], r["rule_name"])
                icon = {"PASS": "✅", "FAIL": "❌", "UNVERIFIED": "⚠️"}.get(r["status"], "")
                st.markdown(f"**{icon} {name}**")
                st.markdown(f"&nbsp;&nbsp;&nbsp;{r['explanation']}")
                st.markdown(
                    f"&nbsp;&nbsp;&nbsp;Observed: `{_fmt_observed(r['rule_name'], r['observed_value'])}`  "
                    f"— Threshold: `{r['threshold']}`"
                )
                st.markdown("---")

        # ── Scope notice ────────────────────────────────────────────────────
        st.info(
            "⚠️ Only four rules evaluated. Not full investment eligibility "
            "or an investment recommendation."
        )

# ── RIGHT: rule-based research summary ─────────────────────────────────────
with right_col:
    st.markdown("#### Research summary")
    st.caption("Rule-based summary — AI agent not connected")

    if state_key in st.session_state:
        result = st.session_state[state_key]
        st.markdown(_build_summary(company_name, result))
        st.markdown("---")
        st.markdown(
            "_This summary is a deterministic explanation of the rule "
            "results above. No news, valuations, price history, or forecasts "
            "are generated. No AI model was consulted._"
        )
    else:
        st.markdown(
            "_Press **▶ Run basic screen** to generate the rule-based summary._"
        )

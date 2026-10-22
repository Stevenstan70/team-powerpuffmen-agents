"""
PPM Finance — Investment Screening & Monitoring Prototype.

STATE: session-only (st.session_state).  Nothing persists across browser
refreshes.  This limitation is labelled throughout the UI.

LIVE/DEMO/NOT-CONNECTED summary (also shown in the About tab):
  • Screening criteria evaluation — LIVE via powerpuffmen_basic_screen.fn
    when inputs are provided; DEMO fixtures when no inputs are supplied.
  • AI agent analysis            — NOT CONNECTED (stub returns clear error).
  • Moomoo / watchlist import    — NOT CONNECTED (UI integration point only).
  • Tracked companies / approval — session-only state, no external write.

No live market data, brokerage connection, or AI-generated output is
displayed without an explicit label.
"""

from __future__ import annotations

import sys
import os
import copy
import datetime
import html
import math
from typing import Any, TypedDict

import altair as alt
import pandas as pd
import streamlit as st

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.dirname(__file__))

from frontend.adapter import (  # pyright: ignore[reportImplicitRelativeImport]
    evaluate_company,
    analyse_company,
    check_for_changes,
    get_simulated_change_scenario,
    validate_ticker,
    resolve_ticker,
    fetch_moomoo_inputs,
)

# ── Backward-compatible: keep existing screen function accessible ────────────
from tools.powerpuffmen_basic_screen import powerpuffmen_basic_screen  # noqa: E402
_screen_fn = powerpuffmen_basic_screen.fn

# ---------------------------------------------------------------------------
# Page config  (must be first Streamlit call)
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="PPM Finance — Investment Research",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
    <style>
    :root {
        --ppm-bg: #0b1220;
        --ppm-surface: #111c2e;
        --ppm-surface-raised: #17243a;
        --ppm-ink: #e6edf7;
        --ppm-muted: #a0aec0;
        --ppm-rule: #2b3b52;
        --ppm-primary: #35b8ff;
        --ppm-green: #35d07f;
        --ppm-amber: #f2c66d;
        --ppm-red: #ff7185;
    }
    html, body, [data-testid="stAppViewContainer"] {
        background: var(--ppm-bg); color: var(--ppm-ink);
    }
    [data-testid="stHeader"] { background: var(--ppm-bg); }
    [data-testid="stAppViewContainer"] [data-testid="stMarkdownContainer"] { color: var(--ppm-ink); }
    .main .block-container { max-width: 1560px; padding: .65rem 2.5rem 4rem; }
    .ppm-skip-link {
        clip: rect(0, 0, 0, 0); clip-path: inset(50%); height: 1px; overflow: hidden;
        position: fixed; left: 1rem; top: .5rem; white-space: nowrap; width: 1px; z-index: 2000;
    }
    .ppm-skip-link:focus {
        background: #e6edf7; border-radius: 4px; clip: auto; clip-path: none;
        color: #0b1220; height: auto; padding: .7rem 1rem; width: auto;
    }
    .ppm-masthead {
        align-items: center; background: var(--ppm-bg); border-bottom: 1px solid var(--ppm-rule);
        color: var(--ppm-ink);
        display: flex; justify-content: space-between; gap: 1rem;
        margin: 0 0 .5rem; padding: .85rem 0 1rem;
    }
    .ppm-brand { color: #f8fafc; font-size: 1.35rem; font-weight: 740; letter-spacing: -.03em; }
    .ppm-tagline { color: var(--ppm-muted); font-size: .85rem; margin-top: .15rem; }
    .ppm-env {
        background: #172d2a; border: 1px solid #285845;
        border-radius: 4px; color: #86e3b1; font-size: .7rem;
        font-weight: 750; letter-spacing: .08em; padding: .45rem .7rem;
        text-transform: uppercase; white-space: nowrap;
    }
    [data-testid="stTabs"] > div:first-child {
        background: var(--ppm-bg); border-bottom: 1px solid var(--ppm-rule);
    }
    [data-testid="stTabs"] [role="tablist"] { gap: 1.1rem; overflow-x: auto; }
    [data-testid="stTabs"] button[role="tab"] {
        align-items: center;
        background: transparent; border: 0; border-bottom: 2px solid transparent;
        border-radius: 0; color: var(--ppm-muted); font-size: .9rem;
        display: inline-flex; flex: 0 0 auto; font-weight: 620;
        gap: .55rem; margin-right: 0;
        min-height: 3rem; padding: .7rem .8rem; white-space: nowrap;
    }
    [data-testid="stTabs"] button[role="tab"]::before {
        background-color: currentColor; content: "";
        height: 1rem; width: 1rem; flex: 0 0 1rem;
        -webkit-mask-position: center; -webkit-mask-repeat: no-repeat; -webkit-mask-size: contain;
        mask-position: center; mask-repeat: no-repeat; mask-size: contain;
    }
    [data-testid="stTabs"] button[role="tab"]:nth-child(1)::before {
        -webkit-mask-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='white' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'%3E%3Ccircle cx='10.8' cy='10.8' r='6.5'/%3E%3Cpath d='m16 16 4.5 4.5'/%3E%3C/svg%3E");
        mask-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='white' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'%3E%3Ccircle cx='10.8' cy='10.8' r='6.5'/%3E%3Cpath d='m16 16 4.5 4.5'/%3E%3C/svg%3E");
    }
    [data-testid="stTabs"] button[role="tab"]:nth-child(2)::before {
        -webkit-mask-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='white' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'%3E%3Crect x='3' y='7' width='18' height='13' rx='2'/%3E%3Cpath d='M8 7V5a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2M3 12h18m-11 0v2h4v-2'/%3E%3C/svg%3E");
        mask-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='white' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'%3E%3Crect x='3' y='7' width='18' height='13' rx='2'/%3E%3Cpath d='M8 7V5a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2M3 12h18m-11 0v2h4v-2'/%3E%3C/svg%3E");
    }
    [data-testid="stTabs"] button[role="tab"]:nth-child(3)::before {
        -webkit-mask-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='white' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M12 22s8-4 8-11V5l-8-3-8 3v6c0 7 8 11 8 11Z'/%3E%3Cpath d='m9 12 2 2 4-4'/%3E%3C/svg%3E");
        mask-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='white' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M12 22s8-4 8-11V5l-8-3-8 3v6c0 7 8 11 8 11Z'/%3E%3Cpath d='m9 12 2 2 4-4'/%3E%3C/svg%3E");
    }
    [data-testid="stTabs"] button[role="tab"]:nth-child(4)::before {
        -webkit-mask-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='white' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'%3E%3Ccircle cx='12' cy='12' r='10'/%3E%3Cpath d='M12 11v5m0-8h.01'/%3E%3C/svg%3E");
        mask-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='white' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'%3E%3Ccircle cx='12' cy='12' r='10'/%3E%3Cpath d='M12 11v5m0-8h.01'/%3E%3C/svg%3E");
    }
    [data-testid="stTabs"] button[role="tab"][aria-selected="true"] {
        background: transparent; border: 0; border-bottom: 2px solid var(--ppm-primary);
        color: #f8fafc;
    }
    [data-testid="stTabs"] [data-baseweb="tab-highlight"] { display: none; }
    [data-testid="stTabs"] button[role="tab"][aria-selected="false"]:hover {
        background: var(--ppm-surface); color: #f8fafc;
    }
    [data-testid="stTabs"] [role="tabpanel"] {
        margin-inline: auto; max-width: 1440px; width: 100%;
    }
    [data-testid="stButton"] button, [data-testid="stFormSubmitButton"] button {
        background: var(--ppm-surface-raised); border: 1px solid var(--ppm-primary);
        border-radius: 5px; color: var(--ppm-ink); font-weight: 650; min-height: 2.6rem;
        transition: background-color 120ms ease, border-color 120ms ease, box-shadow 120ms ease;
    }
    [data-testid="stButton"] button:hover, [data-testid="stFormSubmitButton"] button:hover {
        border-color: var(--ppm-primary); color: #ffffff;
    }
    [data-testid="stFormSubmitButton"] button[kind="primary"],
    [data-testid="stButton"] button[kind="primary"] {
        background: var(--ppm-primary); border-color: var(--ppm-primary); color: var(--ppm-bg);
        box-shadow: 0 1px 4px rgba(53, 184, 255, .2);
    }
    [data-testid="stFormSubmitButton"] button[kind="primary"]:hover,
    [data-testid="stButton"] button[kind="primary"]:hover {
        background: #e6edf7; border-color: #e6edf7; color: var(--ppm-bg);
    }
    [data-testid="stVerticalBlock"] { gap: .65rem; }
    [data-testid="stButton"] button:not([kind="primary"]):hover {
        background: var(--ppm-surface); border-color: var(--ppm-primary);
    }
    [data-testid="stTextInput"] div[data-baseweb="input"] {
        background: #101a2a; border: 1px solid #3b4e68;
        border-radius: 5px; box-shadow: none;
    }
    [data-testid="stTextInput"] div[data-baseweb="input"]:focus-within {
        border-color: var(--ppm-primary);
        box-shadow: 0 0 0 3px rgba(53, 184, 255, .18);
    }
    [data-testid="stTextInput"] input {
        background: #101a2a; border-radius: 5px; color: var(--ppm-ink);
        padding: .65rem .8rem;
    }
    [data-testid="stTextInput"] input::placeholder { color: #93a4b8; opacity: 1; }
    [data-testid="stTextInput"] input { caret-color: var(--ppm-primary); }
    [data-testid="stDataFrame"], [data-testid="stVerticalBlockBorderWrapper"] {
        border: 1px solid var(--ppm-rule); border-radius: 5px;
    }
    [data-testid="stAlert"] {
        background: #132033 !important; border: 1px solid var(--ppm-rule);
        border-radius: 5px; color: var(--ppm-ink) !important; padding: .55rem .8rem;
    }
    [data-testid="stAlert"] [data-baseweb="notification"],
    [data-testid="stAlert"] [role="alert"] {
        background: #132033 !important; border: 0 !important; box-shadow: none !important;
    }
    [data-testid="stAlert"] [data-testid="stMarkdownContainer"],
    [data-testid="stAlert"] [data-testid="stMarkdownContainer"] * {
        color: var(--ppm-ink) !important;
    }
    [data-testid="stAlert"] [data-testid="stMarkdownContainer"] strong {
        color: var(--ppm-amber) !important;
    }
    [data-testid="stExpander"] {
        background: var(--ppm-surface); border: 1px solid var(--ppm-rule);
        border-radius: 5px;
    }
    button:focus-visible, input:focus-visible, [role="tab"]:focus-visible {
        outline: 3px solid rgba(53, 184, 255, .65) !important; outline-offset: 2px !important;
    }
    [data-testid="stDivider"] { color: var(--ppm-rule); }
    [data-testid="stTextInput"] label, [data-testid="stSelectbox"] label { color: #d7e1ee !important; }
    .ppm-screen-intro { margin: .8rem 0 .55rem; }
    .ppm-screen-intro h1 {
        color: #f8fafc; font-size: 1.7rem; font-weight: 680;
        letter-spacing: -.035em; line-height: 1.15; margin: 0;
    }
    .ppm-screen-intro p { color: #a0aec0; font-size: .93rem; margin: .35rem 0 0; }
    .ppm-company-line {
        align-items: baseline; display: flex; flex-wrap: wrap; gap: .55rem;
        margin: 1rem 0 .65rem;
    }
    .ppm-company-line strong { color: #f8fafc; font-size: 1.35rem; font-weight: 680; }
    .ppm-company-line span { color: var(--ppm-muted); font-size: .9rem; }
    .ppm-source-tag {
        color: #86e3b1; font-size: .7rem; font-weight: 700;
        letter-spacing: .07em; margin-left: auto; text-transform: uppercase;
    }
    .ppm-metric-grid {
        background: var(--ppm-rule); border: 1px solid var(--ppm-rule);
        display: grid; grid-template-columns: repeat(4, minmax(0, 1fr));
        gap: 1px; margin: 0 0 1.15rem;
    }
    .ppm-metric { background: var(--ppm-surface); min-width: 0; padding: .7rem .85rem; }
    .ppm-metric-label {
        color: var(--ppm-muted); font-size: .69rem; letter-spacing: .075em;
        text-transform: uppercase;
    }
    .ppm-metric-value {
        color: #f5f8fc; font-size: 1.25rem; font-variant-numeric: tabular-nums;
        font-weight: 650; margin: .38rem 0 .2rem;
    }
    .ppm-metric-state { font-size: .72rem; font-weight: 650; }
    .ppm-history-panel {
        background: var(--ppm-surface); border: 1px solid var(--ppm-rule);
        border-radius: 5px; margin: .2rem 0 1.15rem; padding: 1rem 1.15rem .8rem;
    }
    .ppm-history-heading {
        align-items: center; display: flex; flex-wrap: wrap; gap: .8rem;
        justify-content: space-between; margin-bottom: .3rem;
    }
    .ppm-history-heading strong { color: #f1f5fa; font-size: 1rem; font-weight: 650; }
    .ppm-history-note { color: var(--ppm-muted); font-size: .78rem; }
    .ppm-demo-tag {
        color: var(--ppm-amber); font-size: .68rem; font-weight: 700;
        letter-spacing: .055em;
    }
    .ppm-history-empty {
        align-items: center; border-top: 1px solid var(--ppm-rule);
        color: var(--ppm-muted); display: flex; min-height: 6.5rem;
        padding: 1rem .2rem;
    }
    .ppm-history-table { border-collapse: collapse; font-size: .8rem; margin-top: .25rem; width: 100%; }
    .ppm-history-table th {
        border-bottom: 1px solid var(--ppm-rule); color: var(--ppm-muted);
        font-size: .68rem; font-weight: 600; letter-spacing: .055em;
        padding: .55rem .4rem; text-align: left; text-transform: uppercase;
    }
    .ppm-history-table td {
        border-bottom: 1px solid #233349; color: #e6edf7;
        font-variant-numeric: tabular-nums; padding: .7rem .4rem;
    }
    .ppm-history-table td:last-child { text-align: right; }
    .ppm-criteria-title { color: #f1f5fa; font-size: 1rem; font-weight: 650; margin: .4rem 0 .75rem; }
    .ppm-demo-label { color: var(--ppm-amber); font-size: .7rem; font-weight: 700; }
    ::selection { background: rgba(53, 184, 255, .24); color: #ffffff; }
    @media (max-width: 760px) {
        .main .block-container { padding: .5rem 1rem 2.5rem; }
        .ppm-masthead { align-items: flex-start; flex-direction: column; padding: .7rem 0 .85rem; }
        .ppm-env { white-space: normal; }
        .ppm-metric-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
        [data-testid="stVerticalBlock"] { gap: .55rem; }
        [data-testid="stTabs"] button[role="tab"] { padding: .65rem .7rem; }
    }
    @media (prefers-reduced-motion: reduce) {
        *, *::before, *::after { scroll-behavior: auto !important; transition-duration: .01ms !important; }
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Session-state bootstrap
# ---------------------------------------------------------------------------
_DEFAULTS: dict[str, Any] = {
    # Company selection
    "selected_ticker": "",
    # Validated + resolved company identity (cleared on ticker change)
    # None | { "connected": bool, "found": bool, "ticker": str,
    #           "moomoo_code": str|None, "company_name": str|None, ... }
    "resolved_company": None,
    # Current evaluation result (cleared on ticker change)
    "current_eval": None,
    # Analysis result (cleared on ticker change)
    "current_analysis": None,
    # Tracked companies: { ticker: { "saved_at": str, "evaluation": dict } }
    "tracked": {},
    # Pending approval: None | { "ticker": str, "eval_id": str, "change_result": dict }
    "pending_approval": None,
    # Action history: [ { "action": str, "ticker": str, ... } ]
    "action_log": [],
    # Qualified list: set of tickers the user considers qualified
    "qualified_list": set(),
    # Needs review list: set of tickers flagged for review
    "needs_review_list": set(),
    # Demo scenario state: None | "loaded" | "checked"
    "sim_scenario_state": None,
    # Simulated change data
    "sim_baseline": None,
    "sim_changed": None,
}
for _k, _v in _DEFAULTS.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v

# ---------------------------------------------------------------------------
# Constants / helpers
# ---------------------------------------------------------------------------

_STATUS_COLOURS = {"pass": "#35d07f", "fail": "#ff7185", "unknown": "#f2c66d"}
_STATUS_LABELS = {"pass": "PASS", "fail": "FAIL", "unknown": "UNKNOWN"}
_CHANGE_LABELS = {
    "status_transition": "STATUS CHANGE",
    "value_changed": "VALUE CHANGE",
    "data_unavailable": "DATA UNAVAILABLE",
    "criteria_changed": "CRITERIA UPDATE",
}

class _HistoryMetric(TypedDict):
    label: str
    criterion_id: str
    divisor: float
    axis_title: str
    format: str


_HISTORY_METRICS: dict[str, _HistoryMetric] = {
    "market_cap_usd": {
        "label": "Market capitalisation",
        "criterion_id": "market_cap_range",
        "divisor": 1_000_000_000,
        "axis_title": "Market capitalisation (USD billions)",
        "format": "$,.2f",
    },
    "close_price_usd": {
        "label": "Closing share price",
        "criterion_id": "min_close_price",
        "divisor": 1,
        "axis_title": "Closing share price (USD)",
        "format": "$,.2f",
    },
    "operating_cash_flow_ttm_usd": {
        "label": "Operating cash flow (TTM)",
        "criterion_id": "positive_operating_cash_flow",
        "divisor": 1_000_000,
        "axis_title": "Operating cash flow (USD millions)",
        "format": ",.1f",
    },
    "employee_count": {
        "label": "Employee count",
        "criterion_id": "min_employee_count",
        "divisor": 1,
        "axis_title": "Employees",
        "format": ",.0f",
    },
}
_DEMO_HISTORY_YEARS = (2021, 2022, 2023, 2024, 2025)
_DEMO_HISTORY_FACTORS = {
    "ACME": (0.58, 0.67, 0.78, 0.89, 1.0),
    "BLUE": (0.78, 0.88, 0.76, 0.92, 1.0),
    "CRST": (0.62, 0.73, 0.82, 0.91, 1.0),
    "SMCHG": (0.65, 0.76, 0.84, 0.92, 1.0),
}


def _colour_status(status: str) -> str:
    c = _STATUS_COLOURS.get(status, "#a0aec0")
    label = _STATUS_LABELS.get(status, status.upper())
    return f'<span style="color:{c};font-weight:700;">{label}</span>'


def _clear_company_state():
    """Clear analysis, resolved identity, and pending approval when ticker changes."""
    st.session_state["resolved_company"] = None
    st.session_state["current_eval"] = None
    st.session_state["current_analysis"] = None
    st.session_state["pending_approval"] = None


def _sync_ticker_input() -> None:
    """Commit the ticker input before the next Streamlit script rerun."""
    ticker = str(st.session_state.get("ticker_text_input", "")).strip().upper()
    if ticker != st.session_state["selected_ticker"]:
        st.session_state["selected_ticker"] = ticker
        _clear_company_state()


def _select_demo_ticker(ticker: str) -> None:
    """Load a named demo fixture and keep the ticker input in sync."""
    st.session_state["selected_ticker"] = ticker
    st.session_state["ticker_text_input"] = ticker
    _clear_company_state()
    evaluation = evaluate_company(ticker, None, demo_override=ticker)
    st.session_state["resolved_company"] = {
        "connected": False,
        "found": True,
        "ticker": ticker,
        "moomoo_code": None,
        "company_name": evaluation.get("company_name", ticker),
        "sec_type": "DEMO",
        "error": None,
    }
    st.session_state["current_eval"] = evaluation
    st.session_state["current_analysis"] = {
        "connected": False,
        "demo": True,
        "content": _build_demo_research_brief(ticker, evaluation),
        "error": None,
    }


def _build_demo_research_brief(ticker: str, evaluation: dict[str, Any]) -> str:
    """Create a transparent rule-based sample brief from the selected fixture."""
    criteria = evaluation.get("criteria", [])
    if not criteria:
        return "The demo fixture did not return screening criteria."

    status_counts = {
        status: sum(1 for criterion in criteria if criterion.get("status") == status)
        for status in ("pass", "fail", "unknown")
    }
    lines = [
        f"**{ticker} screening summary**",
        (
            f"{status_counts['pass']} criteria pass, "
            f"{status_counts['fail']} fail, and "
            f"{status_counts['unknown']} are unknown."
        ),
    ]
    for criterion in criteria:
        observed = criterion.get("observed_fmt") or "Unknown / unavailable"
        lines.append(
            f"- **{_STATUS_LABELS.get(criterion.get('status', 'unknown'), 'UNKNOWN')} · "
            f"{criterion.get('label', 'Criterion')}** — observed {observed}; "
            f"threshold: {criterion.get('threshold', 'not provided')}."
        )
    lines.append(
        "This is a deterministic demonstration generated from the synthetic fixture, "
        "not an AI or IBM watsonx Orchestrate response."
    )
    return "\n\n".join(lines)


def _eval_id(evaluation: dict[str, Any]) -> str:
    """Stable string identity for an evaluation (ticker + timestamp)."""
    return f"{evaluation.get('ticker','')}@{evaluation.get('data_timestamp','')}"


def _log_action(action: str, ticker: str, detail: dict[str, Any] | None = None):
    entry = {
        "action": action,
        "ticker": ticker,
        "timestamp": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        **(detail or {}),
    }
    st.session_state["action_log"].append(entry)


def _history_rows(
    evaluation: dict[str, Any], ticker: str, metric_key: str
) -> list[dict[str, int | float]]:
    """Return verified live history or clearly synthetic demo points."""
    metric = _HISTORY_METRICS[metric_key]
    if evaluation.get("mode") == "demo":
        criteria = evaluation.get("criteria", [])
        criterion = next(
            (item for item in criteria if item.get("id") == metric["criterion_id"]),
            None,
        )
        observed = criterion.get("observed_value") if criterion else None
        if not isinstance(observed, (int, float)) or isinstance(observed, bool):
            return []
        factors = _DEMO_HISTORY_FACTORS.get(ticker.upper())
        if factors is None:
            return []
        return [
            {
                "year": year,
                "value": int(round(observed * factor))
                if metric_key == "employee_count"
                else observed * factor / metric["divisor"],
            }
            for year, factor in zip(_DEMO_HISTORY_YEARS, factors)
        ]

    historical_data = evaluation.get("historical_data")
    if not isinstance(historical_data, dict):
        return []
    series = historical_data.get(metric_key)
    if not isinstance(series, list):
        return []
    rows: list[dict[str, int | float]] = []
    for point in series:
        if not isinstance(point, dict):
            continue
        year = point.get("year")
        value = point.get("value")
        if (
            isinstance(year, int)
            and not isinstance(year, bool)
            and isinstance(value, (int, float))
            and not isinstance(value, bool)
            and math.isfinite(value)
        ):
            if metric_key == "employee_count":
                if not float(value).is_integer():
                    continue
                value = int(value)
                scaled_value: int | float = value
            else:
                scaled_value = value / metric["divisor"]
            rows.append({"year": year, "value": scaled_value})
    return rows


def _format_history_value(value: int | float, metric_key: str) -> str:
    if metric_key == "employee_count":
        return f"{int(value):,}"
    if metric_key == "market_cap_usd":
        return f"${value:,.2f}B"
    if metric_key == "operating_cash_flow_ttm_usd":
        return f"${value:,.1f}M"
    return f"${value:,.2f}"


def _render_metric_strip(evaluation: dict[str, Any]) -> None:
    criteria = {item.get("id"): item for item in evaluation.get("criteria", [])}
    cards: list[str] = []
    for metric_key, metric in _HISTORY_METRICS.items():
        criterion = criteria.get(metric["criterion_id"], {})
        status = str(criterion.get("status", "unknown")).lower()
        status_color = _STATUS_COLOURS.get(status, _STATUS_COLOURS["unknown"])
        observed = criterion.get("observed_fmt")
        value = observed if observed is not None else "Unknown"
        cards.append(
            '<div class="ppm-metric">'
            f'<div class="ppm-metric-label">{html.escape(metric["label"])}</div>'
            f'<div class="ppm-metric-value">{html.escape(str(value))}</div>'
            f'<div class="ppm-metric-state" style="color:{status_color}">'
            f'{html.escape(_STATUS_LABELS.get(status, "UNKNOWN"))}'
            '</div></div>'
        )
    st.markdown(
        f'<div class="ppm-metric-grid">{"".join(cards)}</div>',
        unsafe_allow_html=True,
    )


def _render_history_empty_state() -> None:
    st.markdown(
        '<div class="ppm-history-heading">'
        '<strong>Historical Comparison</strong>'
        '<span class="ppm-history-note">Annual view · one screening metric</span>'
        '</div>',
        unsafe_allow_html=True,
    )
    chart_col, controls_col = st.columns([2.2, 1], gap="large")
    with controls_col:
        st.selectbox(
            "Y-axis metric",
            options=list(_HISTORY_METRICS),
            format_func=lambda key: f"{_HISTORY_METRICS[key]['label']} · {key}",
            key="history_metric",
        )
    with chart_col:
        st.markdown(
            '<div class="ppm-history-empty">'
            'Run a screen or choose a demo fixture to load the annual comparison.'
            '</div>',
            unsafe_allow_html=True,
        )


def _render_historical_comparison(evaluation: dict[str, Any], ticker: str) -> None:
    is_demo = evaluation.get("mode") == "demo"
    provenance = "SYNTHETIC · DEMO ONLY" if is_demo else "SOURCE-PROVIDED HISTORY"
    provenance_class = "ppm-demo-tag" if is_demo else "ppm-history-note"
    st.markdown(
        '<div class="ppm-history-heading">'
        '<div><strong>Historical Comparison</strong>'
        f'<div class="ppm-history-note">{html.escape(ticker)} · annual metric series</div></div>'
        f'<span class="{provenance_class}">'
        f'{"SYNTHETIC DEMO SERIES · NOT ACTUAL HISTORY" if is_demo else provenance}</span>'
        '</div>',
        unsafe_allow_html=True,
    )
    chart_col, metric_col = st.columns([2.2, 1], gap="large")
    with metric_col:
        metric_key = st.selectbox(
            "Y-axis metric",
            options=list(_HISTORY_METRICS),
            format_func=lambda key: f"{_HISTORY_METRICS[key]['label']} · {key}",
            key="history_metric",
        )
    metric = _HISTORY_METRICS[metric_key]
    rows = _history_rows(evaluation, ticker, metric_key)

    with chart_col:
        if not rows:
            message = (
                "This fixture has no value for the selected metric; no annual sample is generated."
                if is_demo
                else "Annual history is unavailable. Moomoo currently supplies snapshot and profile data, not verified annual series."
            )
            st.markdown(
                f'<div class="ppm-history-empty">{html.escape(message)}</div>',
                unsafe_allow_html=True,
            )
        else:
            frame = pd.DataFrame(rows)
            x_axis = alt.X("year:O", title="Year", axis=alt.Axis(labelAngle=0))
            y_axis = alt.Y(
                "value:Q",
                title=metric["axis_title"],
                axis=alt.Axis(
                    format=metric["format"],
                    grid=True,
                    gridDash=[3, 4],
                    gridOpacity=0.62,
                    gridWidth=0.8,
                ),
                scale=alt.Scale(zero=False),
            )
            tooltip = [
                alt.Tooltip("year:O", title="Year"),
                alt.Tooltip("value:Q", title=metric["label"], format=metric["format"]),
            ]
            chart = (
                alt.layer(
                    alt.Chart(frame).mark_area(color="#35b8ff", opacity=0.12),
                    alt.Chart(frame).mark_line(
                        color="#35b8ff",
                        point=alt.OverlayMarkDef(filled=True, color="#35b8ff", size=68),
                        strokeWidth=2.5,
                    ),
                )
                .encode(x=x_axis, y=y_axis, tooltip=tooltip)
                .properties(height=245)
                .configure_view(stroke=None)
                .configure_axis(
                    labelColor="#b8c6d8",
                    titleColor="#e6edf7",
                    gridColor="#52647d",
                    domainColor="#52647d",
                    tickColor="#52647d",
                )
                .configure_title(color="#e6edf7")
            )
            st.altair_chart(chart, width="stretch")
            st.caption(
                "Synthetic demo values are illustrative, not reported company history."
                if is_demo
                else "Annual values shown only when provided by a verified source."
            )
    with metric_col:
        if rows:
            history_table_rows = "".join(
                "<tr>"
                f"<td>{row['year']}</td>"
                f"<td>{html.escape(_format_history_value(row['value'], metric_key))}</td>"
                "</tr>"
                for row in rows[-3:]
            )
            st.markdown(
                '<table class="ppm-history-table">'
                '<thead><tr><th>Year</th><th>Value</th></tr></thead>'
                f"<tbody>{history_table_rows}</tbody></table>",
                unsafe_allow_html=True,
            )


# ---------------------------------------------------------------------------
# Global header and primary navigation
# ---------------------------------------------------------------------------
st.markdown(
    """
    <a class="ppm-skip-link" href="#main-content">Skip to main content</a>
    <header class="ppm-masthead">
      <div><div class="ppm-brand">PPM Finance</div>
      <div class="ppm-tagline">Investment research, screening &amp; monitoring</div></div>
      <div class="ppm-env">PROTOTYPE · SYNTHETIC DEMO DATA</div>
    </header>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------
tab_screen, tab_track, tab_approve, tab_about = st.tabs([
    "Screen",
    "Tracked Companies",
    "Approval",
    "About / Demo",
])


# ===========================================================================
# TAB 1 — SCREEN
# ===========================================================================

with tab_screen:
    st.markdown('<div id="main-content" tabindex="-1"></div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="ppm-screen-intro">'
        '<h1>Screen a company</h1>'
        '<p>Apply clear, rules-based criteria and inspect the evidence behind each result.</p>'
        '</div>',
        unsafe_allow_html=True,
    )
    st.warning(
        "**SYNTHETIC DEMO DATA — PROTOTYPE.** Demo shortcuts use synthetic fixtures. "
        "Live Moomoo data appears only when the connection is available. "
        "Tracking is session-only; AI analysis and brokerage trading are not connected.",
        icon=None,
    )

    # ── Ticker input ─────────────────────────────────────────────────────────
    ticker_col, analyse_col = st.columns([4, 1], gap="medium", vertical_alignment="bottom")
    with ticker_col:
        ticker_input = (
            st.text_input(
            "Ticker symbol",
            placeholder="e.g. AAPL",
            key="ticker_text_input",
            on_change=_sync_ticker_input,
            help="Enter a single ticker symbol. Multi-word input like 'baba amskd' will be rejected.",
        )
            or ""
        ).strip().upper()
    with analyse_col:
        with st.form("analyse_form", border=False):
            analyse_pressed = st.form_submit_button(
                "Analyse",
                type="primary",
                use_container_width=True,
                help="Validate ticker, resolve company, fetch data, and run the screen.",
            )

    # ── Demo company shortcuts ────────────────────────────────────────────────
    st.caption(
        "**Quick demo screens** · fictional fixtures; no Moomoo connection required"
    )
    dc1, dc2, dc3, dc4 = st.columns(4)
    dc1.button(
        "ACME — All PASS", key="demo_acme", width="stretch",
        on_click=_select_demo_ticker, args=("ACME",),
    )
    dc2.button(
        "BLUE — OCF FAIL", key="demo_blue", width="stretch",
        on_click=_select_demo_ticker, args=("BLUE",),
    )
    dc3.button(
        "CRST — UNKNOWN", key="demo_crst", width="stretch",
        on_click=_select_demo_ticker, args=("CRST",),
    )
    dc4.button(
        "SMCHG — Sim Change", key="demo_smchg", width="stretch",
        on_click=_select_demo_ticker, args=("SMCHG",),
    )

    ticker = st.session_state["selected_ticker"]

    if not ticker:
        st.caption("Aggregate status: — (run the screen to see results)")
        st.caption("Rule-based summary — AI agent not connected")
        st.info("Enter a ticker above. Press **Analyse** or choose a quick demo screen.")
        with st.container(border=True):
            _render_history_empty_state()
        st.stop()

    # ── Inline ticker format validation (no network call) ────────────────────
    _DEMO_TICKERS = {"ACME", "BLUE", "CRST", "SMCHG"}
    _is_demo = ticker in _DEMO_TICKERS

    if not _is_demo:
        _val = validate_ticker(ticker)
        if not _val["valid"]:
            st.error(f"**Invalid ticker:** {_val['reason']}")
            st.caption("Aggregate status: — (run the screen to see results)")
            st.caption("Rule-based summary — AI agent not connected")
            st.stop()

    current_eval: dict[str, Any] | None = st.session_state["current_eval"]
    resolved: dict[str, Any] | None = st.session_state["resolved_company"]

    if analyse_pressed:
        st.session_state["current_analysis"] = None
        if _is_demo:
            # Demo path — no Moomoo calls
            with st.spinner("Loading demo fixture…"):
                result = evaluate_company(ticker, None, demo_override=ticker)
            st.session_state["resolved_company"] = {
                "connected": False, "found": True,
                "ticker": ticker,
                "moomoo_code": None,
                "company_name": result.get("company_name", ticker),
                "sec_type": "DEMO",
                "error": None,
            }
            st.session_state["current_eval"] = result
        else:
            # Live path: validate → resolve → fetch → screen
            with st.spinner("Resolving ticker…"):
                resolved_result = resolve_ticker(ticker)
            st.session_state["resolved_company"] = resolved_result

            if not resolved_result["connected"]:
                st.session_state["current_eval"] = None
            elif not resolved_result["found"]:
                st.session_state["current_eval"] = None
            else:
                moomoo_code = resolved_result["moomoo_code"]
                with st.spinner(f"Fetching data for {moomoo_code}…"):
                    fetch_result = fetch_moomoo_inputs(moomoo_code)
                if not fetch_result["connected"]:
                    # Connection failed — surface error, don't silently fall back
                    st.session_state["current_eval"] = {
                        "mode": "error",
                        "ticker": ticker,
                        "company_name": resolved_result["company_name"],
                        "currency": "USD",
                        "data_timestamp": fetch_result["data_timestamp"],
                        "is_live": False,
                        "criteria": [],
                        "aggregate_status": "unknown",
                        "scope_note": "",
                        "error": f"Moomoo data retrieval failed: {fetch_result['error']}",
                        "input_notes": fetch_result["input_notes"],
                    }
                else:
                    with st.spinner("Running screen…"):
                        result = evaluate_company(ticker, fetch_result["inputs"])
                    # Attach metadata from the resolve + fetch steps
                    result["company_name"] = resolved_result["company_name"]
                    result["moomoo_code"] = moomoo_code
                    result["input_notes"] = fetch_result["input_notes"]
                    result["is_live"] = True
                    result["mode"] = "live"
                    st.session_state["current_eval"] = result
        st.rerun()

    resolved = st.session_state["resolved_company"]
    current_eval = st.session_state["current_eval"]

    # ── Company heading — only shown after Moomoo verification ───────────────
    if resolved and resolved.get("found"):
        cname = resolved.get("company_name") or ticker
        sec = resolved.get("sec_type", "")
        code = resolved.get("moomoo_code") or ticker
    elif resolved and not resolved.get("found") and resolved.get("connected"):
        # Moomoo connected but ticker not found — show error, not the raw ticker
        st.error(
            f"**Ticker '{ticker}' not found in Moomoo.** "
            f"{resolved.get('error', '')}"
        )
        st.caption("Aggregate status: — (run the screen to see results)")
        st.caption("Rule-based summary — AI agent not connected")
        st.stop()
    elif resolved and not resolved.get("connected"):
        st.warning(
            f"**Moomoo not connected.** {resolved.get('error', '')}  "
            "Results cannot be retrieved automatically."
        )
        st.caption("Aggregate status: — (run the screen to see results)")
        st.caption("Rule-based summary — AI agent not connected")
        st.stop()
    else:
        # No analysis run yet for this ticker
        cname = ticker
        code = ticker
        sec = "Awaiting screen"

    if current_eval and current_eval.get("ticker") == ticker and not current_eval.get("error"):
        aggregate = _STATUS_LABELS.get(
            current_eval.get("aggregate_status", "unknown"),
            current_eval.get("aggregate_status", "unknown").upper(),
        )
        status_color = _STATUS_COLOURS.get(
            current_eval.get("aggregate_status", "unknown"),
            _STATUS_COLOURS["unknown"],
        )
        source_label = f"{'DEMO FIXTURE' if _is_demo else 'LIVE SCREEN'} · {aggregate}"
        st.markdown(
            '<div class="ppm-company-line">'
            f'<strong>{html.escape(cname)}</strong>'
            f'<span>({html.escape(code)}) · {html.escape(str(sec))}</span>'
            f'<span class="ppm-source-tag" style="color:{status_color}">'
            f'{html.escape(source_label)}</span></div>',
            unsafe_allow_html=True,
        )
        st.caption(
            f"Data as of {current_eval.get('data_timestamp', '—')} · "
            f"{current_eval.get('currency', 'USD')} · {aggregate}"
        )
        _render_metric_strip(current_eval)
        with st.container(border=True):
            _render_historical_comparison(current_eval, ticker)
    else:
        st.markdown(
            '<div class="ppm-company-line">'
            f'<strong>{html.escape(cname)}</strong>'
            f'<span>({html.escape(code)}) · {html.escape(str(sec))}</span>'
            '<span class="ppm-source-tag">SCREEN NOT RUN</span></div>',
            unsafe_allow_html=True,
        )
        st.caption("Aggregate status: — (run the screen to see results)")
        with st.container(border=True):
            _render_history_empty_state()

    # ── Aggregate status banner ───────────────────────────────────────────────
    if current_eval and current_eval.get("error"):
        st.error(f"**Retrieval error:** {current_eval['error']}")
        # Show which inputs were and were not connected
        notes = current_eval.get("input_notes", {})
        if notes:
            with st.expander("Data source details", expanded=True):
                for field, note in notes.items():
                    st.caption(f"**{field}:** {note}")

    st.divider()

    # ── Left / Right columns ─────────────────────────────────────────────────
    left_col, right_col = st.columns([1, 1], gap="large")

    # ── LEFT: criteria table ──────────────────────────────────────────────────
    with left_col:
        if current_eval and current_eval.get("ticker") == ticker and not current_eval.get("error"):
            criteria = current_eval.get("criteria", [])
            if not criteria:
                st.warning("No criteria returned by the backend.")
            else:
                # Build table rows dynamically — layout does NOT depend on metric names
                table_rows = []
                for c in criteria:
                    table_rows.append({
                        "Criterion": c["label"],
                        "Period": c["reporting_period"],
                        "Observed": c["observed_fmt"],
                        "Threshold": c["threshold"],
                        "Unit": c["unit"],
                        "Status": _STATUS_LABELS.get(c["status"], c["status"].upper()),
                    })

                st.markdown("#### Criteria results")
                criteria_frame = pd.DataFrame(table_rows)
                status_styles = {
                    "PASS": "color: #35d07f; font-weight: 700;",
                    "FAIL": "color: #ff7185; font-weight: 700;",
                    "UNKNOWN": "color: #f2c66d; font-weight: 700;",
                }
                st.dataframe(
                    criteria_frame.style.map(
                        lambda value: status_styles.get(value, ""),
                        subset=["Status"],
                    ).set_table_styles([
                        {
                            "selector": "th",
                            "props": [
                                ("border-top", "0"),
                                ("border-left", "0"),
                                ("border-right", "0"),
                                ("border-bottom", "1px solid #2b3b52"),
                            ],
                        },
                        {
                            "selector": "td",
                            "props": [
                                ("border-top", "0"),
                                ("border-left", "0"),
                                ("border-right", "0"),
                                ("border-bottom", "1px solid #2b3b52"),
                            ],
                        },
                    ]),
                    hide_index=True,
                    width="stretch",
                )

                # Show data-source notes for live runs
                notes = current_eval.get("input_notes", {})
                if notes and current_eval.get("is_live"):
                    with st.expander("Data sources", expanded=False):
                        for field, note in notes.items():
                            st.caption(f"**{field}:** {note}")

                with st.expander("Criterion explanations", expanded=False):
                    for c in criteria:
                        status = _STATUS_LABELS.get(c["status"], c["status"].upper())
                        st.markdown(f"**{status} · {c['label']}** ({c['reporting_period']})")
                        obs = c["observed_fmt"] if c["observed_value"] is not None else "Unknown / Unavailable"
                        st.markdown(
                            f"&nbsp;&nbsp;&nbsp;Observed: `{obs}`  "
                            f"— Threshold: `{c['threshold']}` {c['unit']}"
                        )
                        st.markdown("---")

                st.info(
                    "Only the criteria returned by the screening tool were evaluated. "
                    "Not full investment eligibility or an investment recommendation."
                )

                # Demo label
                if not current_eval.get("is_live"):
                    st.warning(
                        "**DEMO DATA** — These results are synthetic fixtures, "
                        "not real market data.",
                        icon=None,
                    )

    # ── RIGHT: analysis + save ─────────────────────────────────────────────
    with right_col:
        st.markdown("#### Research brief")
        is_demo_evaluation = bool(current_eval and current_eval.get("mode") == "demo")
        agent_analyse_pressed = st.button(
            "Show demo research brief" if is_demo_evaluation else "Request agent analysis",
            key="agent_analyse_btn",
            type="primary" if is_demo_evaluation else "secondary",
            disabled=(current_eval is None or current_eval.get("ticker") != ticker or bool(current_eval.get("error"))),
        )

        if agent_analyse_pressed and current_eval:
            if is_demo_evaluation:
                analysis_result = {
                    "connected": False,
                    "demo": True,
                    "content": _build_demo_research_brief(ticker, current_eval),
                    "error": None,
                }
            else:
                with st.spinner("Requesting analysis…"):
                    analysis_result = analyse_company(ticker, current_eval)
            st.session_state["current_analysis"] = analysis_result
            st.rerun()

        analysis: dict[str, Any] | None = st.session_state["current_analysis"]
        if analysis is None:
            if current_eval and current_eval.get("ticker") == ticker:
                if is_demo_evaluation:
                    st.caption(
                        "Show a sample brief based on the fixture's screening results. "
                        "It is not generated by an AI agent."
                    )
                else:
                    st.caption("Request a response from the configured AI agent.")
            else:
                st.caption("Run the screen first, then request analysis.")
        elif analysis.get("demo"):
            st.caption("DEMO OUTPUT · RULE-BASED SAMPLE · NOT AN AGENT RESPONSE")
            st.markdown(analysis.get("content", ""))
        elif not analysis.get("connected"):
            st.error(f"**Analysis not connected.** {analysis.get('error','')}")
            st.caption(
                "The IBM watsonx Orchestrate agent has not been configured "
                "for this prototype.  Results shown are rule-based only."
            )
        else:
            # When connected: show real output with clear label
            st.success("**Agent analysis** (live agent output):")
            st.markdown(analysis.get("content", ""))

        st.divider()

        # ── Save baseline ────────────────────────────────────────────────────
        st.markdown("#### Save for monitoring")
        save_pressed = st.button(
            "Save company for monitoring",
            key="save_btn",
            type="primary",
            disabled=(current_eval is None or current_eval.get("ticker") != ticker or bool(current_eval.get("error"))),
        )

        if save_pressed and current_eval:
            entry = {
                "saved_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "evaluation": copy.deepcopy(current_eval),
            }
            st.session_state["tracked"][ticker] = entry
            if ticker not in st.session_state["qualified_list"] and ticker not in st.session_state["needs_review_list"]:
                st.session_state["qualified_list"].add(ticker)
            _log_action("saved_baseline", ticker)
            st.success(f"**{ticker}** saved to Tracked Companies.")
            st.caption("Session-only — this is not persisted beyond the current browser session.")

        if ticker in st.session_state["tracked"]:
            saved_at = st.session_state["tracked"][ticker]["saved_at"]
            st.caption(f"Already tracked — baseline saved at {saved_at}.")

        st.divider()

        # ── Research summary (rule-based, no AI) ─────────────────────────────
        if current_eval and current_eval.get("ticker") == ticker and not current_eval.get("error"):
            agg = current_eval.get("aggregate_status", "unknown")
            agg_label = _STATUS_LABELS.get(agg, agg.upper())
            cname = current_eval.get("company_name", ticker)
            lines = [f"**Screen result for {cname}: {agg_label}**\n"]
            for c in current_eval.get("criteria", []):
                obs = c["observed_fmt"] if c["observed_value"] is not None else "Unknown"
                status = _STATUS_LABELS.get(c["status"], c["status"].upper())
                lines.append(
                    f"**{status} · {c['label']}** — Observed: {obs}; "
                    f"Threshold: {c['threshold']}"
                )
            lines.append("")
            lines.append(f"*{current_eval.get('scope_note', '')}*")
            with st.container(border=True):
                summary_title, summary_status = st.columns([3, 1])
                summary_title.markdown("#### Rule-based Research Summary")
                summary_status.markdown(
                    f'<div style="text-align:right;padding-top:.35rem">'
                    f'{_colour_status(agg.lower())}</div>',
                    unsafe_allow_html=True,
                )
                st.caption("AI agent not connected · deterministic criteria explanation")
                st.markdown("\n\n".join(lines))
                st.caption(
                    "No news, valuations, price history, or forecasts are generated. "
                    "No AI model was consulted."
                )
        else:
            st.markdown("#### Rule-based Research Summary")
            st.caption("AI agent not connected · Press **Analyse** to show the criteria summary.")


# ===========================================================================
# TAB 2 — TRACKED COMPANIES
# ===========================================================================

with tab_track:
    st.subheader("Tracked Companies")
    st.caption(
        "**Session-only** — tracked companies are stored in browser session state "
        "and are lost on page refresh.  No database or scheduler is connected."
    )

    tracked: dict[str, Any] = st.session_state["tracked"]
    qualified: set[str] = st.session_state["qualified_list"]
    needs_review: set[str] = st.session_state["needs_review_list"]

    if not tracked:
        st.info(
            "No companies tracked yet.  Go to the **Screen** tab, run a screen, "
            "and click **Save company for monitoring**."
        )
    else:
        for ticker_t, entry in list(tracked.items()):
            saved_at = entry["saved_at"]
            baseline_eval = entry["evaluation"]
            is_qualified = ticker_t in qualified
            is_review = ticker_t in needs_review
            list_label = "Qualified" if is_qualified else ("Needs Review" if is_review else "—")
            list_colour = "#35d07f" if is_qualified else ("#ff7185" if is_review else "#a0aec0")

            with st.expander(
                f"**{ticker_t}** — {baseline_eval.get('company_name', ticker_t)} | "
                f"Baseline saved: {saved_at} | "
                f"List: {list_label}",
                expanded=False,
            ):
                # Baseline summary
                bm_col, bl_col = st.columns([2, 1])
                with bm_col:
                    baseline_status = baseline_eval.get("aggregate_status", "unknown")
                    st.markdown(
                        f"**Baseline aggregate:** {_colour_status(str(baseline_status).lower())}",
                        unsafe_allow_html=True,
                    )
                    for c in baseline_eval.get("criteria", []):
                        obs = c["observed_fmt"] if c["observed_value"] is not None else "Unknown"
                        status = str(c["status"]).lower()
                        st.markdown(
                            f"- {_colour_status(status)} · **{c['label']}**: {obs}",
                            unsafe_allow_html=True,
                        )
                with bl_col:
                    st.markdown(
                        f'<span style="color:{list_colour};font-weight:700;">'
                        f"List status: {list_label}</span>",
                        unsafe_allow_html=True,
                    )
                    if not baseline_eval.get("is_live"):
                        st.caption("Baseline data is synthetic demo data.")

                st.divider()

                # Check for changes
                st.markdown("**Check for changes**")
                st.caption(
                    "Not automatic or scheduled — click to compare the saved baseline "
                    "with a fresh evaluation."
                )

                check_pressed = st.button(
                    f"Check for changes — {ticker_t}",
                    key=f"check_{ticker_t}",
                    type="primary",
                )

                check_key = f"change_result_{ticker_t}"
                if check_pressed:
                    with st.spinner("Checking…"):
                        # For demo tickers, pass None to get a fresh demo eval
                        fresh_inputs = None if ticker_t.upper() in {"ACME","BLUE","CRST"} else None
                        change_result = check_for_changes(ticker_t, entry, fresh_inputs)
                    st.session_state[check_key] = change_result

                if check_key in st.session_state:
                    cr = st.session_state[check_key]
                    st.markdown(f"_Checked at: {cr['checked_at']}_")

                    if cr["error"]:
                        st.error(f"Change check error: {cr['error']}")
                    elif not cr["comparable"]:
                        st.warning(f"**Not directly comparable:** {cr['not_comparable_reason']}")
                    else:
                        changes = cr["changes"]
                        if not changes:
                            st.success("No changes detected since baseline.")
                        else:
                            for ch in changes:
                                label = _CHANGE_LABELS.get(ch["change_type"], "CHANGE")
                                st.markdown(
                                    f"**{label} · {ch['criterion_label']}** — "
                                    f"{ch['explanation']}"
                                )
                                dc1, dc2 = st.columns(2)
                                dc1.metric("Old value", ch["old_value_fmt"])
                                dc2.metric("New value", ch["new_value_fmt"])

                                # If a pass→fail transition, offer approval workflow
                                if ch["change_type"] == "status_transition" and ch["new_status"] == "fail":
                                    st.warning(
                                        f"Pass → Fail detected on **{ch['criterion_label']}**.  "
                                        "Go to the **Approval** tab to review."
                                    )
                                    pending = {
                                        "ticker": ticker_t,
                                        "eval_id": _eval_id(cr["new_evaluation"]),
                                        "change_result": copy.deepcopy(cr),
                                        "proposed_action": "move_to_needs_review",
                                    }
                                    if st.button(
                                        f"Queue for approval — {ticker_t}",
                                        key=f"queue_{ticker_t}_{ch['criterion_id']}",
                                    ):
                                        st.session_state["pending_approval"] = pending
                                        st.success("Queued.  Review in the **Approval** tab.")

                # Remove from tracking
                if st.button(f"Remove {ticker_t} from tracking", key=f"remove_{ticker_t}"):
                    del st.session_state["tracked"][ticker_t]
                    st.session_state["qualified_list"].discard(ticker_t)
                    st.session_state["needs_review_list"].discard(ticker_t)
                    _log_action("removed_from_tracking", ticker_t)
                    st.rerun()


# ===========================================================================
# TAB 3 — APPROVAL
# ===========================================================================

with tab_approve:
    st.subheader("Approval")
    st.caption(
        "Review proposed status changes.  Approval only updates this application's "
        "review list.  It does not place trades or modify a Moomoo watchlist."
    )

    pending = st.session_state.get("pending_approval")

    if pending is None:
        st.info("No approval pending.  Approvals are queued from the **Tracked Companies** tab.")
    else:
        p_ticker = pending["ticker"]
        p_eval_id = pending["eval_id"]
        p_cr = pending["change_result"]
        p_action = pending["proposed_action"]

        # Verify the pending approval is still valid for the current ticker/eval
        # If ticker or eval changed, invalidate
        tracked_entry = st.session_state["tracked"].get(p_ticker)
        if tracked_entry is None:
            st.warning(
                "The pending approval is no longer valid — "
                f"**{p_ticker}** was removed from tracking."
            )
            st.session_state["pending_approval"] = None
        else:
            new_eval = p_cr.get("new_evaluation", {})
            if _eval_id(new_eval) != p_eval_id:
                st.warning(
                    "The evaluation that triggered this approval has changed.  "
                    "Pending approval invalidated.  Please re-check for changes."
                )
                st.session_state["pending_approval"] = None
            else:
                st.markdown(f"### Proposed action for **{p_ticker}**")
                st.markdown(
                    f"**Proposed:** Move from "
                    f"`{'Qualified' if p_ticker in st.session_state['qualified_list'] else 'Unknown'}` "
                    f"→ `Needs Review`"
                )

                # Show each failing change
                for ch in p_cr.get("changes", []):
                    if ch["change_type"] == "status_transition" and ch["new_status"] == "fail":
                        with st.container(border=True):
                            st.markdown(f"**Affected rule:** {ch['criterion_label']}")
                            r1, r2 = st.columns(2)
                            r1.metric("Old value", ch["old_value_fmt"])
                            r2.metric("New value", ch["new_value_fmt"])
                            st.markdown(
                                f"**Old status:** {_STATUS_LABELS.get(ch['old_status'], ch['old_status'].upper())}  "
                                f"→  **New status:** {_STATUS_LABELS.get(ch['new_status'], ch['new_status'].upper())}"
                            )
                            st.markdown(f"**Explanation:** {ch['explanation']}")
                            b_ts = tracked_entry["saved_at"]
                            n_ts = p_cr.get("checked_at", "—")
                            st.caption(f"Baseline saved: {b_ts}  |  Change detected: {n_ts}")
                            if not new_eval.get("is_live"):
                                st.caption("New evaluation uses synthetic demo data.")

                st.divider()
                ap_col, kc_col = st.columns(2)

                approve_pressed = ap_col.button(
                    "Approve — move to Needs Review",
                    type="primary",
                    key="approve_btn",
                )
                keep_pressed = kc_col.button(
                    "Keep current list status",
                    key="keep_btn",
                )

                if approve_pressed:
                    # Verify approval is bound to this exact ticker + eval
                    if _eval_id(p_cr.get("new_evaluation", {})) == p_eval_id:
                        st.session_state["qualified_list"].discard(p_ticker)
                        st.session_state["needs_review_list"].add(p_ticker)
                        _log_action(
                            "approved_needs_review",
                            p_ticker,
                            {"eval_id": p_eval_id, "changes": len(p_cr.get("changes", []))},
                        )
                        st.session_state["pending_approval"] = None
                        st.success(f"**{p_ticker}** moved to Needs Review.")
                        st.rerun()
                    else:
                        st.error("Approval invalidated — ticker or evaluation changed.")
                        st.session_state["pending_approval"] = None

                if keep_pressed:
                    _log_action(
                        "rejected_keep_current",
                        p_ticker,
                        {"eval_id": p_eval_id},
                    )
                    st.session_state["pending_approval"] = None
                    st.info(
                        f"**{p_ticker}** remains in its current list status.  "
                        "No changes were made."
                    )
                    st.rerun()

    # ── Action log ───────────────────────────────────────────────────────────
    st.divider()
    st.markdown("### Action log")
    st.caption("Session-only.  Cleared on page refresh.")
    log = st.session_state.get("action_log", [])
    if not log:
        st.caption("No actions recorded yet.")
    else:
        log_rows = []
        for entry in reversed(log):
            log_rows.append({
                "Timestamp": entry["timestamp"],
                "Action": entry["action"],
                "Ticker": entry["ticker"],
            })
        st.dataframe(log_rows, hide_index=True, width="stretch")


# ===========================================================================
# TAB 4 — ABOUT / DEMO
# ===========================================================================

with tab_about:
    st.subheader("About this Prototype")

    st.markdown("""
### What is live, demo, or not connected

| Component | Status | Notes |
|---|---|---|
| Screening criteria evaluation | **Live** (when inputs provided) | Uses `powerpuffmen_basic_screen.fn` |
| Screening criteria evaluation | **Demo** (when no inputs / demo ticker) | Clearly labelled fixtures |
| AI agent analysis | **Not connected** | Returns explicit error, no fabricated output |
| Moomoo watchlist import | **Not connected** | UI integration point only |
| Tracked companies / approval | **Session-only state** | Lost on page refresh; no database |
| Continuous / scheduled monitoring | **Not implemented** | Manual "Check for changes" only |

### Session-state limitation

All state (selected ticker, tracked companies, approval queue, action log) is stored in
`st.session_state` only.  **Nothing persists across browser refreshes.**
This limitation is intentional for the prototype and is labelled throughout.

### Demo shortcuts

Use the **ACME / BLUE / CRST / SMCHG** buttons on the Screen tab to load
clearly-labelled demo fixture data.

The **SMCHG** ticker also powers the **Simulated-change scenario** below.
""")

    st.divider()

    # ── Simulated-change scenario ─────────────────────────────────────────────
    st.subheader("Simulated-change Scenario (DEMO only)")
    st.markdown(
        """
This scenario demonstrates a **pass→fail transition** without using live data.
It is entirely synthetic and clearly labelled as a demo.

**Scenario:** *SimCo Inc.* initially passes all four criteria.  A subsequent
evaluation shows the operating cash flow has turned negative — triggering the
approval workflow.

No live data is read or written at any step.
        """
    )

    load_sim = st.button("Load simulated-change baseline", key="sim_load")
    if load_sim:
        scenario = get_simulated_change_scenario()
        st.session_state["sim_baseline"] = scenario["baseline"]
        st.session_state["sim_changed"] = scenario["changed"]
        st.session_state["sim_scenario_state"] = "loaded"

    if st.session_state.get("sim_scenario_state") == "loaded":
        sim_base = st.session_state["sim_baseline"]
        sim_chg  = st.session_state["sim_changed"]

        st.success("Demo baseline loaded.")
        b_col, c_col = st.columns(2)

        with b_col:
            st.markdown("**Baseline evaluation (all PASS):**")
            for c in sim_base["criteria"]:
                status = _STATUS_LABELS.get(c["status"], c["status"].upper())
                st.markdown(f"- **{status}** · {c['label']}: {c['observed_fmt']}")

        with c_col:
            st.markdown("**Changed evaluation (OCF FAIL):**")
            for c in sim_chg["criteria"]:
                status = _STATUS_LABELS.get(c["status"], c["status"].upper())
                st.markdown(f"- **{status}** · {c['label']}: {c['observed_fmt']}")

        run_sim_check = st.button("Run change comparison", key="sim_compare")
        if run_sim_check:
            # Manually build a change result from the two evals
            _cfc = check_for_changes
            fake_entry = {"saved_at": sim_base["data_timestamp"], "evaluation": sim_base}

            # We override the "new" eval by mocking check_for_changes internals
            # Instead, use the adapter's compare logic directly
            import copy
            baseline_criteria = {c["id"]: c for c in sim_base["criteria"]}
            new_criteria = {c["id"]: c for c in sim_chg["criteria"]}
            changes = []
            for cid in baseline_criteria:
                old_c = baseline_criteria[cid]
                new_c = new_criteria.get(cid)
                if new_c is None:
                    continue
                if old_c["status"] != new_c["status"]:
                    changes.append({
                        "criterion_id": cid,
                        "criterion_label": new_c["label"],
                        "change_type": "status_transition",
                        "old_value_fmt": old_c["observed_fmt"],
                        "new_value_fmt": new_c["observed_fmt"],
                        "old_status": old_c["status"],
                        "new_status": new_c["status"],
                        "explanation": (
                            f"'{new_c['label']}' changed from {old_c['status'].upper()} "
                            f"to {new_c['status'].upper()}. "
                            f"Value: {old_c['observed_fmt']} → {new_c['observed_fmt']}."
                        ),
                    })
                elif old_c["observed_value"] != new_c["observed_value"]:
                    changes.append({
                        "criterion_id": cid,
                        "criterion_label": new_c["label"],
                        "change_type": "value_changed",
                        "old_value_fmt": old_c["observed_fmt"],
                        "new_value_fmt": new_c["observed_fmt"],
                        "old_status": old_c["status"],
                        "new_status": new_c["status"],
                        "explanation": (
                            f"'{new_c['label']}' value changed: "
                            f"{old_c['observed_fmt']} → {new_c['observed_fmt']}."
                        ),
                    })

            now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            st.session_state["sim_scenario_state"] = "checked"
            st.session_state["sim_check_result"] = {
                "changes": changes,
                "checked_at": now,
                "new_evaluation": sim_chg,
            }

    if st.session_state.get("sim_scenario_state") == "checked":
        sim_cr = st.session_state.get("sim_check_result", {})
        st.markdown(f"**Comparison result** _(DEMO — simulated, not real data)_:")
        for ch in sim_cr.get("changes", []):
            label = _CHANGE_LABELS.get(ch["change_type"], "CHANGE")
            st.markdown(f"**{label} · {ch['criterion_label']}** — {ch['explanation']}")
        st.info(
            "This is a simulated-change scenario.  No live data was read.  "
            "No write operations were performed."
        )

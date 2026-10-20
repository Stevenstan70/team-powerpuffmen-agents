"""
Powerpuffmen Research — Investment Screening & Monitoring Prototype.

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

import streamlit as st

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.dirname(__file__))

from frontend.adapter import (
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
    page_title="Powerpuffmen Research — Prototype",
    layout="wide",
)

# ---------------------------------------------------------------------------
# Session-state bootstrap
# ---------------------------------------------------------------------------
_DEFAULTS: dict = {
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

_STATUS_COLOURS = {"pass": "#1a7f37", "fail": "#cf222e", "unknown": "#9a6700"}
_STATUS_ICONS   = {"pass": "✅ PASS",  "fail": "❌ FAIL",  "unknown": "⚠️ UNKNOWN"}
_CHANGE_ICONS   = {
    "status_transition":  "🔄",
    "value_changed":      "📊",
    "data_unavailable":   "❓",
    "criteria_changed":   "⚙️",
}


def _colour_status(status: str) -> str:
    c = _STATUS_COLOURS.get(status, "#57606a")
    icon = _STATUS_ICONS.get(status, status.upper())
    return f'<span style="color:{c};font-weight:700;">{icon}</span>'


def _clear_company_state():
    """Clear analysis, resolved identity, and pending approval when ticker changes."""
    st.session_state["resolved_company"] = None
    st.session_state["current_eval"] = None
    st.session_state["current_analysis"] = None
    st.session_state["pending_approval"] = None


def _eval_id(evaluation: dict) -> str:
    """Stable string identity for an evaluation (ticker + timestamp)."""
    return f"{evaluation.get('ticker','')}@{evaluation.get('data_timestamp','')}"


def _log_action(action: str, ticker: str, detail: dict | None = None):
    entry = {
        "action": action,
        "ticker": ticker,
        "timestamp": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        **(detail or {}),
    }
    st.session_state["action_log"].append(entry)


# ---------------------------------------------------------------------------
# Global persistent warning
# ---------------------------------------------------------------------------
st.warning(
    "⚠️ **SYNTHETIC DEMO DATA — PROTOTYPE** — No live market data or brokerage connection.  "
    "Session-only state: data resets on page refresh.  "
    "No AI agent is active unless labelled.",
    icon=None,
)

# ---------------------------------------------------------------------------
# Title
# ---------------------------------------------------------------------------
st.title("Powerpuffmen Research — Screening & Monitoring Prototype")

# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------
tab_screen, tab_track, tab_approve, tab_about = st.tabs([
    "🔍 Screen",
    "📋 Tracked Companies",
    "✅ Approval",
    "ℹ️ About / Demo",
])


# ===========================================================================
# TAB 1 — SCREEN
# ===========================================================================

with tab_screen:

    # ── Moomoo handoff notice ────────────────────────────────────────────────
    with st.expander("ℹ️ How to use this screen", expanded=False):
        st.markdown(
            """
**Workflow:**

1. Enter a single ticker symbol below (e.g. `AAPL`).
2. Press **▶ Analyse** — the app validates the ticker, resolves the company
   name via Moomoo, retrieves available financial data automatically, and
   runs the screening criteria.
3. Review results. A company heading is only shown after the ticker has
   been verified by Moomoo — unverified input is never displayed as a
   company name.

**What is retrieved automatically:**
- Close price and market cap — via Moomoo `get_market_snapshot`
- Employee count — via Moomoo `get_company_profile`
- **Operating cash flow TTM** — _not yet connected_
  (requires backend teammate's `get_financials_statements` field-ID parser)

**Demo shortcuts** load clearly-labelled demo fixtures without hitting Moomoo.
            """
        )

    # ── Ticker input ─────────────────────────────────────────────────────────
    ticker_input = st.text_input(
        "Ticker symbol",
        value=st.session_state["selected_ticker"],
        placeholder="e.g. AAPL",
        key="ticker_text_input",
        help="Enter a single ticker symbol. Multi-word input like 'baba amskd' will be rejected.",
    ).strip().upper()

    # Detect ticker change → clear stale state immediately
    if ticker_input != st.session_state["selected_ticker"]:
        st.session_state["selected_ticker"] = ticker_input
        _clear_company_state()
        st.rerun()

    # ── Demo company shortcuts ────────────────────────────────────────────────
    st.caption(
        "**Demo shortcuts** — load a clearly-labelled fictional fixture without Moomoo:"
    )
    dc1, dc2, dc3, dc4 = st.columns(4)
    if dc1.button("ACME — All PASS",    key="demo_acme"):
        st.session_state["selected_ticker"] = "ACME"
        _clear_company_state()
        st.rerun()
    if dc2.button("BLUE — OCF FAIL",    key="demo_blue"):
        st.session_state["selected_ticker"] = "BLUE"
        _clear_company_state()
        st.rerun()
    if dc3.button("CRST — UNKNOWN",     key="demo_crst"):
        st.session_state["selected_ticker"] = "CRST"
        _clear_company_state()
        st.rerun()
    if dc4.button("SMCHG — Sim Change", key="demo_smchg"):
        st.session_state["selected_ticker"] = "SMCHG"
        _clear_company_state()
        st.rerun()

    ticker = st.session_state["selected_ticker"]

    if not ticker:
        st.caption("Aggregate status: — (run the screen to see results)")
        st.caption("Rule-based summary — AI agent not connected")
        st.info(
            "Enter a ticker above or pick a demo shortcut to begin.  "
            "Press **▶ Analyse** after entering a ticker."
        )
        st.stop()

    # ── Inline ticker format validation (no network call) ────────────────────
    _DEMO_TICKERS = {"ACME", "BLUE", "CRST", "SMCHG"}
    _is_demo = ticker in _DEMO_TICKERS

    if not _is_demo:
        _val = validate_ticker(ticker)
        if not _val["valid"]:
            st.error(f"❌ **Invalid ticker:** {_val['reason']}")
            st.caption("Aggregate status: — (run the screen to see results)")
            st.caption("Rule-based summary — AI agent not connected")
            st.stop()

    # ── Analyse button (single entry point for live flow) ────────────────────
    with st.form("analyse_form"):
        analyse_pressed = st.form_submit_button(
            "▶ Analyse",
            type="primary",
            help="Validate ticker, resolve company, fetch data, and run the screen.",
        )

    current_eval: dict | None = st.session_state["current_eval"]
    resolved: dict | None = st.session_state["resolved_company"]

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

    st.divider()

    # ── Company heading — only shown after Moomoo verification ───────────────
    if resolved and resolved.get("found"):
        cname = resolved.get("company_name") or ticker
        sec = resolved.get("sec_type", "")
        code = resolved.get("moomoo_code") or ticker
        mode_badge = "🔵 DEMO" if _is_demo else "🟢 Live"
        st.subheader(f"{cname}  ({code})")
        st.caption(f"Type: {sec}  |  Mode: {mode_badge}")
    elif resolved and not resolved.get("found") and resolved.get("connected"):
        # Moomoo connected but ticker not found — show error, not the raw ticker
        st.error(
            f"❌ **Ticker '{ticker}' not found in Moomoo.** "
            f"{resolved.get('error', '')}"
        )
        st.caption("Aggregate status: — (run the screen to see results)")
        st.caption("Rule-based summary — AI agent not connected")
        st.stop()
    elif resolved and not resolved.get("connected"):
        st.warning(
            f"⚠️ **Moomoo not connected.** {resolved.get('error', '')}  "
            "Results cannot be retrieved automatically."
        )
        st.caption("Aggregate status: — (run the screen to see results)")
        st.caption("Rule-based summary — AI agent not connected")
        st.stop()
    else:
        # No analysis run yet for this ticker
        st.subheader(ticker)
        st.caption("Aggregate status: — (run the screen to see results)")

    # ── Aggregate status banner ───────────────────────────────────────────────
    if current_eval and current_eval.get("ticker") == ticker and not current_eval.get("error"):
        meta_col, status_col = st.columns([3, 1])
        with meta_col:
            st.markdown(f"**Company:** {current_eval.get('company_name', ticker)}")
            st.markdown(f"**Currency:** {current_eval.get('currency', 'USD')}")
            ts = current_eval.get("data_timestamp", "—")
            is_live = current_eval.get("is_live", False)
            mode_label = "🟢 Live" if is_live else "🔵 Demo"
            st.markdown(f"**Data as of:** {ts}  |  **Mode:** {mode_label}")
        with status_col:
            agg = current_eval.get("aggregate_status", "unknown")
            c = _STATUS_COLOURS.get(agg, "#57606a")
            icon = _STATUS_ICONS.get(agg, agg.upper())
            st.markdown(
                f'<p style="font-size:1.3em;font-weight:700;color:{c};">{icon}</p>',
                unsafe_allow_html=True,
            )
    elif current_eval and current_eval.get("error"):
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
                        "Status": _STATUS_ICONS.get(c["status"], c["status"].upper()),
                    })

                st.markdown("#### Criteria results")
                st.dataframe(table_rows, hide_index=True, use_container_width=True)

                # Show data-source notes for live runs
                notes = current_eval.get("input_notes", {})
                if notes and current_eval.get("is_live"):
                    with st.expander("Data sources", expanded=False):
                        for field, note in notes.items():
                            icon = "✅" if "Moomoo" in note else "⚠️"
                            st.caption(f"{icon} **{field}:** {note}")

                with st.expander("Criterion explanations", expanded=False):
                    for c in criteria:
                        icon = {"pass": "✅", "fail": "❌", "unknown": "⚠️"}.get(c["status"], "")
                        st.markdown(f"**{icon} {c['label']}** ({c['reporting_period']})")
                        obs = c["observed_fmt"] if c["observed_value"] is not None else "Unknown / Unavailable"
                        st.markdown(
                            f"&nbsp;&nbsp;&nbsp;Observed: `{obs}`  "
                            f"— Threshold: `{c['threshold']}` {c['unit']}"
                        )
                        st.markdown("---")

                st.info(
                    "⚠️ Only the criteria returned by the screening tool were evaluated. "
                    "Not full investment eligibility or an investment recommendation."
                )

                # Demo label
                if not current_eval.get("is_live"):
                    st.warning(
                        "🔵 **DEMO DATA** — These results are demo fixtures, "
                        "not real market data.",
                        icon=None,
                    )

    # ── RIGHT: analysis + save ─────────────────────────────────────────────
    with right_col:
        st.markdown("#### Agent Analysis")
        # Note: 'analyse_pressed' here is a separate button from the form submit above
        agent_analyse_pressed = st.button(
            "🤖 Request agent analysis",
            key="agent_analyse_btn",
            disabled=(current_eval is None or current_eval.get("ticker") != ticker or bool(current_eval.get("error"))),
        )

        if agent_analyse_pressed and current_eval:
            with st.spinner("Requesting analysis…"):
                analysis_result = analyse_company(ticker, current_eval)
            st.session_state["current_analysis"] = analysis_result
            st.rerun()

        analysis: dict | None = st.session_state["current_analysis"]
        if analysis is None:
            if current_eval and current_eval.get("ticker") == ticker:
                st.caption("Press **Analyse company** to request an AI agent analysis.")
            else:
                st.caption("Run the screen first, then request analysis.")
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
        st.markdown("#### Save for Monitoring")
        save_pressed = st.button(
            "📌 Save company for monitoring",
            key="save_btn",
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
            st.caption("⚠️ Session-only — this is not persisted beyond the current browser session.")

        if ticker in st.session_state["tracked"]:
            saved_at = st.session_state["tracked"][ticker]["saved_at"]
            st.caption(f"✅ Already tracked — baseline saved at {saved_at}.")

        st.divider()

        # ── Research summary (rule-based, no AI) ─────────────────────────────
        st.markdown("#### Rule-based Research Summary")
        st.caption("Rule-based summary — AI agent not connected")

        if current_eval and current_eval.get("ticker") == ticker and not current_eval.get("error"):
            agg = current_eval.get("aggregate_status", "unknown")
            agg_label = _STATUS_ICONS.get(agg, agg.upper())
            cname = current_eval.get("company_name", ticker)
            lines = [f"**Screen result for {cname}: {agg_label}**\n"]
            for c in current_eval.get("criteria", []):
                obs = c["observed_fmt"] if c["observed_value"] is not None else "Unknown"
                icon = {"pass": "✅", "fail": "❌", "unknown": "⚠️"}.get(c["status"], "")
                lines.append(
                    f"{icon} **{c['label']}** — Observed: {obs}; "
                    f"Threshold: {c['threshold']}"
                )
            lines.append("")
            lines.append(f"*{current_eval.get('scope_note', '')}*")
            st.markdown("\n\n".join(lines))
            st.markdown("---")
            st.markdown(
                "_This summary is a deterministic explanation of the criteria results "
                "above. No news, valuations, price history, or forecasts are generated. "
                "No AI model was consulted._"
            )
        else:
            st.markdown("_Press **▶ Run basic screen** to generate the rule-based summary._")


# ===========================================================================
# TAB 2 — TRACKED COMPANIES
# ===========================================================================

with tab_track:
    st.subheader("Tracked Companies")
    st.caption(
        "⚠️ **Session-only** — tracked companies are stored in browser session state "
        "and are lost on page refresh.  No database or scheduler is connected."
    )

    tracked: dict = st.session_state["tracked"]
    qualified: set = st.session_state["qualified_list"]
    needs_review: set = st.session_state["needs_review_list"]

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
            list_colour = "#1a7f37" if is_qualified else ("#cf222e" if is_review else "#57606a")

            with st.expander(
                f"**{ticker_t}** — {baseline_eval.get('company_name', ticker_t)} | "
                f"Baseline saved: {saved_at} | "
                f"List: {list_label}",
                expanded=False,
            ):
                # Baseline summary
                bm_col, bl_col = st.columns([2, 1])
                with bm_col:
                    st.markdown(f"**Baseline aggregate:** {_STATUS_ICONS.get(baseline_eval.get('aggregate_status','unknown'), '—')}")
                    for c in baseline_eval.get("criteria", []):
                        obs = c["observed_fmt"] if c["observed_value"] is not None else "Unknown"
                        icon = {"pass": "✅", "fail": "❌", "unknown": "⚠️"}.get(c["status"], "")
                        st.markdown(f"- {icon} **{c['label']}**: {obs}")
                with bl_col:
                    st.markdown(
                        f'<span style="color:{list_colour};font-weight:700;">'
                        f"List status: {list_label}</span>",
                        unsafe_allow_html=True,
                    )
                    if not baseline_eval.get("is_live"):
                        st.caption("🔵 Baseline data is DEMO")

                st.divider()

                # Check for changes
                st.markdown("**Check for changes**")
                st.caption(
                    "Not automatic or scheduled — click to compare the saved baseline "
                    "with a fresh evaluation."
                )

                check_pressed = st.button(
                    f"🔄 Check for changes — {ticker_t}",
                    key=f"check_{ticker_t}",
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
                        st.warning(f"⚙️ **Not directly comparable:** {cr['not_comparable_reason']}")
                    else:
                        changes = cr["changes"]
                        if not changes:
                            st.success("No changes detected since baseline.")
                        else:
                            for ch in changes:
                                icon = _CHANGE_ICONS.get(ch["change_type"], "📌")
                                st.markdown(
                                    f"{icon} **{ch['criterion_label']}** — "
                                    f"{ch['explanation']}"
                                )
                                dc1, dc2 = st.columns(2)
                                dc1.metric("Old value", ch["old_value_fmt"])
                                dc2.metric("New value", ch["new_value_fmt"])

                                # If a pass→fail transition, offer approval workflow
                                if ch["change_type"] == "status_transition" and ch["new_status"] == "fail":
                                    st.warning(
                                        f"⚠️ Pass → Fail detected on **{ch['criterion_label']}**.  "
                                        "Go to the **Approval** tab to review."
                                    )
                                    pending = {
                                        "ticker": ticker_t,
                                        "eval_id": _eval_id(cr["new_evaluation"]),
                                        "change_result": copy.deepcopy(cr),
                                        "proposed_action": "move_to_needs_review",
                                    }
                                    if st.button(
                                        f"➡ Queue for approval — {ticker_t}",
                                        key=f"queue_{ticker_t}_{ch['criterion_id']}",
                                    ):
                                        st.session_state["pending_approval"] = pending
                                        st.success("Queued.  Review in the **Approval** tab.")

                # Remove from tracking
                if st.button(f"🗑 Remove {ticker_t} from tracking", key=f"remove_{ticker_t}"):
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
                    "⚠️ The evaluation that triggered this approval has changed.  "
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
                                f"**Old status:** {_STATUS_ICONS.get(ch['old_status'], ch['old_status'].upper())}  "
                                f"→  **New status:** {_STATUS_ICONS.get(ch['new_status'], ch['new_status'].upper())}"
                            )
                            st.markdown(f"**Explanation:** {ch['explanation']}")
                            b_ts = tracked_entry["saved_at"]
                            n_ts = p_cr.get("checked_at", "—")
                            st.caption(f"Baseline saved: {b_ts}  |  Change detected: {n_ts}")
                            if not new_eval.get("is_live"):
                                st.caption("🔵 New evaluation is DEMO data")

                st.divider()
                ap_col, kc_col = st.columns(2)

                approve_pressed = ap_col.button(
                    "✅ Approve — move to Needs Review",
                    type="primary",
                    key="approve_btn",
                )
                keep_pressed = kc_col.button(
                    "❌ Keep current list status",
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
        st.dataframe(log_rows, hide_index=True, use_container_width=True)


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
    st.subheader("🔵 Simulated-change Scenario (DEMO only)")
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

        st.success("🔵 Demo baseline loaded.")
        b_col, c_col = st.columns(2)

        with b_col:
            st.markdown("**Baseline evaluation (all PASS):**")
            for c in sim_base["criteria"]:
                icon = {"pass":"✅","fail":"❌","unknown":"⚠️"}.get(c["status"],"")
                st.markdown(f"- {icon} {c['label']}: {c['observed_fmt']}")

        with c_col:
            st.markdown("**Changed evaluation (OCF FAIL):**")
            for c in sim_chg["criteria"]:
                icon = {"pass":"✅","fail":"❌","unknown":"⚠️"}.get(c["status"],"")
                st.markdown(f"- {icon} {c['label']}: {c['observed_fmt']}")

        run_sim_check = st.button("Run change comparison", key="sim_compare")
        if run_sim_check:
            # Manually build a change result from the two evals
            from frontend.adapter import check_for_changes as _cfc
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
            icon = _CHANGE_ICONS.get(ch["change_type"], "📌")
            st.markdown(f"{icon} **{ch['criterion_label']}** — {ch['explanation']}")
        st.info(
            "🔵 This is a simulated-change scenario.  No live data was read.  "
            "No write operations were performed."
        )

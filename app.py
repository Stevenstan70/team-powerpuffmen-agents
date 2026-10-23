"""InvestIQ: redesigned UI with snapshot policy v2. Session-only."""
from __future__ import annotations
import copy
import hashlib
import html
import json
from datetime import datetime, timezone
import streamlit as st
from frontend.snapshot_adapter import evaluate_snapshot, analyse_snapshot
from frontend.csv_snapshot import read_csv_snapshot
from frontend.real_screen import render_real_screen
from frontend.market_chart import render_market_chart

st.set_page_config(page_title="InvestIQ — Investment Research", layout="wide", initial_sidebar_state="collapsed")
st.markdown("""<style>
:root{--bg:#0b1220;--surface:#111c2e;--ink:#e6edf7;--muted:#a0aec0;--rule:#2b3b52;--cyan:#35b8ff}
html,body,[data-testid="stAppViewContainer"],[data-testid="stHeader"]{background:var(--bg);color:var(--ink)}
.block-container{max-width:1560px;padding-top:1rem}
.ppm-masthead{display:flex;justify-content:space-between;align-items:center;gap:1rem;border-bottom:1px solid var(--rule);padding:.85rem 0 1rem}
.ppm-brand{font-size:1.35rem;font-weight:740;letter-spacing:-.03em;color:#f8fafc}
.ppm-tagline{font-size:.85rem;color:var(--muted)}
.ppm-env{border:1px solid #285845;background:#172d2a;color:#86e3b1;border-radius:4px;padding:.45rem .7rem;font-size:.7rem;letter-spacing:.08em}
.ppm-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:1px;background:var(--rule);border:1px solid var(--rule);margin:1rem 0}
.ppm-metric{background:var(--surface);padding:.8rem;min-width:0}.ppm-label{color:var(--muted);font-size:.7rem;text-transform:uppercase;letter-spacing:.06em}
.ppm-value{font-size:1.25rem;font-weight:650;font-variant-numeric:tabular-nums;margin:.4rem 0;overflow-wrap:anywhere}
[data-testid="stTabs"] [role="tablist"]{gap:1.1rem;border-bottom:1px solid var(--rule);overflow-x:auto}
[data-testid="stTabs"] button[role="tab"][aria-selected="true"]{color:#f8fafc;border-bottom:2px solid var(--cyan)}
[data-testid="stButton"] button{border-radius:5px;border:1px solid var(--cyan)}
[data-testid="stExpander"]{background:var(--surface);border:1px solid var(--rule);border-radius:5px}
button:focus-visible,input:focus-visible,[role="tab"]:focus-visible{outline:3px solid #35b8ff!important;outline-offset:2px}
.ppm-skip{position:absolute;left:-10000px}.ppm-skip:focus{position:fixed;left:1rem;top:1rem;background:#e6edf7;color:#0b1220;padding:1rem;z-index:2000}
@media(max-width:760px){.ppm-masthead{align-items:flex-start;flex-direction:column}.ppm-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.block-container{padding-left:1rem;padding-right:1rem}}
@media(prefers-reduced-motion:reduce){*{transition:none!important}}


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

</style>""", unsafe_allow_html=True)

VERSION = "snapshot-integrated-ui-1"
if st.session_state.get("integrated_ui_version") != VERSION:
    for key in ("current_eval", "current_analysis", "tracked", "pending_approval", "action_log", "needs_review_list", "qualified_list", "v2_checks"):
        st.session_state.pop(key, None)
    st.session_state["integrated_ui_version"] = VERSION
for key, value in {"current_eval":None,"current_analysis":None,"tracked":{},"pending_approval":None,"action_log":[],"needs_review_list":set(),"v2_checks":{}}.items():
    if key not in st.session_state:
        st.session_state[key] = copy.deepcopy(value)

BASE = {"market_cap_usd":8_000_000_000,"close_price_usd":45.20,"net_profit_usd":620_000_000,"snapshot_volume_shares":100_000}
FIXTURES = {
    "ACME":("Synthetic All-Pass Company",dict(BASE)),
    "BLUE":("Synthetic Negative-Profit Company",{**BASE,"net_profit_usd":-1_000_000}),
    "CRST":("Synthetic Missing-Profit Company",{**BASE,"net_profit_usd":None}),
    "SMCHG":("Synthetic Monitoring Company",dict(BASE)),
}
SCENARIOS = {"Baseline / unchanged":{},"Negative net profit":{"net_profit_usd":-1_000_000},"Low snapshot volume":{"snapshot_volume_shares":99_999},"Net profit unavailable":{"net_profit_usd":None}}
LABELS = {"pass":"PASS","fail":"FAIL","unknown":"UNVERIFIED"}
COLOURS = {"pass":"#35d07f","fail":"#ff7185","unknown":"#f2c66d"}

def now():
    return datetime.now(timezone.utc).isoformat()

def identity(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,default=str,allow_nan=False).encode()).hexdigest()

def log(action,ticker):
    st.session_state["action_log"].append({"Timestamp":now(),"Action":action,"Ticker":ticker})

def invalidate(ticker):
    p = st.session_state["pending_approval"]
    if p and p["ticker"] == ticker:
        st.session_state["pending_approval"] = None

def evaluate_demo(ticker,overrides=None):
    name,inputs = FIXTURES[ticker]
    return evaluate_snapshot(ticker,{**inputs,**(overrides or {})},source_mode="demo",company_name=name)

def load_demo(ticker):
    st.session_state["demo_ticker"] = ticker
    st.session_state["current_eval"] = evaluate_demo(ticker)
    st.session_state["current_analysis"] = None

def compare(old,new):
    if old.get("error") or new.get("error"):
        return [],"An evaluation contains an error."
    if not old.get("criteria_version") or old.get("criteria_version") != new.get("criteria_version"):
        return [],"Policy versions differ; save a new baseline."
    if old.get("ticker") != new.get("ticker") or old.get("mode") != new.get("mode"):
        return [],"Company or source mode differs."
    a = {c["id"]:c for c in old.get("criteria",[])}
    b = {c["id"]:c for c in new.get("criteria",[])}
    if not a or a.keys() != b.keys():
        return [],"Criterion sets differ."
    changes = []
    for key,left in a.items():
        right = b[key]
        if any(left.get(f) != right.get(f) for f in ("threshold","operator","unit","reporting_period")):
            return [],"Rule definitions differ."
        if left["status"] != right["status"] or left["observed_value"] != right["observed_value"]:
            changes.append({"Criterion":right["label"],"Old value":left["observed_fmt"],"New value":right["observed_fmt"],"Old status":left["status"],"New status":right["status"]})
    return changes,None

def has_failure(changes):
    return any(c["Old status"]=="pass" and c["New status"]=="fail" for c in changes)

def show_evaluation(e):
    if e.get("error"):
        st.error(e["error"])
        return
    st.subheader(e.get("company_name") or e["ticker"])
    st.caption(f"SYNTHETIC DEMO · {e['criteria_version']} · {LABELS.get(e['aggregate_status'],'UNVERIFIED')}")
    st.caption(f"Evaluated at: {e.get('evaluated_at','—')}. This is not a market-data timestamp.")
    cards = []
    for c in e["criteria"]:
        colour = COLOURS.get(c["status"],COLOURS["unknown"])
        cards.append(f'<div class="ppm-metric"><div class="ppm-metric-label">{html.escape(c["label"])}</div><div class="ppm-metric-value">{html.escape(c["observed_fmt"])}</div><div style="color:{colour}">{LABELS.get(c["status"],"UNVERIFIED")}</div></div>')
    st.markdown('<div class="ppm-metric-grid">'+''.join(cards)+'</div>',unsafe_allow_html=True)
    st.dataframe([{"Criterion":c["label"],"Period":c["reporting_period"],"Observed":c["observed_fmt"],"Threshold":str(c["threshold"]),"Unit":c["unit"],"Status":LABELS.get(c["status"],"UNVERIFIED")} for c in e["criteria"]],hide_index=True,width="stretch")
    st.caption(e["scope_note"])
    with st.expander("Criterion explanations"):
        for c in e["criteria"]:
            st.write(c["label"]+": "+c["explanation"])

def history_empty():
    with st.container(border=True):
        st.subheader("Historical Comparison")
        st.selectbox("Metric",["Market cap · USD","Previous close · USD","Reported net profit · USD; period unspecified","Snapshot trading volume · shares; not average daily volume"],key="v2_history_metric")
        st.info("No verified historical series is connected. No chart points are generated from a single snapshot. Net profit is not relabeled as annual or TTM, and snapshot volume is not average daily volume.")

with st.sidebar:
    st.header("Cached Moomoo CSV")
    st.caption("Saved dataset preview only — not live or verified for screening.")
    ticker = st.text_input("Exact ticker for CSV preview",value="AAPL",key="csv_preview_ticker",on_change=lambda:st.session_state.pop("csv_preview_result",None))
    if st.button("Read saved CSV"):
        st.session_state["csv_preview_result"] = read_csv_snapshot(ticker)
    p = st.session_state.get("csv_preview_result")
    if p:
        if p.get("error"):
            st.error(p["error"])
        elif p.get("found"):
            st.write(f"{p['company_name']} ({p['moomoo_code']})")
            st.write({"Source file":p["source_file"],"Snapshot time (US Eastern; not converted)":p["data_timestamp"] or "Unknown","Currency field":p["provider_currency"] or "Not supplied","Market cap (raw provider units)":p["market_cap_raw"],"Previous close (raw provider units)":p["previous_close_raw"]})
            st.caption("Currency, units, and provider validity are unverified. These values are not sent to the screen or agent.")
            with st.expander("Dataset fingerprint"):
                st.code(p["dataset_sha256"],language=None)

st.markdown("""<a class="ppm-skip-link" href="#main-content">Skip to main content</a><header class="ppm-masthead"><div><div class="ppm-brand">InvestIQ</div><div class="ppm-tagline">Investment research, screening &amp; monitoring</div></div><div class="ppm-env">PROTOTYPE · SYNTHETIC SCREENING</div></header>""",unsafe_allow_html=True)
st.info("Session-only state resets on refresh. No trades, watchlist writes, database, or scheduler. Cloud-agent analysis runs only when requested, using synthetic inputs.")
screen,tracking,approval,about = st.tabs(["Screen","Tracked Companies","Approval","About / Demo"])

def render_screen():
    st.markdown('<div id="main-content" tabindex="-1"></div>',unsafe_allow_html=True)
    st.header("Screen a company")
    source = st.radio("Input source",["Synthetic demo","Real company — gated"],horizontal=True)
    if source != "Synthetic demo":
        render_real_screen()
        history_empty()
        return
    st.caption("Quick demo screens — explicitly fictional companies")
    for col,ticker in zip(st.columns(4),FIXTURES):
        col.button(ticker,key=f"demo_{ticker.lower()}",on_click=load_demo,args=(ticker,),width="stretch")
    ticker = st.selectbox("Synthetic company",list(FIXTURES),key="demo_ticker")
    e = st.session_state["current_eval"]
    if e and e.get("ticker") != ticker:
        st.session_state["current_eval"] = None
        st.session_state["current_analysis"] = None
        e = None
    if st.button("Analyse",type="primary"):
        load_demo_result = evaluate_demo(ticker)
        st.session_state["current_eval"] = load_demo_result
        st.session_state["current_analysis"] = None
        e = load_demo_result
    if not e:
        st.info("Choose a quick demo or select a company and press Analyse.")
        history_empty()
        return
    show_evaluation(e)
    history_empty()
    if e.get("error"):
        return
    st.divider()
    st.subheader("Agent Analysis")
    st.caption("One cloud-agent request using the synthetic snapshot-policy inputs above. The deterministic screen is not an AI response.")
    if st.button("Request agent analysis",key="agent_analyse_btn",type="primary"):
        with st.spinner("Calling snapshot-policy cloud agent…"):
            st.session_state["current_analysis"] = analyse_snapshot(e)
    a = st.session_state["current_analysis"]
    if a:
        if a.get("connected"):
            st.success("Cloud-agent response — synthetic inputs, not real-company research")
            st.markdown(a.get("content",""))
            if a.get("run_id"):
                st.caption(f"Run ID: {a['run_id']}")
        else:
            st.error(a.get("error","Agent request failed."))
    st.divider()
    if st.button("Save company for monitoring"):
        st.session_state["tracked"][ticker] = {"saved_at":now(),"evaluation":copy.deepcopy(e)}
        st.session_state["needs_review_list"].discard(ticker)
        st.session_state["v2_checks"].pop(ticker,None)
        invalidate(ticker)
        log("saved_baseline",ticker)
        st.success("Synthetic baseline saved. Previous comparison and list status cleared. Saving is not a qualification decision.")

with screen:
    st.markdown("""
    <style>
    .st-key-market_chart_panel {
        width: 100%;
        max-width: 100%;
        min-width: 0;
        box-sizing: border-box;
    }
    .st-key-market_chart_panel [data-testid="stExpander"],
    .st-key-market_chart_panel [data-testid="stExpanderDetails"],
    .st-key-market_chart_panel [data-testid="stVerticalBlock"],
    .st-key-market_chart_panel [data-testid="stVegaLiteChart"] {
        max-width: 100%;
        min-width: 0;
        box-sizing: border-box;
    }
    .st-key-market_chart_panel [data-testid="stVegaLiteChart"] {
        overflow-x: auto;
    }
    </style>
    """, unsafe_allow_html=True)
    with st.container(key="market_chart_panel"):
        render_market_chart()
    render_screen()
with tracking:
    st.subheader("Tracked Companies")
    st.caption("Manual synthetic comparisons only. No live data is fetched; session-only storage.")
    if not st.session_state["tracked"]:
        st.info("Screen a synthetic company and save its baseline first.")
    for ticker,entry in list(st.session_state["tracked"].items()):
        status = "Needs Review" if ticker in st.session_state["needs_review_list"] else "Unassigned"
        with st.expander(f"{ticker} — {status}"):
            st.caption("Baseline saved: "+entry["saved_at"])
            show_evaluation(entry["evaluation"])
            scenario = st.selectbox("Synthetic comparison scenario",list(SCENARIOS),key=f"scenario_{ticker}")
            if st.button("Compare synthetic scenario",key=f"check_{ticker}"):
                invalidate(ticker)
                new = evaluate_demo(ticker,SCENARIOS[scenario])
                changes,error = compare(entry["evaluation"],new)
                st.session_state["v2_checks"][ticker] = {"ticker":ticker,"baseline_id":identity(entry),"evaluation":new,"evaluation_id":identity(new),"changes":changes,"error":error,"checked_at":now(),"scenario":scenario}
            result = st.session_state["v2_checks"].get(ticker)
            if result:
                st.caption(f"Compared at {result['checked_at']} | Scenario used: {result['scenario']}")
                if result["error"]:
                    st.warning(result["error"])
                elif not result["changes"]:
                    st.success("No changes against the saved synthetic baseline.")
                else:
                    st.dataframe(result["changes"],hide_index=True,width="stretch")
                    if has_failure(result["changes"]) and st.button("Queue for approval",key=f"queue_{ticker}"):
                        st.session_state["pending_approval"] = copy.deepcopy(result)
                        st.success("Queued. This replaces any previous pending proposal.")
            if st.button("Remove from tracking",key=f"remove_{ticker}"):
                del st.session_state["tracked"][ticker]
                st.session_state["v2_checks"].pop(ticker,None)
                st.session_state["needs_review_list"].discard(ticker)
                invalidate(ticker)
                log("removed_from_tracking",ticker)
                st.rerun()
with approval:
    st.subheader("Approval")
    st.caption("Review-list updates only. No brokerage or watchlist actions.")
    p = st.session_state["pending_approval"]
    if not p:
        st.info("No pending approval. Queue a synthetic PASS → FAIL comparison from Tracked Companies.")
    else:
        ticker = p["ticker"]
        entry = st.session_state["tracked"].get(ticker)
        latest = st.session_state["v2_checks"].get(ticker)
        valid = entry is not None and latest is not None and identity(entry)==p["baseline_id"] and identity(latest)==identity(p) and identity(p["evaluation"])==p["evaluation_id"] and not p["error"] and has_failure(p["changes"])
        if not valid:
            st.session_state["pending_approval"] = None
            st.warning("Baseline or comparison changed; queue a fresh proposal.")
        else:
            st.write(f"Proposed: move {ticker} to Needs Review — synthetic demonstration.")
            st.dataframe(p["changes"],hide_index=True,width="stretch")
            a,b = st.columns(2)
            if a.button("Approve — move to Needs Review",type="primary"):
                st.session_state["needs_review_list"].add(ticker)
                st.session_state["pending_approval"] = None
                log("approved_needs_review",ticker)
                st.rerun()
            if b.button("Keep current list status"):
                st.session_state["pending_approval"] = None
                log("rejected_keep_current",ticker)
                st.rerun()
    st.subheader("Action log")
    if st.session_state["action_log"]:
        st.dataframe(list(reversed(st.session_state["action_log"])),hide_index=True,width="stretch")
    else:
        st.caption("No actions recorded this session.")
with about:
    st.subheader("About / Demo")
    st.markdown("""
### Snapshot policy v2
- Market cap: USD 2B–100B, inclusive.
- Previous completed-session close: at least USD 10.
- Provider-reported net profit: greater than zero; reporting period unspecified.
- Snapshot trading volume: at least 100,000 shares; not average daily volume.

The imported snapshot tool evaluates these rules. Missing values stay unverified.
No employee counts or cash-flow observations are relabeled as revised inputs.

### Data and connection status
- Screening: snapshot-policy tool with explicit synthetic fixtures.
- Agent: calls the existing snapshot adapter only on request; displays success or failure.
- Real-company screening and agent analysis: gated pending provenance verification.
- CSV: read-only saved-data preview; not screening input.
- History: unavailable; no fabricated annual chart or inferred profit period.
- Monitoring: manual synthetic comparisons; policy and rule definitions must match.
- State: session-only, lost on refresh. No database, scheduler, trades, or watchlist writes.

### Simulated-change workflow
1. Screen SMCHG and save its baseline.
2. In Tracked Companies choose Negative net profit or Low snapshot volume.
3. Compare, then queue the PASS → FAIL result.
4. Review it in Approval.

A replacement baseline clears its previous list status and comparison. A new comparison
invalidates that company's older proposal. Legacy session evaluations are cleared on
first use of this integrated page. Saving a baseline does not mark it Qualified.
""")

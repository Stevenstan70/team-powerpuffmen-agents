"""
frontend/adapter.py — Data adapter for the Powerpuffmen screening UI.

Separates presentation from backend calls.  Three public functions:

    evaluate_company(ticker, inputs)   → screening criteria result
    analyse_company(ticker, inputs)    → AI agent analysis result
    check_for_changes(ticker, baseline) → change-detection result

Live path: calls tools/powerpuffmen_basic_screen via .fn() where available.
Demo path: returns clearly-labelled fixtures when live data is not present.
The adapter never pretends demo output is live output.

Demo mode must not call live write operations.
"""

from __future__ import annotations

import sys
import os
import copy
import datetime as _dt
from typing import Optional

# ---------------------------------------------------------------------------
# Allow import of tools/ without installing the package
# ---------------------------------------------------------------------------
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

# ---------------------------------------------------------------------------
# Try to import the real screening backend
# ---------------------------------------------------------------------------
try:
    from tools.powerpuffmen_basic_screen import powerpuffmen_basic_screen
    _screen_fn = powerpuffmen_basic_screen.fn
    _SCREEN_BACKEND_AVAILABLE = True
except Exception:  # pragma: no cover
    _screen_fn = None
    _SCREEN_BACKEND_AVAILABLE = False

# ---------------------------------------------------------------------------
# Try to import Moomoo (optional — not available in all environments)
# ---------------------------------------------------------------------------
try:
    import moomoo as _ft
    _MOOMOO_AVAILABLE = True
except ImportError:  # pragma: no cover
    _ft = None
    _MOOMOO_AVAILABLE = False

_MOOMOO_HOST = "127.0.0.1"
_MOOMOO_PORT = 11111

# ---------------------------------------------------------------------------
# Canonical AdapterResult shape
# ---------------------------------------------------------------------------
# evaluate_company returns:
# {
#   "mode":        "live" | "demo",
#   "ticker":      str,
#   "company_name": str,
#   "currency":    str,
#   "data_timestamp": str (ISO-8601),
#   "is_live":     bool,
#   "criteria":    [ CriterionResult, ... ],
#   "aggregate_status": "pass" | "fail" | "unknown",
#   "scope_note":  str,
#   "error":       None | str,
# }
#
# CriterionResult:
# {
#   "id":              str,       # rule_name key
#   "label":           str,       # human-readable label
#   "operator":        str,       # e.g. "between", ">= ", "> "
#   "threshold":       str,       # raw threshold expression
#   "unit":            str,       # "USD", "count", etc.
#   "reporting_period": str,       # "TTM", "latest", etc.
#   "observed_value":  float|None,
#   "observed_fmt":    str,        # pre-formatted display string
#   "status":          "pass" | "fail" | "unknown",
# }

_SCOPE_NOTE = (
    "Only the criteria returned by the screening tool were evaluated. "
    "This does not establish full investment eligibility or constitute "
    "an investment recommendation."
)

_DEMO_TS = "2025-01-01T00:00:00Z"
_DEMO_COMPANY_NAMES = {
    "ACME":  "Acme Galactic Ltd (Demo)",
    "BLUE":  "Bluebird Ventures (Demo)",
    "CRST":  "Crescent Peak Corp (Demo)",
    "SMCHG": "SimCo Inc. (Simulated-change Demo)",
}

# ---------------------------------------------------------------------------
# Formatting helpers (kept local; presentation layer may override)
# ---------------------------------------------------------------------------

def _fmt_usd(v) -> str:
    if v is None:
        return "Unknown"
    if abs(v) >= 1_000_000_000:
        return f"${v / 1_000_000_000:,.2f} B"
    if abs(v) >= 1_000_000:
        return f"${v / 1_000_000:,.2f} M"
    return f"${v:,.2f}"


def _fmt_employees(v) -> str:
    if v is None:
        return "Unknown"
    return f"{int(v):,}"


# ---------------------------------------------------------------------------
# Convert a raw rule dict (from powerpuffmen_basic_screen) to a CriterionResult
# ---------------------------------------------------------------------------
_RULE_META: dict[str, dict] = {
    "market_cap_range": {
        "label": "Market Cap Range",
        "operator": "between",
        "unit": "USD",
        "reporting_period": "latest",
    },
    "min_close_price": {
        "label": "Min Close Price",
        "operator": ">=",
        "unit": "USD",
        "reporting_period": "latest",
    },
    "positive_operating_cash_flow": {
        "label": "Positive Operating Cash Flow (TTM)",
        "operator": ">",
        "unit": "USD",
        "reporting_period": "TTM",
    },
    "min_employee_count": {
        "label": "Min Employee Count",
        "operator": ">=",
        "unit": "count",
        "reporting_period": "latest",
    },
}

_RULE_FMT = {
    "market_cap_range": _fmt_usd,
    "positive_operating_cash_flow": _fmt_usd,
    "min_close_price": lambda v: f"${v:,.2f}" if v is not None else "Unknown",
    "min_employee_count": _fmt_employees,
}


def _rule_to_criterion(rule: dict) -> dict:
    rule_id = rule["rule_name"]
    meta = _RULE_META.get(rule_id, {
        "label": rule_id.replace("_", " ").title(),
        "operator": "?",
        "unit": "",
        "reporting_period": "",
    })
    status_map = {"PASS": "pass", "FAIL": "fail", "UNVERIFIED": "unknown"}
    fmt_fn = _RULE_FMT.get(rule_id, lambda v: str(v) if v is not None else "Unknown")
    return {
        "id": rule_id,
        "label": meta["label"],
        "operator": meta["operator"],
        "threshold": rule["threshold"],
        "unit": meta["unit"],
        "reporting_period": meta["reporting_period"],
        "observed_value": rule["observed_value"],
        "observed_fmt": fmt_fn(rule["observed_value"]),
        "status": status_map.get(rule["status"], "unknown"),
    }


def _aggregate_from_criteria(criteria: list[dict]) -> str:
    statuses = {c["status"] for c in criteria}
    if "fail" in statuses:
        return "fail"
    if "unknown" in statuses:
        return "unknown"
    return "pass"


# ---------------------------------------------------------------------------
# Public: validate_ticker
# ---------------------------------------------------------------------------

#: Regex for a syntactically valid ticker: 1–10 word characters only.
#: Rejects multi-word strings like "baba amskd".
import re as _re
_TICKER_RE = _re.compile(r'^[A-Z0-9]{1,10}$')


def validate_ticker(raw: str) -> dict:
    """Validate a ticker string entered by the user.

    Returns:
        {
            "valid":   bool,
            "ticker":  str,   # normalised (upper-stripped) if valid, else ""
            "reason":  str | None,  # human-readable rejection reason
        }

    Validation rules (all in the frontend — no network call):
    1. Must be non-empty after stripping whitespace.
    2. Must be a single word (no spaces).
    3. Must match ^[A-Z0-9]{1,10}$ after uppercasing.
    Inputs like "baba amskd" are rejected at rule 2.
    Inputs like "XYZXYZ999999" are rejected at rule 3.
    """
    stripped = raw.strip()
    if not stripped:
        return {"valid": False, "ticker": "", "reason": "Ticker cannot be empty."}
    if " " in stripped or "\t" in stripped:
        return {
            "valid": False,
            "ticker": "",
            "reason": (
                f"'{stripped}' looks like multiple words. "
                "Enter a single ticker symbol, e.g. AAPL."
            ),
        }
    upper = stripped.upper()
    if not _TICKER_RE.match(upper):
        return {
            "valid": False,
            "ticker": "",
            "reason": (
                f"'{upper}' is not a valid ticker format. "
                "Use 1–10 letters/digits only, e.g. AAPL or BRK.A."
            ),
        }
    return {"valid": True, "ticker": upper, "reason": None}


# ---------------------------------------------------------------------------
# Public: resolve_ticker
# ---------------------------------------------------------------------------

def resolve_ticker(ticker: str) -> dict:
    """Look up a ticker in Moomoo and return company metadata.

    This is the single point of contact with Moomoo for company identity.
    It does NOT retrieve financial metrics — that is fetch_moomoo_inputs().

    Returns:
        {
            "connected":    bool,
            "found":        bool,
            "ticker":       str,          # e.g. "AAPL"
            "moomoo_code":  str | None,   # e.g. "US.AAPL"
            "company_name": str | None,
            "sec_type":     str | None,   # "STOCK", "ETF", etc.
            "error":        str | None,
        }

    Only tickers of sec_type STOCK are considered valid for screening.
    If Moomoo OpenD is not running, returns connected=False with a clear error.
    Never fabricates a company name — unverified input is not shown as a heading.
    """
    if not _MOOMOO_AVAILABLE:
        return {
            "connected": False, "found": False,
            "ticker": ticker, "moomoo_code": None,
            "company_name": None, "sec_type": None,
            "error": "moomoo-api package is not installed.",
        }

    ctx = None
    try:
        ctx = _ft.OpenQuoteContext(host=_MOOMOO_HOST, port=_MOOMOO_PORT)
        # Search with the raw ticker as keyword; exact match wins
        ret, data = ctx.get_search_quote(ticker, max_count=10)
        if ret != _ft.RET_OK:
            return {
                "connected": True, "found": False,
                "ticker": ticker, "moomoo_code": None,
                "company_name": None, "sec_type": None,
                "error": f"Moomoo search failed: {data}",
            }
        if data.empty:
            return {
                "connected": True, "found": False,
                "ticker": ticker, "moomoo_code": None,
                "company_name": None, "sec_type": None,
                "error": f"No results found for '{ticker}'.",
            }
        # Prefer an exact US STOCK match; fall back to first STOCK result
        candidates = data[data["sec_type"] == "STOCK"]
        if candidates.empty:
            return {
                "connected": True, "found": False,
                "ticker": ticker, "moomoo_code": None,
                "company_name": None, "sec_type": data.iloc[0]["sec_type"],
                "error": (
                    f"'{ticker}' was found but is a {data.iloc[0]['sec_type']}, "
                    "not a STOCK. Only stocks are supported."
                ),
            }
        # Prefer US market exact code match
        us_exact = candidates[candidates["code"] == f"US.{ticker}"]
        row = us_exact.iloc[0] if not us_exact.empty else candidates.iloc[0]
        return {
            "connected": True, "found": True,
            "ticker": ticker,
            "moomoo_code": row["code"],
            "company_name": row["name"],
            "sec_type": row["sec_type"],
            "error": None,
        }
    except Exception as exc:
        return {
            "connected": False, "found": False,
            "ticker": ticker, "moomoo_code": None,
            "company_name": None, "sec_type": None,
            "error": f"Moomoo connection error: {exc}",
        }
    finally:
        if ctx is not None:
            try:
                ctx.close()
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Public: fetch_moomoo_inputs
# ---------------------------------------------------------------------------

def fetch_moomoo_inputs(moomoo_code: str) -> dict:
    """Retrieve the financial inputs needed for screening from Moomoo.

    Uses verified fields from moomoo-api 10.11.7108:
      - close_price_usd:    get_market_snapshot → last_price
      - market_cap_usd:     get_market_snapshot → total_market_val
      - employee_count:     get_company_profile → "Employees" row

    BLOCKED — operating_cash_flow_ttm_usd:
      The per-ticker TTM OCF is available via get_financials_statements
      but requires raw field-ID parsing owned by the backend teammate.
      This field is returned as None with a clear not-connected note.
      It is NOT substituted with demo data or set to zero.

    Returns:
        {
            "connected":    bool,
            "moomoo_code":  str,
            "inputs": {
                "market_cap_usd":               float | None,
                "close_price_usd":              float | None,
                "operating_cash_flow_ttm_usd":  float | None,  # always None (blocked)
                "employee_count":               int | None,
            },
            "input_notes": {
                "market_cap_usd":               str,  # source / status
                "close_price_usd":              str,
                "operating_cash_flow_ttm_usd":  str,
                "employee_count":               str,
            },
            "currency": str,
            "data_timestamp": str,
            "error": str | None,
        }
    """
    now_iso = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    if not _MOOMOO_AVAILABLE:
        return {
            "connected": False,
            "moomoo_code": moomoo_code,
            "inputs": {k: None for k in (
                "market_cap_usd", "close_price_usd",
                "operating_cash_flow_ttm_usd", "employee_count",
            )},
            "input_notes": {k: "moomoo-api not installed" for k in (
                "market_cap_usd", "close_price_usd",
                "operating_cash_flow_ttm_usd", "employee_count",
            )},
            "currency": "USD",
            "data_timestamp": now_iso,
            "error": "moomoo-api package is not installed.",
        }

    inputs: dict = {
        "market_cap_usd": None,
        "close_price_usd": None,
        "operating_cash_flow_ttm_usd": None,
        "employee_count": None,
    }
    notes: dict = {
        "market_cap_usd": "Not retrieved",
        "close_price_usd": "Not retrieved",
        "operating_cash_flow_ttm_usd": (
            "Not connected — TTM OCF retrieval from get_financials_statements "
            "requires raw field-ID parsing (backend teammate dependency)."
        ),
        "employee_count": "Not retrieved",
    }
    errors: list[str] = []

    ctx = None
    try:
        ctx = _ft.OpenQuoteContext(host=_MOOMOO_HOST, port=_MOOMOO_PORT)

        # ── Snapshot: price + market cap ─────────────────────────────────────
        try:
            ret, snap = ctx.get_market_snapshot([moomoo_code])
            if ret == _ft.RET_OK and not snap.empty:
                row = snap.iloc[0]
                price = row.get("last_price")
                mktcap = row.get("total_market_val")
                if price is not None and str(price) not in ("nan", "None"):
                    inputs["close_price_usd"] = float(price)
                    notes["close_price_usd"] = f"Moomoo get_market_snapshot → last_price ({now_iso})"
                if mktcap is not None and str(mktcap) not in ("nan", "None"):
                    inputs["market_cap_usd"] = float(mktcap)
                    notes["market_cap_usd"] = f"Moomoo get_market_snapshot → total_market_val ({now_iso})"
            else:
                errors.append(f"Snapshot failed for {moomoo_code}: {snap}")
        except Exception as exc:
            errors.append(f"Snapshot error: {exc}")

        # ── Company profile: employee count ───────────────────────────────────
        try:
            ret, prof = ctx.get_company_profile(moomoo_code)
            if ret == _ft.RET_OK and not prof.empty:
                emp_rows = prof[prof["name"] == "Employees"]
                if not emp_rows.empty:
                    raw_emp = emp_rows.iloc[0]["value"]
                    try:
                        inputs["employee_count"] = int(str(raw_emp).replace(",", ""))
                        notes["employee_count"] = f"Moomoo get_company_profile → Employees ({now_iso})"
                    except (ValueError, TypeError):
                        notes["employee_count"] = f"Employee count not parseable: {raw_emp!r}"
                else:
                    notes["employee_count"] = "Employee count not present in company profile"
            else:
                errors.append(f"Company profile failed for {moomoo_code}: {prof}")
        except Exception as exc:
            errors.append(f"Company profile error: {exc}")

    except Exception as exc:
        return {
            "connected": False,
            "moomoo_code": moomoo_code,
            "inputs": inputs,
            "input_notes": notes,
            "currency": "USD",
            "data_timestamp": now_iso,
            "error": f"Moomoo connection error: {exc}",
        }
    finally:
        if ctx is not None:
            try:
                ctx.close()
            except Exception:
                pass

    return {
        "connected": True,
        "moomoo_code": moomoo_code,
        "inputs": inputs,
        "input_notes": notes,
        "currency": "USD",
        "data_timestamp": now_iso,
        "error": "; ".join(errors) if errors else None,
    }


# ---------------------------------------------------------------------------
# Public: evaluate_company
# ---------------------------------------------------------------------------

def evaluate_company(
    ticker: str,
    inputs: Optional[dict] = None,
    *,
    demo_override: Optional[str] = None,
) -> dict:
    """Screen a company against the available criteria.

    Parameters
    ----------
    ticker:
        Stock ticker symbol (used as a label; not used to fetch live data).
    inputs:
        Dict with keys: market_cap_usd, close_price_usd,
        operating_cash_flow_ttm_usd, employee_count.  Any may be None.
        When None and no demo_override, the adapter returns a demo fixture.
    demo_override:
        Force a named demo fixture ("ACME", "BLUE", "CRST", "SMCHG").
        Used by the UI to demonstrate scenarios explicitly.
    """
    now_iso = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # ── Demo fixture path ────────────────────────────────────────────────────
    if inputs is None or demo_override is not None:
        return _demo_evaluate(ticker, demo_override or ticker.upper(), now_iso)

    # ── Live path (uses real screening backend) ──────────────────────────────
    if not _SCREEN_BACKEND_AVAILABLE:
        return {
            "mode": "error",
            "ticker": ticker,
            "company_name": ticker,
            "currency": "USD",
            "data_timestamp": now_iso,
            "is_live": False,
            "criteria": [],
            "aggregate_status": "unknown",
            "scope_note": _SCOPE_NOTE,
            "error": (
                "Screening backend (powerpuffmen_basic_screen) is not available. "
                "Provide inputs manually or select a demo fixture."
            ),
        }

    try:
        raw = _screen_fn(
            market_cap_usd=inputs.get("market_cap_usd"),
            close_price_usd=inputs.get("close_price_usd"),
            operating_cash_flow_ttm_usd=inputs.get("operating_cash_flow_ttm_usd"),
            employee_count=inputs.get("employee_count"),
        )
    except Exception as exc:
        return {
            "mode": "error",
            "ticker": ticker,
            "company_name": ticker,
            "currency": "USD",
            "data_timestamp": now_iso,
            "is_live": False,
            "criteria": [],
            "aggregate_status": "unknown",
            "scope_note": _SCOPE_NOTE,
            "error": f"Screening tool raised an error: {exc}",
        }

    criteria = [_rule_to_criterion(r) for r in raw["rules"]]
    return {
        "mode": "live",
        "ticker": ticker,
        "company_name": ticker,
        "currency": "USD",
        "data_timestamp": now_iso,
        "is_live": True,
        "criteria": criteria,
        "aggregate_status": _aggregate_from_criteria(criteria),
        "scope_note": raw.get("scope_note", _SCOPE_NOTE),
        "error": None,
    }


# ---------------------------------------------------------------------------
# Public: analyse_company (agent integration point)
# ---------------------------------------------------------------------------

def analyse_company(ticker: str, evaluation: dict) -> dict:
    """Request an AI-agent analysis of a screened company.

    Returns a result dict:
        { "connected": bool, "content": str | None, "error": str | None }

    The IBM watsonx Orchestrate agent is NOT currently wired to this
    prototype.  Returns connected=False with a clear explanation.
    Do not return fabricated agent output labelled as real.
    """
    # Intentionally not connected.
    # When a real agent endpoint is wired, replace this stub.
    return {
        "connected": False,
        "content": None,
        "error": (
            "Analysis not connected. The IBM watsonx Orchestrate agent "
            "endpoint has not been configured for this prototype session."
        ),
    }


# ---------------------------------------------------------------------------
# Public: check_for_changes
# ---------------------------------------------------------------------------

def check_for_changes(ticker: str, baseline: dict, current_inputs: Optional[dict]) -> dict:
    """Compare a new evaluation against a saved baseline.

    Returns:
    {
        "ticker": str,
        "checked_at": str (ISO-8601),
        "comparable": bool,
        "not_comparable_reason": str | None,
        "changes": [ ChangeEntry, ... ],
        "new_evaluation": dict,    # full evaluate_company result
        "error": str | None,
    }

    ChangeEntry:
    {
        "criterion_id": str,
        "criterion_label": str,
        "change_type": "value_changed" | "status_transition" | "data_unavailable" | "criteria_changed",
        "old_value_fmt": str,
        "new_value_fmt": str,
        "old_status": str,
        "new_status": str,
        "explanation": str,
    }
    """
    now_iso = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    new_eval = evaluate_company(ticker, current_inputs)

    if new_eval["error"]:
        return {
            "ticker": ticker,
            "checked_at": now_iso,
            "comparable": False,
            "not_comparable_reason": f"New evaluation failed: {new_eval['error']}",
            "changes": [],
            "new_evaluation": new_eval,
            "error": new_eval["error"],
        }

    baseline_eval = baseline.get("evaluation", {})
    baseline_criteria = {c["id"]: c for c in baseline_eval.get("criteria", [])}
    new_criteria = {c["id"]: c for c in new_eval.get("criteria", [])}

    # Check if the set of criteria IDs changed
    if set(baseline_criteria.keys()) != set(new_criteria.keys()):
        return {
            "ticker": ticker,
            "checked_at": now_iso,
            "comparable": False,
            "not_comparable_reason": (
                "The set of screening criteria has changed since the baseline was saved. "
                "Evaluations are not directly comparable. Save a new baseline to reset."
            ),
            "changes": [],
            "new_evaluation": new_eval,
            "error": None,
        }

    changes = []
    all_ids = set(baseline_criteria.keys()) | set(new_criteria.keys())
    for cid in all_ids:
        old_c = baseline_criteria.get(cid)
        new_c = new_criteria.get(cid)

        if old_c is None or new_c is None:
            changes.append({
                "criterion_id": cid,
                "criterion_label": (new_c or old_c or {}).get("label", cid),
                "change_type": "criteria_changed",
                "old_value_fmt": old_c["observed_fmt"] if old_c else "N/A",
                "new_value_fmt": new_c["observed_fmt"] if new_c else "N/A",
                "old_status": old_c["status"] if old_c else "unknown",
                "new_status": new_c["status"] if new_c else "unknown",
                "explanation": "This criterion was added or removed since the baseline.",
            })
            continue

        old_val = old_c["observed_value"]
        new_val = new_c["observed_value"]
        old_status = old_c["status"]
        new_status = new_c["status"]

        # Missing data — never treated as zero or confirmed failure
        if new_val is None and old_val is not None:
            changes.append({
                "criterion_id": cid,
                "criterion_label": new_c["label"],
                "change_type": "data_unavailable",
                "old_value_fmt": old_c["observed_fmt"],
                "new_value_fmt": "Unavailable",
                "old_status": old_status,
                "new_status": "unknown",
                "explanation": (
                    f"Data for '{new_c['label']}' is no longer available. "
                    "This is not treated as a failure — the status is Unknown."
                ),
            })
            continue

        status_changed = old_status != new_status
        value_changed = old_val != new_val

        if status_changed:
            changes.append({
                "criterion_id": cid,
                "criterion_label": new_c["label"],
                "change_type": "status_transition",
                "old_value_fmt": old_c["observed_fmt"],
                "new_value_fmt": new_c["observed_fmt"],
                "old_status": old_status,
                "new_status": new_status,
                "explanation": (
                    f"'{new_c['label']}' changed from {old_status.upper()} "
                    f"to {new_status.upper()}. "
                    f"Value: {old_c['observed_fmt']} → {new_c['observed_fmt']}."
                ),
            })
        elif value_changed:
            changes.append({
                "criterion_id": cid,
                "criterion_label": new_c["label"],
                "change_type": "value_changed",
                "old_value_fmt": old_c["observed_fmt"],
                "new_value_fmt": new_c["observed_fmt"],
                "old_status": old_status,
                "new_status": new_status,
                "explanation": (
                    f"'{new_c['label']}' value changed: "
                    f"{old_c['observed_fmt']} → {new_c['observed_fmt']} "
                    f"(status unchanged: {new_status.upper()})."
                ),
            })

    return {
        "ticker": ticker,
        "checked_at": now_iso,
        "comparable": True,
        "not_comparable_reason": None,
        "changes": changes,
        "new_evaluation": new_eval,
        "error": None,
    }


# ---------------------------------------------------------------------------
# Demo fixtures
# ---------------------------------------------------------------------------

def _demo_evaluate(ticker: str, fixture_key: str, ts: str) -> dict:
    """Return a named demo fixture.  All results are explicitly mode='demo'."""
    fixtures = _DEMO_FIXTURES()
    fixture = fixtures.get(fixture_key.upper(), fixtures["ACME"])
    result = copy.deepcopy(fixture)
    result["ticker"] = ticker
    result["data_timestamp"] = ts
    result["mode"] = "demo"
    result["is_live"] = False
    return result


def _DEMO_FIXTURES() -> dict:
    """Build and return demo fixtures (called lazily to keep module load fast)."""

    def _make_criteria(rules_raw):
        return [_rule_to_criterion(r) for r in rules_raw]

    # ── ACME: all pass ───────────────────────────────────────────────────────
    acme_rules = [
        {"rule_name": "market_cap_range",            "observed_value": 15_000_000_000, "threshold": "2,000,000,000 <= x <= 100,000,000,000", "status": "PASS", "explanation": "Market cap is within USD 2B–100B."},
        {"rule_name": "min_close_price",              "observed_value": 42.50,          "threshold": "x >= 10", "status": "PASS", "explanation": "Close price meets the USD 10 minimum."},
        {"rule_name": "positive_operating_cash_flow", "observed_value": 850_000_000,    "threshold": "x > 0",   "status": "PASS", "explanation": "Operating cash flow is positive."},
        {"rule_name": "min_employee_count",           "observed_value": 3_200,          "threshold": "x >= 20", "status": "PASS", "explanation": "Employee count meets the minimum of 20."},
    ]
    acme_criteria = _make_criteria(acme_rules)

    # ── BLUE: OCF FAIL ───────────────────────────────────────────────────────
    blue_rules = [
        {"rule_name": "market_cap_range",            "observed_value": 5_500_000_000,   "threshold": "2,000,000,000 <= x <= 100,000,000,000", "status": "PASS", "explanation": "Market cap is within USD 2B–100B."},
        {"rule_name": "min_close_price",              "observed_value": 18.75,           "threshold": "x >= 10", "status": "PASS", "explanation": "Close price meets the USD 10 minimum."},
        {"rule_name": "positive_operating_cash_flow", "observed_value": -120_000_000,    "threshold": "x > 0",   "status": "FAIL", "explanation": "Operating cash flow is not strictly positive."},
        {"rule_name": "min_employee_count",           "observed_value": 870,             "threshold": "x >= 20", "status": "PASS", "explanation": "Employee count meets the minimum of 20."},
    ]
    blue_criteria = _make_criteria(blue_rules)

    # ── CRST: employees UNVERIFIED ───────────────────────────────────────────
    crst_rules = [
        {"rule_name": "market_cap_range",            "observed_value": 8_200_000_000,  "threshold": "2,000,000,000 <= x <= 100,000,000,000", "status": "PASS", "explanation": "Market cap is within USD 2B–100B."},
        {"rule_name": "min_close_price",              "observed_value": 67.00,          "threshold": "x >= 10", "status": "PASS", "explanation": "Close price meets the USD 10 minimum."},
        {"rule_name": "positive_operating_cash_flow", "observed_value": 310_000_000,    "threshold": "x > 0",   "status": "PASS", "explanation": "Operating cash flow is positive."},
        {"rule_name": "min_employee_count",           "observed_value": None,           "threshold": "x >= 20", "status": "UNVERIFIED", "explanation": "Employee count not provided."},
    ]
    crst_criteria = _make_criteria(crst_rules)

    # ── SMCHG: simulated-change demo ─────────────────────────────────────────
    # Baseline: ACME-like (all pass); "new" state: OCF goes negative (fail).
    # Used to demonstrate a pass→fail transition without touching live data.
    smchg_baseline_rules = [
        {"rule_name": "market_cap_range",            "observed_value": 12_000_000_000, "threshold": "2,000,000,000 <= x <= 100,000,000,000", "status": "PASS", "explanation": "Market cap is within USD 2B–100B."},
        {"rule_name": "min_close_price",              "observed_value": 55.00,          "threshold": "x >= 10", "status": "PASS", "explanation": "Close price meets the USD 10 minimum."},
        {"rule_name": "positive_operating_cash_flow", "observed_value": 200_000_000,    "threshold": "x > 0",   "status": "PASS", "explanation": "Operating cash flow is positive."},
        {"rule_name": "min_employee_count",           "observed_value": 1_500,          "threshold": "x >= 20", "status": "PASS", "explanation": "Employee count meets the minimum of 20."},
    ]
    smchg_criteria = _make_criteria(smchg_baseline_rules)

    def _make(name, currency, criteria, agg):
        return {
            "mode": "demo",
            "ticker": name,
            "company_name": _DEMO_COMPANY_NAMES.get(name, name),
            "currency": currency,
            "data_timestamp": _DEMO_TS,
            "is_live": False,
            "criteria": criteria,
            "aggregate_status": agg,
            "scope_note": _SCOPE_NOTE,
            "error": None,
        }

    return {
        "ACME":  _make("ACME",  "USD", acme_criteria, "pass"),
        "BLUE":  _make("BLUE",  "USD", blue_criteria, "fail"),
        "CRST":  _make("CRST",  "USD", crst_criteria, "unknown"),
        "SMCHG": _make("SMCHG", "USD", smchg_criteria, "pass"),
    }


# ---------------------------------------------------------------------------
# Simulated-change scenario helper
# ---------------------------------------------------------------------------

def get_simulated_change_scenario() -> dict:
    """Return (baseline_eval, changed_eval) for the simulated-change demo.

    Demonstrates a PASS → FAIL transition on the OCF criterion.
    Clearly labelled as DEMO — does not call any live data source.
    """
    fixtures = _DEMO_FIXTURES()
    baseline_eval = copy.deepcopy(fixtures["SMCHG"])

    # Build the "changed" evaluation: OCF flips negative
    changed_rules = [
        {"rule_name": "market_cap_range",            "observed_value": 12_000_000_000, "threshold": "2,000,000,000 <= x <= 100,000,000,000", "status": "PASS", "explanation": "Market cap is within USD 2B–100B."},
        {"rule_name": "min_close_price",              "observed_value": 55.00,          "threshold": "x >= 10", "status": "PASS", "explanation": "Close price meets the USD 10 minimum."},
        {"rule_name": "positive_operating_cash_flow", "observed_value": -45_000_000,    "threshold": "x > 0",   "status": "FAIL", "explanation": "Operating cash flow is not strictly positive."},
        {"rule_name": "min_employee_count",           "observed_value": 1_500,          "threshold": "x >= 20", "status": "PASS", "explanation": "Employee count meets the minimum of 20."},
    ]
    changed_criteria = [_rule_to_criterion(r) for r in changed_rules]
    changed_eval = copy.deepcopy(baseline_eval)
    changed_eval["criteria"] = changed_criteria
    changed_eval["aggregate_status"] = "fail"
    changed_eval["data_timestamp"] = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    return {"baseline": baseline_eval, "changed": changed_eval}

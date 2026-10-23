"""
Data adapter for the Powerpuffmen screening UI.

Preserves the original screening policy:
- Market-cap range
- Minimum previous closing price
- Positive operating cash flow TTM
- Minimum employee count

This module does not implement a new policy, CSV integration,
scheduled monitoring, backtesting, or an Orchestrate connection.

Demo data requires an explicit demo_override.
Missing inputs never silently become demo data.
"""

from __future__ import annotations

import copy
import datetime as _dt
import math
import os
import re
import sys
from typing import Optional


_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)


_SCREEN_IMPORT_ERROR = None

try:
    from tools.powerpuffmen_basic_screen import powerpuffmen_basic_screen

    _screen_fn = getattr(
        powerpuffmen_basic_screen,
        "fn",
        powerpuffmen_basic_screen,
    )
    _SCREEN_BACKEND_AVAILABLE = callable(_screen_fn)
except Exception as exc:
    _screen_fn = None
    _SCREEN_BACKEND_AVAILABLE = False
    _SCREEN_IMPORT_ERROR = str(exc)


try:
    import moomoo as _ft

    _MOOMOO_AVAILABLE = True
except ImportError:
    _ft = None
    _MOOMOO_AVAILABLE = False


_MOOMOO_HOST = "127.0.0.1"
_MOOMOO_PORT = 11111

_POLICY_VERSION = "legacy-four-rules-previous-close-v1"

_SCOPE_NOTE = (
    "Only the criteria returned by the screening tool were evaluated. "
    "This does not establish full investment eligibility or constitute "
    "an investment recommendation."
)

_INPUT_KEYS = (
    "market_cap_usd",
    "close_price_usd",
    "operating_cash_flow_ttm_usd",
    "employee_count",
)

_DEMO_TS = "2025-01-01T00:00:00Z"

_DEMO_COMPANY_NAMES = {
    "ACME": "Acme Galactic Ltd (Demo)",
    "BLUE": "Bluebird Ventures (Demo)",
    "CRST": "Crescent Peak Corp (Demo)",
    "SMCHG": "SimCo Inc. (Simulated-change Demo)",
}

# Syntax only. Security existence is verified separately.
# No automatic mapping between "." and "-" share-class notation.
_TICKER_RE = re.compile(r"[A-Z0-9]+(?:[.-][A-Z0-9]+)*")

_RULE_META = {
    "market_cap_range": {
        "label": "Market Cap Range",
        "operator": "between",
        "unit": "USD",
        "reporting_period": "latest",
    },
    "min_close_price": {
        "label": "Minimum Previous Close Price",
        "operator": ">=",
        "unit": "USD",
        "reporting_period": "previous completed trading session",
    },
    "positive_operating_cash_flow": {
        "label": "Positive Operating Cash Flow (TTM)",
        "operator": ">",
        "unit": "USD",
        "reporting_period": "TTM",
    },
    "min_employee_count": {
        "label": "Minimum Employee Count",
        "operator": ">=",
        "unit": "count",
        "reporting_period": "company profile; date unverified",
    },
}


def _now_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


def _number(value, *, integer=False):
    """Convert finite numeric values; unknown/invalid values become None."""
    if value is None or isinstance(value, bool):
        return None

    try:
        if isinstance(value, str):
            value = value.strip().replace(",", "")
            if not value:
                return None

        result = float(value)

        if not math.isfinite(result):
            return None

        if integer:
            if result < 0 or not result.is_integer():
                return None
            return int(result)

        return result
    except (ValueError, TypeError, OverflowError):
        return None


def _text(value):
    if value is None:
        return None

    text = str(value).strip()

    if not text or text.lower() in {"nan", "none", "nat", "<na>"}:
        return None

    return text


def _fmt_usd(value) -> str:
    value = _number(value)

    if value is None:
        return "Unknown"
    if abs(value) >= 1_000_000_000:
        return f"${value / 1_000_000_000:,.2f} B"
    if abs(value) >= 1_000_000:
        return f"${value / 1_000_000:,.2f} M"

    return f"${value:,.2f}"


def _fmt_employees(value) -> str:
    value = _number(value, integer=True)
    return "Unknown" if value is None else f"{value:,}"


_RULE_FMT = {
    "market_cap_range": _fmt_usd,
    "min_close_price": _fmt_usd,
    "positive_operating_cash_flow": _fmt_usd,
    "min_employee_count": _fmt_employees,
}


def _normalise_inputs(inputs: dict) -> dict:
    result = {
        key: _number(
            inputs.get(key),
            integer=(key == "employee_count"),
        )
        for key in _INPUT_KEYS
    }

    for key in ("market_cap_usd", "close_price_usd"):
        value = result[key]
        if value is not None and value <= 0:
            result[key] = None

    return result


def _close_context(ctx):
    if ctx is not None:
        try:
            ctx.close()
        except Exception:
            pass


def _rule_to_criterion(rule: dict) -> dict:
    rule_id = str(rule["rule_name"])

    meta = _RULE_META.get(
        rule_id,
        {
            "label": rule_id.replace("_", " ").title(),
            "operator": "?",
            "unit": "",
            "reporting_period": "",
        },
    )

    value = _number(
        rule.get("observed_value"),
        integer=(rule_id == "min_employee_count"),
    )

    if (
        rule_id in {"market_cap_range", "min_close_price"}
        and value is not None
        and value <= 0
    ):
        value = None

    status_map = {
        "PASS": "pass",
        "FAIL": "fail",
        "UNVERIFIED": "unknown",
        "UNKNOWN": "unknown",
    }

    status = status_map.get(
        str(rule.get("status", "")).upper(),
        "unknown",
    )

    if value is None:
        status = "unknown"

    formatter = _RULE_FMT.get(
        rule_id,
        lambda v: "Unknown" if v is None else str(v),
    )

    return {
        "id": rule_id,
        "label": meta["label"],
        "operator": meta["operator"],
        "threshold": str(rule.get("threshold", "")),
        "unit": meta["unit"],
        "reporting_period": meta["reporting_period"],
        "observed_value": value,
        "observed_fmt": formatter(value),
        "status": status,
        "explanation": str(rule.get("explanation", "")),
    }


def _aggregate_from_criteria(criteria: list[dict]) -> str:
    if not criteria:
        return "unknown"

    statuses = {c.get("status", "unknown") for c in criteria}

    if "fail" in statuses:
        return "fail"
    if statuses == {"pass"}:
        return "pass"

    return "unknown"


def _evaluation_error(ticker: str, message: str) -> dict:
    return {
        "mode": "error",
        "ticker": ticker,
        "company_name": None,
        "currency": "USD",
        "data_timestamp": None,
        "evaluated_at": _now_iso(),
        "criteria_version": _POLICY_VERSION,
        "source": "unavailable",
        "is_live": False,
        "criteria": [],
        "aggregate_status": "unknown",
        "scope_note": _SCOPE_NOTE,
        "error": message,
    }


def validate_ticker(raw: str) -> dict:
    """Validate one US ticker's syntax without a network request."""
    if not isinstance(raw, str) or not raw.strip():
        return {
            "valid": False,
            "ticker": "",
            "reason": "Ticker cannot be empty.",
        }

    ticker = raw.strip().upper()

    if any(char.isspace() for char in ticker):
        return {
            "valid": False,
            "ticker": "",
            "reason": (
                "Input looks like multiple words. "
                "Enter one ticker symbol."
            ),
        }

    if ticker.startswith("US."):
        ticker = ticker[3:]

    if (
        not 1 <= len(ticker) <= 10
        or _TICKER_RE.fullmatch(ticker) is None
    ):
        return {
            "valid": False,
            "ticker": "",
            "reason": (
                "Use one ticker with 1-10 letters/digits and optional "
                "internal dots or hyphens. Its existence will be checked "
                "separately against Moomoo."
            ),
        }

    return {"valid": True, "ticker": ticker, "reason": None}


def resolve_ticker(ticker: str) -> dict:
    """Resolve an exact US STOCK match; never choose a similar company."""
    validation = validate_ticker(ticker)
    normalised = validation["ticker"] if validation["valid"] else ""

    result = {
        "connected": False,
        "found": False,
        "ticker": normalised,
        "moomoo_code": None,
        "company_name": None,
        "sec_type": None,
        "error": None,
    }

    if not validation["valid"]:
        result["error"] = validation["reason"]
        return result

    if not _MOOMOO_AVAILABLE:
        result["error"] = "moomoo-api package is not installed."
        return result

    ctx = None

    try:
        ctx = _ft.OpenQuoteContext(
            host=_MOOMOO_HOST,
            port=_MOOMOO_PORT,
        )

        ret, data = ctx.get_search_quote(normalised, max_count=10)

        if ret != _ft.RET_OK:
            result["error"] = (
                f"Unable to verify company: Moomoo search failed: {data}"
            )
            return result

        result["connected"] = True

        if data.empty:
            result["error"] = (
                f"No exact US stock match found for '{normalised}'."
            )
            return result

        required = {"code", "name", "sec_type"}
        if not required.issubset(data.columns):
            result["error"] = (
                "Unexpected search response schema. Company not verified."
            )
            return result

        expected_code = f"US.{normalised}"

        exact = data[
            data["code"].astype(str).str.upper().eq(expected_code)
        ]

        if exact.empty:
            result["error"] = (
                f"No exact US stock match found for '{normalised}'. "
                "No alternative company was selected."
            )
            return result

        stock_rows = exact[
            exact["sec_type"].astype(str).str.upper().eq("STOCK")
        ]

        if stock_rows.empty:
            result["sec_type"] = str(exact.iloc[0]["sec_type"])
            result["error"] = (
                "The exact security is not classified as STOCK. "
                "Only stocks are supported."
            )
            return result

        names = stock_rows["name"].dropna().astype(str).unique()
        if len(names) != 1:
            result["error"] = (
                "Ambiguous company identity. No company was selected."
            )
            return result

        row = stock_rows.iloc[0]

        result.update(
            found=True,
            moomoo_code=str(row["code"]),
            company_name=str(row["name"]),
            sec_type="STOCK",
            error=None,
        )
        return result

    except Exception as exc:
        result["error"] = (
            f"Unable to verify company: {type(exc).__name__}: {exc}"
        )
        return result
    finally:
        _close_context(ctx)


def fetch_moomoo_inputs(moomoo_code: str) -> dict:
    """
    Retrieve original-policy inputs.

    close_price_usd uses prev_close_price, not last_price.
    Cash-flow retrieval remains unconnected.
    Employee lookup is optional and may be unavailable.
    """
    retrieved_at = _now_iso()

    inputs = dict.fromkeys(_INPUT_KEYS)

    notes = {
        "market_cap_usd": "Not retrieved.",
        "close_price_usd": "Not retrieved.",
        "operating_cash_flow_ttm_usd": (
            "Not connected: verified TTM operating-cash-flow "
            "retrieval has not been implemented."
        ),
        "employee_count": "Not retrieved.",
    }

    result = {
        "connected": False,
        "moomoo_code": moomoo_code,
        "inputs": inputs,
        "input_notes": notes,
        "currency": "USD",
        "data_timestamp": None,
        "retrieved_at": retrieved_at,
        "source": "moomoo",
        "price_basis": "previous completed trading session close",
        "snapshot_update_time": None,
        "snapshot_update_time_timezone": (
            "Provider US-market timestamp; not converted to UTC"
        ),
        "error": None,
    }

    validation = validate_ticker(moomoo_code)

    if (
        not isinstance(moomoo_code, str)
        or not moomoo_code.upper().startswith("US.")
        or not validation["valid"]
    ):
        result["error"] = (
            "Expected a verified US security code, such as US.AAPL."
        )
        return result

    canonical_code = f"US.{validation['ticker']}"
    result["moomoo_code"] = canonical_code

    if not _MOOMOO_AVAILABLE:
        result["error"] = "moomoo-api package is not installed."
        return result

    errors = []
    ctx = None

    try:
        ctx = _ft.OpenQuoteContext(
            host=_MOOMOO_HOST,
            port=_MOOMOO_PORT,
        )

        ret, snap = ctx.get_market_snapshot([canonical_code])

        if ret != _ft.RET_OK:
            result["error"] = f"Snapshot request failed: {snap}"
            return result

        if snap.empty or "code" not in snap.columns:
            result["error"] = "No identifiable snapshot returned."
            return result

        exact = snap[
            snap["code"].astype(str).str.upper().eq(canonical_code)
        ]

        if len(exact) != 1:
            result["error"] = (
                "Snapshot did not return exactly the requested security."
            )
            return result

        row = exact.iloc[0]
        result["connected"] = True

        provider_time = _text(row.get("update_time"))
        result["data_timestamp"] = provider_time
        result["snapshot_update_time"] = provider_time

        price = _number(row.get("prev_close_price"))
        market_cap = _number(row.get("total_market_val"))

        if price is not None and price > 0:
            inputs["close_price_usd"] = price
            notes["close_price_usd"] = (
                "Moomoo snapshot prev_close_price: previous-session "
                "close. It is not last_price. "
                f"Snapshot update_time={provider_time or 'unavailable'}; "
                f"retrieved_at={retrieved_at}."
            )
        else:
            notes["close_price_usd"] = (
                "Previous closing price is unavailable or invalid."
            )

        if market_cap is not None and market_cap > 0:
            inputs["market_cap_usd"] = market_cap
            notes["market_cap_usd"] = (
                "Moomoo snapshot total_market_val. "
                f"Snapshot update_time={provider_time or 'unavailable'}; "
                f"retrieved_at={retrieved_at}."
            )
        else:
            notes["market_cap_usd"] = (
                "Market capitalisation is unavailable or invalid."
            )

        profile_method = getattr(ctx, "get_company_profile", None)

        if not callable(profile_method):
            notes["employee_count"] = (
                "Company-profile lookup is unavailable in this SDK."
            )
        else:
            try:
                profile_ret, profile = profile_method(canonical_code)

                if profile_ret != _ft.RET_OK:
                    notes["employee_count"] = (
                        "Employee lookup failed; value remains unknown."
                    )
                    errors.append(f"Company profile failed: {profile}")
                elif (
                    profile.empty
                    or not {"name", "value"}.issubset(profile.columns)
                ):
                    notes["employee_count"] = (
                        "Expected employee field is absent from "
                        "the company-profile response."
                    )
                else:
                    employee_rows = profile[
                        profile["name"]
                        .astype(str)
                        .str.strip()
                        .str.casefold()
                        .eq("employees")
                    ]

                    if len(employee_rows) != 1:
                        notes["employee_count"] = (
                            "Employee field is absent or ambiguous."
                        )
                    else:
                        employee = _number(
                            employee_rows.iloc[0]["value"],
                            integer=True,
                        )

                        inputs["employee_count"] = employee
                        notes["employee_count"] = (
                            "Moomoo company profile Employees field; "
                            "reporting date unverified."
                            if employee is not None
                            else "Employee value is not a valid count."
                        )

            except Exception as exc:
                notes["employee_count"] = (
                    "Employee lookup unavailable; value remains unknown."
                )
                errors.append(f"Company profile error: {exc}")

    except Exception as exc:
        errors.append(
            f"Moomoo retrieval error: {type(exc).__name__}: {exc}"
        )
    finally:
        _close_context(ctx)

    result["error"] = "; ".join(errors) if errors else None
    return result


def evaluate_company(
    ticker: str,
    inputs: Optional[dict] = None,
    *,
    demo_override: Optional[str] = None,
    source_mode: str = "supplied",
    company_name: Optional[str] = None,
    data_timestamp: Optional[str] = None,
) -> dict:
    """
    Evaluate supplied original-policy inputs.

    source_mode:
      supplied: provenance not verified by this function
      live: caller explicitly supplies freshly retrieved API inputs
      cached: caller supplies a saved dataset observation

    This function does not fetch data.

    Demo requires demo_override to name a known fixture.
    """
    if demo_override is not None:
        return _demo_evaluate(ticker, demo_override, _now_iso())

    if inputs is None:
        return _evaluation_error(
            ticker,
            "No screening inputs supplied. No demo data was substituted.",
        )

    if not isinstance(inputs, dict):
        return _evaluation_error(ticker, "Inputs must be a dictionary.")

    if source_mode not in {"supplied", "live", "cached"}:
        return _evaluation_error(
            ticker,
            "source_mode must be supplied, live, or cached.",
        )

    if not _SCREEN_BACKEND_AVAILABLE or not callable(_screen_fn):
        detail = (
            f" Import error: {_SCREEN_IMPORT_ERROR}"
            if _SCREEN_IMPORT_ERROR
            else ""
        )
        return _evaluation_error(
            ticker,
            "Screening backend is unavailable." + detail,
        )

    clean_inputs = _normalise_inputs(inputs)

    try:
        raw = _screen_fn(**clean_inputs)

        if not isinstance(raw, dict):
            raise ValueError("Screening backend returned a non-dictionary.")

        rules = raw.get("rules")

        if not isinstance(rules, list) or not rules:
            raise ValueError("Screening backend returned no rules.")

        criteria = [_rule_to_criterion(rule) for rule in rules]
        ids = [criterion["id"] for criterion in criteria]

        if len(ids) != len(set(ids)):
            raise ValueError("Screening backend returned duplicate rule IDs.")

        if set(ids) != set(_RULE_META):
            raise ValueError(
                "Backend rule schema differs from this adapter's "
                "original policy. Update both components together."
            )

        return {
            "mode": source_mode,
            "ticker": ticker,
            "company_name": company_name or ticker,
            "currency": "USD",
            "data_timestamp": data_timestamp,
            "evaluated_at": _now_iso(),
            "criteria_version": _POLICY_VERSION,
            "source": source_mode,
            "is_live": source_mode == "live",
            "criteria": criteria,
            "aggregate_status": _aggregate_from_criteria(criteria),
            "scope_note": raw.get("scope_note", _SCOPE_NOTE),
            "error": None,
        }

    except Exception as exc:
        return _evaluation_error(
            ticker,
            f"Screening evaluation failed: {type(exc).__name__}: {exc}",
        )


def analyse_company(ticker: str, evaluation: dict) -> dict:
    """Agent connection remains explicit and unimplemented."""
    return {
        "connected": False,
        "content": None,
        "error": (
            "Analysis not connected. The IBM watsonx Orchestrate "
            "endpoint has not been configured for this prototype."
        ),
    }


def _canonical_ticker(value):
    if not isinstance(value, str):
        return ""
    value = value.strip().upper()
    return value[3:] if value.startswith("US.") else value


def _policy_signature(criteria):
    return sorted(
        (
            str(c.get("id", "")),
            str(c.get("operator", "")),
            str(c.get("threshold", "")),
            str(c.get("unit", "")),
            str(c.get("reporting_period", "")),
        )
        for c in criteria
    )


def check_for_changes(
    ticker: str,
    baseline: dict,
    current_inputs: Optional[dict],
    *,
    source_mode: str = "supplied",
    data_timestamp: Optional[str] = None,
) -> dict:
    """
    Compare caller-supplied current inputs against a saved baseline.

    Does not fetch data or modify saved records.
    Does not automatically reuse demo fixtures.
    """
    new_eval = evaluate_company(
        ticker,
        current_inputs,
        source_mode=source_mode,
        data_timestamp=data_timestamp,
    )

    result = {
        "ticker": ticker,
        "checked_at": _now_iso(),
        "comparable": False,
        "not_comparable_reason": None,
        "changes": [],
        "new_evaluation": new_eval,
        "error": None,
    }

    if new_eval.get("error"):
        result["error"] = new_eval["error"]
        result["not_comparable_reason"] = (
            f"New evaluation failed: {new_eval['error']}"
        )
        return result

    if not isinstance(baseline, dict):
        result["not_comparable_reason"] = "Invalid saved baseline."
        return result

    baseline_eval = baseline.get("evaluation", {})

    if not isinstance(baseline_eval, dict):
        result["not_comparable_reason"] = "Invalid saved evaluation."
        return result

    saved_ticker = baseline_eval.get("ticker") or baseline.get("ticker")

    if _canonical_ticker(saved_ticker) != _canonical_ticker(ticker):
        result["not_comparable_reason"] = (
            "Baseline belongs to a different or unidentified company."
        )
        return result

    if baseline_eval.get("error"):
        result["not_comparable_reason"] = (
            "The saved baseline contains an evaluation error."
        )
        return result

    if baseline_eval.get("mode") not in {"supplied", "live", "cached"}:
        result["not_comparable_reason"] = (
            "Baseline data mode is demo, unknown, or unsupported. "
            "Save a new non-demo baseline."
        )
        return result

    if baseline_eval.get("currency") != new_eval.get("currency"):
        result["not_comparable_reason"] = "Evaluation currencies differ."
        return result

    if (
        baseline_eval.get("criteria_version")
        != new_eval.get("criteria_version")
    ):
        result["not_comparable_reason"] = (
            "Criteria version changed or is missing. "
            "Review the current policy and save a new baseline."
        )
        return result

    old_list = baseline_eval.get("criteria", [])
    new_list = new_eval.get("criteria", [])

    if not old_list or not new_list:
        result["not_comparable_reason"] = (
            "Both evaluations must contain screening criteria."
        )
        return result

    old_ids = [c.get("id") for c in old_list]
    new_ids = [c.get("id") for c in new_list]

    if (
        len(old_ids) != len(set(old_ids))
        or len(new_ids) != len(set(new_ids))
    ):
        result["not_comparable_reason"] = (
            "Duplicate criterion IDs prevent reliable comparison."
        )
        return result

    if _policy_signature(old_list) != _policy_signature(new_list):
        result["not_comparable_reason"] = (
            "Criteria, thresholds, units, operators, or reporting "
            "periods changed. Review and save a new baseline."
        )
        return result

    old_by_id = {c["id"]: c for c in old_list}
    changes = []

    for new_c in new_list:
        old_c = old_by_id[new_c["id"]]

        old_value = _number(old_c.get("observed_value"))
        new_value = _number(new_c.get("observed_value"))

        old_status = (
            "unknown" if old_value is None
            else old_c.get("status", "unknown")
        )
        new_status = (
            "unknown" if new_value is None
            else new_c.get("status", "unknown")
        )

        old_fmt = (
            "Unknown" if old_value is None
            else old_c.get("observed_fmt", str(old_value))
        )
        new_fmt = (
            "Unknown" if new_value is None
            else new_c.get("observed_fmt", str(new_value))
        )

        if new_value is None and old_value is not None:
            change_type = "data_unavailable"
            explanation = (
                f"Data for '{new_c['label']}' is now unavailable. "
                "This is unknown, not a confirmed rule failure."
            )
            new_fmt = "Unavailable"

        elif old_status != new_status:
            change_type = "status_transition"
            explanation = (
                f"'{new_c['label']}' changed from "
                f"{old_status.upper()} to {new_status.upper()}. "
                f"Value: {old_fmt} -> {new_fmt}."
            )

        elif old_value != new_value:
            change_type = "value_changed"
            explanation = (
                f"'{new_c['label']}' changed from "
                f"{old_fmt} to {new_fmt}; status remains "
                f"{new_status.upper()}."
            )

        else:
            continue

        changes.append({
            "criterion_id": new_c["id"],
            "criterion_label": new_c["label"],
            "change_type": change_type,
            "old_value_fmt": old_fmt,
            "new_value_fmt": new_fmt,
            "old_status": old_status,
            "new_status": new_status,
            "explanation": explanation,
        })

    result["comparable"] = True
    result["changes"] = changes
    return result


def _DEMO_FIXTURES() -> dict:
    """Named synthetic fixtures; no API or backend calls."""
    specifications = {
        "ACME": (15_000_000_000, 42.50, 850_000_000, 3200),
        "BLUE": (5_500_000_000, 18.75, -120_000_000, 870),
        "CRST": (8_200_000_000, 67.00, 310_000_000, None),
        "SMCHG": (12_000_000_000, 55.00, 200_000_000, 1500),
    }

    definitions = (
        (
            "market_cap_range",
            "2,000,000,000 <= x <= 100,000,000,000",
            lambda value: 2_000_000_000 <= value <= 100_000_000_000,
        ),
        ("min_close_price", "x >= 10", lambda value: value >= 10),
        (
            "positive_operating_cash_flow",
            "x > 0",
            lambda value: value > 0,
        ),
        ("min_employee_count", "x >= 20", lambda value: value >= 20),
    )

    fixtures = {}

    for name, values in specifications.items():
        rules = []

        for (rule_id, threshold, predicate), value in zip(
            definitions, values
        ):
            status = (
                "UNVERIFIED"
                if value is None
                else "PASS" if predicate(value) else "FAIL"
            )

            rules.append({
                "rule_name": rule_id,
                "observed_value": value,
                "threshold": threshold,
                "status": status,
                "explanation": "Synthetic demo fixture.",
            })

        criteria = [_rule_to_criterion(rule) for rule in rules]

        fixtures[name] = {
            "mode": "demo",
            "ticker": name,
            "company_name": _DEMO_COMPANY_NAMES[name],
            "currency": "USD",
            "data_timestamp": _DEMO_TS,
            "evaluated_at": _DEMO_TS,
            "criteria_version": _POLICY_VERSION,
            "source": "synthetic fixture",
            "is_live": False,
            "criteria": criteria,
            "aggregate_status": _aggregate_from_criteria(criteria),
            "scope_note": _SCOPE_NOTE,
            "error": None,
        }

    return fixtures


def _demo_evaluate(ticker: str, fixture_key: str, ts: str) -> dict:
    """An unknown fixture is an error, never an ACME fallback."""
    if not isinstance(fixture_key, str):
        return _evaluation_error(ticker, "Invalid demo fixture name.")

    key = fixture_key.strip().upper()
    fixtures = _DEMO_FIXTURES()

    if key not in fixtures:
        return _evaluation_error(
            ticker,
            f"Unknown demo fixture '{key}'. "
            "Choose ACME, BLUE, CRST, or SMCHG.",
        )

    result = copy.deepcopy(fixtures[key])
    result["requested_ticker"] = ticker
    result["evaluated_at"] = ts

    # Preserve fictional identity and original fixture observation time.
    result["ticker"] = key
    return result


def get_simulated_change_scenario() -> dict:
    """Explicit synthetic PASS-to-FAIL scenario; no external writes."""
    baseline = copy.deepcopy(_DEMO_FIXTURES()["SMCHG"])
    changed = copy.deepcopy(baseline)

    for criterion in changed["criteria"]:
        if criterion["id"] == "positive_operating_cash_flow":
            criterion["observed_value"] = -45_000_000
            criterion["observed_fmt"] = _fmt_usd(-45_000_000)
            criterion["status"] = "fail"
            criterion["explanation"] = (
                "Synthetic change: operating cash flow became negative."
            )

    changed["aggregate_status"] = _aggregate_from_criteria(
        changed["criteria"]
    )
    changed["data_timestamp"] = "2025-01-02T00:00:00Z"
    changed["evaluated_at"] = _now_iso()

    return {"baseline": baseline, "changed": changed}

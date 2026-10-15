"""
Investment research basic screening tool.

Applies four quantitative rules to provided financial metrics and returns
a per-rule breakdown plus an aggregate screening status.

Scope note: This checks only four screening rules. It does not establish
full investment eligibility or constitute an investment recommendation.
"""

import math
from typing import Optional

from ibm_watsonx_orchestrate.agent_builder.tools import tool, ToolPermission

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_SCOPE_NOTE = (
    "This checks only four screening rules. It does not establish full "
    "investment eligibility or constitute an investment recommendation."
)


def _validate_numeric(value, name: str, allow_fraction: bool = True):
    """Raise ValueError when *value* is not a clean finite number.

    Booleans are explicitly rejected (bool is a subclass of int in Python).
    NaN and infinity are rejected. When *allow_fraction* is False, non-integer
    values are also rejected.
    """
    if isinstance(value, bool):
        raise ValueError(f"'{name}' must be a number, not a boolean.")
    if not isinstance(value, (int, float)):
        raise ValueError(f"'{name}' must be numeric, got {type(value).__name__}.")
    if math.isnan(value):
        raise ValueError(f"'{name}' must not be NaN.")
    if math.isinf(value):
        raise ValueError(f"'{name}' must not be infinite.")
    if not allow_fraction and value != int(value):
        raise ValueError(f"'{name}' must be a whole number, got {value}.")


def _rule(rule_name: str, observed, threshold_str: str, passed: bool, explanation: str) -> dict:
    return {
        "rule_name": rule_name,
        "observed_value": observed,
        "threshold": threshold_str,
        "status": "PASS" if passed else "FAIL",
        "explanation": explanation,
    }


def _unverified_rule(rule_name: str, threshold_str: str, explanation: str) -> dict:
    return {
        "rule_name": rule_name,
        "observed_value": None,
        "threshold": threshold_str,
        "status": "UNVERIFIED",
        "explanation": explanation,
    }


# ---------------------------------------------------------------------------
# Tool
# ---------------------------------------------------------------------------

@tool(permission=ToolPermission.READ_ONLY)
def powerpuffmen_basic_screen(
    market_cap_usd: Optional[float] = None,
    close_price_usd: Optional[float] = None,
    operating_cash_flow_ttm_usd: Optional[float] = None,
    employee_count: Optional[float] = None,
) -> dict:
    """Screen a company against four basic investment research rules.

    Args:
        market_cap_usd (Optional[float]): Total market capitalisation in USD.
        close_price_usd (Optional[float]): Most recent closing share price in USD.
        operating_cash_flow_ttm_usd (Optional[float]): Trailing-12-month operating cash flow in USD.
        employee_count (Optional[float]): Total number of employees (must be a whole number).

    Returns:
        dict: Per-rule results, an aggregate basic_screen_status, and a scope note.
    """
    # --- input validation (raise on invalid; None means missing/unverified) ---
    if market_cap_usd is not None:
        _validate_numeric(market_cap_usd, "market_cap_usd")
    if close_price_usd is not None:
        _validate_numeric(close_price_usd, "close_price_usd")
    if operating_cash_flow_ttm_usd is not None:
        _validate_numeric(operating_cash_flow_ttm_usd, "operating_cash_flow_ttm_usd")
    if employee_count is not None:
        _validate_numeric(employee_count, "employee_count", allow_fraction=False)

    # --- Rule 1: Market cap USD 2B – USD 100B inclusive ---
    if market_cap_usd is None:
        r1 = _unverified_rule(
            "market_cap_range",
            "2,000,000,000 <= x <= 100,000,000,000",
            "market_cap_usd not provided.",
        )
    else:
        passed = 2_000_000_000 <= market_cap_usd <= 100_000_000_000
        r1 = _rule(
            "market_cap_range",
            market_cap_usd,
            "2,000,000,000 <= x <= 100,000,000,000",
            passed,
            "Market cap is within the USD 2B–100B range." if passed
            else "Market cap is outside the USD 2B–100B range.",
        )

    # --- Rule 2: Close price >= USD 10 ---
    if close_price_usd is None:
        r2 = _unverified_rule(
            "min_close_price",
            "x >= 10",
            "close_price_usd not provided.",
        )
    else:
        passed = close_price_usd >= 10
        r2 = _rule(
            "min_close_price",
            close_price_usd,
            "x >= 10",
            passed,
            "Close price meets the USD 10 minimum." if passed
            else "Close price is below the USD 10 minimum.",
        )

    # --- Rule 3: Operating cash flow > 0 (strictly) ---
    if operating_cash_flow_ttm_usd is None:
        r3 = _unverified_rule(
            "positive_operating_cash_flow",
            "x > 0",
            "operating_cash_flow_ttm_usd not provided.",
        )
    else:
        passed = operating_cash_flow_ttm_usd > 0
        r3 = _rule(
            "positive_operating_cash_flow",
            operating_cash_flow_ttm_usd,
            "x > 0",
            passed,
            "Operating cash flow is positive." if passed
            else "Operating cash flow is not strictly positive.",
        )

    # --- Rule 4: Employee count >= 20 ---
    if employee_count is None:
        r4 = _unverified_rule(
            "min_employee_count",
            "x >= 20",
            "employee_count not provided.",
        )
    else:
        passed = employee_count >= 20
        r4 = _rule(
            "min_employee_count",
            employee_count,
            "x >= 20",
            passed,
            "Employee count meets the minimum of 20." if passed
            else "Employee count is below the minimum of 20.",
        )

    rules = [r1, r2, r3, r4]

    # --- Aggregate status: FAIL > UNVERIFIED > PASS ---
    statuses = {r["status"] for r in rules}
    if "FAIL" in statuses:
        aggregate = "FAIL"
    elif "UNVERIFIED" in statuses:
        aggregate = "UNVERIFIED"
    else:
        aggregate = "PASS"

    return {
        "basic_screen_status": aggregate,
        "rules": rules,
        "scope_note": _SCOPE_NOTE,
    }

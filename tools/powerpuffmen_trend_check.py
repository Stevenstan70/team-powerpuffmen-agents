"""Price-trend check v1. No data retrieval or external writes.

Second tool for the InvestIQ research agent. The application computes the
measures from validated daily candles; this tool only applies the rules.
"""

import math
from typing import Optional

from ibm_watsonx_orchestrate.agent_builder.tools import tool, ToolPermission


POLICY_VERSION = "trend-check-v1"

SCOPE_NOTE = (
    "Three price-trend conditions were checked on unadjusted daily closes. "
    "This is not a buy or sell signal, not a VCP determination, and says "
    "nothing about valuation, fundamentals or news."
)


def _validate(value, name):
    if value is None:
        return
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be numeric, not boolean or text.")
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f"{name} must be a finite positive price.")


@tool(permission=ToolPermission.READ_ONLY)
def powerpuffmen_trend_check(
    last_close: Optional[float] = None,
    sma_150: Optional[float] = None,
    sma_200: Optional[float] = None,
    avg_close_12m: Optional[float] = None,
    high_52w: Optional[float] = None,
    low_52w: Optional[float] = None,
) -> dict:
    """Apply three price-trend rules to supplied price measures.

    Args:
        last_close: Most recent daily close, in the same price units as the
            averages.
        sma_150: Average of the last 150 daily closes.
        sma_200: Average of the last 200 daily closes.
        avg_close_12m: Average of the last 252 daily closes.
        high_52w: Highest daily high over the last 252 sessions (context only).
        low_52w: Lowest daily low over the last 252 sessions (context only).

    Returns:
        Per-rule results, aggregate status, policy version, context and scope
        note. None means unavailable; the caller must omit unavailable
        arguments and never substitute zero or an estimate.
    """
    values = {
        "last_close": last_close, "sma_150": sma_150, "sma_200": sma_200,
        "avg_close_12m": avg_close_12m, "high_52w": high_52w, "low_52w": low_52w,
    }
    for name, value in values.items():
        _validate(value, name)

    definitions = (
        ("above_12m_average", "avg_close_12m", "last_close > 12-month average close"),
        ("above_sma_200", "sma_200", "last_close > 200-session average"),
        ("above_sma_150", "sma_150", "last_close > 150-session average"),
    )
    rules = []
    for rule_id, key, threshold in definitions:
        reference = values[key]
        if last_close is None or reference is None:
            status = "UNVERIFIED"
            explanation = (
                "last_close or " + key + " was not provided; the rule cannot be evaluated."
            )
        elif last_close > reference:
            status = "PASS"
            explanation = "Last close is strictly above the reference average."
        else:
            status = "FAIL"
            explanation = "Last close is not strictly above the reference average."
        rules.append({
            "rule_name": rule_id,
            "observed_value": last_close,
            "reference_value": reference,
            "threshold": threshold,
            "status": status,
            "explanation": explanation,
        })

    statuses = {rule["status"] for rule in rules}
    aggregate = (
        "FAIL" if "FAIL" in statuses
        else "UNVERIFIED" if "UNVERIFIED" in statuses
        else "PASS"
    )

    context = {}
    if last_close is not None and high_52w is not None:
        context["pct_below_52w_high"] = round((high_52w - last_close) / high_52w * 100, 2)
    if last_close is not None and low_52w is not None:
        context["pct_above_52w_low"] = round((last_close - low_52w) / low_52w * 100, 2)

    return {
        "trend_check_status": aggregate,
        "criteria_version": POLICY_VERSION,
        "rules": rules,
        "context": context,
        "scope_note": SCOPE_NOTE,
    }

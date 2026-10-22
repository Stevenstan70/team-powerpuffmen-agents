"""Snapshot-policy screening v2. No data retrieval or external writes."""

import math
from typing import Optional

from ibm_watsonx_orchestrate.agent_builder.tools import tool, ToolPermission


POLICY_VERSION = "snapshot-net-profit-volume-v2"

SCOPE_NOTE = (
    "Only four screening rules were checked. This result does not establish "
    "full investment eligibility and does not constitute an investment "
    "recommendation. Net profit is provider-reported; its reporting period "
    "is unspecified. Volume is snapshot trading volume, not average daily volume."
)


def _validate(value, name, *, whole=False):
    if value is None:
        return
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be numeric, not boolean or text.")
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite.")
    if whole and (value < 0 or value != int(value)):
        raise ValueError(f"{name} must be a non-negative whole number.")


@tool(permission=ToolPermission.READ_ONLY)
def powerpuffmen_snapshot_screen(
    market_cap_usd: Optional[float] = None,
    close_price_usd: Optional[float] = None,
    net_profit_usd: Optional[float] = None,
    snapshot_volume_shares: Optional[float] = None,
) -> dict:
    """Apply the approved four-rule snapshot screening policy.

    Args:
        market_cap_usd: Market capitalisation with verified USD currency/units.
        close_price_usd: Previous completed trading-session close in USD.
        net_profit_usd: Provider-reported net profit in verified USD units.
            Reporting period is unspecified; never describe it as TTM or annual.
        snapshot_volume_shares: Snapshot trading volume in shares, not average
            daily volume. Must be a non-negative whole number.

    Returns:
        Per-rule results, aggregate status, policy version, and scope note.
        None means unavailable or unverified. The caller must omit monetary
        inputs whose currency/units are unverified, and equity fields whose
        provider validity flag is false or unknown.
    """
    values = {
        "market_cap_usd": market_cap_usd,
        "close_price_usd": close_price_usd,
        "net_profit_usd": net_profit_usd,
        "snapshot_volume_shares": snapshot_volume_shares,
    }
    for name, value in values.items():
        _validate(value, name, whole=name == "snapshot_volume_shares")

    definitions = (
        (
            "market_cap_range", "market_cap_usd",
            "2,000,000,000 <= x <= 100,000,000,000",
            lambda x: 2_000_000_000 <= x <= 100_000_000_000,
            "Market cap is within the USD 2B-100B range.",
            "Market cap is outside the USD 2B-100B range.",
        ),
        (
            "min_close_price", "close_price_usd", "x >= 10",
            lambda x: x >= 10,
            "Previous close meets the USD 10 minimum.",
            "Previous close is below the USD 10 minimum.",
        ),
        (
            "positive_net_profit", "net_profit_usd", "x > 0",
            lambda x: x > 0,
            "Provider-reported net profit is positive.",
            "Provider-reported net profit is not strictly positive.",
        ),
        (
            "min_snapshot_volume", "snapshot_volume_shares", "x >= 100,000",
            lambda x: x >= 100_000,
            "Snapshot trading volume meets the 100,000-share minimum.",
            "Snapshot trading volume is below the 100,000-share minimum.",
        ),
    )

    rules = []
    for rule_id, key, threshold, predicate, passed_text, failed_text in definitions:
        value = values[key]
        passed = predicate(value) if value is not None else None
        rules.append({
            "rule_name": rule_id,
            "observed_value": value,
            "threshold": threshold,
            "status": (
                "UNVERIFIED" if value is None
                else "PASS" if passed else "FAIL"
            ),
            "explanation": (
                f"{key} not provided or unverified." if value is None
                else passed_text if passed else failed_text
            ),
        })

    statuses = {rule["status"] for rule in rules}
    aggregate = (
        "FAIL" if "FAIL" in statuses
        else "UNVERIFIED" if "UNVERIFIED" in statuses
        else "PASS"
    )

    return {
        "basic_screen_status": aggregate,
        "criteria_version": POLICY_VERSION,
        "rules": rules,
        "scope_note": SCOPE_NOTE,
    }
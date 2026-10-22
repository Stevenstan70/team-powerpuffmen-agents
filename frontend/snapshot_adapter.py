"""Structured UI adapter for snapshot screening policy v2.

No market-data retrieval, currency conversion, demo substitution, or cloud calls.
"""

from datetime import datetime, timezone

from tools.powerpuffmen_snapshot_screen import (
    POLICY_VERSION,
    SCOPE_NOTE,
    powerpuffmen_snapshot_screen,
)


_screen = getattr(
    powerpuffmen_snapshot_screen,
    "fn",
    powerpuffmen_snapshot_screen,
)

INPUT_KEYS = (
    "market_cap_usd",
    "close_price_usd",
    "net_profit_usd",
    "snapshot_volume_shares",
)

RULE_META = {
    "market_cap_range": {
        "label": "Market Cap Range",
        "operator": "between",
        "unit": "USD",
        "reporting_period": "provider snapshot",
    },
    "min_close_price": {
        "label": "Minimum Previous Close Price",
        "operator": ">=",
        "unit": "USD",
        "reporting_period": "previous completed trading session",
    },
    "positive_net_profit": {
        "label": "Positive Reported Net Profit",
        "operator": ">",
        "unit": "USD",
        "reporting_period": "provider reporting period unspecified",
    },
    "min_snapshot_volume": {
        "label": "Minimum Snapshot Trading Volume",
        "operator": ">=",
        "unit": "shares",
        "reporting_period": "provider snapshot; not average daily volume",
    },
}


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _format(value, unit):
    if value is None:
        return "Unknown"
    if unit == "shares":
        return f"{int(value):,} shares"
    return f"${value:,.2f}"


def evaluate_snapshot(
    ticker,
    inputs,
    *,
    source_mode="supplied",
    company_name=None,
    data_timestamp=None,
):
    """Evaluate explicitly supplied, verified-unit inputs under policy v2."""
    result = {
        "mode": source_mode,
        "ticker": ticker,
        "company_name": company_name,
        "currency": "USD",
        "data_timestamp": data_timestamp,
        "evaluated_at": _now(),
        "criteria_version": POLICY_VERSION,
        "source": source_mode,
        "is_live": source_mode == "live",
        "criteria": [],
        "aggregate_status": "unknown",
        "scope_note": SCOPE_NOTE,
        "error": None,
    }

    try:
        if source_mode not in {"supplied", "live", "cached", "demo"}:
            raise ValueError("Unsupported source mode.")
        if not isinstance(ticker, str) or not ticker.strip():
            raise ValueError("A ticker is required.")
        if not isinstance(inputs, dict):
            raise ValueError("Explicit input dictionary required.")

        unexpected = set(inputs) - set(INPUT_KEYS)
        if unexpected:
            raise ValueError(
                "Unexpected input keys: "
                + ", ".join(sorted(map(str, unexpected)))
            )

        raw = _screen(**{key: inputs.get(key) for key in INPUT_KEYS})
        rules = raw["rules"]

        ids = [rule["rule_name"] for rule in rules]
        if len(ids) != len(set(ids)) or set(ids) != set(RULE_META):
            raise ValueError("Unexpected snapshot-policy rule schema.")

        status_map = {
            "PASS": "pass",
            "FAIL": "fail",
            "UNVERIFIED": "unknown",
        }

        criteria = []
        for rule in rules:
            rule_id = rule["rule_name"]
            meta = RULE_META[rule_id]
            value = rule["observed_value"]
            criteria.append({
                "id": rule_id,
                **meta,
                "threshold": rule["threshold"],
                "observed_value": value,
                "observed_fmt": _format(value, meta["unit"]),
                "status": status_map[rule["status"]],
                "explanation": rule["explanation"],
            })

        result.update(
            company_name=company_name or ticker,
            criteria=criteria,
            aggregate_status=status_map[raw["basic_screen_status"]],
        )

    except (ValueError, TypeError, KeyError, OverflowError) as exc:
        result.update(
            mode="error",
            is_live=False,
            source="unavailable",
            error=f"Snapshot evaluation failed: {exc}",
        )

    return result


def analyse_snapshot(evaluation):
    """Send snapshot-policy inputs to the matching cloud agent."""
    import json
    import os

    def failure(message):
        return {"connected": False, "content": None, "error": message}

    if not isinstance(evaluation, dict):
        return failure("A snapshot evaluation is required.")
    if evaluation.get("error"):
        return failure("Cannot analyse an evaluation containing an error.")
    if evaluation.get("criteria_version") != POLICY_VERSION:
        return failure("Evaluation does not use snapshot policy v2.")

    # Real-data integration remains gated until provenance is verified.
    if evaluation.get("mode") != "demo":
        return failure(
            "Real-data agent analysis is not enabled yet. "
            "Currency, units, and provider validity must be verified first."
        )

    api_key = os.environ.get("WXO_API_KEY", "").strip()
    if not api_key:
        return failure("WXO_API_KEY is not configured.")

    mapping = {
        "market_cap_range": "market_cap_usd",
        "min_close_price": "close_price_usd",
        "positive_net_profit": "net_profit_usd",
        "min_snapshot_volume": "snapshot_volume_shares",
    }

    criteria = evaluation.get("criteria", [])
    if not isinstance(criteria, list):
        return failure("Invalid evaluation criteria.")

    by_id = {}
    for criterion in criteria:
        if not isinstance(criterion, dict):
            return failure("Invalid criterion.")
        rule_id = criterion.get("id")
        if rule_id not in mapping or rule_id in by_id:
            return failure("Unexpected or duplicate rule ID.")
        by_id[rule_id] = criterion

    if set(by_id) != set(mapping):
        return failure("All four snapshot-policy rules must be represented.")

    inputs = {
        mapping[rule_id]: criterion.get("observed_value")
        for rule_id, criterion in by_id.items()
    }

    prompt = (
        "Synthetic example, not a real company. Monetary inputs are USD. "
        "Apply snapshot policy v2 using powerpuffmen_snapshot_screen. "
        "Net profit reporting period is unspecified. Volume is snapshot "
        "trading volume in shares, not average daily volume. "
        "Null inputs are explicitly unavailable; do not ask for them again. "
        "Return the tool results, policy version, and scope note.\n"
        + json.dumps(inputs, allow_nan=False)
    )

    base_url = (
        "https://api.ca-tor.watson-orchestrate.cloud.ibm.com/instances/"
        "b0f64331-1d61-42e3-aa44-b238b83c0046"
    )
    agent_id = "ac91e23e-cb35-405e-af72-4d63944b13d9"

    try:
        import requests

        auth = requests.post(
            "https://iam.cloud.ibm.com/identity/token",
            data={
                "grant_type": "urn:ibm:params:oauth:grant-type:apikey",
                "apikey": api_key,
            },
            timeout=30,
        )
        if not auth.ok:
            return failure(f"Authentication failed: HTTP {auth.status_code}.")

        token = auth.json()["access_token"]
        response = requests.post(
            f"{base_url}/v1/orchestrate/{agent_id}/chat/completions",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
            },
            timeout=180,
        )
        if not response.ok:
            return failure(f"Agent request failed: HTTP {response.status_code}.")

        payload = response.json()
        content = payload["choices"][0]["message"]["content"]
        if not isinstance(content, str) or not content.strip():
            return failure("Agent returned no readable response.")

        return {
            "connected": True,
            "content": (
                "Synthetic demo inputs — not real company data.\n\n" + content
            ),
            "error": None,
            "run_id": payload.get("run_id"),
            "trace_id": payload.get("trace_id"),
        }

    except Exception as exc:
        return failure(f"Agent request failed ({type(exc).__name__}).")
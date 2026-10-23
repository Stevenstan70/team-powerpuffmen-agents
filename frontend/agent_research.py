"""Real-company analysis through the InvestIQ IBM Orchestrate agent.

Separate from frontend.snapshot_adapter.analyse_snapshot, which stays limited
to synthetic demo inputs. Evidence here is retrieved by the application from
Moomoo; the agent receives it as supplied data and retrieves nothing itself.

Configuration (server environment only, never in code or the browser):
    WXO_API_KEY            IBM Cloud API key
    WXO_RESEARCH_AGENT_ID  id of the imported investiq_research_agent
    WXO_BASE_URL           optional; defaults to the project's Orchestrate instance
"""
import json
import os

SNAPSHOT_MARKER = "snapshot-net-profit-volume-v2"
TREND_MARKER = "trend-check-v1"

DEFAULT_BASE_URL = (
    "https://api.ca-tor.watson-orchestrate.cloud.ibm.com/instances/"
    "b0f64331-1d61-42e3-aa44-b238b83c0046"
)

_SNAPSHOT_IDS = {
    "positive_net_profit": "net_profit_usd",
    "min_snapshot_volume": "snapshot_volume_shares",
}
_TREND_KEYS = ("last_close", "sma_150", "sma_200", "avg_close_12m",
               "high_52w", "low_52w")


def build_evidence(result):
    """Only validated facts. Unverified or unavailable values are left out."""
    e = result["evaluation"]
    screening_inputs = {}
    for c in e["criteria"]:
        key = _SNAPSHOT_IDS.get(c.get("id"))
        if key and c.get("observed_value") is not None:
            screening_inputs[key] = c["observed_value"]

    technical_inputs = {}
    t = result.get("technicals")
    if result.get("technicals_status") == "computed" and t:
        technical_inputs = {k: t[k] for k in _TREND_KEYS if t.get(k) is not None}

    return {
        "ticker": e["ticker"],
        "company_name": e.get("company_name"),
        "retrieved_by": "the InvestIQ application, from a local Moomoo OpenD gateway",
        "provider_snapshot_timestamp": e.get("data_timestamp"),
        "retrieved_at_utc": result.get("fetched_at"),
        "request_time_evidence_not_streaming": True,
        "screening_inputs_validated": screening_inputs,
        "screening_inputs_withheld_unverified": [
            "market_cap_usd (USD mapping unverified)",
            "close_price_usd (USD mapping unverified)",
        ] + ([] if "net_profit_usd" in screening_inputs
             else ["net_profit_usd (statement evidence not validated or not requested)"]),
        "statement_status": result.get("statement_status"),
        "recovery_warnings": [
            {"stage": w["stage"], "error_type": w["error_type"]}
            for w in result.get("warnings", [])
        ],
        "technical_inputs_validated": technical_inputs,
        "technicals_status": result.get("technicals_status"),
        "technical_reliability_note": (
            (t or {}).get("reliability", {}).get("reason") if t else None
        ),
    }


def build_prompt(evidence):
    return (
        "REAL COMPANY EVIDENCE. This is real data, not a synthetic example. "
        "The application retrieved it from Moomoo; you did not, and it is "
        "request-time data, not a live feed. Follow your instructions: state "
        "your plan, call powerpuffmen_snapshot_screen and "
        "powerpuffmen_trend_check with only the validated inputs below "
        "(omit anything not listed), then write the research summary. Do not "
        "recommend trades.\n" + json.dumps(evidence, allow_nan=False, indent=2)
    )


def analyse_research(result):
    """Ask the Orchestrate agent to analyse one stored research result."""

    def failure(kind, message):
        return {"connected": False, "content": None, "error": message, "kind": kind}

    if not isinstance(result, dict) or result.get("evaluation", {}).get("error"):
        return failure("input", "A valid research result is required.")
    if result["evaluation"].get("criteria_version") != SNAPSHOT_MARKER:
        return failure("input", "Result does not use snapshot policy v2.")

    api_key = os.environ.get("WXO_API_KEY", "").strip()
    if not api_key:
        return failure("config", "WXO_API_KEY is not configured in the API window.")
    agent_id = os.environ.get("WXO_RESEARCH_AGENT_ID", "").strip()
    if not agent_id:
        return failure(
            "config",
            "WXO_RESEARCH_AGENT_ID is not configured. Import the "
            "investiq_research_agent into Orchestrate and set its id.",
        )
    base_url = os.environ.get("WXO_BASE_URL", "").strip() or DEFAULT_BASE_URL

    try:
        evidence = build_evidence(result)
        prompt = build_prompt(evidence)
    except (KeyError, TypeError, ValueError) as exc:
        return failure("input", f"Evidence could not be prepared ({type(exc).__name__}).")

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
            return failure("remote", f"Authentication failed: HTTP {auth.status_code}.")
        token = auth.json()["access_token"]
        response = requests.post(
            f"{base_url}/v1/orchestrate/{agent_id}/chat/completions",
            headers={"Authorization": f"Bearer {token}"},
            json={"messages": [{"role": "user", "content": prompt}], "stream": False},
            timeout=180,
        )
        if not response.ok:
            return failure("remote", f"Agent request failed: HTTP {response.status_code}.")
        payload = response.json()
        content = payload["choices"][0]["message"]["content"]
        if not isinstance(content, str) or not content.strip():
            return failure("remote", "Agent returned no readable response.")
    except Exception as exc:
        return failure("remote", f"Agent request failed ({type(exc).__name__}).")

    return {
        "connected": True,
        "content": content,
        "error": None,
        "kind": None,
        "run_id": payload.get("run_id"),
        "trace_id": payload.get("trace_id"),
        # Weak check only: both tools' version strings appear in the reply.
        # The Orchestrate trace is the evidence that the tools actually ran.
        "tool_markers_in_response": {
            "snapshot_screen": SNAPSHOT_MARKER in content,
            "trend_check": TREND_MARKER in content,
        },
        "evidence_sent": evidence,
    }

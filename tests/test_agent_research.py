"""Real-company Orchestrate adapter, with the IBM endpoints mocked."""
import json
from unittest.mock import Mock

import pytest

from frontend import agent_research as ar
from frontend.snapshot_adapter import evaluate_snapshot


def make_result(profit=None, technicals=True):
    inputs = {"market_cap_usd": None, "close_price_usd": None,
              "net_profit_usd": profit, "snapshot_volume_shares": 150000}
    ev = evaluate_snapshot("AAPL", inputs, company_name="Apple",
                           data_timestamp="2026-10-22 16:00:00")
    result = {"evaluation": ev, "code": "US.AAPL", "fetched_at": "2026-10-23T10:00:00+00:00",
              "statement_status": "not_requested", "warnings": [], "raw": []}
    if technicals:
        result.update(
            technicals_status="computed",
            technicals={"last_close": 120.0, "sma_150": 100.0, "sma_200": None,
                        "avg_close_12m": 95.0, "high_52w": 130.0, "low_52w": 70.0,
                        "reliability": {"ok": True, "reason": None}},
        )
    else:
        result["technicals_status"] = "unavailable"
        result["technicals"] = None
    return result


@pytest.fixture
def env(monkeypatch):
    monkeypatch.setenv("WXO_API_KEY", "test-key-not-real")
    monkeypatch.setenv("WXO_RESEARCH_AGENT_ID", "agent-123")
    monkeypatch.delenv("WXO_BASE_URL", raising=False)


def mock_ibm(monkeypatch, content="reply", auth_ok=True, agent_ok=True):
    import requests
    calls = []

    def post(url, **kw):
        calls.append((url, kw))
        if "iam.cloud.ibm.com" in url:
            return Mock(ok=auth_ok, status_code=200 if auth_ok else 401,
                        json=lambda: {"access_token": "tok"})
        return Mock(ok=agent_ok, status_code=200 if agent_ok else 500,
                    json=lambda: {"choices": [{"message": {"content": content}}],
                                  "run_id": "run-1", "trace_id": "trace-1"})
    monkeypatch.setattr(requests, "post", post)
    return calls


def test_evidence_contains_only_validated_inputs():
    e = ar.build_evidence(make_result(profit=None))
    assert e["screening_inputs_validated"] == {"snapshot_volume_shares": 150000}
    assert any("market_cap_usd" in w for w in e["screening_inputs_withheld_unverified"])
    assert any("net_profit_usd" in w for w in e["screening_inputs_withheld_unverified"])
    # unavailable technical measure (sma_200) is omitted, never zero
    assert e["technical_inputs_validated"] == {
        "last_close": 120.0, "sma_150": 100.0, "avg_close_12m": 95.0,
        "high_52w": 130.0, "low_52w": 70.0}


def test_evidence_without_technicals_sends_no_technical_values():
    e = ar.build_evidence(make_result(technicals=False))
    assert e["technical_inputs_validated"] == {}
    assert e["technicals_status"] == "unavailable"


def test_prompt_states_real_data_and_not_synthetic():
    prompt = ar.build_prompt(ar.build_evidence(make_result()))
    assert "REAL COMPANY EVIDENCE" in prompt and "not a synthetic example" in prompt
    assert "you did not" in prompt and "Do not recommend trades" in prompt
    assert "150000" in prompt


def test_missing_key_or_agent_id_is_a_config_error(monkeypatch):
    monkeypatch.delenv("WXO_API_KEY", raising=False)
    monkeypatch.delenv("WXO_RESEARCH_AGENT_ID", raising=False)
    out = ar.analyse_research(make_result())
    assert out["connected"] is False and out["kind"] == "config" and "WXO_API_KEY" in out["error"]
    monkeypatch.setenv("WXO_API_KEY", "k")
    out = ar.analyse_research(make_result())
    assert out["kind"] == "config" and "WXO_RESEARCH_AGENT_ID" in out["error"]


def test_success_returns_ids_markers_and_evidence_sent(env, monkeypatch):
    calls = mock_ibm(monkeypatch, content=f"{ar.SNAPSHOT_MARKER} ... {ar.TREND_MARKER}")
    out = ar.analyse_research(make_result())
    assert out["connected"] is True
    assert out["run_id"] == "run-1" and out["trace_id"] == "trace-1"
    assert out["tool_markers_in_response"] == {"snapshot_screen": True, "trend_check": True}
    assert out["evidence_sent"]["ticker"] == "AAPL"
    url, kw = calls[1]
    assert url.endswith("/v1/orchestrate/agent-123/chat/completions")
    assert kw["headers"] == {"Authorization": "Bearer tok"}
    body = kw["json"]["messages"][0]["content"]
    assert "REAL COMPANY EVIDENCE" in body
    assert "test-key-not-real" not in json.dumps(kw["json"])  # key never sent to the agent


def test_missing_markers_are_reported_not_assumed(env, monkeypatch):
    mock_ibm(monkeypatch, content="plain answer with no tool strings")
    out = ar.analyse_research(make_result())
    assert out["tool_markers_in_response"] == {"snapshot_screen": False, "trend_check": False}


def test_remote_failures_are_reported(env, monkeypatch):
    mock_ibm(monkeypatch, auth_ok=False)
    out = ar.analyse_research(make_result())
    assert out["connected"] is False and out["kind"] == "remote" and "Authentication failed" in out["error"]
    mock_ibm(monkeypatch, agent_ok=False)
    out = ar.analyse_research(make_result())
    assert out["kind"] == "remote" and "HTTP 500" in out["error"]


def test_error_evaluation_is_refused(env):
    bad = make_result()
    bad["evaluation"]["error"] = "x"
    assert ar.analyse_research(bad)["kind"] == "input"

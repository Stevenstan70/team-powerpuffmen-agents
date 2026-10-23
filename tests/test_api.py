"""Offline tests for the local HTTP API.

Only the Moomoo SDK is faked. Real retrieval, screening and brief code runs.
Most tests run the worker in-process; the last group exercises the real
child-process isolation with stand-in worker commands.
"""
import sys
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import Mock
from zoneinfo import ZoneInfo

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from api import server, worker

client = TestClient(server.app)


@pytest.fixture
def inprocess(monkeypatch):
    """Run the real worker code in this process so the fake SDK is visible."""
    monkeypatch.setattr(server, "_run_worker", worker.run)


def fake_sdk(monkeypatch, factory):
    monkeypatch.setitem(sys.modules, "moomoo", SimpleNamespace(
        RET_OK=0, Market=SimpleNamespace(US="US"),
        SecurityType=SimpleNamespace(STOCK="STOCK"),
        KLType=SimpleNamespace(K_DAY="K_DAY"),
        AuType=SimpleNamespace(NONE="NONE"),
        OpenQuoteContext=factory,
    ))


def candles(code="US.AAPL", n=270, base=100.0, step=0.1):
    """n daily sessions ending yesterday (US Eastern), rising slowly."""
    end = datetime.now(ZoneInfo("America/New_York")).date() - timedelta(days=1)
    days = pd.bdate_range(end=end, periods=n)
    rows = []
    for i, d in enumerate(days):
        price = round(base + step * i, 2)
        rows.append({"code": code, "time_key": d.strftime("%Y-%m-%d 00:00:00"),
                     "open": price, "high": price + 1, "low": price - 1,
                     "close": price + 0.05, "volume": 1_000_000})
    return pd.DataFrame(rows)


@pytest.fixture
def provider(monkeypatch, inprocess):
    payload = {
        "next_key": None,
        "structure_list": [],
        "report_list": [{
            "date_time_str": "2026-06-26",
            "fiscal_year": 2026,
            "financial_type": "Q3",
            "period_text": "2026/Q3",
            "currency_code": "USD",
            "accounting_standards": "US_GAAP",
            "item_list": [{
                "field_id": 8037,
                "display_name": "Net Profit",
                "data": 29789000000.0,
            }],
        }],
    }
    ctx = Mock()
    ctx.get_stock_basicinfo.return_value = (
        0, pd.DataFrame([{"code": "US.AAPL", "name": "Apple",
                          "stock_type": "STOCK"}]),
    )
    ctx.get_market_snapshot.return_value = (
        0, pd.DataFrame([{
            "code": "US.AAPL", "update_time": "2026-10-22 16:00:00",
            "equity_valid": True, "volume": 150000,
            "total_market_val": 999999, "prev_close_price": 123,
            "net_profit": -999,
        }]),
    )
    ctx.get_financials_statements.return_value = (0, payload)
    ctx.request_history_kline.return_value = (0, candles(), None)
    monkeypatch.setenv("ENABLE_MOOMOO_CHART", "1")
    fake_sdk(monkeypatch, Mock(return_value=ctx))
    return SimpleNamespace(ctx=ctx, payload=payload)


def post(ticker="AAPL", statements=False):
    return client.post("/api/research", json={
        "ticker": ticker, "include_statement_profit": statements,
    })


def test_health():
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "opend_checked": False}


def test_ticker_to_brief_with_validated_statement(provider):
    r = post(statements=True)
    assert r.status_code == 200
    body = r.json()
    assert body["code"] == "US.AAPL"
    assert body["statement_status"] == "validated"
    assert body["warnings"] == []
    profit = next(c for c in body["evaluation"]["criteria"]
                  if "net profit" in c["label"].lower())
    assert profit["status"] == "pass"
    # Market cap and previous close stay withheld, so the screen is incomplete.
    assert body["evaluation"]["aggregate_status"] == "unknown"
    assert "# InvestIQ preliminary company research brief" in body["brief_markdown"]
    assert "not an IBM-agent-generated research opinion" in body["brief_markdown"]
    assert isinstance(body["server_elapsed_seconds"], float)
    assert provider.ctx.close.call_count == 2  # screen context + price-history context


def test_missing_statement_is_recovered_not_substituted(provider):
    provider.ctx.get_financials_statements.side_effect = RuntimeError("boom")
    r = post(statements=True)
    assert r.status_code == 200
    body = r.json()
    assert body["statement_status"] == "unavailable"
    assert [w["stage"] for w in body["warnings"]] == ["statement_retrieval"]
    profit = next(c for c in body["evaluation"]["criteria"]
                  if "net profit" in c["label"].lower())
    assert profit["status"] == "unknown"
    assert "-999" not in str(profit["observed_fmt"])
    assert "Recovery: statement_retrieval" in body["brief_markdown"]
    assert "No statement profit was substituted" in body["brief_markdown"]


@pytest.mark.parametrize("ticker", ["not a ticker", "ACME", "BLUE", "TOOLONGTICKER1"])
def test_bad_or_fictional_ticker_is_rejected_with_no_data(provider, ticker):
    r = post(ticker)
    assert r.status_code == 422
    assert "evaluation" not in r.json()
    provider.ctx.get_market_snapshot.assert_not_called()


def test_provider_failure_returns_error_not_sample_data(provider):
    provider.ctx.get_market_snapshot.return_value = (-1, "provider down")
    r = post()
    assert r.status_code == 502
    body = r.json()
    assert "Snapshot retrieval failed" in body["detail"]
    assert "evaluation" not in body and "brief_markdown" not in body
    provider.ctx.close.assert_called_once_with()


def test_gateway_unreachable_is_reported(monkeypatch, inprocess):
    def boom(**_):
        raise ConnectionError("OpenD not running")
    fake_sdk(monkeypatch, boom)
    r = post()
    assert r.status_code == 502
    assert "OpenD not running" in r.json()["detail"]


def test_sdk_calling_exit_is_reported_not_fatal(monkeypatch, inprocess):
    def boom(**_):
        raise SystemExit(1)
    fake_sdk(monkeypatch, boom)
    r = post()
    assert r.status_code == 502
    assert "SystemExit" in r.json()["detail"]


def test_technicals_are_computed_from_candles_and_in_the_brief(provider):
    body = post().json()
    assert body["technicals_status"] == "computed"
    t = body["technicals"]
    assert t["sessions"] == 270 and t["sma_200"] is not None
    assert t["avg_close_12m"] is not None and t["reliability"]["ok"] is True
    assert body["trend"]["trend_check_status"] == "PASS"  # price drifts upward
    assert body["trend"]["criteria_version"] == "trend-check-v1"
    assert len(body["price_series"]) == 270
    assert body["price_series"][-1]["sma_200"] is not None
    assert "## Technical measures (price history)" in body["brief_markdown"]
    assert "Trend check (trend-check-v1): PASS" in body["brief_markdown"]
    assert body["research_id"]
    # statement and technical lookups each open and close their own context
    assert provider.ctx.close.call_count == 2


def test_price_history_failure_is_recovered_not_estimated(provider):
    provider.ctx.request_history_kline.return_value = (-1, "quota exceeded", None)
    r = post()
    assert r.status_code == 200
    body = r.json()
    assert body["technicals_status"] == "unavailable"
    assert body["technicals"] is None and body["trend"] is None
    assert body["price_series"] == []
    assert [w["stage"] for w in body["warnings"]] == ["technicals_retrieval"]
    assert "quota exceeded" in body["warnings"][0]["message"]
    assert "No technical indicator has been estimated" in body["brief_markdown"]
    # the four-rule screen is unaffected
    assert body["evaluation"]["aggregate_status"] == "unknown"


def test_second_ticker_after_first_succeeds(provider):
    assert post("AAPL").status_code == 200
    provider.ctx.get_stock_basicinfo.return_value = (
        0, pd.DataFrame([{"code": "US.NVDA", "name": "NVIDIA",
                          "stock_type": "STOCK"}]),
    )
    provider.ctx.get_market_snapshot.return_value = (
        0, pd.DataFrame([{
            "code": "US.NVDA", "update_time": "2026-10-22 16:00:00",
            "equity_valid": True, "volume": 900000,
            "total_market_val": 1, "prev_close_price": 1, "net_profit": 1,
        }]),
    )
    provider.ctx.request_history_kline.return_value = (0, candles("US.NVDA"), None)
    r = post("NVDA")
    assert r.status_code == 200
    assert r.json()["code"] == "US.NVDA"


def test_empty_ticker_fails_request_validation():
    assert client.post("/api/research", json={"ticker": ""}).status_code == 422


# --- real child-process isolation, with stand-in worker commands -----------

def use_command(monkeypatch, *code_lines):
    code = "\n".join(code_lines)
    monkeypatch.setattr(
        server, "_worker_command",
        lambda t, f, out: [sys.executable, "-c", code, str(out)],
    )


def test_worker_process_crash_does_not_kill_the_api(monkeypatch):
    use_command(monkeypatch, "import os", "os._exit(3)")
    r = post()
    assert r.status_code == 502
    assert "stopped unexpectedly (exit code 3)" in r.json()["detail"]
    assert client.get("/api/health").status_code == 200


def test_worker_timeout_is_reported(monkeypatch):
    monkeypatch.setattr(server, "WORKER_TIMEOUT_SECONDS", 1)
    use_command(monkeypatch, "import time", "time.sleep(10)")
    r = post()
    assert r.status_code == 504
    assert "timed out" in r.json()["detail"]
    assert client.get("/api/health").status_code == 200


def test_worker_result_file_is_returned(monkeypatch):
    use_command(
        monkeypatch,
        "import json, sys",
        "outcome = {'ok': True, 'brief': '# b', 'result': {'code': 'US.X',"
        " 'evaluation': {}, 'raw': [], 'fetched_at': 't',"
        " 'statement_status': 'not_requested', 'warnings': []}}",
        "json.dump(outcome, open(sys.argv[1], 'w'))",
    )
    r = post()
    assert r.status_code == 200
    assert r.json()["code"] == "US.X" and r.json()["brief_markdown"] == "# b"


# --- IBM Orchestrate agent endpoint (the IBM call itself is mocked) --------

def test_agent_analyses_the_stored_result_not_client_data(provider, monkeypatch):
    research_id = post().json()["research_id"]
    seen = {}

    def fake_analyse(result):
        seen["code"] = result["code"]
        seen["technicals"] = result["technicals_status"]
        return {"connected": True, "content": "agent reply", "error": None, "kind": None,
                "run_id": "r1", "trace_id": "t1",
                "tool_markers_in_response": {"snapshot_screen": True, "trend_check": True},
                "evidence_sent": {"ticker": "AAPL"}}

    monkeypatch.setattr("frontend.agent_research.analyse_research", fake_analyse)
    r = client.post(f"/api/research/{research_id}/agent")
    assert r.status_code == 200
    body = r.json()
    assert body["content"] == "agent reply" and body["trace_id"] == "t1"
    assert seen == {"code": "US.AAPL", "technicals": "computed"}
    assert isinstance(body["elapsed_seconds"], float)


def test_agent_unknown_research_id_is_404():
    r = client.post("/api/research/does-not-exist/agent")
    assert r.status_code == 404 and "Run the lookup again" in r.json()["detail"]


@pytest.mark.parametrize("kind,status", [("config", 503), ("remote", 502), ("input", 422)])
def test_agent_failures_map_to_http_errors(provider, monkeypatch, kind, status):
    research_id = post().json()["research_id"]
    monkeypatch.setattr(
        "frontend.agent_research.analyse_research",
        lambda result: {"connected": False, "content": None,
                        "error": f"{kind} problem", "kind": kind},
    )
    r = client.post(f"/api/research/{research_id}/agent")
    assert r.status_code == status and r.json()["detail"] == f"{kind} problem"
    assert "content" not in r.json()


def test_stored_results_are_bounded():
    server._results.clear()
    for i in range(server._MAX_STORED + 5):
        server._store({"n": i})
    assert len(server._results) == server._MAX_STORED
    assert {"n": 0} not in server._results.values()


def test_worker_outcome_survives_the_json_hand_off(provider):
    """The worker passes its result to the API as a JSON file; nothing may break it."""
    import json
    outcome = worker.run("AAPL", True)
    assert outcome["ok"] is True
    text = json.dumps(outcome, default=worker._default)
    again = json.loads(text)
    assert again["result"]["technicals"]["sessions"] == 270
    assert len(again["result"]["price_series"]) == 270
    assert again["result"]["statement_status"] == "validated"

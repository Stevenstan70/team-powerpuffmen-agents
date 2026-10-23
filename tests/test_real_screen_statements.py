"""Offline integration tests for optional statement-profit retrieval."""
import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pandas as pd
import pytest

from frontend.real_screen import retrieve_real_screen


@pytest.fixture
def provider(monkeypatch):
    payload = {
        "next_key": "older-page",
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
        0,
        pd.DataFrame([{
            "code": "US.AAPL",
            "name": "Apple",
            "stock_type": "STOCK",
        }]),
    )
    ctx.get_market_snapshot.return_value = (
        0,
        pd.DataFrame([{
            "code": "US.AAPL",
            "update_time": "2026-10-22 16:00:00",
            "equity_valid": True,
            "volume": 150000,
            "total_market_val": 999999,
            "prev_close_price": 123,
            "net_profit": -999,
        }]),
    )
    ctx.get_financials_statements.return_value = (0, payload)
    factory = Mock(return_value=ctx)
    fake_sdk = SimpleNamespace(
        RET_OK=0,
        Market=SimpleNamespace(US="US"),
        SecurityType=SimpleNamespace(STOCK="STOCK"),
        OpenQuoteContext=factory,
    )
    monkeypatch.setitem(sys.modules, "moomoo", fake_sdk)
    return SimpleNamespace(ctx=ctx, payload=payload, factory=factory)


def profit_row(result):
    rows = [
        c for c in result["evaluation"]["criteria"]
        if "net profit" in c["label"].lower()
    ]
    assert len(rows) == 1
    return rows[0]


def test_default_does_not_request_statements(provider):
    result = retrieve_real_screen("AAPL")
    provider.ctx.get_financials_statements.assert_not_called()
    assert profit_row(result)["status"] == "unknown"
    provider.ctx.close.assert_called_once_with()


def test_opt_in_uses_statement_profit_and_preserves_provenance(provider):
    result = retrieve_real_screen(" aapl ", include_statement_profit=True)
    provider.factory.assert_called_once_with(host="127.0.0.1", port=11111)
    provider.ctx.get_financials_statements.assert_called_once_with(
        code="US.AAPL"
    )
    profit = profit_row(result)
    assert profit["status"] == "pass"
    evidence = profit["provenance"]
    assert evidence["value"] == 29789000000.0
    assert evidence["requested_code"] == "US.AAPL"
    assert evidence["currency_code"] == "USD"
    assert evidence["field_id"] == 8037
    assert evidence["period_text"] == "2026/Q3"
    assert evidence["has_more_pages"] is True
    assert evidence["selection_basis"] == "most recent report in returned response"
    assert "2026-06-26" in profit["reporting_period"]
    assert result["evaluation"]["aggregate_status"] == "unknown"
    assert any(
        row["Provider field"] == "financial statements: field 8037"
        for row in result["raw"]
    )
    provider.ctx.close.assert_called_once_with()


def assert_recovered_without_profit(result, provider, stage, error_type=None):
    """Optional statement evidence failed: record it, never invent profit."""
    assert result["statement_status"] == "unavailable"
    assert len(result["warnings"]) == 1
    warning = result["warnings"][0]
    assert warning["stage"] == stage
    if error_type is not None:
        assert warning["error_type"] == error_type
    profit = profit_row(result)
    assert profit["status"] == "unknown"
    assert "provenance" not in profit or profit["provenance"] is None
    # The snapshot's own net_profit (-999) must never be substituted.
    assert "-999" not in str(profit["observed_fmt"])
    assert not any(
        row["Provider field"] == "financial statements: field 8037"
        for row in result["raw"]
    )
    # The screen still ran on the validated snapshot volume.
    volume = [c for c in result["evaluation"]["criteria"]
              if "volume" in c["label"].lower()]
    assert len(volume) == 1 and volume[0]["status"] == "pass"
    assert result["evaluation"]["aggregate_status"] == "unknown"
    provider.ctx.close.assert_called_once_with()


def test_statement_api_error_recovers_without_snapshot_profit(provider):
    provider.ctx.get_financials_statements.return_value = (-1, "unavailable")
    result = retrieve_real_screen("AAPL", include_statement_profit=True)
    assert_recovered_without_profit(
        result, provider, "statement_retrieval", "RuntimeError"
    )


def test_statement_exception_recovers_and_closes_context(provider):
    provider.ctx.get_financials_statements.side_effect = RuntimeError(
        "statement transport failed"
    )
    result = retrieve_real_screen("AAPL", include_statement_profit=True)
    assert_recovered_without_profit(
        result, provider, "statement_retrieval", "RuntimeError"
    )


@pytest.mark.parametrize("target,key,value", [
    ("report", "currency_code", "HKD"),
    ("report", "date_time_str", "invalid"),
    ("report", "period_text", ""),
    ("item", "field_id", 8043),
    ("item", "data", None),
    ("item", "data", True),
])
def test_invalid_statement_evidence_is_rejected_and_recovered(
    provider, target, key, value
):
    report = provider.payload["report_list"][0]
    destination = report if target == "report" else report["item_list"][0]
    destination[key] = value
    result = retrieve_real_screen("AAPL", include_statement_profit=True)
    assert_recovered_without_profit(
        result, provider, "statement_validation", "ValueError"
    )


def test_empty_reports_recover_without_snapshot_profit(provider):
    provider.payload["report_list"] = []
    result = retrieve_real_screen("AAPL", include_statement_profit=True)
    assert_recovered_without_profit(
        result, provider, "statement_validation", "ValueError"
    )


def test_identity_or_snapshot_errors_still_stop_the_request(provider):
    provider.ctx.get_market_snapshot.return_value = (-1, "provider down")
    with pytest.raises(RuntimeError, match="Snapshot retrieval failed"):
        retrieve_real_screen("AAPL", include_statement_profit=True)
    provider.ctx.close.assert_called_once_with()


@pytest.mark.parametrize("value", [0.0, -25.5, 42.0])
def test_numeric_statement_profit_is_not_replaced_by_snapshot_value(
    provider, value
):
    provider.payload["report_list"][0]["item_list"][0]["data"] = value
    result = retrieve_real_screen("AAPL", include_statement_profit=True)
    profit = profit_row(result)
    assert profit["provenance"]["value"] == value
    assert profit["status"] in {"pass", "fail"}
    provider.ctx.close.assert_called_once_with()

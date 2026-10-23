"""Offline tests: no installed Moomoo SDK or OpenD connection required."""
import sys
from datetime import timedelta
from types import ModuleType, SimpleNamespace
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from frontend import market_chart as chart
from frontend import real_screen as screen


@pytest.fixture
def provider(monkeypatch):
    mm = ModuleType("moomoo")
    mm.RET_OK = 0
    mm.Market = SimpleNamespace(US="US")
    mm.SecurityType = SimpleNamespace(STOCK="STOCK")
    mm.KLType = SimpleNamespace(K_DAY="K_DAY")
    mm.AuType = SimpleNamespace(NONE="NONE")
    ctx = MagicMock()
    mm.OpenQuoteContext = MagicMock(return_value=ctx)
    monkeypatch.setitem(sys.modules, "moomoo", mm)

    basic = pd.DataFrame([{
        "code": "US.AAPL", "name": "Test Apple", "stock_type": "STOCK",
    }])
    snapshot = pd.DataFrame([{
        "code": "US.AAPL",
        "update_time": "2026-10-22 16:00:00",
        "equity_valid": True,
        "volume": 150000,
        "total_market_val": 8000000000,
        "prev_close_price": 45.2,
        "net_profit": 620000000,
    }])
    ctx.get_stock_basicinfo.return_value = (0, basic)
    ctx.get_market_snapshot.return_value = (0, snapshot)
    return mm, ctx, basic, snapshot


@pytest.mark.parametrize("volume,expected", [
    (0, "fail"), (99999, "fail"), (100000, "pass"), (150000, "pass"),
])
def test_real_screen_maps_only_volume(provider, volume, expected):
    mm, ctx, basic, snapshot = provider
    snapshot.loc[0, "volume"] = volume

    with patch.object(
        screen, "evaluate_snapshot", wraps=screen.evaluate_snapshot
    ) as evaluate:
        result = screen.retrieve_real_screen(" aapl ")

    mm.OpenQuoteContext.assert_called_once_with(host="127.0.0.1", port=11111)
    ctx.get_market_snapshot.assert_called_once_with(["US.AAPL"])
    ctx.close.assert_called_once_with()
    evaluate.assert_called_once()
    args, kwargs = evaluate.call_args
    assert args == ("AAPL", {
        "market_cap_usd": None,
        "close_price_usd": None,
        "net_profit_usd": None,
        "snapshot_volume_shares": volume,
    })
    assert kwargs["source_mode"] == "supplied"
    assert kwargs["company_name"] == "Test Apple"
    assert kwargs["data_timestamp"] == "2026-10-22 16:00:00"
    assert result["code"] == "US.AAPL"
    assert result["fetched_at"]

    e = result["evaluation"]
    assert not e.get("error")
    assert len(e["criteria"]) == 4
    volume_rules = [c for c in e["criteria"] if c["unit"] == "shares"]
    assert len(volume_rules) == 1
    assert volume_rules[0]["status"] == expected
    assert sum(c["status"] == "unknown" for c in e["criteria"]) == 3
    assert e["aggregate_status"] != "pass"

    raw = {r["Provider field"]: r for r in result["raw"]}
    assert set(raw) == {
        "total_market_val", "prev_close_price", "net_profit", "volume",
    }
    for name in ("total_market_val", "prev_close_price", "net_profit"):
        assert raw[name]["Use"] == "Not evaluated: USD mapping unverified"


@pytest.mark.parametrize("field,value,message", [
    ("code", "US.MSFT", "does not match"),
    ("equity_valid", False, "equity fields invalid"),
    ("update_time", "", "timestamp is missing"),
    ("volume", -1, "nonnegative share count"),
    ("volume", 1.5, "nonnegative share count"),
    ("volume", float("nan"), "nonnegative share count"),
    ("volume", float("inf"), "nonnegative share count"),
])
def test_real_screen_rejects_bad_snapshot(provider, field, value, message):
    _, ctx, _, snapshot = provider
    snapshot[field] = pd.Series([value])
    with pytest.raises(ValueError, match=message):
        screen.retrieve_real_screen("AAPL")
    ctx.close.assert_called_once_with()


@pytest.mark.parametrize("stage", ["basic", "snapshot"])
def test_real_screen_provider_failure_closes_context(provider, stage):
    _, ctx, _, _ = provider
    method = (
        ctx.get_stock_basicinfo if stage == "basic"
        else ctx.get_market_snapshot
    )
    method.return_value = (-1, "mock failure")
    with pytest.raises(RuntimeError, match="mock failure"):
        screen.retrieve_real_screen("AAPL")
    ctx.close.assert_called_once_with()


def test_real_screen_rejects_unverified_company(provider):
    _, ctx, basic, _ = provider
    basic.loc[0, "code"] = "US.MSFT"
    with pytest.raises(ValueError, match="not verified"):
        screen.retrieve_real_screen("AAPL")
    ctx.get_market_snapshot.assert_not_called()
    ctx.close.assert_called_once_with()


@pytest.mark.parametrize("ticker", ["", "AAPL!", "ACME", "BLUE", "CRST", "SMCHG"])
def test_invalid_symbols_never_open_context(provider, ticker):
    mm, _, _, _ = provider
    with pytest.raises(ValueError):
        screen.retrieve_real_screen(ticker)
    with pytest.raises(ValueError):
        chart.fetch_daily_candles(ticker, 30)
    mm.OpenQuoteContext.assert_not_called()


def install_candles(ctx, mutate=None, ret=0, page=None):
    def response(code, **kwargs):
        end = pd.Timestamp(kwargs["end"])
        frame = pd.DataFrame([
            {
                "code": code,
                "time_key": (end - timedelta(days=1)).isoformat(),
                "open": 10.0, "high": 12.0, "low": 9.0,
                "close": 11.0, "volume": 200,
            },
            {
                "code": code,
                "time_key": (end - timedelta(days=2)).isoformat(),
                "open": 11.0, "high": 12.0, "low": 9.0,
                "close": 10.0, "volume": 100,
            },
        ])
        if mutate:
            frame = mutate(frame, kwargs)
        return ret, frame, page
    ctx.request_history_kline.side_effect = response


@pytest.mark.parametrize("days", [30, 90, 180])
def test_candles_success_sorts_and_preserves_values(provider, days):
    mm, ctx, _, _ = provider
    install_candles(ctx)
    result = chart.fetch_daily_candles(" aapl ", days)
    frame = result["frame"]
    assert result["ticker"] == "AAPL"
    assert result["code"] == "US.AAPL"
    assert result["days"] == days
    assert frame["date"].is_monotonic_increasing
    assert list(frame["close"]) == [10.0, 11.0]
    assert list(frame["volume"]) == [100, 200]
    assert list(frame["direction"]) == ["Down", "Up"]
    args, kwargs = ctx.request_history_kline.call_args
    assert args == ("US.AAPL",)
    assert kwargs["ktype"] == mm.KLType.K_DAY
    assert kwargs["autype"] == mm.AuType.NONE
    assert kwargs["extended_time"] is False
    assert kwargs["max_count"] == 1000
    assert (
        pd.Timestamp(kwargs["end"]) - pd.Timestamp(kwargs["start"])
    ).days == days
    assert result["requested_end"] == kwargs["end"]
    ctx.close.assert_called_once_with()


def bad_candles(case):
    def mutate(frame, kwargs):
        if case == "schema":
            return frame.drop(columns=["close"])
        if case == "empty":
            return frame.iloc[:0]
        if case == "wrong_security":
            frame.loc[0, "code"] = "US.MSFT"
        elif case == "nonfinite":
            frame.loc[0, "close"] = float("inf")
        elif case == "bad_price":
            frame.loc[0, "open"] = 0
        elif case == "negative_volume":
            frame.loc[0, "volume"] = -1
        elif case == "bad_ohlc":
            frame.loc[0, "high"] = 8
        elif case == "duplicate":
            frame.loc[0, "time_key"] = frame.loc[1, "time_key"]
        elif case == "outside_range":
            frame.loc[0, "time_key"] = (
                pd.Timestamp(kwargs["end"]) + timedelta(days=1)
            ).isoformat()
        elif case == "invalid_date":
            frame.loc[0, "time_key"] = "not-a-date"
        return frame
    return mutate


@pytest.mark.parametrize("case", [
    "schema", "empty", "wrong_security", "nonfinite", "bad_price",
    "negative_volume", "bad_ohlc", "duplicate", "outside_range", "invalid_date",
])
def test_candles_reject_invalid_response_and_close(provider, case):
    _, ctx, _, _ = provider
    install_candles(ctx, mutate=bad_candles(case))
    with pytest.raises(ValueError):
        chart.fetch_daily_candles("AAPL", 30)
    ctx.close.assert_called_once_with()


@pytest.mark.parametrize("ret,page,message", [
    (-1, None, "could not return candles"),
    (0, "next-page", "refusing a partial chart"),
])
def test_candles_reject_provider_failure_or_pagination(provider, ret, page, message):
    _, ctx, _, _ = provider
    install_candles(ctx, ret=ret, page=page)
    with pytest.raises(RuntimeError, match=message):
        chart.fetch_daily_candles("AAPL", 30)
    ctx.close.assert_called_once_with()


def test_unsupported_range_never_opens_context(provider):
    mm, _, _, _ = provider
    with pytest.raises(ValueError, match="Unsupported date range"):
        chart.fetch_daily_candles("AAPL", 7)
    mm.OpenQuoteContext.assert_not_called()


def test_chart_specs_keep_responsive_width_and_provider_unit_labels(provider):
    _, ctx, _, _ = provider
    install_candles(ctx)
    result = chart.fetch_daily_candles("AAPL", 30)
    price, volume = chart.candle_chart(result["frame"])
    for plot in (price, volume):
        spec = plot.to_dict()
        assert spec["width"] == "container"
        assert spec["autosize"]["type"] == "fit-x"
        assert spec["autosize"]["contains"] == "padding"
        assert spec["autosize"]["resize"] is True
    price_spec = price.to_dict()
    assert len(price_spec["layer"]) == 3
    assert price_spec["layer"][0]["encoding"]["y"]["title"] == (
        "Price (provider units)"
    )
    assert volume.to_dict()["encoding"]["y"]["title"] == "Volume (shares)"

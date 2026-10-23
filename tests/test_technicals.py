"""Deterministic technical measures: windows, unavailability and split guard."""
import pandas as pd
import pytest

from api.technicals import chart_series, compute_technicals


def frame(closes, volume=1000.0, spread=1.0):
    dates = pd.bdate_range(end="2026-10-22", periods=len(closes))
    return pd.DataFrame({
        "date": dates,
        "open": closes,
        "high": [c + spread for c in closes],
        "low": [c - spread for c in closes],
        "close": closes,
        "volume": [volume] * len(closes),
    })


def test_averages_use_exact_windows():
    closes = [round(100 + 0.1 * i, 2) for i in range(260)]
    t = compute_technicals(frame(closes))
    assert t["sessions"] == 260
    assert t["last_close"] == closes[-1]
    assert t["sma_50"] == pytest.approx(sum(closes[-50:]) / 50, abs=1e-4)
    assert t["sma_150"] == pytest.approx(sum(closes[-150:]) / 150, abs=1e-4)
    assert t["sma_200"] == pytest.approx(sum(closes[-200:]) / 200, abs=1e-4)
    assert t["avg_close_12m"] == pytest.approx(sum(closes[-252:]) / 252, abs=1e-4)
    assert t["high_52w"] == closes[-1] + 1.0  # high of last 252 sessions (spread 1)
    assert t["low_52w"] == closes[-252] - 1.0
    assert t["reliability"]["ok"] is True
    assert t["unavailable"] == []


def test_short_history_leaves_long_windows_unavailable_not_estimated():
    t = compute_technicals(frame([round(100 + 0.1 * i, 2) for i in range(120)]))  # 120 sessions
    assert t["sma_50"] is not None
    assert t["sma_150"] is None and t["sma_200"] is None
    assert t["avg_close_12m"] is None and t["high_52w"] is None
    assert t["pct_below_52w_high"] is None
    assert set(t["unavailable"]) == {"sma_150", "sma_200", "avg_close_12m", "high_52w", "low_52w"}


def test_large_one_day_move_withholds_averages():
    closes = [100.0] * 200 + [20.0] * 70  # looks like an unadjusted 5:1 split
    t = compute_technicals(frame(closes))
    assert t["reliability"]["ok"] is False
    assert "unadjusted" in t["reliability"]["reason"]
    assert t["last_close"] == 20.0
    assert t["sma_150"] is None and t["sma_200"] is None and t["avg_close_12m"] is None


def test_empty_frame_is_rejected():
    with pytest.raises(ValueError):
        compute_technicals(frame([]))


def test_chart_series_only_fills_complete_windows():
    closes = [round(100 + 0.1 * i, 2) for i in range(260)]
    f = frame(closes)
    rows = chart_series(f, compute_technicals(f))
    assert len(rows) == 260
    assert rows[148]["sma_150"] is None and rows[149]["sma_150"] == pytest.approx(sum(closes[:150]) / 150, abs=1e-4)
    assert rows[198]["sma_200"] is None and rows[199]["sma_200"] is not None
    assert rows[-1]["close"] == closes[-1]


def test_chart_series_withheld_when_unreliable():
    f = frame([100.0] * 200 + [20.0] * 70)
    rows = chart_series(f, compute_technicals(f))
    assert all(r["sma_150"] is None and r["sma_200"] is None for r in rows)

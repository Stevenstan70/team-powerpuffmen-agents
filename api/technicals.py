"""Deterministic technical measures from validated daily candles.

Pure functions: no network, no AI. Windows are never shortened to fit the data;
a measure without enough sessions is None (unavailable), not an estimate.
"""
import math

METHOD_VERSION = "technicals-v1"
SESSIONS_12M = 252
# Candles are unadjusted, so a split would show up as a huge one-day move.
MAX_ABS_DAILY_MOVE = 0.45


def _mean(values):
    return sum(values) / len(values)


def _r(value):
    return None if value is None else round(float(value), 4)


def _reliability(frame):
    closes = frame["close"].astype(float).tolist()
    dates = frame["date"].dt.strftime("%Y-%m-%d").tolist()
    worst, worst_date = 0.0, None
    for i in range(1, len(closes)):
        move = abs(closes[i] / closes[i - 1] - 1)
        if move > worst:
            worst, worst_date = move, dates[i]
    if worst > MAX_ABS_DAILY_MOVE:
        return {
            "ok": False,
            "reason": (
                f"Largest one-day close change was {worst:.0%} on {worst_date}. "
                "Prices are unadjusted, so a split or other corporate action "
                "may distort averages; averages are withheld."
            ),
        }
    return {"ok": True, "reason": None}


def compute_technicals(frame):
    """Measures from a date-ascending frame with open/high/low/close/volume."""
    n = len(frame)
    if n == 0:
        raise ValueError("No candles to measure.")
    closes = frame["close"].astype(float).tolist()
    highs = frame["high"].astype(float).tolist()
    lows = frame["low"].astype(float).tolist()
    volumes = frame["volume"].astype(float).tolist()
    reliability = _reliability(frame)
    trusted = reliability["ok"]

    def sma(k):
        return _mean(closes[-k:]) if trusted and n >= k else None

    high_52w = max(highs[-SESSIONS_12M:]) if trusted and n >= SESSIONS_12M else None
    low_52w = min(lows[-SESSIONS_12M:]) if trusted and n >= SESSIONS_12M else None
    last = closes[-1]

    out = {
        "method_version": METHOD_VERSION,
        "price_basis": (
            "Moomoo daily candles, unadjusted, regular sessions; "
            "provider price units (currency not independently verified)"
        ),
        "sessions": n,
        "first_date": frame["date"].iloc[0].strftime("%Y-%m-%d"),
        "last_date": frame["date"].iloc[-1].strftime("%Y-%m-%d"),
        "last_close": _r(last),
        "sma_50": _r(sma(50)),
        "sma_150": _r(sma(150)),
        "sma_200": _r(sma(200)),
        "avg_close_12m": _r(sma(SESSIONS_12M)),
        "high_52w": _r(high_52w),
        "low_52w": _r(low_52w),
        "pct_below_52w_high": (
            _r((high_52w - last) / high_52w * 100) if high_52w else None
        ),
        "pct_above_52w_low": (
            _r((last - low_52w) / low_52w * 100) if low_52w else None
        ),
        "avg_volume_50d": _r(_mean(volumes[-50:])) if n >= 50 else None,
        "reliability": reliability,
    }
    out["unavailable"] = sorted(
        k for k in (
            "sma_50", "sma_150", "sma_200", "avg_close_12m", "high_52w",
            "low_52w", "avg_volume_50d",
        ) if out[k] is None
    )
    return out


def chart_series(frame, technicals):
    """Per-session close with 150/200-session averages (None until filled)."""
    closes = frame["close"].astype(float).tolist()
    dates = frame["date"].dt.strftime("%Y-%m-%d").tolist()
    trusted = technicals["reliability"]["ok"]
    rows = []
    for i, (d, c) in enumerate(zip(dates, closes)):
        def window(k):
            if not trusted or i + 1 < k:
                return None
            return _r(_mean(closes[i + 1 - k:i + 1]))
        rows.append({"date": d, "close": _r(c),
                     "sma_150": window(150), "sma_200": window(200)})
    return rows


def finite(value):
    return value is None or (isinstance(value, (int, float)) and math.isfinite(value))

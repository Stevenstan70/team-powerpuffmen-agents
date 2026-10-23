"""Read-only Moomoo daily candles, separate from synthetic screening."""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import re

import altair as alt
import numpy as np
import pandas as pd
import streamlit as st


def fetch_daily_candles(ticker, days):
    import moomoo as mm

    ticker = ticker.strip().upper()
    if not re.fullmatch(r"[A-Z][A-Z0-9.-]{0,9}", ticker):
        raise ValueError("Enter an exact US ticker, for example AAPL.")
    if ticker in {"ACME", "BLUE", "CRST", "SMCHG"}:
        raise ValueError("Demo fixture symbols are not market-chart inputs.")
    if days not in (30, 90, 180):
        raise ValueError("Unsupported date range.")

    code = f"US.{ticker}"
    end = datetime.now(ZoneInfo("America/New_York")).date() - timedelta(days=1)
    start = end - timedelta(days=days)
    ctx = None
    try:
        ctx = mm.OpenQuoteContext(host="127.0.0.1", port=11111)
        ret, data, next_page = ctx.request_history_kline(
            code,
            start=start.isoformat(),
            end=end.isoformat(),
            ktype=mm.KLType.K_DAY,
            autype=mm.AuType.NONE,
            max_count=1000,
            extended_time=False,
        )
        if ret != mm.RET_OK:
            raise RuntimeError(f"Moomoo could not return candles: {data}")
        if next_page is not None:
            raise RuntimeError("Response is paginated; refusing a partial chart.")

        fields = ["code", "time_key", "open", "high", "low", "close", "volume"]
        if not isinstance(data, pd.DataFrame) or not set(fields).issubset(data.columns):
            raise ValueError("Unexpected candle response schema.")
        frame = data[fields].copy()
        if frame.empty:
            raise ValueError("No candles returned for this ticker and date range.")
        if not frame["code"].eq(code).all():
            raise ValueError("Response contains a different security.")

        numeric = ["open", "high", "low", "close", "volume"]
        frame[numeric] = frame[numeric].apply(pd.to_numeric, errors="coerce")
        if not np.isfinite(frame[numeric].to_numpy()).all():
            raise ValueError("Candles contain missing or non-finite values.")
        if (frame[["open", "high", "low", "close"]] <= 0).any().any():
            raise ValueError("Candles contain invalid prices.")
        if (frame["volume"] < 0).any():
            raise ValueError("Candles contain negative volume.")
        if (
            (frame["high"] < frame[["open", "close", "low"]].max(axis=1))
            | (frame["low"] > frame[["open", "close", "high"]].min(axis=1))
        ).any():
            raise ValueError("Candles contain inconsistent OHLC prices.")

        frame["date"] = pd.to_datetime(frame["time_key"], errors="raise")
        if frame["date"].duplicated().any():
            raise ValueError("Duplicate candle timestamps.")
        dates = frame["date"].dt.date
        if not ((dates >= start) & (dates <= end)).all():
            raise ValueError("Response contains dates outside the requested range.")

        frame = frame.sort_values("date").reset_index(drop=True)
        frame["direction"] = np.where(frame["close"] >= frame["open"], "Up", "Down")
        return {
            "ticker": ticker,
            "code": code,
            "days": days,
            "requested_end": end.isoformat(),
            "fetched_at": datetime.now(ZoneInfo("UTC")).isoformat(),
            "frame": frame,
        }
    finally:
        if ctx is not None:
            ctx.close()


def candle_chart(frame):
    colors = alt.Color(
        "direction:N",
        scale=alt.Scale(domain=["Up", "Down"], range=["#35d07f", "#ff7185"]),
        legend=alt.Legend(title="Close versus open"),
    )
    tooltip = [
        alt.Tooltip("date:T", title="Session date", format="%Y-%m-%d"),
        alt.Tooltip("open:Q", format=",.3f"),
        alt.Tooltip("high:Q", format=",.3f"),
        alt.Tooltip("low:Q", format=",.3f"),
        alt.Tooltip("close:Q", format=",.3f"),
        alt.Tooltip("volume:Q", format=",.0f"),
    ]
    base = alt.Chart(frame).encode(
        x=alt.X("date:T", title="US session date"),
        color=colors,
        tooltip=tooltip,
    )
    wick = base.mark_rule().encode(
        y=alt.Y("low:Q", title="Price (provider units)", scale=alt.Scale(zero=False)),
        y2="high:Q",
    )
    body = base.mark_bar(size=6).encode(
        y=alt.Y("open:Q", title="Price (provider units)", scale=alt.Scale(zero=False)),
        y2="close:Q",
    )
    doji = base.transform_filter(
        alt.datum.open == alt.datum.close
    ).mark_tick(orient="horizontal", size=7).encode(y="close:Q")
    price = (wick + body + doji).properties(height=310)
    volume = base.mark_bar(size=6).encode(
        y=alt.Y("volume:Q", title="Volume (shares)")
    ).properties(height=95)
    def styled(chart):
        return (
            chart.properties(
                width="container",
                autosize=alt.AutoSizeParams(
                    type="fit-x",
                    contains="padding",
                    resize=True,
                ),
            ).configure_view(stroke=None)
            .configure_axis(
                labelColor="#b8c6d8",
                titleColor="#e6edf7",
                gridColor="#2b3b52",
            )
        )
    return styled(price), styled(volume)


def render_market_chart():
    with st.expander("Market price & volume — Moomoo", expanded=True):
        st.caption(
            "Separate real-security chart. Not synthetic screening data, "
            "not an agent result, and not a live stream."
        )
        with st.form("market_chart_form"):
            left, right = st.columns([3, 1])
            ticker = left.text_input("US market-chart ticker", value="AAPL")
            days = right.selectbox("Calendar-day lookback", [30, 90, 180])
            submitted = st.form_submit_button("Load daily candles")

        if submitted:
            st.session_state.pop("market_candle_result", None)
            st.session_state.pop("market_candle_error", None)
            try:
                with st.spinner("Reading historical candles from Moomoo..."):
                    st.session_state["market_candle_result"] = fetch_daily_candles(
                        ticker, days
                    )
            except Exception as exc:
                st.session_state["market_candle_error"] = str(exc)

        error = st.session_state.get("market_candle_error")
        if error:
            st.error(error)

        result = st.session_state.get("market_candle_result")
        if result is not None:
            frame = result["frame"]
            st.subheader(f"{result['code']} — daily candlesticks")
            st.caption(
                f"Moomoo historical data | Unadjusted | Regular session | "
                f"{result['days']}-calendar-day lookback | "
                f"Last returned session: {frame['date'].max():%Y-%m-%d}"
            )
            price_chart, volume_chart = candle_chart(frame)
            st.altair_chart(price_chart, width="stretch")
            st.altair_chart(volume_chart, width="stretch")
            st.caption(
                f"Fetched at {result['fetched_at']} | "
                "Date labels follow the provider's US Eastern session dates. "
                "Weekends and non-trading days may create gaps. "
                "Unadjusted prices may jump around corporate actions. "
                "Currency is not independently verified by this chart."
            )
        else:
            st.info("Enter a real US ticker and load its historical daily candles.")

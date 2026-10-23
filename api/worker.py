"""One isolated research lookup.

The API runs this in a separate process for every request. If the Moomoo SDK
crashes, exits or hangs on a ticker, only this process is lost; the API stays
up and reports the failure. Run as:

    python -m api.worker TICKER 0|1 OUTPUT_JSON_PATH
"""
import json
import sys

CANDLE_DAYS = 400  # about 275 sessions: enough for the 200-session and 12-month windows


def _default(value):
    # Convert numpy/pandas scalars; refuse anything else rather than guessing.
    if hasattr(value, "item"):
        return value.item()
    raise TypeError(f"Value of type {type(value).__name__} is not JSON serialisable")


def collect_technicals(ticker):
    """Price-history measures and local trend-rule result, or a recovery note.

    Optional evidence: any failure is recorded, never replaced with estimates.
    """
    try:
        from api.technicals import chart_series, compute_technicals
        from frontend.market_chart import fetch_daily_candles
        from tools.powerpuffmen_trend_check import powerpuffmen_trend_check

        candles = fetch_daily_candles(ticker, CANDLE_DAYS)
        frame = candles["frame"]
        technicals = compute_technicals(frame)
        series = chart_series(frame, technicals)
        trend_tool = getattr(powerpuffmen_trend_check, "fn", powerpuffmen_trend_check)
        trend = trend_tool(**{
            k: technicals[k]
            for k in ("last_close", "sma_150", "sma_200", "avg_close_12m",
                      "high_52w", "low_52w")
            if technicals[k] is not None
        })
        technicals["requested_end"] = candles["requested_end"]
        technicals["fetched_at"] = candles["fetched_at"]
        return {"status": "computed", "technicals": technicals, "trend": trend,
                "price_series": series, "warning": None}
    except BaseException as exc:
        return {
            "status": "unavailable", "technicals": None, "trend": None,
            "price_series": [],
            "warning": {
                "stage": "technicals_retrieval",
                "error_type": type(exc).__name__,
                "message": (
                    "Price-history measures were unavailable. Technical "
                    "indicators are not estimated; the research continued "
                    "without them. " + str(exc)
                ),
            },
        }


def run(ticker, include_statement_profit):
    """Return an outcome dict. Never raises for ordinary failures."""
    try:
        from frontend.real_screen import retrieve_real_screen
        from frontend.research_brief import build_research_brief

        result = retrieve_real_screen(
            ticker, include_statement_profit=include_statement_profit
        )
        tech = collect_technicals(ticker)
        result["technicals_status"] = tech["status"]
        result["technicals"] = tech["technicals"]
        result["trend"] = tech["trend"]
        result["price_series"] = tech["price_series"]
        if tech["warning"]:
            result["warnings"] = list(result.get("warnings", [])) + [tech["warning"]]
        return {"ok": True, "result": result, "brief": build_research_brief(result)}
    except ImportError as exc:
        return {"ok": False, "kind": "dependency",
                "error": f"Backend dependency is not installed: {exc.name or exc}"}
    except ValueError as exc:
        # Bad ticker, unverified security, or evidence that failed validation.
        return {"ok": False, "kind": "validation", "error": str(exc)}
    except BaseException as exc:  # SDKs sometimes raise SystemExit
        return {"ok": False, "kind": "provider",
                "error": f"{type(exc).__name__}: {exc}"}


def main(argv):
    ticker, flag, out_path = argv[1], argv[2] == "1", argv[3]
    outcome = run(ticker, flag)
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(outcome, fh, default=_default)


if __name__ == "__main__":
    main(sys.argv)

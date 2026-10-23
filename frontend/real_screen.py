"""Real-company evidence and partial snapshot-policy evaluation."""
from datetime import datetime, timezone
import math
import re

import pandas as pd
import streamlit as st

from frontend.snapshot_adapter import evaluate_snapshot


def retrieve_real_screen(ticker, *, include_statement_profit=False):
    import moomoo as mm

    ticker = ticker.strip().upper()
    if not re.fullmatch(r"[A-Z][A-Z0-9.-]{0,9}", ticker):
        raise ValueError("Enter an exact US ticker, for example AAPL.")
    if ticker in {"ACME", "BLUE", "CRST", "SMCHG"}:
        raise ValueError("Use Synthetic demo for the fictional fixture symbols.")

    code = f"US.{ticker}"
    ctx = None
    try:
        ctx = mm.OpenQuoteContext(host="127.0.0.1", port=11111)

        ret, basic = ctx.get_stock_basicinfo(
            mm.Market.US,
            stock_type=mm.SecurityType.STOCK,
            code_list=[code],
        )
        if ret != mm.RET_OK:
            raise RuntimeError(f"Company verification failed: {basic}")
        if not {"code", "name", "stock_type"}.issubset(basic.columns):
            raise ValueError("Unexpected company-information schema.")
        exact = basic[
            basic["code"].eq(code)
            & basic["stock_type"].astype(str).str.upper().eq("STOCK")
        ]
        if len(exact) != 1 or pd.isna(exact.iloc[0]["name"]):
            raise ValueError("An exact, unambiguous US stock was not verified.")

        ret, data = ctx.get_market_snapshot([code])
        if ret != mm.RET_OK:
            raise RuntimeError(f"Snapshot retrieval failed: {data}")
        required = {"code", "update_time", "equity_valid", "volume"}
        if not required.issubset(data.columns):
            raise ValueError("Unexpected snapshot schema.")
        if len(data) != 1 or data.iloc[0]["code"] != code:
            raise ValueError("Snapshot does not match the requested security.")

        row = data.iloc[0]
        flag = row["equity_valid"]
        if pd.isna(flag) or not bool(flag):
            raise ValueError("Provider marked equity fields invalid.")

        timestamp = row["update_time"]
        if pd.isna(timestamp) or not str(timestamp).strip():
            raise ValueError("Provider snapshot timestamp is missing.")
        pd.to_datetime(str(timestamp), errors="raise")

        volume = row["volume"]
        if isinstance(volume, bool):
            raise ValueError("Invalid snapshot volume.")
        volume = float(volume)
        if not math.isfinite(volume) or volume < 0 or not volume.is_integer():
            raise ValueError("Snapshot volume is not a nonnegative share count.")

        statement_evidence = None
        if include_statement_profit:
            from frontend.statement_evidence import extract_net_profit_evidence

            ret, statement_payload = ctx.get_financials_statements(code=code)
            if ret != mm.RET_OK:
                raise RuntimeError(
                    f"Financial-statement retrieval failed: {statement_payload}"
                )
            statement_evidence = extract_net_profit_evidence(
                statement_payload, code
            )

        inputs = {
            "market_cap_usd": None,
            "close_price_usd": None,
            "net_profit_usd": (
                statement_evidence["value"]
                if statement_evidence is not None
                else None
            ),
            "snapshot_volume_shares": int(volume),
        }
        evaluation = evaluate_snapshot(
            ticker,
            inputs,
            source_mode="supplied",
            company_name=str(exact.iloc[0]["name"]),
            data_timestamp=str(timestamp),
            **(
                {"net_profit_evidence": statement_evidence}
                if statement_evidence is not None
                else {}
            ),
        )
        if evaluation.get("error"):
            raise ValueError(evaluation["error"])

        raw = []
        for field in (
            "total_market_val", "prev_close_price", "net_profit", "volume"
        ):
            value = row.get(field)
            raw.append({
                "Provider field": field,
                "Raw value": "Unavailable" if pd.isna(value) else str(value),
                "Use": (
                    "Evaluated as snapshot shares"
                    if field == "volume"
                    else "Not evaluated: USD mapping unverified"
                ),
            })

        if statement_evidence is not None:
            raw.append({
                "Provider field": "financial statements: field 8037",
                "Raw value": str(statement_evidence["value"]),
                "Use": (
                    "Evaluated as USD net profit for "
                    + statement_evidence["period_text"]
                    + " (report end " + statement_evidence["report_end"] + "); "
                    + "most recent returned report, not inferred annual or TTM"
                ),
            })

        return {
            "evaluation": evaluation,
            "raw": raw,
            "code": code,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        }
    finally:
        if ctx is not None:
            ctx.close()


def render_real_screen():
    st.caption(
        "Real-company evidence from Moomoo. Partial evaluation only; "
        "not synthetic data and not a complete eligibility decision."
    )

    def clear_result():
        st.session_state.pop("real_screen_result", None)
        st.session_state.pop("real_screen_error", None)

    ticker = st.text_input(
        "Real US stock ticker",
        value="AAPL",
        key="real_screen_ticker",
        on_change=clear_result,
    )
    include_statements = st.checkbox(
        "Include statement-reported USD net profit",
        value=False,
        key="real_screen_statements",
        on_change=clear_result,
        help=(
            "Requests financial statements in addition to the snapshot. "
            "Uses the most recent report in the returned response; "
            "does not infer annual or TTM profit. "
            "Retrieval or validation failures stop this request."
        ),
    )
    if st.button("Retrieve real-company screen", key="real_screen_load"):
        clear_result()
        try:
            with st.spinner("Verifying stock and retrieving selected evidence..."):
                st.session_state["real_screen_result"] = retrieve_real_screen(
                    ticker,
                    **(
                        {"include_statement_profit": True}
                        if include_statements
                        else {}
                    ),
                )
        except Exception as exc:
            st.session_state["real_screen_error"] = str(exc)

    if st.session_state.get("real_screen_error"):
        st.error(st.session_state["real_screen_error"])

    result = st.session_state.get("real_screen_result")
    if result is None:
        st.info("Enter a real US ticker and retrieve its available screening evidence.")
        return

    e = result["evaluation"]
    st.subheader(f"{e['company_name']} ({result['code']})")
    st.warning(
        "INCOMPLETE SCREEN: some criteria remain unverified. "
        "Real-data screening and agent analysis are blocked from a complete "
        "decision pending currency, units, and provider-validity verification."
    )
    st.caption(
        f"Provider snapshot: {e['data_timestamp']} "
        "(provider timestamp; timezone not independently verified). "
        f"Retrieved at: {result['fetched_at']}. Not a streaming feed."
    )
    labels = {"pass": "PASS", "fail": "FAIL", "unknown": "UNVERIFIED"}
    st.dataframe(
        [
            {
                "Criterion": c["label"],
                "Observed": c["observed_fmt"],
                "Threshold": str(c["threshold"]),
                "Status": labels[c["status"]],
                "Period": c["reporting_period"],
            }
            for c in e["criteria"]
        ],
        hide_index=True,
        width="stretch",
    )
    with st.expander("Raw provider evidence", expanded=True):
        st.dataframe(result["raw"], hide_index=True, width="stretch")
        for criterion in e["criteria"]:
            provenance = criterion.get("provenance")
            if provenance is not None:
                st.caption("Statement provenance: " + criterion["label"])
                st.json(provenance)
    st.caption(e["scope_note"])
    st.info(
        "Real-company cloud-agent analysis and monitoring are not enabled here. "
        "These results are kept separate from synthetic baselines and approvals."
    )

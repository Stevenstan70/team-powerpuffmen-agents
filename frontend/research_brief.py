"""Deterministic preliminary brief; no network calls or AI claims."""

STATUS = {"pass": "PASS", "fail": "FAIL", "unknown": "UNVERIFIED"}


def _cell(value):
    if value is None:
        return "Unavailable"
    return str(value).replace("|", "/").replace("\n", " ").replace("\r", " ")


def _num(value):
    return "Unavailable" if value is None else f"{value:,.2f}"


def _technical_lines(result):
    """Price-trend section; omitted entirely when technicals were not attempted."""
    status = result.get("technicals_status")
    if status is None:
        return []
    lines = ["", "## Technical measures (price history)"]
    t = result.get("technicals")
    if status != "computed" or not t:
        lines.append(
            "- Price-history measures were not retrieved. No technical "
            "indicator has been estimated. See the recovery notes below."
        )
        return lines

    lines += [
        "- Source: Moomoo request_history_kline, daily candles, unadjusted, "
        "regular sessions. Prices are in provider units; the currency is not "
        "independently verified (ratios between prices in one series are "
        "unit-independent).",
        f"- Sessions used: {t['sessions']} ({_cell(t['first_date'])} to "
        f"{_cell(t['last_date'])}). Request-time evidence, not a streaming feed.",
        f"- Last close: {_num(t['last_close'])} on {_cell(t['last_date'])}",
        f"- 50 / 150 / 200-session average: {_num(t['sma_50'])} / "
        f"{_num(t['sma_150'])} / {_num(t['sma_200'])}",
        f"- 12-month (252-session) average close: {_num(t['avg_close_12m'])}",
        f"- 52-week high / low: {_num(t['high_52w'])} / {_num(t['low_52w'])}",
        f"- Distance below 52-week high: {_num(t['pct_below_52w_high'])}%; "
        f"above 52-week low: {_num(t['pct_above_52w_low'])}%",
        f"- 50-session average volume: {_num(t['avg_volume_50d'])} shares",
    ]
    if not t["reliability"]["ok"]:
        lines.append(f"- Reliability: {_cell(t['reliability']['reason'])}")
    if t["unavailable"]:
        lines.append(
            "- Unavailable (not enough sessions or withheld): "
            + ", ".join(t["unavailable"]) + "."
        )

    trend = result.get("trend")
    if trend:
        lines += [
            "",
            f"Trend check ({_cell(trend['criteria_version'])}): "
            f"{_cell(trend['trend_check_status'])}",
            "| Rule | Last close | Reference | Status |",
            "|---|---|---|---|",
        ]
        for r in trend["rules"]:
            lines.append(
                f"| {_cell(r['threshold'])} | {_num(r['observed_value'])} | "
                f"{_num(r['reference_value'])} | {_cell(r['status'])} |"
            )
        lines.append(f"- {_cell(trend['scope_note'])}")
    return lines


def build_research_brief(result):
    """Format existing evidence without changing it or inventing facts."""
    e = result["evaluation"]
    if e.get("error"):
        raise ValueError("Cannot build a brief from an invalid evaluation.")

    rules = e["criteria"]
    missing = [c for c in rules if c["status"] == "unknown"]
    statement_status = result.get("statement_status", "not_recorded")

    lines = [
        "# InvestIQ preliminary company research brief",
        "",
        f"Company: {_cell(e.get('company_name'))} ({_cell(result['code'])})",
        "",
        "Brief status: preliminary; incomplete evidence.",
        f"Screen outcome: {STATUS[e['aggregate_status']]}",
        f"Policy: {_cell(e['criteria_version'])}",
        "",
        "This is a deterministic report assembled by the application, "
        "not an IBM-agent-generated research opinion.",
        "",
        "## Evidence and timing",
        "- Identity source: Moomoo get_stock_basicinfo.",
        "- Snapshot source: Moomoo get_market_snapshot.",
        f"- Provider snapshot timestamp: {_cell(e.get('data_timestamp'))}. "
        "Provider timezone is not independently verified.",
        f"- Retrieved at (UTC): {_cell(result.get('fetched_at'))}.",
        f"- Evaluated at: {_cell(e.get('evaluated_at'))}.",
        "- This is request-time evidence, not a streaming feed.",
        "",
        "## Screening results",
        "| Rule | Observed | Threshold | Status | Period |",
        "|---|---|---|---|---|",
    ]
    for c in rules:
        cells = [
            c["label"], c["observed_fmt"], c["threshold"],
            STATUS[c["status"]], c["reporting_period"],
        ]
        lines.append("| " + " | ".join(_cell(x) for x in cells) + " |")

    lines += ["", "## Rule explanations"]
    for c in rules:
        lines.append(f"- {_cell(c['label'])}: {_cell(c['explanation'])}")

    lines += _technical_lines(result)

    lines += ["", "## Statement evidence"]
    if statement_status == "not_requested":
        lines.append("Optional financial statements were not requested.")
    elif statement_status == "unavailable":
        lines.append(
            "Statements were requested but retrieval or validation failed. "
            "No statement profit was substituted."
        )
    elif statement_status == "validated":
        lines.append(
            "Statement evidence passed the application's validation. "
            "This is not independent verification of the provider."
        )
    else:
        lines.append("Statement request status was not recorded.")

    for c in rules:
        p = c.get("provenance")
        if p:
            for field in (
                "source", "requested_code", "field_id", "provider_label",
                "value", "currency_code", "period_text", "financial_type",
                "report_end", "selection_basis", "has_more_pages",
            ):
                lines.append(f"- {field}: {_cell(p.get(field))}")
            lines.append(
                "- Most recent report in the returned response does not "
                "establish latest available filing or complete pagination."
            )

    lines += ["", "## Missing information and recovery"]
    if missing:
        for c in missing:
            lines.append(f"- {_cell(c['label'])}: {_cell(c['explanation'])}")
    else:
        lines.append("- No screening input is marked unavailable.")

    lines.append(
        "- Provider snapshot market cap and previous close are withheld "
        "from screening because their USD mappings remain unverified."
    )
    for warning in result.get("warnings", []):
        lines.append(
            f"- Recovery: {_cell(warning['stage'])} "
            f"({_cell(warning['error_type'])}): {_cell(warning['message'])}"
        )

    lines += [
        "",
        "## Raw provider evidence",
        "These observations are not automatically verified screening inputs.",
        "| Provider field | Raw value | Use |",
        "|---|---|---|",
    ]
    for row in result.get("raw", []):
        lines.append(
            "| " + " | ".join(_cell(row.get(k)) for k in
            ("Provider field", "Raw value", "Use")) + " |"
        )

    lines += [
        "",
        "## News and conflicting evidence",
        "- News: not retrieved in this workflow.",
        "- No cross-source conflict check performed.",
        "",
        "## Limitations and next steps",
        "- The identity lookup checks an exact provider US STOCK record. "
        "Domestic-issuer/common-stock eligibility is not fully established.",
        "- Verify currency and unit mappings before using withheld values.",
        "- Obtain missing evidence and investigate material news before "
        "drawing a broader research conclusion.",
        "- Snapshot volume is not average daily volume.",
        "- Reported profit is not automatically annual or TTM profit.",
        "- No accepted research assumptions were changed by this report.",
        "",
        e["scope_note"],
    ]
    return "\n".join(lines) + "\n"
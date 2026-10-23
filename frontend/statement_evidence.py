"""Validate provider statement evidence separately from screening policy."""
from datetime import date
import math
from numbers import Real


def extract_net_profit_evidence(payload, requested_code):
    """Extract net profit from the most recent report in this response.

    This does not establish that the response contains the latest available
    filing, that all pages have been retrieved, or that a quarterly amount
    satisfies an annual/TTM policy.
    """
    if not isinstance(requested_code, str) or not requested_code.startswith("US."):
        raise ValueError("An explicit requested US security code is required.")
    if not isinstance(payload, dict):
        raise ValueError("Unexpected statement response schema.")

    reports = payload.get("report_list")
    if not isinstance(reports, list) or not reports:
        raise ValueError("No financial reports returned.")

    dated = []
    for report in reports:
        if not isinstance(report, dict):
            raise ValueError("Unexpected financial report schema.")
        end_text = report.get("date_time_str")
        if not isinstance(end_text, str):
            raise ValueError("Report-end date is missing.")
        end = date.fromisoformat(end_text)
        if end.isoformat() != end_text:
            raise ValueError("Report-end date must use YYYY-MM-DD.")
        dated.append((end, report))

    newest = max(end for end, _ in dated)
    candidates = [r for end, r in dated if end == newest]
    if len(candidates) != 1:
        raise ValueError("Most recent returned report is ambiguous.")
    report = candidates[0]

    if report.get("currency_code") != "USD":
        raise ValueError("Returned report currency is not explicitly USD.")

    period = report.get("period_text")
    financial_type = report.get("financial_type")
    if not isinstance(period, str) or not period.strip():
        raise ValueError("Report period is missing.")
    if not isinstance(financial_type, str) or not financial_type.strip():
        raise ValueError("Financial report type is missing.")

    items = report.get("item_list")
    if not isinstance(items, list):
        raise ValueError("Financial item list is missing.")
    matches = [
        item for item in items
        if isinstance(item, dict) and item.get("field_id") == 8037
    ]
    if len(matches) != 1:
        raise ValueError("Expected exactly one Net Profit field 8037.")

    item = matches[0]
    value = item.get("data")
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError("Net profit must be numeric, not missing or boolean.")
    value = float(value)
    if not math.isfinite(value):
        raise ValueError("Net profit must be finite.")

    return {
        "source": "moomoo.get_financials_statements",
        "requested_code": requested_code,
        "field_id": 8037,
        "provider_label": item.get("display_name"),
        "value": value,
        "currency_code": "USD",
        "period_text": period,
        "financial_type": financial_type,
        "report_end": newest.isoformat(),
        "fiscal_year": report.get("fiscal_year"),
        "accounting_standards": report.get("accounting_standards"),
        "selection_basis": "most recent report in returned response",
        "next_key": payload.get("next_key"),
        "has_more_pages": payload.get("next_key") not in (None, ""),
    }

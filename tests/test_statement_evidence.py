"""Offline tests for financial-statement evidence extraction."""
import copy

import pytest

from frontend.statement_evidence import extract_net_profit_evidence


@pytest.fixture
def payload():
    return {
        "next_key": "older-page",
        "structure_list": [],
        "report_list": [{
            "date_time_str": "2026-06-26",
            "fiscal_year": 2026,
            "financial_type": "Q3",
            "period_text": "2026/Q3",
            "currency_code": "USD",
            "accounting_standards": "US_GAAP",
            "item_list": [
                {
                    "field_id": 8037,
                    "display_name": "Net Profit",
                    "data": 29789000000.0,
                },
                {
                    "field_id": 8043,
                    "display_name": "Net Income to Parent Company",
                    "data": 123.0,
                },
            ],
        }],
    }


def test_extract_preserves_provenance_without_mutating_payload(payload):
    before = copy.deepcopy(payload)
    result = extract_net_profit_evidence(payload, "US.AAPL")
    assert result == {
        "source": "moomoo.get_financials_statements",
        "requested_code": "US.AAPL",
        "field_id": 8037,
        "provider_label": "Net Profit",
        "value": 29789000000.0,
        "currency_code": "USD",
        "period_text": "2026/Q3",
        "financial_type": "Q3",
        "report_end": "2026-06-26",
        "fiscal_year": 2026,
        "accounting_standards": "US_GAAP",
        "selection_basis": "most recent report in returned response",
        "next_key": "older-page",
        "has_more_pages": True,
    }
    assert payload == before


def test_selects_by_report_end_not_list_position(payload):
    older = copy.deepcopy(payload["report_list"][0])
    older.update(
        date_time_str="2026-03-27",
        financial_type="Q2",
        period_text="2026/Q2",
    )
    older["item_list"][0]["data"] = 10.0
    payload["report_list"].insert(0, older)
    result = extract_net_profit_evidence(payload, "US.AAPL")
    assert result["period_text"] == "2026/Q3"
    assert result["value"] == 29789000000.0


@pytest.mark.parametrize("value", [0, -25.5, 42])
def test_zero_and_negative_profit_remain_valid_evidence(payload, value):
    payload["report_list"][0]["item_list"][0]["data"] = value
    result = extract_net_profit_evidence(payload, "US.AAPL")
    assert result["value"] == float(value)


@pytest.mark.parametrize("value", [
    None, True, False, "29789000000", float("nan"),
    float("inf"), float("-inf"),
])
def test_rejects_missing_boolean_string_or_nonfinite_profit(payload, value):
    payload["report_list"][0]["item_list"][0]["data"] = value
    with pytest.raises(ValueError, match="Net profit"):
        extract_net_profit_evidence(payload, "US.AAPL")


@pytest.mark.parametrize("bad", [None, [], {}, {"report_list": []}])
def test_rejects_missing_response_or_reports(bad):
    with pytest.raises(ValueError):
        extract_net_profit_evidence(bad, "US.AAPL")


@pytest.mark.parametrize("key,value,message", [
    ("currency_code", "HKD", "not explicitly USD"),
    ("currency_code", None, "not explicitly USD"),
    ("period_text", "", "Report period"),
    ("period_text", None, "Report period"),
    ("financial_type", "", "report type"),
    ("date_time_str", None, "Report-end date"),
    ("date_time_str", "not-a-date", None),
    ("date_time_str", "2026-02-30", None),
    ("item_list", None, "item list"),
])
def test_rejects_invalid_report_metadata(payload, key, value, message):
    payload["report_list"][0][key] = value
    with pytest.raises(ValueError, match=message):
        extract_net_profit_evidence(payload, "US.AAPL")


def test_does_not_substitute_parent_income_for_net_profit(payload):
    report = payload["report_list"][0]
    report["item_list"] = [
        i for i in report["item_list"] if i["field_id"] != 8037
    ]
    with pytest.raises(ValueError, match="exactly one Net Profit"):
        extract_net_profit_evidence(payload, "US.AAPL")


def test_rejects_duplicate_net_profit_items(payload):
    report = payload["report_list"][0]
    report["item_list"].append(copy.deepcopy(report["item_list"][0]))
    with pytest.raises(ValueError, match="exactly one Net Profit"):
        extract_net_profit_evidence(payload, "US.AAPL")


def test_rejects_ambiguous_most_recent_report(payload):
    payload["report_list"].append(copy.deepcopy(payload["report_list"][0]))
    with pytest.raises(ValueError, match="ambiguous"):
        extract_net_profit_evidence(payload, "US.AAPL")


def test_does_not_fall_back_to_older_report_when_newest_is_invalid(payload):
    older = copy.deepcopy(payload["report_list"][0])
    older["date_time_str"] = "2026-03-27"
    payload["report_list"].append(older)
    payload["report_list"][0]["currency_code"] = "HKD"
    with pytest.raises(ValueError, match="not explicitly USD"):
        extract_net_profit_evidence(payload, "US.AAPL")


@pytest.mark.parametrize("cursor,has_more", [
    (None, False), ("", False), ("older-page", True),
])
def test_preserves_pagination_boundary(payload, cursor, has_more):
    payload["next_key"] = cursor
    result = extract_net_profit_evidence(payload, "US.AAPL")
    assert result["next_key"] == cursor
    assert result["has_more_pages"] is has_more


@pytest.mark.parametrize("code", [None, "", "AAPL", "HK.00700"])
def test_requires_explicit_us_request_code(payload, code):
    with pytest.raises(ValueError, match="requested US security code"):
        extract_net_profit_evidence(payload, code)


def statement_inputs(value):
    return {
        "market_cap_usd": None,
        "close_price_usd": None,
        "net_profit_usd": value,
        "snapshot_volume_shares": 150000,
    }


def test_adapter_preserves_statement_period_and_input_isolation(payload):
    from frontend.snapshot_adapter import evaluate_snapshot
    evidence = extract_net_profit_evidence(payload, "US.AAPL")
    before = copy.deepcopy(evidence)
    result = evaluate_snapshot(
        "AAPL", statement_inputs(evidence["value"]),
        net_profit_evidence=evidence,
    )
    assert result["error"] is None, result["error"]
    profit = [
        c for c in result["criteria"] if "net profit" in c["label"].lower()
    ]
    assert len(profit) == 1
    assert profit[0]["status"] == "pass"
    assert "2026/Q3" in profit[0]["reporting_period"]
    assert "2026-06-26" in profit[0]["reporting_period"]
    assert profit[0]["provenance"]["currency_code"] == "USD"
    assert "reporting period is unspecified" not in result["scope_note"]
    assert "not relabeled as annual or TTM" in result["scope_note"]
    assert result["aggregate_status"] == "unknown"
    assert evidence == before
    evidence["period_text"] = "MUTATED"
    assert profit[0]["provenance"]["period_text"] == "2026/Q3"


@pytest.mark.parametrize("key,value", [
    ("source", "unknown"),
    ("requested_code", "US.MSFT"),
    ("field_id", 8043),
    ("currency_code", "HKD"),
    ("period_text", ""),
    ("report_end", "invalid"),
    ("value", None),
    ("value", float("inf")),
])
def test_adapter_rejects_bad_statement_provenance(payload, key, value):
    from frontend.snapshot_adapter import evaluate_snapshot
    evidence = extract_net_profit_evidence(payload, "US.AAPL")
    evidence[key] = value
    result = evaluate_snapshot(
        "AAPL", statement_inputs(29789000000.0),
        net_profit_evidence=evidence,
    )
    assert result["error"]
    assert result["criteria"] == []
    assert result["aggregate_status"] == "unknown"


@pytest.mark.parametrize("value", [None, True, 1.0])
def test_adapter_rejects_missing_or_mismatched_profit_input(payload, value):
    from frontend.snapshot_adapter import evaluate_snapshot
    evidence = extract_net_profit_evidence(payload, "US.AAPL")
    result = evaluate_snapshot(
        "AAPL", statement_inputs(value),
        net_profit_evidence=evidence,
    )
    assert result["error"]
    assert result["criteria"] == []


def test_adapter_rejects_statement_evidence_in_demo_mode(payload):
    from frontend.snapshot_adapter import evaluate_snapshot
    evidence = extract_net_profit_evidence(payload, "US.AAPL")
    result = evaluate_snapshot(
        "AAPL", statement_inputs(evidence["value"]),
        source_mode="demo",
        net_profit_evidence=evidence,
    )
    assert result["error"]
    assert result["criteria"] == []

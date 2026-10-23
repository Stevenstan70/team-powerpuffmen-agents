"""Second Orchestrate tool: three price-trend rules on supplied measures."""
import pytest

from tools.powerpuffmen_trend_check import POLICY_VERSION, powerpuffmen_trend_check

check = getattr(powerpuffmen_trend_check, "fn", powerpuffmen_trend_check)


def statuses(result):
    return {r["rule_name"]: r["status"] for r in result["rules"]}


def test_all_pass_when_close_is_above_every_average():
    r = check(last_close=120, sma_150=100, sma_200=95, avg_close_12m=90,
              high_52w=130, low_52w=70)
    assert r["trend_check_status"] == "PASS"
    assert r["criteria_version"] == POLICY_VERSION == "trend-check-v1"
    assert set(statuses(r).values()) == {"PASS"}
    assert r["context"] == {"pct_below_52w_high": 7.69, "pct_above_52w_low": 71.43}


def test_equal_is_not_above():
    r = check(last_close=100, sma_150=100, sma_200=90, avg_close_12m=90)
    assert statuses(r)["above_sma_150"] == "FAIL"
    assert r["trend_check_status"] == "FAIL"


def test_fail_beats_unverified():
    r = check(last_close=80, sma_150=100)  # one FAIL, two unavailable
    assert statuses(r) == {
        "above_12m_average": "UNVERIFIED",
        "above_sma_200": "UNVERIFIED",
        "above_sma_150": "FAIL",
    }
    assert r["trend_check_status"] == "FAIL"


def test_missing_inputs_are_unverified_never_zero():
    r = check(last_close=100, sma_200=90)
    assert statuses(r)["above_sma_200"] == "PASS"
    assert statuses(r)["above_sma_150"] == "UNVERIFIED"
    assert r["trend_check_status"] == "UNVERIFIED"
    assert check()["trend_check_status"] == "UNVERIFIED"


@pytest.mark.parametrize("field,value", [
    ("last_close", 0), ("sma_150", -5), ("sma_200", float("nan")),
    ("avg_close_12m", float("inf")), ("high_52w", True), ("low_52w", "10"),
])
def test_invalid_inputs_are_rejected(field, value):
    with pytest.raises(ValueError):
        check(**{field: value})


def test_scope_note_denies_signal_claims():
    note = check()["scope_note"]
    assert "not a buy or sell signal" in note and "not a VCP determination" in note

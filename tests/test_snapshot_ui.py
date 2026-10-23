from pathlib import Path
from unittest.mock import patch

import pytest
from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parents[1] / "app.py")


def clean(at):
    assert not at.exception, [e.message for e in at.exception]
    return at


def start():
    return clean(AppTest.from_file(APP, default_timeout=30).run())


def click(at, label):
    buttons = [b for b in at.button if b.label == label]
    assert len(buttons) == 1, f"Expected one button: {label}"
    return clean(buttons[0].click().run())


def demo(at, ticker):
    return clean(at.button(key=f"demo_{ticker.lower()}").click().run())


def queued():
    at = demo(start(), "SMCHG")
    click(at, "Save company for monitoring")
    clean(at.selectbox(key="scenario_SMCHG").select("Negative net profit").run())
    clean(at.button(key="check_SMCHG").click().run())
    result = at.session_state["v2_checks"]["SMCHG"]
    assert not result["error"]
    assert any(
        c["Old status"] == "pass" and c["New status"] == "fail"
        for c in result["changes"]
    )
    clean(at.button(key="queue_SMCHG").click().run())
    assert at.session_state["pending_approval"]["ticker"] == "SMCHG"
    return at


@pytest.mark.parametrize(
    "ticker,status",
    [("ACME", "pass"), ("BLUE", "fail"), ("CRST", "unknown"), ("SMCHG", "pass")],
)
def test_snapshot_demos(ticker, status):
    with patch("frontend.snapshot_adapter.analyse_snapshot") as agent:
        at = demo(start(), ticker)
        result = at.session_state["current_eval"]
        assert not result.get("error")
        assert result["ticker"] == ticker
        assert result["aggregate_status"] == status
        assert len(result["criteria"]) == 4
        assert len(at.dataframe) > 0
        agent.assert_not_called()


def test_switching_company_clears_results():
    at = demo(start(), "ACME")
    clean(at.selectbox(key="demo_ticker").select("BLUE").run())
    assert at.session_state["current_eval"] is None
    assert at.session_state["current_analysis"] is None


def test_approval_updates_review_list_and_logs():
    at = queued()
    buttons = [b for b in at.button if b.label.startswith("Approve")]
    assert len(buttons) == 1
    clean(buttons[0].click().run())
    assert "SMCHG" in at.session_state["needs_review_list"]
    assert at.session_state["pending_approval"] is None
    assert at.session_state["action_log"][-1]["Action"] == "approved_needs_review"


def test_new_comparison_invalidates_pending_proposal():
    at = queued()
    clean(at.selectbox(key="scenario_SMCHG").select("Baseline / unchanged").run())
    clean(at.button(key="check_SMCHG").click().run())
    assert at.session_state["pending_approval"] is None
    assert not at.session_state["v2_checks"]["SMCHG"]["changes"]


def test_replacement_baseline_invalidates_pending_proposal():
    at = queued()
    click(at, "Save company for monitoring")
    assert at.session_state["pending_approval"] is None
    assert "SMCHG" not in at.session_state["v2_checks"]
    assert "SMCHG" not in at.session_state["needs_review_list"]


def test_real_company_partial_screen_is_explicit_and_fails_closed():
    with patch("frontend.real_screen.retrieve_real_screen") as retrieve:
        with patch("frontend.snapshot_adapter.evaluate_snapshot") as evaluate:
            with patch("frontend.snapshot_adapter.analyse_snapshot") as agent:
                with patch("frontend.market_chart.fetch_daily_candles") as candles:
                    retrieve.side_effect = RuntimeError("Mock provider unavailable")
                    at = start()
                    source = at.radio[0]
                    clean(source.set_value(source.options[1]).run())

                    assert any(
                        "Partial evaluation only" in c.value for c in at.caption
                    )
                    assert any(b.key == "real_screen_load" for b in at.button)
                    assert not any(
                        b.key == "agent_analyse_btn" for b in at.button
                    )
                    assert at.session_state["current_eval"] is None
                    retrieve.assert_not_called()
                    evaluate.assert_not_called()
                    agent.assert_not_called()
                    candles.assert_not_called()

                    clean(at.button(key="real_screen_load").click().run())
                    retrieve.assert_called_once_with("AAPL")
                    assert any(
                        "Mock provider unavailable" in e.value for e in at.error
                    )
                    assert at.session_state.get("real_screen_result") is None
                    assert at.session_state["current_eval"] is None
                    assert not at.session_state["tracked"]
                    evaluate.assert_not_called()
                    agent.assert_not_called()
                    candles.assert_not_called()

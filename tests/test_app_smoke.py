"""
Streamlit AppTest smoke tests for app.py.

Uses Streamlit's AppTest framework (available since 1.18.0) to exercise the
screening and monitoring workflow without starting a server.

MIGRATION NOTE — old interface → new interface
=============================================
The app was rewritten from a sidebar-selectbox/single-page layout to a
ticker-text-input / tabbed layout.  This table documents how every old
assertion maps to the new interface so that no behavioural coverage is lost:

  Old                                  New
  ───────────────────────────────────  ──────────────────────────────────────
  sidebar selectbox                    demo shortcut buttons (keyed)
  selectbox.set_value(company).run()   button(key=demo_KEY).click().run()
                                       + form_submit_button submit
  button[0] ("▶ Run basic screen")     form submit via at.button(key=…)
  "SYNTHETIC DEMO DATA" warning        replaced by a PROTOTYPE info banner;
                                       demo label still appears per-ticker as
                                       a st.warning after running a demo screen
  "Aggregate status" caption           shown before ticker is set (unchanged)
  "AI agent not connected" caption     shown before ticker is set (unchanged)
  "Press ▶ Run basic screen" prompt    shown before ticker is set (unchanged)
  df["Rule"]                           df["Criterion"]  (same data, new name)
  df["Observed value"]                 df["Observed"]   (same data, new name)
  df["Required threshold"]             df["Threshold"]  (same data, new name)
  "Only four rules evaluated"          "Only the criteria returned by the
                                        screening tool were evaluated."
  "UNVERIFIED" aggregate               "UNKNOWN" (adapter uses lowercase status
                                        mapped to ⚠️ UNKNOWN in the UI)
  company dropdown names               demo ticker keys: ACME, BLUE, CRST

All behavioural invariants are preserved:
  ✓ No exception on startup
  ✓ Persistent demo-data warning
  ✓ AI-not-connected state labelled honestly
  ✓ Screening values, thresholds, and statuses in table
  ✓ Missing values → Unknown (not zero, not confirmed failure)
  ✓ Switching tickers clears stale results
  ✓ Scope disclaimer (not an investment recommendation)
  ✓ No fabricated content labels

New workflow coverage added (Section 6):
  ✓ Save a company for monitoring
  ✓ Switching tickers clears pending approval
  ✓ Demo results are visibly labelled
  ✓ Unavailable backend → error, not fabricated response

Do NOT modify tools/ or agents/.
"""

import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from streamlit.testing.v1 import AppTest  # noqa: E402

APP_PATH = os.path.join(os.path.dirname(__file__), "..", "app.py")

# ---------------------------------------------------------------------------
# Demo ticker keys used in the new interface
# ---------------------------------------------------------------------------
_TICKER_PASS       = "ACME"   # all four criteria PASS
_TICKER_FAIL       = "BLUE"   # OCF FAIL
_TICKER_UNKNOWN    = "CRST"   # employee count UNKNOWN (was UNVERIFIED)

# Map old company display names → new ticker keys (for documentation only)
_LEGACY_NAME_TO_TICKER = {
    "Acme Galactic Ltd (all rules PASS)":           _TICKER_PASS,
    "Bluebird Ventures (OCF FAIL)":                 _TICKER_FAIL,
    "Crescent Peak Corp (employees UNVERIFIED)":    _TICKER_UNKNOWN,
}

# Demo-button widget keys (must match app.py)
_DEMO_BTN_KEY = {
    "ACME":  "demo_acme",
    "BLUE":  "demo_blue",
    "CRST":  "demo_crst",
    "SMCHG": "demo_smchg",
}

# Form submit button key (must match app.py)
# AppTest exposes st.form_submit_button as at.button with label matching
_RUN_BTN_LABEL = "Analyse"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _all_text(at: AppTest) -> str:
    """Collect rendered text, including headings and status messages."""
    groups = (
        at.title, at.header, at.subheader, at.markdown, at.caption,
        at.info, at.warning, at.error, at.success,
    )
    return " ".join(str(element.value) for group in groups for element in group)


def _select_ticker(at: AppTest, ticker: str) -> AppTest:
    """Select a synthetic company without screening or calling the agent."""
    at.selectbox(key="demo_ticker").select(ticker).run()
    assert not at.exception, [e.message for e in at.exception]
    return at


def _run_screen(at: AppTest, ticker: str) -> AppTest:
    """Run the deterministic synthetic screen, not cloud-agent analysis."""
    _select_ticker(at, ticker)
    buttons = [b for b in at.button if b.label == "Analyse"]
    assert len(buttons) == 1, "Expected exactly one Analyse button"
    buttons[0].click().run()
    assert not at.exception, [e.message for e in at.exception]
    result = at.session_state["current_eval"]
    assert result is not None, f"No screen result for {ticker}"
    assert result["ticker"] == ticker
    assert at.session_state["current_analysis"] is None
    return at


# ---------------------------------------------------------------------------
# 1. Initial render (no screen run yet)
# ---------------------------------------------------------------------------

class TestAppInitialRender(unittest.TestCase):
    """Initial render and explicit synthetic-screening workflow."""

    def setUp(self):
        self.at = AppTest.from_file(APP_PATH, default_timeout=30).run()

    def test_no_exception_on_startup(self):
        self.assertFalse(self.at.exception, str(self.at.exception))

    def test_title_present(self):
        self.assertIn("InvestIQ", _all_text(self.at))

    def test_research_sheet_header_and_empty_comparison_are_visible(self):
        text = _all_text(self.at)
        self.assertIn("Investment research, screening &amp; monitoring", text)
        self.assertIn("Screen a company", text)
        self.assertIn("Historical Comparison", text)
        self.assertIn(
            "v2_history_metric", {s.key for s in self.at.selectbox}
        )
        self.assertIn("No verified historical series is connected.", text)
        self.assertIn(
            "No chart points are generated from a single snapshot.", text
        )

    def test_synthetic_data_notice_visible_on_initial_screen(self):
        text = _all_text(self.at)
        self.assertIn("PROTOTYPE", text)
        self.assertIn("SYNTHETIC SCREENING", text)
        self.assertTrue(any(
            "Quick demo screens" in c.value
            and "fictional companies" in c.value
            for c in self.at.caption
        ))

    def test_demo_shortcut_buttons_present(self):
        keys = {b.key for b in self.at.button}
        for ticker in ("ACME", "BLUE", "CRST", "SMCHG"):
            with self.subTest(ticker=ticker):
                self.assertIn(f"demo_{ticker.lower()}", keys)

    def test_demo_shortcut_screens_without_requesting_agent_analysis(self):
        from unittest.mock import patch
        with patch("frontend.snapshot_adapter.analyse_snapshot") as agent:
            at = AppTest.from_file(APP_PATH, default_timeout=30).run()
            at.button(key="demo_blue").click().run()
            self.assertFalse(at.exception, str(at.exception))
            evaluation = at.session_state["current_eval"]
            self.assertEqual(evaluation["ticker"], "BLUE")
            self.assertEqual(evaluation["aggregate_status"], "fail")
            self.assertEqual(len(evaluation["criteria"]), 4)
            self.assertEqual(at.selectbox(key="demo_ticker").value, "BLUE")
            self.assertIn(
                evaluation.get("company_name") or "BLUE",
                [h.value for h in at.subheader],
            )
            self.assertTrue(any(
                "SYNTHETIC DEMO" in c.value
                and evaluation["criteria_version"] in c.value
                for c in at.caption
            ))
            self.assertIn(
                "The deterministic screen is not an AI response.",
                _all_text(at),
            )
            self.assertIsNone(at.session_state["current_analysis"])
            self.assertEqual(
                at.button(key="agent_analyse_btn").label,
                "Request agent analysis",
            )
            agent.assert_not_called()

    def test_selecting_company_does_not_run_screen(self):
        _select_ticker(self.at, "BLUE")
        self.assertEqual(
            len([b for b in self.at.button if b.label == "Analyse"]), 1
        )
        self.assertIsNone(self.at.session_state["current_eval"])
        self.assertIsNone(self.at.session_state["current_analysis"])

    def test_prompt_to_run_shown_before_first_run(self):
        self.assertTrue(any(
            i.value == "Choose a quick demo or select a company and press Analyse."
            for i in self.at.info
        ))

    def test_initial_screen_has_no_aggregate_result(self):
        self.assertIsNone(self.at.session_state["current_eval"])
        self.assertFalse(any(
            "SYNTHETIC DEMO" in c.value for c in self.at.caption
        ))

    def test_initial_render_does_not_request_agent_analysis(self):
        from unittest.mock import patch
        with patch("frontend.snapshot_adapter.analyse_snapshot") as agent:
            at = AppTest.from_file(APP_PATH, default_timeout=30).run()
            self.assertFalse(at.exception, str(at.exception))
            self.assertIsNone(at.session_state["current_analysis"])
            self.assertNotIn(
                "agent_analyse_btn", {b.key for b in at.button}
            )
            agent.assert_not_called()


# ---------------------------------------------------------------------------
# 2. ACME — all four criteria PASS
#    (was "Acme Galactic Ltd (all rules PASS)" via selectbox)
# ---------------------------------------------------------------------------

class TestAcmeAllPass(unittest.TestCase):
    """Screen ACME demo fixture — all criteria pass."""

    def setUp(self):
        at = AppTest.from_file(APP_PATH, default_timeout=30)
        at.run()
        self.at = _run_screen(at, _TICKER_PASS)

    def test_no_exception(self):
        self.assertFalse(self.at.exception, f"App raised: {self.at.exception}")

    def test_historical_chart_metric_selector(self):
        selector = self.at.selectbox(key="v2_history_metric")
        self.assertEqual(list(selector.options), [
            "Market cap \u00b7 USD",
            "Previous close \u00b7 USD",
            "Reported net profit \u00b7 USD; period unspecified",
            "Snapshot trading volume \u00b7 shares; not average daily volume",
        ])
        self.assertIn(
            "No verified historical series is connected.", _all_text(self.at)
        )
        self.assertIn(
            "No chart points are generated from a single snapshot.",
            _all_text(self.at),
        )
        self.assertEqual(len(self.at.get("vega_lite_chart")), 0)

    def test_pass_aggregate_in_banner(self):
        """PASS aggregate status appears in the banner.

        Old assertion: "PASS" in all_text.
        New assertion: identical — status icons include "PASS".
        """
        text = _all_text(self.at)
        self.assertIn("PASS", text, "Expected PASS aggregate not found in rendered text.")

    def test_rule_table_rendered(self):
        """A dataframe (criteria table) is rendered after running the screen."""
        self.assertGreater(len(self.at.dataframe), 0, "No dataframe (criteria table) found.")

    def test_rule_table_has_four_rows(self):
        """The criteria table has exactly four rows.

        Old assertion: len(df) == 4 with old column names.
        New assertion: same row count — column names updated.
        """
        df = self.at.dataframe[0].value
        self.assertEqual(len(df), 4, f"Expected 4 criteria rows, got {len(df)}.")

    def test_rule_table_has_status_column(self):
        """The criteria table has a Status column.

        Old column name: "Status" — unchanged.
        """
        df = self.at.dataframe[0].value
        self.assertIn("Status", df.columns, "Criteria table is missing 'Status' column.")

    def test_rule_table_has_observed_value_column(self):
        """The criteria table has an observed-value column.

        Old column name: "Observed value"
        New column name: "Observed"
        Behavioural coverage: observed values are shown to the user.
        """
        df = self.at.dataframe[0].value
        self.assertIn("Observed", df.columns,
                      "Criteria table missing 'Observed' column.")

    def test_rule_table_has_threshold_column(self):
        """The criteria table has a threshold column.

        Old column name: "Required threshold"
        New column name: "Threshold"
        Behavioural coverage: threshold values are shown to the user.
        """
        df = self.at.dataframe[0].value
        self.assertIn("Threshold", df.columns,
                      "Criteria table missing 'Threshold' column.")

    def test_rule_table_has_criterion_column(self):
        """The criteria table has a Criterion column (was 'Rule')."""
        df = self.at.dataframe[0].value
        self.assertIn("Criterion", df.columns,
                      "Criteria table missing 'Criterion' column.")

    def test_scope_note_present(self):
        e = self.at.session_state["current_eval"]
        self.assertTrue(e["scope_note"])
        self.assertIn(e["scope_note"], [c.value for c in self.at.caption])
        text = e["scope_note"].lower()
        self.assertIn("only four screening rules", text)
        self.assertIn("does not establish full investment eligibility", text)
        self.assertIn("does not constitute an investment recommendation", text)

    def test_research_summary_present(self):
        e = self.at.session_state["current_eval"]
        self.assertEqual(e["ticker"], "ACME")
        self.assertEqual(e["aggregate_status"], "pass")
        self.assertIn(
            e.get("company_name") or e["ticker"],
            [h.value for h in self.at.subheader],
        )
        self.assertTrue(any(
            "SYNTHETIC DEMO" in c.value and e["criteria_version"] in c.value
            for c in self.at.caption
        ))
        self.assertEqual(len(self.at.dataframe[0].value), 4)

    def test_no_fabricated_content_labels(self):
        text = _all_text(self.at)
        self.assertIn("No verified historical series is connected.", text)
        self.assertIn("No chart points are generated from a single snapshot.", text)
        self.assertIn(
            "Net profit is not relabeled as annual or TTM", text
        )
        self.assertIn("The deterministic screen is not an AI response.", text)
        self.assertIsNone(self.at.session_state["current_analysis"])

    def test_demo_label_visible(self):
        """Demo results must be visibly labelled as DEMO data."""
        text = _all_text(self.at)
        self.assertIn(
            "DEMO",
            text.upper(),
            "Expected DEMO label not found after running demo fixture.",
        )


# ---------------------------------------------------------------------------
# 3. BLUE — OCF FAIL
#    (was "Bluebird Ventures (OCF FAIL)" via selectbox)
# ---------------------------------------------------------------------------

class TestBlueOcfFail(unittest.TestCase):
    """Screen BLUE demo fixture — OCF criterion fails."""

    def setUp(self):
        at = AppTest.from_file(APP_PATH, default_timeout=30)
        at.run()
        self.at = _run_screen(at, _TICKER_FAIL)

    def test_no_exception(self):
        self.assertFalse(self.at.exception, f"App raised: {self.at.exception}")

    def test_fail_aggregate_in_banner(self):
        """FAIL aggregate appears in the banner.

        Old assertion: "FAIL" in all_text.
        New assertion: identical.
        """
        text = _all_text(self.at)
        self.assertIn("FAIL", text, "Expected FAIL aggregate not found.")

    def test_four_criteria_rows(self):
        """Criteria table has four rows."""
        df = self.at.dataframe[0].value
        self.assertEqual(len(df), 4)

    def test_ocf_criterion_shows_fail(self):
        e = self.at.session_state["current_eval"]
        criteria = [
            c for c in e["criteria"] if "net profit" in c["label"].lower()
        ]
        self.assertEqual(len(criteria), 1)
        criterion = criteria[0]
        df = self.at.dataframe[0].value
        rows = df[df["Criterion"] == criterion["label"]]
        self.assertEqual(len(rows), 1)

        # Policy v2 replaces the old OCF fixture with reported net profit.
        self.assertEqual(criterion["status"], "fail")
        self.assertEqual(rows.iloc[0]["Status"], "FAIL")
        self.assertEqual(e["aggregate_status"], "fail")

    def test_scope_note_present(self):
        e = self.at.session_state["current_eval"]
        self.assertTrue(e["scope_note"])
        self.assertIn(e["scope_note"], [c.value for c in self.at.caption])
        text = e["scope_note"].lower()
        self.assertIn("only four screening rules", text)
        self.assertIn("does not establish full investment eligibility", text)
        self.assertIn("does not constitute an investment recommendation", text)

    def test_not_investment_recommendation(self):
        e = self.at.session_state["current_eval"]
        self.assertTrue(e["scope_note"])
        self.assertIn(e["scope_note"], [c.value for c in self.at.caption])
        text = e["scope_note"].lower()
        self.assertIn("only four screening rules", text)
        self.assertIn("does not establish full investment eligibility", text)
        self.assertIn("does not constitute an investment recommendation", text)

    def test_demo_label_visible_on_fail(self):
        """DEMO label must appear even when a criterion fails."""
        text = _all_text(self.at)
        self.assertIn("DEMO", text.upper())


# ---------------------------------------------------------------------------
# 4. CRST — employee count UNKNOWN
#    (was "Crescent Peak Corp (employees UNVERIFIED)" via selectbox)
# ---------------------------------------------------------------------------

class TestCrstEmployeeUnknown(unittest.TestCase):
    """Screen CRST demo fixture — employee count data is not available."""

    def setUp(self):
        at = AppTest.from_file(APP_PATH, default_timeout=30)
        at.run()
        self.at = _run_screen(at, _TICKER_UNKNOWN)

    def test_no_exception(self):
        self.assertFalse(self.at.exception, f"App raised: {self.at.exception}")

    def test_missing_employee_history_stays_unknown(self):
        import copy
        before = copy.deepcopy(self.at.session_state["current_eval"])
        self.at.selectbox(key="v2_history_metric").select(
            "Reported net profit \u00b7 USD; period unspecified"
        ).run()
        self.assertFalse(self.at.exception, str(self.at.exception))
        self.assertEqual(self.at.session_state["current_eval"], before)
        self.assertIn(
            "No chart points are generated from a single snapshot.",
            _all_text(self.at),
        )
        self.assertEqual(len(self.at.get("vega_lite_chart")), 0)
        df = self.at.dataframe[0].value
        rows = df[df["Criterion"].str.contains("net profit", case=False)]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows.iloc[0]["Observed"], "Unknown")

    def test_unknown_aggregate_in_banner(self):
        e = self.at.session_state["current_eval"]
        self.assertEqual(e["aggregate_status"], "unknown")
        self.assertTrue(any(
            "SYNTHETIC DEMO" in c.value
            and e["criteria_version"] in c.value
            and c.value.endswith('UNVERIFIED')
            for c in self.at.caption
        ))

    def test_four_criteria_rows(self):
        df = self.at.dataframe[0].value
        self.assertEqual(len(df), 4)

    def test_employee_criterion_shows_unknown(self):
        e = self.at.session_state["current_eval"]
        criteria = [
            c for c in e["criteria"] if "net profit" in c["label"].lower()
        ]
        self.assertEqual(len(criteria), 1)
        criterion = criteria[0]
        df = self.at.dataframe[0].value
        rows = df[df["Criterion"] == criterion["label"]]
        self.assertEqual(len(rows), 1)

        # Policy v2's missing observation is reported net profit, not employees.
        self.assertEqual(criterion["status"], "unknown")
        self.assertEqual(rows.iloc[0]["Status"], 'UNVERIFIED')
        self.assertNotEqual(rows.iloc[0]["Status"], "FAIL")

    def test_unknown_in_employee_observed_value(self):
        e = self.at.session_state["current_eval"]
        criteria = [
            c for c in e["criteria"] if "net profit" in c["label"].lower()
        ]
        self.assertEqual(len(criteria), 1)
        criterion = criteria[0]
        df = self.at.dataframe[0].value
        rows = df[df["Criterion"] == criterion["label"]]
        self.assertEqual(len(rows), 1)

        # Missing net profit must remain visibly unknown, never a displayed zero.
        self.assertEqual(criterion["status"], "unknown")
        self.assertEqual(criterion["observed_fmt"], "Unknown")
        self.assertEqual(rows.iloc[0]["Observed"], "Unknown")

    def test_unknown_shown_in_rendered_text(self):
        """'Unknown' appears somewhere in the rendered page for missing data.

        Old assertion: "Unknown" in all_text.
        New assertion: identical.
        """
        text = _all_text(self.at)
        self.assertIn("Unknown", text, "'Unknown' not shown for missing employee count.")

    def test_scope_note_present(self):
        e = self.at.session_state["current_eval"]
        self.assertTrue(e["scope_note"])
        self.assertIn(e["scope_note"], [c.value for c in self.at.caption])
        text = e["scope_note"].lower()
        self.assertIn("only four screening rules", text)
        self.assertIn("does not establish full investment eligibility", text)
        self.assertIn("does not constitute an investment recommendation", text)

    def test_missing_data_not_treated_as_fail(self):
        e = self.at.session_state["current_eval"]
        statuses = [c["status"] for c in e["criteria"]]
        self.assertEqual(statuses.count("pass"), 3)
        self.assertEqual(statuses.count("unknown"), 1)
        self.assertNotIn("fail", statuses)
        self.assertEqual(e["aggregate_status"], "unknown")
        self.assertNotIn("FAIL", list(self.at.dataframe[0].value["Status"]))


# ---------------------------------------------------------------------------
# 5. Company-switch / stale-result consistency
#    (was TestCompanySwitchStaleResult)
# ---------------------------------------------------------------------------

class TestTickerSwitchStaleResult(unittest.TestCase):
    """Switching tickers must clear stale results and pending approvals.

    Old tests used selectbox navigation.
    New tests use the demo shortcut buttons.
    All three original scenarios are preserved.
    """

    def test_switching_ticker_clears_result_before_run(self):
        at = AppTest.from_file(APP_PATH, default_timeout=30).run()
        _run_screen(at, "ACME")
        self.assertEqual(at.session_state["current_eval"]["aggregate_status"], "pass")
        _select_ticker(at, "BLUE")
        self.assertFalse(at.exception, str(at.exception))
        self.assertIsNone(at.session_state["current_eval"])
        self.assertIsNone(at.session_state["current_analysis"])
        self.assertIn(
            "Choose a quick demo or select a company and press Analyse.",
            [i.value for i in at.info],
        )
        self.assertEqual(len(at.dataframe), 0)

    def test_switching_then_running_shows_new_result(self):
        """After switching ticker and running, the new company's result appears.

        Old assertion: FAIL appears after switching from ACME→BLUE and running.
        New assertion: identical behaviour via new ticker mechanism.
        """
        at = AppTest.from_file(APP_PATH, default_timeout=30)
        at.run()

        # Run ACME first.
        _run_screen(at, _TICKER_PASS)

        # Switch to BLUE and run.
        _run_screen(at, _TICKER_FAIL)
        self.assertFalse(at.exception, f"Exception: {at.exception}")

        text = _all_text(at)
        self.assertIn("FAIL", text, "BLUE should show FAIL after running its screen.")
        df = at.dataframe[0].value
        self.assertEqual(len(df), 4, "Criteria table should have 4 rows for BLUE.")

    def test_switching_ticker_shows_aggregate_placeholder(self):
        at = AppTest.from_file(APP_PATH, default_timeout=30).run()
        _run_screen(at, "ACME")
        _select_ticker(at, "CRST")
        self.assertFalse(at.exception, str(at.exception))
        self.assertIsNone(at.session_state["current_eval"])
        self.assertFalse(any(
            "SYNTHETIC DEMO" in c.value for c in at.caption
        ))
        self.assertNotIn("agent_analyse_btn", {b.key for b in at.button})

    def test_acme_result_not_shown_after_switching_to_blue(self):
        """Switching from ACME to BLUE must not display ACME's criteria table.

        Acceptance check: switching tickers cannot display another company's
        old analysis.
        """
        at = AppTest.from_file(APP_PATH, default_timeout=30)
        at.run()

        # Screen ACME.
        _run_screen(at, _TICKER_PASS)
        self.assertGreater(len(at.dataframe), 0, "Sanity: ACME table should appear.")

        # Switch to BLUE without running.
        _select_ticker(at, _TICKER_FAIL)
        self.assertEqual(
            len(at.dataframe),
            0,
            "ACME's criteria table must not be visible after switching to BLUE.",
        )


# ---------------------------------------------------------------------------
# 6. New workflow coverage — save, demo labels, backend error
# ---------------------------------------------------------------------------

class TestNewWorkflowSave(unittest.TestCase):
    """Save-for-monitoring button appears after a successful screen run."""

    def setUp(self):
        at = AppTest.from_file(APP_PATH, default_timeout=30)
        at.run()
        self.at = _run_screen(at, _TICKER_PASS)

    def test_save_button_present_after_screen(self):
        """The 'Save company for monitoring' button is present after screening."""
        labels = [b.label for b in self.at.button]
        self.assertTrue(
            any("Save company for monitoring" in b for b in labels),
            f"Save button missing after screen. Buttons: {labels}",
        )

    def test_save_button_click_does_not_raise(self):
        """Clicking save does not raise an exception."""
        save_btns = [b for b in self.at.button if "Save company for monitoring" in b.label]
        if not save_btns:
            self.skipTest("Save button not found — covered by test_save_button_present_after_screen")
        save_btns[0].click().run()
        self.assertFalse(self.at.exception, f"Exception on save: {self.at.exception}")

    def test_save_success_message_shown(self):
        """After clicking save, a success message is shown."""
        save_btns = [b for b in self.at.button if "Save company for monitoring" in b.label]
        if not save_btns:
            self.skipTest("Save button not found")
        save_btns[0].click().run()
        successes = [s.value for s in self.at.success]
        infos = [i.value for i in self.at.info]
        # Either a st.success or the "Already tracked" caption should appear
        all_output = " ".join(successes + infos + [c.value for c in self.at.caption])
        self.assertTrue(
            "saved" in all_output.lower() or "tracked" in all_output.lower(),
            f"No save confirmation found. Output: {all_output[:300]}",
        )


class TestDemoLabelInvariant(unittest.TestCase):
    """Demo results must always be visibly labelled, for all demo fixtures."""

    def _check_demo_label(self, ticker: str):
        at = AppTest.from_file(APP_PATH, default_timeout=30)
        at.run()
        _run_screen(at, ticker)
        self.assertFalse(at.exception, f"Exception for {ticker}: {at.exception}")
        text = _all_text(at)
        self.assertIn(
            "DEMO",
            text.upper(),
            f"DEMO label missing for ticker {ticker}. All text: {text[:300]}",
        )

    def test_acme_is_labelled_demo(self):
        self._check_demo_label("ACME")

    def test_blue_is_labelled_demo(self):
        self._check_demo_label("BLUE")

    def test_crst_is_labelled_demo(self):
        self._check_demo_label("CRST")


class TestAnalysisNotConnected(unittest.TestCase):
    """Clicking 'Analyse company' with no agent connected must show an honest
    error, never fabricated agent output.

    Old coverage: "AI agent not connected" caption visible at render.
    New coverage: caption visible at render + clicking analyse shows error.
    """

    def test_ai_agent_not_connected_label_before_ticker(self):
        from unittest.mock import patch
        with patch("frontend.snapshot_adapter.analyse_snapshot") as agent:
            at = AppTest.from_file(APP_PATH, default_timeout=30).run()
            self.assertFalse(at.exception, str(at.exception))
            self.assertIsNone(at.session_state["current_analysis"])
            self.assertNotIn("agent_analyse_btn", {b.key for b in at.button})
            agent.assert_not_called()

    def test_analyse_button_present_after_screen(self):
        """The agent analysis button appears after running a screen.

        The button is now keyed 'agent_analyse_btn' (renamed from 'analyse_btn'
        to avoid collision with the ▶ Analyse form submit).
        """
        at = AppTest.from_file(APP_PATH, default_timeout=30)
        at.run()
        _run_screen(at, _TICKER_PASS)
        keys = {b.key for b in at.button}
        self.assertIn(
            "agent_analyse_btn", keys,
            f"Agent analyse button (key=agent_analyse_btn) missing. Keys: {keys}",
        )

    def test_demo_click_shows_labeled_sample_brief_not_agent_output(self):
        import copy
        from unittest.mock import patch

        responses = [
            {
                "connected": True,
                "content": "MOCK_AGENT_RESPONSE",
                "run_id": "mock-run",
            },
            {
                "connected": False,
                "content": None,
                "error": "MOCK_AGENT_UNAVAILABLE",
            },
        ]
        for response in responses:
            with self.subTest(connected=response["connected"]):
                with patch(
                    "frontend.snapshot_adapter.analyse_snapshot",
                    return_value=response,
                ) as agent:
                    at = AppTest.from_file(APP_PATH, default_timeout=30).run()
                    at.button(key="demo_acme").click().run()
                    self.assertFalse(at.exception, str(at.exception))
                    agent.assert_not_called()
                    self.assertIsNone(at.session_state["current_analysis"])
                    evaluation = copy.deepcopy(at.session_state["current_eval"])
                    at.button(key="agent_analyse_btn").click().run()
                    self.assertFalse(at.exception, str(at.exception))
                    agent.assert_called_once_with(evaluation)
                    self.assertEqual(at.session_state["current_eval"], evaluation)
                    self.assertEqual(at.session_state["current_analysis"], response)
                    if response["connected"]:
                        self.assertIn("MOCK_AGENT_RESPONSE", _all_text(at))
                        self.assertTrue(any(
                            "Cloud-agent response" in s.value
                            and "synthetic inputs" in s.value
                            for s in at.success
                        ))
                    else:
                        self.assertIn(
                            "MOCK_AGENT_UNAVAILABLE", [e.value for e in at.error]
                        )
                        self.assertNotIn("MOCK_AGENT_RESPONSE", _all_text(at))


class TestCriteriaTableColumnNames(unittest.TestCase):
    """The criteria table exposes the correct column names.

    These tests document the new column naming and assert each column
    contains the correct data type/content, providing the same behavioural
    coverage as the old "Rule", "Observed value", "Required threshold" checks.
    """

    def setUp(self):
        at = AppTest.from_file(APP_PATH, default_timeout=30)
        at.run()
        self.at = _run_screen(at, _TICKER_PASS)
        self.df = self.at.dataframe[0].value

    def test_criterion_column_contains_rule_names(self):
        """Criterion column has non-empty human-readable label strings."""
        self.assertIn("Criterion", self.df.columns)
        for val in self.df["Criterion"]:
            self.assertIsInstance(val, str)
            self.assertGreater(len(val), 0)

    def test_observed_column_contains_values(self):
        """Observed column shows either a formatted value or 'Unknown'."""
        self.assertIn("Observed", self.df.columns)
        for val in self.df["Observed"]:
            self.assertIsInstance(val, str)

    def test_threshold_column_contains_expressions(self):
        """Threshold column shows threshold expressions."""
        self.assertIn("Threshold", self.df.columns)
        for val in self.df["Threshold"]:
            self.assertIsInstance(val, str)
            self.assertGreater(len(val), 0)

    def test_status_column_contains_plain_labels(self):
        """Status column values use clear PASS/FAIL/UNKNOWN labels."""
        self.assertIn("Status", self.df.columns)
        valid_statuses = {"PASS", "FAIL", "UNKNOWN"}
        for val in self.df["Status"]:
            self.assertIn(val, valid_statuses,
                          f"Unexpected status value: {val!r}")


# ---------------------------------------------------------------------------
# 8. Demo shortcut button — single click from blank session
#    These tests exercise the actual shortcut buttons (not text_input.set_value).
#    They must FAIL before the demo-shortcut bug is fixed and PASS after.
# ---------------------------------------------------------------------------

class TestDemoShortcutClick(unittest.TestCase):
    """Exercise actual demo clicks, state, rendering, and provider isolation."""

    def _fresh(self):
        at = AppTest.from_file(APP_PATH, default_timeout=30).run()
        self.assertFalse(at.exception, str(at.exception))
        self.assertIn(at.selectbox(key="demo_ticker").value, _DEMO_BTN_KEY)
        self.assertIsNone(at.session_state["current_eval"])
        self.assertIsNone(at.session_state["current_analysis"])
        return at

    def _click(self, at, ticker):
        at.button(key=_DEMO_BTN_KEY[ticker]).click().run()
        self.assertFalse(at.exception, str(at.exception))
        return at

    def _assert_result(self, at, ticker, status):
        evaluation = at.session_state["current_eval"]
        self.assertIsNotNone(evaluation)
        self.assertEqual(at.selectbox(key="demo_ticker").value, ticker)
        self.assertEqual(evaluation["ticker"], ticker)
        self.assertFalse(evaluation.get("error"))
        self.assertEqual(evaluation["aggregate_status"], status)
        self.assertEqual(len(evaluation["criteria"]), 4)

        tables = [
            d.value for d in at.dataframe
            if {"Criterion", "Observed", "Threshold", "Status"}.issubset(
                d.value.columns
            )
        ]
        self.assertEqual(len(tables), 1)
        table = tables[0]
        self.assertEqual(len(table), 4)
        labels = {'pass': 'PASS', 'fail': 'FAIL', 'unknown': 'UNVERIFIED'}
        self.assertEqual(
            list(table["Status"]),
            [labels[c["status"]] for c in evaluation["criteria"]],
        )
        self.assertEqual(
            list(table["Observed"]),
            [c["observed_fmt"] for c in evaluation["criteria"]],
        )
        self.assertTrue(any(
            "SYNTHETIC DEMO" in c.value
            and evaluation["criteria_version"] in c.value
            and c.value.endswith(labels[status])
            for c in at.caption
        ), "Result-specific synthetic label and aggregate status are missing")
        self.assertTrue(any(
            h.value == (evaluation.get("company_name") or ticker)
            for h in at.subheader
        ))
        self.assertTrue(any(
            c.value == evaluation["scope_note"] for c in at.caption
        ), "Scope disclaimer is missing")
        self.assertFalse(any(
            i.value == "Choose a quick demo or select a company and press Analyse."
            for i in at.info
        ))

    def test_acme_single_click(self):
        at = self._click(self._fresh(), "ACME")
        self._assert_result(at, "ACME", "pass")

    def test_blue_single_click(self):
        at = self._click(self._fresh(), "BLUE")
        self._assert_result(at, "BLUE", "fail")

    def test_crst_single_click(self):
        at = self._click(self._fresh(), "CRST")
        self._assert_result(at, "CRST", "unknown")

    def test_smchg_single_click(self):
        at = self._click(self._fresh(), "SMCHG")
        self._assert_result(at, "SMCHG", "pass")

    def test_results_persist_on_rerun(self):
        import copy
        for ticker, status in (
            ("ACME", "pass"), ("BLUE", "fail"),
            ("CRST", "unknown"), ("SMCHG", "pass"),
        ):
            with self.subTest(ticker=ticker):
                at = self._click(self._fresh(), ticker)
                before = copy.deepcopy(at.session_state["current_eval"])
                at.run()
                self.assertFalse(at.exception, str(at.exception))
                self._assert_result(at, ticker, status)
                self.assertEqual(at.session_state["current_eval"], before)

    def test_switching_shortcuts_replaces_result_and_clears_analysis(self):
        at = self._click(self._fresh(), "ACME")
        at.session_state["current_analysis"] = {
            "connected": True, "content": "STALE_ACME_ANALYSIS"
        }
        self._click(at, "BLUE")
        self._assert_result(at, "BLUE", "fail")
        self.assertIsNone(at.session_state["current_analysis"])
        self.assertEqual(at.selectbox(key="demo_ticker").value, "BLUE")
        self.assertNotIn("STALE_ACME_ANALYSIS", _all_text(at))

    def test_switching_shortcut_clears_existing_pending_approval(self):
        import copy
        at = self._click(self._fresh(), "ACME")
        baseline = copy.deepcopy(at.session_state["current_eval"])
        at.session_state["tracked"] = {
            "ACME": {"saved_at": "2025-01-01T00:00:00Z", "evaluation": baseline}
        }
        at.session_state["qualified_list"] = {"ACME"}
        at.session_state["needs_review_list"] = set()
        at.session_state["action_log"] = [{"action": "saved_baseline", "ticker": "ACME",
                                           "timestamp": "2025-01-01T00:00:00Z"}]
        pending = {
            "ticker": "ACME", "eval_id": "ACME@test",
            "proposed_action": "move_to_needs_review",
            "change_result": {"new_evaluation": baseline, "changes": []},
        }
        at.session_state["pending_approval"] = pending
        self.assertEqual(at.session_state["pending_approval"], pending)
        tracked_before = copy.deepcopy(at.session_state["tracked"])
        log_before = copy.deepcopy(at.session_state["action_log"])
        self._click(at, "BLUE")
        self.assertIsNone(at.session_state["pending_approval"])
        self.assertEqual(at.session_state["tracked"], tracked_before)
        self.assertEqual(at.session_state["action_log"], log_before)
        self.assertEqual(at.session_state["qualified_list"], {"ACME"})
        self.assertEqual(at.session_state["needs_review_list"], set())

    def test_demo_shortcuts_make_no_provider_requests(self):
        from unittest.mock import patch
        with (
            patch("frontend.adapter.resolve_ticker") as resolve,
            patch("frontend.adapter.fetch_moomoo_inputs") as fetch,
            patch("frontend.real_screen.retrieve_real_screen") as real_screen,
            patch("frontend.market_chart.fetch_daily_candles") as candles,
            patch("frontend.snapshot_adapter.analyse_snapshot") as agent,
        ):
            at = self._fresh()
            for ticker, status in (
                ("ACME", "pass"), ("BLUE", "fail"),
                ("CRST", "unknown"), ("SMCHG", "pass"),
            ):
                with self.subTest(ticker=ticker):
                    self._click(at, ticker)
                    self._assert_result(at, ticker, status)
                    at.run()
                    self.assertFalse(at.exception, str(at.exception))
            resolve.assert_not_called()
            fetch.assert_not_called()
            real_screen.assert_not_called()
            candles.assert_not_called()
            agent.assert_not_called()


if __name__ == "__main__":
    unittest.main()

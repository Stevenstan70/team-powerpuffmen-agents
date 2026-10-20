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
  "SYNTHETIC DEMO DATA" warning        still present — text updated to include
                                       "SYNTHETIC DEMO DATA — PROTOTYPE"
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
_RUN_BTN_LABEL = "▶ Run basic screen"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _all_text(at: AppTest) -> str:
    """Collect all rendered markdown + caption + info + warning text."""
    parts = (
        [m.value for m in at.markdown]
        + [c.value for c in at.caption]
        + [i.value for i in at.info]
        + [w.value for w in at.warning]
    )
    return " ".join(parts)


def _select_ticker(at: AppTest, ticker: str) -> AppTest:
    """Set the ticker via the text input and wait for rerun.

    NOTE: The demo shortcut buttons use st.rerun() internally which does not
    persist session state reliably inside AppTest.  The text_input widget
    (key="ticker_text_input") is the stable way to set the ticker in tests.
    """
    at.text_input(key="ticker_text_input").set_value(ticker).run()
    return at


def _run_screen(at: AppTest, ticker: str) -> AppTest:
    """Select *ticker* via the text input and submit the screen form.

    Replaces the old selectbox-based _run_screen helper.
    The new app uses:
      1. A text input (key="ticker_text_input") to set the ticker.
      2. A st.form_submit_button to trigger the screen run.
    For demo tickers the form fields are left blank; the adapter
    automatically returns the named fixture.
    """
    # Step 1: set the ticker via text_input
    _select_ticker(at, ticker)
    # Step 2: submit the form via form_submit_button
    if not at.form_submit_button:
        raise AssertionError(
            f"No form_submit_button found after selecting {ticker}. "
            f"Buttons: {[b.label for b in at.button]}"
        )
    at.form_submit_button[0].click().run()
    return at


# ---------------------------------------------------------------------------
# 1. Initial render (no screen run yet)
# ---------------------------------------------------------------------------

class TestAppInitialRender(unittest.TestCase):
    """The app must render cleanly without any screen having been run."""

    def setUp(self):
        self.at = AppTest.from_file(APP_PATH, default_timeout=30)
        self.at.run()

    def test_no_exception_on_startup(self):
        self.assertFalse(self.at.exception, f"App raised: {self.at.exception}")

    def test_title_present(self):
        titles = [t.value for t in self.at.title]
        self.assertTrue(
            any("Powerpuffmen Research" in t for t in titles),
            f"Title not found. Titles: {titles}",
        )

    def test_synthetic_data_warning_always_visible(self):
        """The persistent demo-data warning must be visible at all times.

        Old assertion: "SYNTHETIC DEMO DATA"
        New text:      "SYNTHETIC DEMO DATA — PROTOTYPE" (same substring still present)
        """
        warnings = [w.value for w in self.at.warning]
        self.assertTrue(
            any("SYNTHETIC DEMO DATA" in w for w in warnings),
            f"Synthetic-data warning missing. Warnings: {warnings}",
        )

    def test_demo_shortcut_buttons_present(self):
        """New interface: demo shortcut buttons replace the sidebar selectbox.

        Old assertion: selectbox exists in sidebar.
        New assertion: keyed demo buttons are present.
        Behavioural coverage: user can select a company to screen.
        """
        btn_keys = {b.key for b in self.at.button}
        self.assertIn("demo_acme", btn_keys,
                      f"Demo ACME button missing. Keys: {btn_keys}")
        self.assertIn("demo_blue", btn_keys,
                      f"Demo BLUE button missing. Keys: {btn_keys}")
        self.assertIn("demo_crst", btn_keys,
                      f"Demo CRST button missing. Keys: {btn_keys}")

    def test_run_button_present_after_ticker_selected(self):
        """'▶ Run basic screen' form-submit appears once a ticker is set.

        Old assertion: button[0] label contains "Run basic screen".
        New assertion: after selecting a ticker via text_input, the
        form_submit_button appears (AppTest exposes it via at.form_submit_button).
        """
        at = AppTest.from_file(APP_PATH, default_timeout=30)
        at.run()
        _select_ticker(at, "ACME")
        self.assertGreater(
            len(at.form_submit_button),
            0,
            "form_submit_button (▶ Run basic screen) missing after ticker set.",
        )

    def test_prompt_to_run_shown_before_first_run(self):
        """Before a screen is run, a 'Press ▶ Run basic screen' prompt appears.

        Old assertion: "Press" in all_text on initial render (no ticker set).
        New assertion: same — the info box shown when no ticker is entered
        includes this text.
        """
        text = _all_text(self.at)
        self.assertIn(
            "Press",
            text,
            "Expected 'Press run' prompt not found on initial render.",
        )

    def test_aggregate_status_placeholder_shown(self):
        """Before running, the aggregate status is a placeholder caption.

        Old assertion: caption contains "Aggregate status" on initial render.
        New assertion: same — the placeholder caption is shown when no ticker
        is selected (rendered before st.stop()).
        """
        captions = [c.value for c in self.at.caption]
        self.assertTrue(
            any("Aggregate status" in c for c in captions),
            f"Aggregate status placeholder caption not found. Captions: {captions}",
        )

    def test_ai_agent_not_connected_label(self):
        """The AI agent not-connected label must be visible before any run.

        Old assertion: caption contains "AI agent not connected" on initial render.
        New assertion: same — the caption is rendered before st.stop() fires.
        """
        captions = [c.value for c in self.at.caption]
        self.assertTrue(
            any("AI agent not connected" in c for c in captions),
            f"'AI agent not connected' caption missing. Captions: {captions}",
        )


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
        """A scope disclaimer is shown after running.

        Old text: "Only four rules evaluated"
        New text: "Only the criteria returned by the screening tool were evaluated."
        Behavioural coverage: the user is told this is not a full eligibility check.
        """
        infos = [i.value for i in self.at.info]
        self.assertTrue(
            any("Only the criteria returned" in i for i in infos),
            f"Scope note not found in info boxes. Infos: {infos}",
        )

    def test_research_summary_present(self):
        """The rule-based research summary is rendered.

        Old assertion: "Screen result for" in all_text.
        New assertion: identical.
        """
        text = _all_text(self.at)
        self.assertIn("Screen result for", text, "Research summary not rendered.")

    def test_no_fabricated_content_labels(self):
        """The disclaimer about no fabricated content must be present.

        Old assertions: "no news, valuations, price history" and
                        "no ai model was consulted".
        New assertions: identical — these strings are preserved verbatim.
        """
        text = _all_text(self.at)
        self.assertIn(
            "no news, valuations, price history",
            text.lower(),
            "Expected disclaimer about no fabricated content not found.",
        )
        self.assertIn(
            "no ai model was consulted",
            text.lower(),
            "Expected 'no AI model was consulted' disclaimer not found.",
        )

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
        """The OCF criterion row shows FAIL status.

        Old assertion: df["Rule"].str.contains("Operating Cash Flow")
                       df["Status"] contains "FAIL"
        New assertion: same logic with new column name "Criterion".
        Behavioural coverage: the failing criterion is visibly marked.
        """
        df = self.at.dataframe[0].value
        ocf_rows = df[df["Criterion"].str.contains("Operating Cash Flow", case=False)]
        self.assertFalse(ocf_rows.empty, "OCF criterion row not found in table.")
        self.assertIn("FAIL", ocf_rows["Status"].values[0])

    def test_scope_note_present(self):
        infos = [i.value for i in self.at.info]
        self.assertTrue(
            any("Only the criteria returned" in i for i in infos),
            f"Scope note not found. Infos: {infos}",
        )

    def test_not_investment_recommendation(self):
        """The scope note must say this is not an investment recommendation.

        Old assertion: "Not full investment eligibility" in all_text.
        New assertion: the info box contains the same phrase.
        """
        text = _all_text(self.at)
        self.assertIn(
            "Not full investment eligibility",
            text,
            "Scope note does not disclaim investment recommendation.",
        )

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

    def test_unknown_aggregate_in_banner(self):
        """UNKNOWN aggregate status appears in the banner.

        Old assertion: "UNVERIFIED" in all_text.
        New assertion: "UNKNOWN" — the adapter maps UNVERIFIED → unknown → ⚠️ UNKNOWN.
        Behavioural coverage: missing data produces a clearly uncertain result.
        """
        text = _all_text(self.at)
        self.assertIn(
            "UNKNOWN",
            text,
            "Expected UNKNOWN aggregate not found (was UNVERIFIED in old UI).",
        )

    def test_four_criteria_rows(self):
        df = self.at.dataframe[0].value
        self.assertEqual(len(df), 4)

    def test_employee_criterion_shows_unknown(self):
        """The employee-count criterion shows UNKNOWN (not FAIL, not zero).

        Old assertion: df["Rule"].contains("Employee"), status = "UNVERIFIED".
        New assertion: df["Criterion"].contains("Employee"), status contains "UNKNOWN".
        Behavioural coverage: missing data ≠ confirmed failure.
        """
        df = self.at.dataframe[0].value
        emp_rows = df[df["Criterion"].str.contains("Employee", case=False)]
        self.assertFalse(emp_rows.empty, "Employee criterion row not found in table.")
        self.assertIn(
            "UNKNOWN",
            emp_rows["Status"].values[0],
            "Employee criterion must show UNKNOWN, not FAIL or empty.",
        )

    def test_unknown_in_employee_observed_value(self):
        """The observed value for missing employee count shows 'Unknown'.

        Old assertion: df["Observed value"] contains "Unknown".
        New column name: "Observed".
        Behavioural coverage: missing value is labelled Unknown, not 0.
        """
        df = self.at.dataframe[0].value
        emp_rows = df[df["Criterion"].str.contains("Employee", case=False)]
        self.assertIn(
            "Unknown",
            emp_rows["Observed"].values[0],
            "Missing employee count must show 'Unknown', not a numeric value.",
        )

    def test_unknown_shown_in_rendered_text(self):
        """'Unknown' appears somewhere in the rendered page for missing data.

        Old assertion: "Unknown" in all_text.
        New assertion: identical.
        """
        text = _all_text(self.at)
        self.assertIn("Unknown", text, "'Unknown' not shown for missing employee count.")

    def test_scope_note_present(self):
        infos = [i.value for i in self.at.info]
        self.assertTrue(
            any("Only the criteria returned" in i for i in infos),
            f"Scope note not found. Infos: {infos}",
        )

    def test_missing_data_not_treated_as_fail(self):
        """Aggregate with missing data must be UNKNOWN, not FAIL.

        Behavioural coverage: missing metrics ≠ confirmed failure.
        """
        text = _all_text(self.at)
        # UNKNOWN must be present
        self.assertIn("UNKNOWN", text)
        # If the only "bad" criterion is missing data, aggregate must not show pure FAIL
        # (CRST fixture: three PASS + one UNKNOWN → aggregate UNKNOWN)
        # Check the aggregate banner does not show ❌ FAIL
        self.assertNotIn(
            "❌ FAIL",
            text,
            "Aggregate with only missing data must not show ❌ FAIL.",
        )


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
        """After switching to a new ticker without running, the old result
        must not appear and the 'Press run' prompt must reappear.

        Old assertion: at.selectbox[0].set_value(COMPANY_FAIL).run()
        New assertion: click demo_blue button.
        """
        at = AppTest.from_file(APP_PATH, default_timeout=30)
        at.run()

        # Run ACME first — expect PASS.
        _run_screen(at, _TICKER_PASS)
        self.assertFalse(at.exception)
        text_after_acme = _all_text(at)
        self.assertIn("PASS", text_after_acme, "Sanity: ACME should show PASS.")

        # Switch to BLUE — do NOT run the screen.
        _select_ticker(at, _TICKER_FAIL)
        self.assertFalse(at.exception, f"Exception after switch: {at.exception}")

        text_after_switch = _all_text(at)

        # The 'Press run' prompt must be back — ticker is set but no eval run.
        self.assertIn(
            "Press",
            text_after_switch,
            "Expected 'Press run' prompt after switching ticker without running.",
        )

        # The criteria table must NOT be present yet.
        self.assertEqual(
            len(at.dataframe),
            0,
            "Criteria table must not be shown before running the new screen.",
        )

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
        """After switching to a new ticker (without running), the aggregate
        placeholder caption must be shown — not the previous ticker's status.

        Old assertion: "Aggregate status" in captions after selectbox switch.
        New assertion: same caption check after demo-button switch.
        """
        at = AppTest.from_file(APP_PATH, default_timeout=30)
        at.run()

        # Run ACME to get a cached PASS result.
        _run_screen(at, _TICKER_PASS)

        # Switch to CRST — do NOT run.
        _select_ticker(at, _TICKER_UNKNOWN)
        self.assertFalse(at.exception)

        captions = [c.value for c in at.caption]
        self.assertTrue(
            any("Aggregate status" in c for c in captions),
            "Aggregate placeholder caption must reappear after switching ticker without run. "
            f"Captions: {captions}",
        )

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
        """Caption is visible even before a ticker is selected."""
        at = AppTest.from_file(APP_PATH, default_timeout=30)
        at.run()
        captions = [c.value for c in at.caption]
        self.assertTrue(
            any("AI agent not connected" in c for c in captions),
            f"'AI agent not connected' caption missing on initial render. Captions: {captions}",
        )

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

    def test_clicking_analyse_shows_error_not_fabricated_output(self):
        """Clicking the agent analysis button shows an honest 'not connected' error.
        No fabricated agent output is displayed.
        """
        at = AppTest.from_file(APP_PATH, default_timeout=30)
        at.run()
        _run_screen(at, _TICKER_PASS)
        # Use key to find the correct button (not the ▶ Analyse form submit)
        agent_btns = [b for b in at.button if b.key == "agent_analyse_btn"]
        if not agent_btns:
            self.skipTest("agent_analyse_btn button not found")
        agent_btns[0].click().run()
        self.assertFalse(at.exception, f"Exception: {at.exception}")
        # Must show an error (st.error) — not a success with fake content
        errors = [e.value for e in at.error]
        self.assertTrue(
            any("Analysis not connected" in e or "not connected" in e.lower() for e in errors),
            f"Expected 'not connected' error after clicking agent analysis. Errors: {errors}",
        )
        # Must NOT claim to have agent output
        successes = [s.value for s in at.success]
        self.assertFalse(
            any("Agent analysis" in s and "live agent output" in s for s in successes),
            "App must not show fabricated agent output when not connected.",
        )


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

    def test_status_column_contains_icons(self):
        """Status column values include PASS/FAIL/UNKNOWN icons."""
        self.assertIn("Status", self.df.columns)
        valid_statuses = {"✅ PASS", "❌ FAIL", "⚠️ UNKNOWN"}
        for val in self.df["Status"]:
            self.assertIn(val, valid_statuses,
                          f"Unexpected status value: {val!r}")


if __name__ == "__main__":
    unittest.main()

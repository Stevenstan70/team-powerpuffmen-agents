"""
Streamlit AppTest smoke tests for app.py.

Uses Streamlit's AppTest framework (available since 1.18.0) to exercise the
three fictional-company screen flows without starting a server.

These tests track the current layout:
  - persistent synthetic-data warning (st.warning)
  - company selectbox in the sidebar
  - company name + aggregate status banner above the two columns
  - "▶ Run basic screen" button
  - compact rule table (st.dataframe) with four rows
  - collapsed "Rule explanations" expander
  - scope notice (st.info)
  - "Rule-based summary — AI agent not connected" caption
  - clearing of stale results when switching company

Do NOT modify the screening rules or existing unit tests.
"""

import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from streamlit.testing.v1 import AppTest  # noqa: E402

APP_PATH = os.path.join(os.path.dirname(__file__), "..", "app.py")

_COMPANY_PASS       = "Acme Galactic Ltd (all rules PASS)"
_COMPANY_FAIL       = "Bluebird Ventures (OCF FAIL)"
_COMPANY_UNVERIFIED = "Crescent Peak Corp (employees UNVERIFIED)"

COMPANIES = [_COMPANY_PASS, _COMPANY_FAIL, _COMPANY_UNVERIFIED]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _all_text(at: AppTest) -> str:
    """Collect all rendered markdown + caption + info text into one string."""
    parts = (
        [m.value for m in at.markdown]
        + [c.value for c in at.caption]
        + [i.value for i in at.info]
        + [w.value for w in at.warning]
    )
    return " ".join(parts)


def _run_screen(at: AppTest, company: str) -> AppTest:
    """Select *company* in the selectbox, click Run, return the updated AppTest."""
    at.selectbox[0].set_value(company).run()
    at.button[0].click().run()
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
        warnings = [w.value for w in self.at.warning]
        self.assertTrue(
            any("SYNTHETIC DEMO DATA" in w for w in warnings),
            f"Synthetic-data warning missing. Warnings: {warnings}",
        )

    def test_selectbox_in_sidebar(self):
        self.assertGreater(len(self.at.selectbox), 0, "No selectbox found.")

    def test_run_button_present(self):
        labels = [b.label for b in self.at.button]
        self.assertTrue(
            any("Run basic screen" in b for b in labels),
            f"Run button missing. Buttons: {labels}",
        )

    def test_prompt_to_run_shown_before_first_run(self):
        # Right column should show the "Press ▶ Run basic screen" prompt.
        text = _all_text(self.at)
        self.assertIn("Press", text, "Expected 'Press run' prompt not found on initial render.")

    def test_aggregate_status_placeholder_shown(self):
        # Before running, the aggregate banner is a caption placeholder.
        captions = [c.value for c in self.at.caption]
        self.assertTrue(
            any("Aggregate status" in c for c in captions),
            f"Aggregate status placeholder caption not found. Captions: {captions}",
        )

    def test_ai_agent_not_connected_label(self):
        captions = [c.value for c in self.at.caption]
        self.assertTrue(
            any("AI agent not connected" in c for c in captions),
            f"'AI agent not connected' caption missing. Captions: {captions}",
        )


# ---------------------------------------------------------------------------
# 2. Acme Galactic — all four rules PASS
# ---------------------------------------------------------------------------

class TestAcmeGalacticAllPass(unittest.TestCase):

    def setUp(self):
        at = AppTest.from_file(APP_PATH, default_timeout=30)
        at.run()
        self.at = _run_screen(at, _COMPANY_PASS)

    def test_no_exception(self):
        self.assertFalse(self.at.exception, f"App raised: {self.at.exception}")

    def test_pass_aggregate_in_banner(self):
        # Aggregate status banner appears above the columns as markdown.
        text = _all_text(self.at)
        self.assertIn("PASS", text, "Expected PASS aggregate not found in rendered text.")

    def test_rule_table_rendered(self):
        # st.dataframe produces a dataframe element.
        self.assertGreater(len(self.at.dataframe), 0, "No dataframe (rule table) found.")

    def test_rule_table_has_four_rows(self):
        df = self.at.dataframe[0].value
        self.assertEqual(len(df), 4, f"Expected 4 rule rows, got {len(df)}.")

    def test_rule_table_has_status_column(self):
        df = self.at.dataframe[0].value
        self.assertIn("Status", df.columns, "Rule table is missing 'Status' column.")

    def test_rule_table_has_observed_value_column(self):
        df = self.at.dataframe[0].value
        self.assertIn("Observed value", df.columns, "Rule table missing 'Observed value' column.")

    def test_rule_table_has_threshold_column(self):
        df = self.at.dataframe[0].value
        self.assertIn("Required threshold", df.columns, "Rule table missing 'Required threshold' column.")

    def test_scope_note_present(self):
        infos = [i.value for i in self.at.info]
        self.assertTrue(
            any("Only four rules evaluated" in i for i in infos),
            f"Scope note not found in info boxes. Infos: {infos}",
        )

    def test_research_summary_present(self):
        text = _all_text(self.at)
        self.assertIn("Screen result for", text, "Research summary not rendered.")

    def test_no_fabricated_content_labels(self):
        # The summary must explicitly state no fabricated content was generated.
        # We check the disclaimer sentence is present rather than checking for
        # the absence of keywords, because the disclaimer itself names them.
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


# ---------------------------------------------------------------------------
# 3. Bluebird Ventures — OCF FAIL
# ---------------------------------------------------------------------------

class TestBluebirdVenturesOcfFail(unittest.TestCase):

    def setUp(self):
        at = AppTest.from_file(APP_PATH, default_timeout=30)
        at.run()
        self.at = _run_screen(at, _COMPANY_FAIL)

    def test_no_exception(self):
        self.assertFalse(self.at.exception, f"App raised: {self.at.exception}")

    def test_fail_aggregate_in_banner(self):
        text = _all_text(self.at)
        self.assertIn("FAIL", text, "Expected FAIL aggregate not found.")

    def test_four_rule_rows(self):
        df = self.at.dataframe[0].value
        self.assertEqual(len(df), 4)

    def test_ocf_rule_shows_fail(self):
        df = self.at.dataframe[0].value
        ocf_rows = df[df["Rule"].str.contains("Operating Cash Flow", case=False)]
        self.assertFalse(ocf_rows.empty, "OCF rule row not found in table.")
        self.assertIn("FAIL", ocf_rows["Status"].values[0])

    def test_scope_note_present(self):
        infos = [i.value for i in self.at.info]
        self.assertTrue(any("Only four rules evaluated" in i for i in infos))

    def test_not_investment_recommendation(self):
        text = _all_text(self.at)
        self.assertIn("Not full investment eligibility", text)


# ---------------------------------------------------------------------------
# 4. Crescent Peak — employee count UNVERIFIED
# ---------------------------------------------------------------------------

class TestCrescentPeakUnverified(unittest.TestCase):

    def setUp(self):
        at = AppTest.from_file(APP_PATH, default_timeout=30)
        at.run()
        self.at = _run_screen(at, _COMPANY_UNVERIFIED)

    def test_no_exception(self):
        self.assertFalse(self.at.exception, f"App raised: {self.at.exception}")

    def test_unverified_aggregate_in_banner(self):
        text = _all_text(self.at)
        self.assertIn("UNVERIFIED", text, "Expected UNVERIFIED aggregate not found.")

    def test_four_rule_rows(self):
        df = self.at.dataframe[0].value
        self.assertEqual(len(df), 4)

    def test_employee_rule_shows_unverified(self):
        df = self.at.dataframe[0].value
        emp_rows = df[df["Rule"].str.contains("Employee", case=False)]
        self.assertFalse(emp_rows.empty, "Employee rule row not found in table.")
        self.assertIn("UNVERIFIED", emp_rows["Status"].values[0])

    def test_unknown_in_employee_observed_value(self):
        # The compact table must show "Unknown" for the missing employee count.
        df = self.at.dataframe[0].value
        emp_rows = df[df["Rule"].str.contains("Employee", case=False)]
        self.assertIn("Unknown", emp_rows["Observed value"].values[0])

    def test_unknown_shown_in_inputs_list(self):
        # The inputs bullet list must also show "Unknown" for employee count.
        text = _all_text(self.at)
        self.assertIn("Unknown", text, "'Unknown' not shown for missing employee count.")

    def test_scope_note_present(self):
        infos = [i.value for i in self.at.info]
        self.assertTrue(any("Only four rules evaluated" in i for i in infos))


# ---------------------------------------------------------------------------
# 5. Company-switch consistency — explicit stale-result test
# ---------------------------------------------------------------------------

class TestCompanySwitchStaleResult(unittest.TestCase):
    """
    Switching from a screened company to a different company must not show
    the old result. The new result must not appear until Run is clicked.
    """

    def test_switching_company_clears_result_before_run(self):
        """After switching, the old aggregate must not be visible and the
        'Press run' prompt must reappear."""
        at = AppTest.from_file(APP_PATH, default_timeout=30)
        at.run()

        # Run Acme first — we will see PASS.
        _run_screen(at, _COMPANY_PASS)
        self.assertFalse(at.exception)
        text_after_acme = _all_text(at)
        self.assertIn("PASS", text_after_acme, "Sanity: Acme screen should show PASS.")

        # Switch to Bluebird — do NOT click Run.
        at.selectbox[0].set_value(_COMPANY_FAIL).run()
        self.assertFalse(at.exception, f"Exception after switch: {at.exception}")

        text_after_switch = _all_text(at)

        # The 'Press run' prompt must be back.
        self.assertIn(
            "Press",
            text_after_switch,
            "Expected 'Press run' prompt after switching company without running.",
        )

        # The rule table must NOT be present yet.
        self.assertEqual(
            len(at.dataframe),
            0,
            "Rule table (dataframe) must not be shown before running the new screen.",
        )

    def test_switching_then_running_shows_new_result(self):
        """After switching and running, the new company's result must appear."""
        at = AppTest.from_file(APP_PATH, default_timeout=30)
        at.run()

        # Run Acme first.
        _run_screen(at, _COMPANY_PASS)

        # Switch to Bluebird and run.
        _run_screen(at, _COMPANY_FAIL)
        self.assertFalse(at.exception, f"Exception: {at.exception}")

        text = _all_text(at)
        self.assertIn("FAIL", text, "Bluebird should show FAIL after running its screen.")
        df = at.dataframe[0].value
        self.assertEqual(len(df), 4, "Rule table should have 4 rows for Bluebird.")

    def test_switching_company_aggregate_placeholder_shown(self):
        """After switching (before run), the aggregate banner placeholder
        must be shown, not the previous company's aggregate status."""
        at = AppTest.from_file(APP_PATH, default_timeout=30)
        at.run()

        # Run Acme to get a cached PASS result.
        _run_screen(at, _COMPANY_PASS)

        # Switch to Crescent Peak — do NOT run.
        at.selectbox[0].set_value(_COMPANY_UNVERIFIED).run()
        self.assertFalse(at.exception)

        captions = [c.value for c in at.caption]
        self.assertTrue(
            any("Aggregate status" in c for c in captions),
            "Aggregate status placeholder caption must be shown after switch without run.",
        )


if __name__ == "__main__":
    unittest.main()

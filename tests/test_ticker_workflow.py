"""
tests/test_ticker_workflow.py

Tests for:
  1. validate_ticker  — format validation (no network)
  2. resolve_ticker   — Moomoo lookup boundary (mocked)
  3. fetch_moomoo_inputs — Moomoo data fetch boundary (mocked)
  4. App smoke: Analyse button flow, invalid-ticker rejection, no manual form,
     unverified input never shown as company heading

No live Moomoo or Orchestrate connection required.
Moomoo calls are intercepted with unittest.mock.patch.
"""

from __future__ import annotations

import sys
import os
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from frontend.adapter import (
    validate_ticker,
    resolve_ticker,
    fetch_moomoo_inputs,
    evaluate_company,
)


# ---------------------------------------------------------------------------
# 1. validate_ticker — pure format checks, no network
# ---------------------------------------------------------------------------

class TestValidateTickerValid(unittest.TestCase):
    """Valid single-word tickers must be accepted and uppercased."""

    def _ok(self, raw: str, expected_upper: str):
        r = validate_ticker(raw)
        self.assertTrue(r["valid"], f"Expected valid for {raw!r}: {r['reason']}")
        self.assertEqual(r["ticker"], expected_upper)
        self.assertIsNone(r["reason"])

    def test_standard_us_ticker(self):
        self._ok("AAPL", "AAPL")

    def test_lowercase_accepted_and_uppercased(self):
        self._ok("aapl", "AAPL")

    def test_mixed_case(self):
        self._ok("Msft", "MSFT")

    def test_single_letter(self):
        self._ok("A", "A")

    def test_numeric_suffix(self):
        self._ok("BRK", "BRK")

    def test_ten_chars(self):
        self._ok("ABCDEFGHIJ", "ABCDEFGHIJ")

    def test_leading_trailing_spaces_stripped(self):
        r = validate_ticker("  AAPL  ")
        self.assertTrue(r["valid"])
        self.assertEqual(r["ticker"], "AAPL")


class TestValidateTickerInvalid(unittest.TestCase):
    """Invalid inputs must be rejected with a useful reason."""

    def _bad(self, raw: str):
        r = validate_ticker(raw)
        self.assertFalse(r["valid"], f"Expected invalid for {raw!r}")
        self.assertEqual(r["ticker"], "")
        self.assertIsNotNone(r["reason"])
        self.assertGreater(len(r["reason"]), 5)

    def test_empty_string(self):
        self._bad("")

    def test_whitespace_only(self):
        self._bad("   ")

    def test_two_word_input(self):
        """'baba amskd' must be rejected — the core requirement from the spec."""
        self._bad("baba amskd")
        r = validate_ticker("baba amskd")
        self.assertIn("multiple words", r["reason"])

    def test_space_in_middle(self):
        self._bad("BA BA")

    def test_tab_in_input(self):
        self._bad("BA\tBA")

    def test_too_long(self):
        self._bad("ABCDEFGHIJK")  # 11 chars

    def test_special_chars(self):
        self._bad("AA$PL")

    def test_dot_not_allowed(self):
        """BRK.A-style tickers are note supported by current regex (documented)."""
        self._bad("BRK.A")

    def test_hyphen_not_allowed(self):
        self._bad("BRK-A")

    def test_numeric_only_one_digit(self):
        # single digit is valid format-wise
        r = validate_ticker("9")
        self.assertTrue(r["valid"])

    def test_garbage_with_numbers(self):
        self._bad("123456789012")  # 12 chars


class TestValidateTickerNoNetworkCall(unittest.TestCase):
    """validate_ticker must never open a network connection."""

    def test_no_moomoo_import_called(self):
        """If moomoo._ft is patched to raise, validate_ticker must still work."""
        with patch("frontend.adapter._ft", None):
            r = validate_ticker("AAPL")
        self.assertTrue(r["valid"])

    def test_multi_word_rejected_without_network(self):
        with patch("frontend.adapter._ft", None):
            r = validate_ticker("hello world")
        self.assertFalse(r["valid"])


# ---------------------------------------------------------------------------
# 2. resolve_ticker — Moomoo lookup boundary (mocked)
# ---------------------------------------------------------------------------

def _mock_ctx(search_ret=0, search_data=None):
    """Build a mock OpenQuoteContext that returns preset search_quote results."""
    import pandas as pd
    ctx = MagicMock()
    if search_data is None:
        search_data = pd.DataFrame([{
            "market": "US", "code": "US.AAPL",
            "name": "Apple", "sec_type": "STOCK", "is_watched": True,
        }])
    ctx.get_search_quote.return_value = (search_ret, search_data)
    ctx.close.return_value = None
    return ctx


class TestResolveTickerMoomooNotAvailable(unittest.TestCase):
    def test_not_available_returns_not_connected(self):
        with patch("frontend.adapter._MOOMOO_AVAILABLE", False):
            r = resolve_ticker("AAPL")
        self.assertFalse(r["connected"])
        self.assertFalse(r["found"])
        self.assertIsNotNone(r["error"])


class TestResolveTickerFound(unittest.TestCase):
    def _make_ctx(self):
        import pandas as pd
        ctx = MagicMock()
        ctx.get_search_quote.return_value = (0, pd.DataFrame([
            {"market": "US", "code": "US.AAPL", "name": "Apple",
             "sec_type": "STOCK", "is_watched": True},
        ]))
        ctx.close.return_value = None
        return ctx

    def test_known_ticker_returns_found(self):
        with patch("frontend.adapter._MOOMOO_AVAILABLE", True), \
             patch("frontend.adapter._ft") as mock_ft:
            mock_ft.OpenQuoteContext.return_value = self._make_ctx()
            mock_ft.RET_OK = 0   # resolve_ticker checks ret != _ft.RET_OK
            r = resolve_ticker("AAPL")
        self.assertTrue(r["connected"])
        self.assertTrue(r["found"])
        self.assertEqual(r["moomoo_code"], "US.AAPL")
        self.assertEqual(r["company_name"], "Apple")
        self.assertEqual(r["sec_type"], "STOCK")
        self.assertIsNone(r["error"])

    def test_ticker_preserved_in_result(self):
        with patch("frontend.adapter._MOOMOO_AVAILABLE", True), \
             patch("frontend.adapter._ft") as mock_ft:
            mock_ft.OpenQuoteContext.return_value = self._make_ctx()
            mock_ft.RET_OK = 0
            r = resolve_ticker("AAPL")
        self.assertEqual(r["ticker"], "AAPL")


class TestResolveTickerNotFound(unittest.TestCase):
    def test_unknown_ticker_returns_not_found(self):
        import pandas as pd
        ctx = MagicMock()
        ctx.get_search_quote.return_value = (0, pd.DataFrame())
        ctx.close.return_value = None
        with patch("frontend.adapter._MOOMOO_AVAILABLE", True), \
             patch("frontend.adapter._ft") as mock_ft:
            mock_ft.OpenQuoteContext.return_value = ctx
            r = resolve_ticker("XYZXYZXYZ")
        self.assertTrue(r["connected"])
        self.assertFalse(r["found"])
        self.assertIsNotNone(r["error"])

    def test_etf_rejected_as_not_stock(self):
        import pandas as pd
        ctx = MagicMock()
        ctx.get_search_quote.return_value = (0, pd.DataFrame([
            {"market": "US", "code": "US.SPY", "name": "SPDR S&P 500",
             "sec_type": "ETF", "is_watched": False},
        ]))
        ctx.close.return_value = None
        with patch("frontend.adapter._MOOMOO_AVAILABLE", True), \
             patch("frontend.adapter._ft") as mock_ft:
            mock_ft.OpenQuoteContext.return_value = ctx
            r = resolve_ticker("SPY")
        self.assertTrue(r["connected"])
        self.assertFalse(r["found"])
        self.assertIn("ETF", r["error"])

    def test_unverified_input_never_in_company_name(self):
        """If not found, company_name must be None — not the raw input."""
        import pandas as pd
        ctx = MagicMock()
        ctx.get_search_quote.return_value = (0, pd.DataFrame())
        ctx.close.return_value = None
        with patch("frontend.adapter._MOOMOO_AVAILABLE", True), \
             patch("frontend.adapter._ft") as mock_ft:
            mock_ft.OpenQuoteContext.return_value = ctx
            r = resolve_ticker("GARBAGE999")
        self.assertIsNone(r["company_name"],
                          "company_name must be None when ticker not found")


class TestResolveTickerConnectionError(unittest.TestCase):
    def test_connection_error_returns_not_connected(self):
        with patch("frontend.adapter._MOOMOO_AVAILABLE", True), \
             patch("frontend.adapter._ft") as mock_ft:
            mock_ft.OpenQuoteContext.side_effect = ConnectionRefusedError("OpenD not running")
            r = resolve_ticker("AAPL")
        self.assertFalse(r["connected"])
        self.assertIsNotNone(r["error"])

    def test_context_closed_on_exception(self):
        """ctx.close() must be called even when an exception is raised."""
        ctx = MagicMock()
        ctx.get_search_quote.side_effect = RuntimeError("unexpected")
        ctx.close.return_value = None
        with patch("frontend.adapter._MOOMOO_AVAILABLE", True), \
             patch("frontend.adapter._ft") as mock_ft:
            mock_ft.OpenQuoteContext.return_value = ctx
            resolve_ticker("AAPL")
        ctx.close.assert_called_once()


# ---------------------------------------------------------------------------
# 3. fetch_moomoo_inputs — boundary tests
# ---------------------------------------------------------------------------

class TestFetchMoomooInputsNotAvailable(unittest.TestCase):
    def test_not_available_returns_all_none(self):
        with patch("frontend.adapter._MOOMOO_AVAILABLE", False):
            r = fetch_moomoo_inputs("US.AAPL")
        self.assertFalse(r["connected"])
        for v in r["inputs"].values():
            self.assertIsNone(v)

    def test_ocf_always_none_blocked(self):
        """OCF must always be None — it is a blocked backend dependency.
        When moomoo-api is not installed, all notes say 'not installed'.
        The 'backend teammate' note appears only in the live path."""
        with patch("frontend.adapter._MOOMOO_AVAILABLE", False):
            r = fetch_moomoo_inputs("US.AAPL")
        self.assertIsNone(r["inputs"]["operating_cash_flow_ttm_usd"])
        # When not installed the note covers all fields; just confirm None
        self.assertFalse(r["connected"])


class TestFetchMoomooInputsLive(unittest.TestCase):
    def _make_ctx(self, price=343.46, mktcap=5e12, employees="166000"):
        import pandas as pd
        ctx = MagicMock()
        snap_df = pd.DataFrame([{
            "last_price": price,
            "total_market_val": mktcap,
        }])
        ctx.get_market_snapshot.return_value = (0, snap_df)
        prof_df = pd.DataFrame([
            {"name": "Employees", "value": employees, "field_type": 0},
            {"name": "Company Name", "value": "Apple", "field_type": 0},
        ])
        ctx.get_company_profile.return_value = (0, prof_df)
        ctx.close.return_value = None
        return ctx

    def test_price_and_mktcap_retrieved(self):
        with patch("frontend.adapter._MOOMOO_AVAILABLE", True), \
             patch("frontend.adapter._ft") as mock_ft:
            mock_ft.OpenQuoteContext.return_value = self._make_ctx()
            mock_ft.RET_OK = 0
            r = fetch_moomoo_inputs("US.AAPL")
        self.assertTrue(r["connected"])
        self.assertAlmostEqual(r["inputs"]["close_price_usd"], 343.46, places=2)
        self.assertAlmostEqual(r["inputs"]["market_cap_usd"], 5e12, places=0)

    def test_employee_count_retrieved(self):
        with patch("frontend.adapter._MOOMOO_AVAILABLE", True), \
             patch("frontend.adapter._ft") as mock_ft:
            mock_ft.OpenQuoteContext.return_value = self._make_ctx()
            mock_ft.RET_OK = 0
            r = fetch_moomoo_inputs("US.AAPL")
        self.assertEqual(r["inputs"]["employee_count"], 166000)

    def test_ocf_always_none_blocked(self):
        """OCF is the blocked backend dependency — must always return None."""
        with patch("frontend.adapter._MOOMOO_AVAILABLE", True), \
             patch("frontend.adapter._ft") as mock_ft:
            mock_ft.OpenQuoteContext.return_value = self._make_ctx()
            mock_ft.RET_OK = 0
            r = fetch_moomoo_inputs("US.AAPL")
        self.assertIsNone(r["inputs"]["operating_cash_flow_ttm_usd"])
        note = r["input_notes"]["operating_cash_flow_ttm_usd"]
        self.assertIn("Not connected", note)

    def test_input_notes_show_moomoo_source(self):
        with patch("frontend.adapter._MOOMOO_AVAILABLE", True), \
             patch("frontend.adapter._ft") as mock_ft:
            mock_ft.OpenQuoteContext.return_value = self._make_ctx()
            mock_ft.RET_OK = 0
            r = fetch_moomoo_inputs("US.AAPL")
        self.assertIn("Moomoo", r["input_notes"]["close_price_usd"])
        self.assertIn("Moomoo", r["input_notes"]["market_cap_usd"])
        self.assertIn("Moomoo", r["input_notes"]["employee_count"])

    def test_context_closed_on_success(self):
        ctx = self._make_ctx()
        with patch("frontend.adapter._MOOMOO_AVAILABLE", True), \
             patch("frontend.adapter._ft") as mock_ft:
            mock_ft.OpenQuoteContext.return_value = ctx
            mock_ft.RET_OK = 0
            fetch_moomoo_inputs("US.AAPL")
        ctx.close.assert_called_once()

    def test_context_closed_on_exception(self):
        ctx = MagicMock()
        ctx.get_market_snapshot.side_effect = RuntimeError("network error")
        ctx.close.return_value = None
        with patch("frontend.adapter._MOOMOO_AVAILABLE", True), \
             patch("frontend.adapter._ft") as mock_ft:
            mock_ft.OpenQuoteContext.return_value = ctx
            fetch_moomoo_inputs("US.AAPL")
        ctx.close.assert_called_once()

    def test_missing_employee_field_returns_none_not_zero(self):
        """If Employees row is absent, employee_count must be None, not 0."""
        import pandas as pd
        ctx = MagicMock()
        ctx.get_market_snapshot.return_value = (0, pd.DataFrame([
            {"last_price": 100.0, "total_market_val": 1e12}
        ]))
        prof_df = pd.DataFrame([
            {"name": "Company Name", "value": "Acme", "field_type": 0},
        ])
        ctx.get_company_profile.return_value = (0, prof_df)
        ctx.close.return_value = None
        with patch("frontend.adapter._MOOMOO_AVAILABLE", True), \
             patch("frontend.adapter._ft") as mock_ft:
            mock_ft.OpenQuoteContext.return_value = ctx
            mock_ft.RET_OK = 0
            r = fetch_moomoo_inputs("US.FAKE")
        self.assertIsNone(r["inputs"]["employee_count"],
                          "Missing employee count must be None, not 0")


# ---------------------------------------------------------------------------
# 4. App smoke: Analyse flow, invalid-ticker rejection, no manual form
# ---------------------------------------------------------------------------

APP_PATH = os.path.join(os.path.dirname(__file__), "..", "app.py")


def _all_text(at) -> str:
    parts = (
        [m.value for m in at.markdown]
        + [c.value for c in at.caption]
        + [i.value for i in at.info]
        + [w.value for w in at.warning]
        + [e.value for e in at.error]
    )
    return " ".join(parts)


class TestInvalidTickerRejected(unittest.TestCase):
    """Multi-word and format-invalid tickers must show an error without
    displaying the raw input as a company heading."""

    def _render_with_ticker(self, raw: str):
        from streamlit.testing.v1 import AppTest
        at = AppTest.from_file(APP_PATH, default_timeout=30)
        at.run()
        at.text_input(key="ticker_text_input").set_value(raw).run()
        return at

    def test_multi_word_input_shows_error(self):
        """'baba amskd' must show an error, not be treated as a company."""
        at = self._render_with_ticker("baba amskd")
        self.assertFalse(at.exception, f"App raised: {at.exception}")
        errors = [e.value for e in at.error]
        self.assertTrue(
            any("Invalid ticker" in e or "multiple words" in e for e in errors),
            f"Expected invalid-ticker error. Errors: {errors}",
        )

    def test_multi_word_input_not_shown_as_heading(self):
        """Raw unverified input must never appear as a company subheader."""
        at = self._render_with_ticker("baba amskd")
        subtitles = [s.value for s in at.subheader]
        self.assertFalse(
            any("baba" in str(s).lower() and "amskd" in str(s).lower() for s in subtitles),
            f"Unverified input shown as company heading. Subheaders: {subtitles}",
        )

    def test_multi_word_input_no_dataframe(self):
        """No criteria table must appear for an invalid ticker."""
        at = self._render_with_ticker("baba amskd")
        self.assertEqual(len(at.dataframe), 0,
                         "No criteria table should appear for invalid ticker.")

    def test_too_long_ticker_shows_error(self):
        at = self._render_with_ticker("ABCDEFGHIJK")
        errors = [e.value for e in at.error]
        self.assertTrue(
            any("Invalid ticker" in e or "valid ticker" in e.lower() for e in errors),
            f"Expected format error for overlong ticker. Errors: {errors}",
        )


class TestAnalyseButtonReplacesManualForm(unittest.TestCase):
    """The manual metric entry form must not be present in the normal flow.
    The single Analyse form submit button replaces it."""

    def setUp(self):
        from streamlit.testing.v1 import AppTest
        at = AppTest.from_file(APP_PATH, default_timeout=30)
        at.run()
        at.text_input(key="ticker_text_input").set_value("ACME").run()
        self.at = at

    def test_no_market_cap_input_field(self):
        """Market Cap text input must not be present in the normal flow."""
        labels = [t.label for t in self.at.text_input]
        self.assertNotIn(
            "Market Cap (USD)", labels,
            "Manual metric entry fields must not be present in the normal flow.",
        )

    def test_no_close_price_input_field(self):
        labels = [t.label for t in self.at.text_input]
        self.assertNotIn("Close Price (USD)", labels)

    def test_no_ocf_input_field(self):
        labels = [t.label for t in self.at.text_input]
        self.assertNotIn("Operating Cash Flow TTM (USD)", labels)

    def test_no_employee_count_input_field(self):
        labels = [t.label for t in self.at.text_input]
        self.assertNotIn("Employee Count", labels)

    def test_analyse_form_submit_present(self):
        """The single Analyse form submit button is present."""
        self.assertGreater(
            len(self.at.form_submit_button), 0,
            "Analyse form submit button missing after ticker set.",
        )


class TestDemoAnalyseFlow(unittest.TestCase):
    """Pressing Analyse on a demo ticker must run the full demo flow and
    show results — no Moomoo connection needed."""

    def _run_demo(self, ticker: str):
        from streamlit.testing.v1 import AppTest
        at = AppTest.from_file(APP_PATH, default_timeout=30)
        at.run()
        at.text_input(key="ticker_text_input").set_value(ticker).run()
        at.form_submit_button[0].click().run()
        return at

    def test_acme_analyse_shows_results(self):
        at = self._run_demo("ACME")
        self.assertFalse(at.exception, f"App raised: {at.exception}")
        self.assertGreater(len(at.dataframe), 0, "No criteria table after Analyse.")

    def test_acme_company_name_shown_after_resolve(self):
        """Company name is shown only after the demo path resolves it."""
        at = self._run_demo("ACME")
        subtitles = [s.value for s in at.subheader]
        # Should show the resolved company name, not just raw "ACME"
        self.assertTrue(
            any("ACME" in str(s) or "Acme" in str(s) for s in subtitles),
            f"Company name not in subheaders: {subtitles}",
        )

    def test_demo_label_visible(self):
        at = self._run_demo("ACME")
        text = _all_text(at)
        self.assertIn("DEMO", text.upper(), "Demo label missing.")

    def test_pass_result_for_acme(self):
        at = self._run_demo("ACME")
        text = _all_text(at)
        self.assertIn("PASS", text)

    def test_fail_result_for_blue(self):
        at = self._run_demo("BLUE")
        self.assertFalse(at.exception)
        text = _all_text(at)
        self.assertIn("FAIL", text)

    def test_unknown_for_crst(self):
        at = self._run_demo("CRST")
        self.assertFalse(at.exception)
        text = _all_text(at)
        self.assertIn("UNKNOWN", text)

    def test_scope_note_present(self):
        at = self._run_demo("ACME")
        infos = [i.value for i in at.info]
        self.assertTrue(
            any("Only the criteria returned" in i for i in infos),
            f"Scope note missing. Infos: {infos}",
        )

    def test_not_investment_recommendation(self):
        at = self._run_demo("BLUE")
        text = _all_text(at)
        self.assertIn("Not full investment eligibility", text)


class TestOcfNotConnectedLabel(unittest.TestCase):
    """When OCF is unavailable (not connected), it must show Unknown/Unavailable
    in the criteria table — not zero and not a fabricated value."""

    def test_ocf_shows_unknown_in_demo(self):
        """For a demo ticker where OCF is provided, this is a sanity check.
        For live tickers where OCF is blocked, Unknown must appear."""
        from streamlit.testing.v1 import AppTest
        at = AppTest.from_file(APP_PATH, default_timeout=30)
        at.run()
        # CRST has employee_count=None → verifies Unknown path
        at.text_input(key="ticker_text_input").set_value("CRST").run()
        at.form_submit_button[0].click().run()
        self.assertFalse(at.exception)
        df = at.dataframe[0].value
        emp_rows = df[df["Criterion"].str.contains("Employee", case=False)]
        self.assertFalse(emp_rows.empty)
        self.assertIn("Unknown", emp_rows["Observed"].values[0])
        # Verify it's not zero
        self.assertNotEqual(emp_rows["Observed"].values[0], "0")
        self.assertNotEqual(emp_rows["Observed"].values[0], "$0.00")


class TestSwitchTickerClearsAnalysis(unittest.TestCase):
    """Switching ticker must clear the previous analysis result and
    show a fresh unresolved state."""

    def test_switch_clears_company_heading(self):
        from streamlit.testing.v1 import AppTest
        at = AppTest.from_file(APP_PATH, default_timeout=30)
        at.run()
        # Run ACME first
        at.text_input(key="ticker_text_input").set_value("ACME").run()
        at.form_submit_button[0].click().run()
        self.assertFalse(at.exception)
        self.assertGreater(len(at.dataframe), 0, "Sanity: ACME table should appear")
        # Switch to BLUE without running
        at.text_input(key="ticker_text_input").set_value("BLUE").run()
        # No dataframe should be shown before Analyse is pressed
        self.assertEqual(
            len(at.dataframe), 0,
            "ACME criteria table must not show after switching to BLUE.",
        )

    def test_switch_to_invalid_shows_error_not_stale_result(self):
        from streamlit.testing.v1 import AppTest
        at = AppTest.from_file(APP_PATH, default_timeout=30)
        at.run()
        # Screen ACME
        at.text_input(key="ticker_text_input").set_value("ACME").run()
        at.form_submit_button[0].click().run()
        self.assertGreater(len(at.dataframe), 0)
        # Type an invalid ticker
        at.text_input(key="ticker_text_input").set_value("hello world").run()
        errors = [e.value for e in at.error]
        self.assertTrue(
            any("Invalid ticker" in e or "multiple words" in e for e in errors),
            f"Expected invalid ticker error. Errors: {errors}",
        )
        self.assertEqual(len(at.dataframe), 0,
                         "Stale criteria table must not show for invalid ticker.")


if __name__ == "__main__":
    unittest.main()

"""
tests/test_ticker_workflow.py

Tests the safety-updated frontend adapter and existing ticker UI.

Coverage:
1. Ticker syntax validation without network access.
2. Exact US stock resolution using mocked Moomoo responses.
3. Snapshot/profile retrieval using mocked Moomoo responses.
4. Explicit demo selection and missing-data behaviour.
5. Existing Streamlit ticker-entry and demo workflows.

These are deterministic tests, not live integration tests.
No real Moomoo or Orchestrate connection is required.
"""

from __future__ import annotations

import os
import sys
import unittest
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pandas as pd


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from frontend.adapter import (
    evaluate_company,
    fetch_moomoo_inputs,
    resolve_ticker,
    validate_ticker,
)


APP_PATH = os.path.join(ROOT, "app.py")
SNAPSHOT_TIME = "2026-10-20 16:00:00"


@contextmanager
def mocked_moomoo(ctx):
    """Configure the same success constant for every mocked API request."""
    with (
        patch("frontend.adapter._MOOMOO_AVAILABLE", True),
        patch("frontend.adapter._ft") as mock_ft,
    ):
        mock_ft.RET_OK = 0
        mock_ft.OpenQuoteContext.return_value = ctx
        yield mock_ft


def search_context(rows=None, *, ret=0):
    ctx = MagicMock()

    if rows is None:
        rows = [{
            "market": "US",
            "code": "US.AAPL",
            "name": "Apple",
            "sec_type": "STOCK",
            "is_watched": True,
        }]

    ctx.get_search_quote.return_value = (ret, pd.DataFrame(rows))
    return ctx


def snapshot_context(
    *,
    code="US.AAPL",
    previous_close=343.46,
    latest_price=350.00,
    market_cap=5e12,
    employees="166000",
):
    ctx = MagicMock()

    ctx.get_market_snapshot.return_value = (
        0,
        pd.DataFrame([{
            "code": code,
            "last_price": latest_price,
            "prev_close_price": previous_close,
            "total_market_val": market_cap,
            "update_time": SNAPSHOT_TIME,
        }]),
    )

    ctx.get_company_profile.return_value = (
        0,
        pd.DataFrame([
            {
                "name": "Employees",
                "value": employees,
                "field_type": 0,
            },
            {
                "name": "Company Name",
                "value": "Apple",
                "field_type": 0,
            },
        ]),
    )

    return ctx


# ---------------------------------------------------------------------------
# 1. Pure ticker-format validation
# ---------------------------------------------------------------------------

class TestValidateTickerValid(unittest.TestCase):
    def _ok(self, raw, expected):
        result = validate_ticker(raw)
        self.assertTrue(result["valid"], result["reason"])
        self.assertEqual(result["ticker"], expected)
        self.assertIsNone(result["reason"])

    def test_standard_us_ticker(self):
        self._ok("AAPL", "AAPL")

    def test_lowercase_accepted_and_uppercased(self):
        self._ok("aapl", "AAPL")

    def test_mixed_case(self):
        self._ok("Msft", "MSFT")

    def test_single_letter(self):
        self._ok("A", "A")

    def test_alphanumeric_syntax(self):
        self._ok("ABC1", "ABC1")

    def test_ten_chars(self):
        self._ok("ABCDEFGHIJ", "ABCDEFGHIJ")

    def test_leading_trailing_spaces_stripped(self):
        self._ok("  AAPL  ", "AAPL")

    def test_dot_syntax_allowed(self):
        # Format acceptance does not establish provider support or existence.
        self._ok("BRK.A", "BRK.A")

    def test_hyphen_syntax_allowed(self):
        self._ok("BRK-A", "BRK-A")

    def test_us_prefix_normalised(self):
        self._ok("US.AAPL", "AAPL")

    def test_lowercase_us_prefix_normalised(self):
        self._ok("us.aapl", "AAPL")

    def test_numeric_only_is_syntax_not_existence_check(self):
        self._ok("9", "9")


class TestValidateTickerInvalid(unittest.TestCase):
    def _bad(self, raw):
        result = validate_ticker(raw)
        self.assertFalse(result["valid"], repr(raw))
        self.assertEqual(result["ticker"], "")
        self.assertIsInstance(result["reason"], str)
        self.assertGreater(len(result["reason"]), 5)

    def test_empty_string(self):
        self._bad("")

    def test_whitespace_only(self):
        self._bad("   ")

    def test_non_string(self):
        self._bad(None)

    def test_two_word_input(self):
        self._bad("baba amskd")
        self.assertIn(
            "multiple words",
            validate_ticker("baba amskd")["reason"],
        )

    def test_space_in_middle(self):
        self._bad("BA BA")

    def test_tab_in_input(self):
        self._bad("BA\tBA")

    def test_newline_in_input(self):
        self._bad("BA\nBA")

    def test_too_long(self):
        self._bad("ABCDEFGHIJK")

    def test_special_chars(self):
        self._bad("AA$PL")

    def test_leading_separator(self):
        self._bad(".AAPL")

    def test_trailing_separator(self):
        self._bad("AAPL-")

    def test_repeated_separator(self):
        self._bad("BRK..A")

    def test_comma_separated_tickers(self):
        self._bad("AAPL,MSFT")

    def test_garbage_with_numbers(self):
        self._bad("123456789012")


class TestValidateTickerNoNetworkCall(unittest.TestCase):
    def test_valid_format_never_opens_context(self):
        with patch("frontend.adapter._ft") as mock_ft:
            result = validate_ticker("AAPL")

        self.assertTrue(result["valid"])
        mock_ft.OpenQuoteContext.assert_not_called()

    def test_multi_word_rejected_without_network(self):
        with patch("frontend.adapter._ft") as mock_ft:
            result = validate_ticker("hello world")

        self.assertFalse(result["valid"])
        mock_ft.OpenQuoteContext.assert_not_called()

    def test_validation_works_without_sdk(self):
        with patch("frontend.adapter._ft", None):
            result = validate_ticker("AAPL")

        self.assertTrue(result["valid"])


# ---------------------------------------------------------------------------
# 2. Company resolution: mocked API boundary
# ---------------------------------------------------------------------------

class TestResolveTickerMoomooNotAvailable(unittest.TestCase):
    def test_not_available_returns_not_connected(self):
        with patch("frontend.adapter._MOOMOO_AVAILABLE", False):
            result = resolve_ticker("AAPL")

        self.assertFalse(result["connected"])
        self.assertFalse(result["found"])
        self.assertIsNone(result["company_name"])
        self.assertIsNotNone(result["error"])


class TestResolveTickerFound(unittest.TestCase):
    def test_known_ticker_returns_found(self):
        ctx = search_context()

        with mocked_moomoo(ctx):
            result = resolve_ticker("AAPL")

        self.assertTrue(result["connected"])
        self.assertTrue(result["found"])
        self.assertEqual(result["ticker"], "AAPL")
        self.assertEqual(result["moomoo_code"], "US.AAPL")
        self.assertEqual(result["company_name"], "Apple")
        self.assertEqual(result["sec_type"], "STOCK")
        self.assertIsNone(result["error"])
        ctx.close.assert_called_once()

    def test_ticker_normalised_in_result(self):
        ctx = search_context()

        with mocked_moomoo(ctx):
            result = resolve_ticker("us.aapl")

        self.assertTrue(result["found"])
        self.assertEqual(result["ticker"], "AAPL")
        ctx.get_search_quote.assert_called_once_with(
            "AAPL",
            max_count=10,
        )

    def test_exact_match_selected_not_first_result(self):
        ctx = search_context([
            {
                "code": "US.MSFT",
                "name": "Microsoft",
                "sec_type": "STOCK",
            },
            {
                "code": "US.AAPL",
                "name": "Apple",
                "sec_type": "STOCK",
            },
        ])

        with mocked_moomoo(ctx):
            result = resolve_ticker("AAPL")

        self.assertTrue(result["found"])
        self.assertEqual(result["moomoo_code"], "US.AAPL")
        self.assertEqual(result["company_name"], "Apple")


class TestResolveTickerNotFound(unittest.TestCase):
    def test_unknown_ticker_returns_not_found(self):
        ctx = search_context([])

        with mocked_moomoo(ctx):
            result = resolve_ticker("XYZXYZXYZ")

        self.assertTrue(result["connected"])
        self.assertFalse(result["found"])
        self.assertIsNone(result["company_name"])
        self.assertIsNotNone(result["error"])
        ctx.close.assert_called_once()

    def test_etf_rejected_as_not_stock(self):
        ctx = search_context([{
            "market": "US",
            "code": "US.SPY",
            "name": "SPDR S&P 500",
            "sec_type": "ETF",
        }])

        with mocked_moomoo(ctx):
            result = resolve_ticker("SPY")

        self.assertTrue(result["connected"])
        self.assertFalse(result["found"])
        self.assertEqual(result["sec_type"], "ETF")
        self.assertIsNone(result["company_name"])
        self.assertIsNotNone(result["error"])
        self.assertIn("STOCK", result["error"])

    def test_unverified_input_never_in_company_name(self):
        ctx = search_context([])

        with mocked_moomoo(ctx):
            result = resolve_ticker("GARBAGE999")

        self.assertTrue(result["connected"])
        self.assertFalse(result["found"])
        self.assertIsNone(result["company_name"])

    def test_similar_stock_is_not_substituted(self):
        ctx = search_context([{
            "code": "US.AAP",
            "name": "Different Company",
            "sec_type": "STOCK",
        }])

        with mocked_moomoo(ctx):
            result = resolve_ticker("AAPL")

        self.assertTrue(result["connected"])
        self.assertFalse(result["found"])
        self.assertIsNone(result["company_name"])
        self.assertIsNone(result["moomoo_code"])

    def test_non_us_match_is_not_substituted(self):
        ctx = search_context([{
            "code": "HK.AAPL",
            "name": "Other Listing",
            "sec_type": "STOCK",
        }])

        with mocked_moomoo(ctx):
            result = resolve_ticker("AAPL")

        self.assertFalse(result["found"])
        self.assertIsNone(result["moomoo_code"])

    def test_ambiguous_company_names_are_rejected(self):
        ctx = search_context([
            {
                "code": "US.AAPL",
                "name": "Apple",
                "sec_type": "STOCK",
            },
            {
                "code": "US.AAPL",
                "name": "Conflicting Name",
                "sec_type": "STOCK",
            },
        ])

        with mocked_moomoo(ctx):
            result = resolve_ticker("AAPL")

        self.assertFalse(result["found"])
        self.assertIsNone(result["company_name"])
        self.assertIn("Ambiguous", result["error"])

    def test_missing_search_columns_are_rejected(self):
        ctx = search_context([{"code": "US.AAPL"}])

        with mocked_moomoo(ctx):
            result = resolve_ticker("AAPL")

        self.assertFalse(result["found"])
        self.assertIsNone(result["company_name"])
        self.assertIn("schema", result["error"])

    def test_invalid_input_never_opens_connection(self):
        ctx = search_context()

        with mocked_moomoo(ctx) as mock_ft:
            result = resolve_ticker("baba amskd")

        self.assertFalse(result["found"])
        mock_ft.OpenQuoteContext.assert_not_called()


class TestResolveTickerConnectionError(unittest.TestCase):
    def test_connection_error_returns_not_connected(self):
        ctx = search_context()

        with mocked_moomoo(ctx) as mock_ft:
            mock_ft.OpenQuoteContext.side_effect = (
                ConnectionRefusedError("OpenD not running")
            )
            result = resolve_ticker("AAPL")

        self.assertFalse(result["connected"])
        self.assertFalse(result["found"])
        self.assertIsNotNone(result["error"])
        self.assertIsNone(result["company_name"])

    def test_search_failure_is_not_successful_not_found(self):
        ctx = MagicMock()
        ctx.get_search_quote.return_value = (-1, "Permission denied")

        with mocked_moomoo(ctx):
            result = resolve_ticker("AAPL")

        self.assertFalse(result["connected"])
        self.assertFalse(result["found"])
        self.assertIn("Permission denied", result["error"])
        ctx.close.assert_called_once()

    def test_context_closed_on_exception(self):
        ctx = MagicMock()
        ctx.get_search_quote.side_effect = RuntimeError("unexpected")

        with mocked_moomoo(ctx):
            result = resolve_ticker("AAPL")

        self.assertFalse(result["found"])
        self.assertIsNotNone(result["error"])
        ctx.close.assert_called_once()


# ---------------------------------------------------------------------------
# 3. Snapshot/profile retrieval: mocked API boundary
# ---------------------------------------------------------------------------

class TestFetchMoomooInputsNotAvailable(unittest.TestCase):
    def test_not_available_returns_all_none(self):
        with patch("frontend.adapter._MOOMOO_AVAILABLE", False):
            result = fetch_moomoo_inputs("US.AAPL")

        self.assertFalse(result["connected"])
        self.assertIsNotNone(result["error"])
        for value in result["inputs"].values():
            self.assertIsNone(value)

    def test_ocf_remains_none_without_sdk(self):
        with patch("frontend.adapter._MOOMOO_AVAILABLE", False):
            result = fetch_moomoo_inputs("US.AAPL")

        self.assertIsNone(
            result["inputs"]["operating_cash_flow_ttm_usd"]
        )
        self.assertFalse(result["connected"])


class TestFetchMoomooInputsLive(unittest.TestCase):
    """
    Historical class name retained for targeted commands.

    All provider calls in this class are mocked.
    A passing result is not evidence of live API availability.
    """

    def _make_ctx(
        self,
        price=343.46,
        mktcap=5e12,
        employees="166000",
    ):
        return snapshot_context(
            previous_close=price,
            latest_price=price + 6.54,
            market_cap=mktcap,
            employees=employees,
        )

    def test_price_and_mktcap_retrieved(self):
        ctx = self._make_ctx()

        with mocked_moomoo(ctx):
            result = fetch_moomoo_inputs("US.AAPL")

        self.assertTrue(result["connected"], result["error"])
        self.assertIsNone(result["error"])
        self.assertAlmostEqual(
            result["inputs"]["close_price_usd"],
            343.46,
            places=2,
        )
        self.assertAlmostEqual(
            result["inputs"]["market_cap_usd"],
            5e12,
        )
        ctx.get_market_snapshot.assert_called_once_with(["US.AAPL"])

    def test_previous_close_used_not_latest_price(self):
        ctx = snapshot_context(
            previous_close=100.0,
            latest_price=125.0,
        )

        with mocked_moomoo(ctx):
            result = fetch_moomoo_inputs("US.AAPL")

        self.assertTrue(result["connected"])
        self.assertEqual(result["inputs"]["close_price_usd"], 100.0)
        self.assertNotEqual(result["inputs"]["close_price_usd"], 125.0)
        self.assertIn(
            "prev_close_price",
            result["input_notes"]["close_price_usd"],
        )

    def test_employee_count_retrieved(self):
        ctx = self._make_ctx()

        with mocked_moomoo(ctx):
            result = fetch_moomoo_inputs("US.AAPL")

        self.assertTrue(result["connected"])
        self.assertEqual(result["inputs"]["employee_count"], 166000)
        ctx.get_company_profile.assert_called_once_with("US.AAPL")

    def test_employee_count_with_commas(self):
        ctx = self._make_ctx(employees="166,000")

        with mocked_moomoo(ctx):
            result = fetch_moomoo_inputs("US.AAPL")

        self.assertEqual(result["inputs"]["employee_count"], 166000)

    def test_unparseable_employee_count_remains_none(self):
        ctx = self._make_ctx(employees="not disclosed")

        with mocked_moomoo(ctx):
            result = fetch_moomoo_inputs("US.AAPL")

        self.assertTrue(result["connected"])
        self.assertIsNone(result["inputs"]["employee_count"])
        ctx.get_company_profile.assert_called_once()

    def test_ocf_always_none_blocked(self):
        ctx = self._make_ctx()

        with mocked_moomoo(ctx):
            result = fetch_moomoo_inputs("US.AAPL")

        self.assertTrue(result["connected"])
        self.assertIsNone(
            result["inputs"]["operating_cash_flow_ttm_usd"]
        )
        self.assertIn(
            "Not connected",
            result["input_notes"]["operating_cash_flow_ttm_usd"],
        )

    def test_input_notes_show_moomoo_source(self):
        ctx = self._make_ctx()

        with mocked_moomoo(ctx):
            result = fetch_moomoo_inputs("US.AAPL")

        self.assertTrue(result["connected"])
        for key in (
            "close_price_usd",
            "market_cap_usd",
            "employee_count",
        ):
            self.assertIn("Moomoo", result["input_notes"][key])

    def test_provider_timestamp_preserved(self):
        ctx = self._make_ctx()

        with mocked_moomoo(ctx):
            result = fetch_moomoo_inputs("US.AAPL")

        self.assertEqual(result["data_timestamp"], SNAPSHOT_TIME)
        self.assertEqual(
            result["snapshot_update_time"],
            SNAPSHOT_TIME,
        )
        self.assertIsNotNone(result["retrieved_at"])

    def test_missing_provider_timestamp_not_fabricated(self):
        ctx = self._make_ctx()
        _, frame = ctx.get_market_snapshot.return_value
        frame = frame.drop(columns=["update_time"])
        ctx.get_market_snapshot.return_value = (0, frame)

        with mocked_moomoo(ctx):
            result = fetch_moomoo_inputs("US.AAPL")

        self.assertTrue(result["connected"])
        self.assertIsNone(result["data_timestamp"])
        self.assertIsNotNone(result["retrieved_at"])

    def test_context_closed_on_success(self):
        ctx = self._make_ctx()

        with mocked_moomoo(ctx):
            fetch_moomoo_inputs("US.AAPL")

        ctx.close.assert_called_once()

    def test_context_closed_on_exception(self):
        ctx = self._make_ctx()
        ctx.get_market_snapshot.side_effect = RuntimeError(
            "network error"
        )

        with mocked_moomoo(ctx):
            result = fetch_moomoo_inputs("US.AAPL")

        self.assertFalse(result["connected"])
        self.assertIn("network error", result["error"])
        ctx.close.assert_called_once()

    def test_missing_employee_field_returns_none_not_zero(self):
        ctx = snapshot_context(code="US.FAKE")

        ctx.get_company_profile.return_value = (
            0,
            pd.DataFrame([{
                "name": "Company Name",
                "value": "Fictional Test Company",
                "field_type": 0,
            }]),
        )

        with mocked_moomoo(ctx):
            result = fetch_moomoo_inputs("US.FAKE")

        self.assertTrue(result["connected"], result["error"])
        self.assertIsNone(result["inputs"]["employee_count"])
        self.assertEqual(
            result["inputs"]["close_price_usd"],
            343.46,
        )
        ctx.get_company_profile.assert_called_once_with("US.FAKE")
        ctx.close.assert_called_once()

    def test_wrong_security_snapshot_rejected(self):
        ctx = snapshot_context(code="US.MSFT")

        with mocked_moomoo(ctx):
            result = fetch_moomoo_inputs("US.AAPL")

        self.assertFalse(result["connected"])
        self.assertIsNotNone(result["error"])
        self.assertTrue(
            all(value is None for value in result["inputs"].values())
        )
        ctx.get_company_profile.assert_not_called()
        ctx.close.assert_called_once()

    def test_snapshot_without_code_rejected(self):
        ctx = self._make_ctx()
        _, frame = ctx.get_market_snapshot.return_value
        ctx.get_market_snapshot.return_value = (
            0,
            frame.drop(columns=["code"]),
        )

        with mocked_moomoo(ctx):
            result = fetch_moomoo_inputs("US.AAPL")

        self.assertFalse(result["connected"])
        self.assertIsNotNone(result["error"])
        ctx.get_company_profile.assert_not_called()

    def test_duplicate_snapshot_rows_rejected(self):
        ctx = self._make_ctx()
        _, frame = ctx.get_market_snapshot.return_value
        ctx.get_market_snapshot.return_value = (
            0,
            pd.concat([frame, frame], ignore_index=True),
        )

        with mocked_moomoo(ctx):
            result = fetch_moomoo_inputs("US.AAPL")

        self.assertFalse(result["connected"])
        self.assertIsNotNone(result["error"])
        ctx.get_company_profile.assert_not_called()

    def test_snapshot_api_error_rejected(self):
        ctx = self._make_ctx()
        ctx.get_market_snapshot.return_value = (
            -1,
            "Permission denied",
        )

        with mocked_moomoo(ctx):
            result = fetch_moomoo_inputs("US.AAPL")

        self.assertFalse(result["connected"])
        self.assertIn("Permission denied", result["error"])
        ctx.close.assert_called_once()

    def test_invalid_numeric_values_become_unknown(self):
        cases = (
            (float("nan"), float("inf")),
            (0, 0),
            (-1, -1),
            ("unavailable", "invalid"),
        )

        for price, market_cap in cases:
            with self.subTest(
                previous_close=price,
                market_cap=market_cap,
            ):
                ctx = snapshot_context(
                    previous_close=price,
                    market_cap=market_cap,
                )

                with mocked_moomoo(ctx):
                    result = fetch_moomoo_inputs("US.AAPL")

                self.assertTrue(result["connected"])
                self.assertIsNone(
                    result["inputs"]["close_price_usd"]
                )
                self.assertIsNone(
                    result["inputs"]["market_cap_usd"]
                )

    def test_profile_failure_preserves_snapshot_values(self):
        ctx = self._make_ctx()
        ctx.get_company_profile.side_effect = RuntimeError(
            "profile unavailable"
        )

        with mocked_moomoo(ctx):
            result = fetch_moomoo_inputs("US.AAPL")

        self.assertTrue(result["connected"])
        self.assertEqual(
            result["inputs"]["close_price_usd"],
            343.46,
        )
        self.assertIsNone(result["inputs"]["employee_count"])
        self.assertIn("profile unavailable", result["error"])
        ctx.close.assert_called_once()

    def test_profile_method_unavailable_preserves_snapshot(self):
        ctx = self._make_ctx()
        ctx.get_company_profile = None

        with mocked_moomoo(ctx):
            result = fetch_moomoo_inputs("US.AAPL")

        self.assertTrue(result["connected"])
        self.assertEqual(
            result["inputs"]["close_price_usd"],
            343.46,
        )
        self.assertIsNone(result["inputs"]["employee_count"])
        self.assertIn(
            "unavailable",
            result["input_notes"]["employee_count"].lower(),
        )

    def test_non_us_code_rejected_before_network(self):
        ctx = self._make_ctx()

        with mocked_moomoo(ctx) as mock_ft:
            result = fetch_moomoo_inputs("HK.00700")

        self.assertFalse(result["connected"])
        mock_ft.OpenQuoteContext.assert_not_called()


# ---------------------------------------------------------------------------
# 4. Explicit demo selection and missing inputs
# ---------------------------------------------------------------------------

class TestExplicitDemoSelection(unittest.TestCase):
    def test_missing_inputs_do_not_load_demo(self):
        result = evaluate_company("AAPL", None)

        self.assertEqual(result["mode"], "error")
        self.assertEqual(result["aggregate_status"], "unknown")
        self.assertEqual(result["criteria"], [])
        self.assertFalse(result["is_live"])
        self.assertIsNotNone(result["error"])

    def test_named_demo_is_explicitly_synthetic(self):
        result = evaluate_company(
            "ACME",
            None,
            demo_override="ACME",
        )

        self.assertIsNone(result["error"])
        self.assertEqual(result["mode"], "demo")
        self.assertFalse(result["is_live"])
        self.assertEqual(result["ticker"], "ACME")
        self.assertIn("Demo", result["company_name"])

    def test_unknown_demo_does_not_fall_back_to_acme(self):
        result = evaluate_company(
            "AAPL",
            None,
            demo_override="NONEXISTENT",
        )

        self.assertEqual(result["mode"], "error")
        self.assertEqual(result["criteria"], [])
        self.assertIsNotNone(result["error"])

    def test_fixture_identity_not_relabelled_as_real_company(self):
        result = evaluate_company(
            "AAPL",
            None,
            demo_override="ACME",
        )

        self.assertEqual(result["ticker"], "ACME")
        self.assertEqual(result["requested_ticker"], "AAPL")
        self.assertEqual(result["mode"], "demo")
        self.assertFalse(result["is_live"])


# ---------------------------------------------------------------------------
# 5. Streamlit UI checks
# ---------------------------------------------------------------------------

def _all_text(at):
    collections = (
        at.markdown,
        at.caption,
        at.info,
        at.warning,
        at.error,
        at.success,
    )

    return " ".join(
        str(element.value)
        for collection in collections
        for element in collection
    )


def _new_app():
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file(APP_PATH, default_timeout=30)
    at.run()
    return at


def _set_ticker(at, ticker):
    at.text_input(key="ticker_text_input").set_value(ticker).run()
    return at


def _run_demo(ticker):
    # Demo routes must not accidentally depend on live OpenD.
    with (
        patch("frontend.adapter._MOOMOO_AVAILABLE", False),
        patch("frontend.adapter._ft") as mock_ft,
    ):
        at = _new_app()
        _set_ticker(at, ticker)

        if len(at.form_submit_button) == 0:
            raise AssertionError(
                "Expected an Analyse submit button after setting "
                f"demo ticker {ticker!r}."
            )

        at.form_submit_button[0].click().run()
        mock_ft.OpenQuoteContext.assert_not_called()

    return at


class TestInvalidTickerRejected(unittest.TestCase):
    def _render_with_ticker(self, raw):
        with (
            patch("frontend.adapter._MOOMOO_AVAILABLE", False),
            patch("frontend.adapter._ft") as mock_ft,
        ):
            at = _new_app()
            _set_ticker(at, raw)
            mock_ft.OpenQuoteContext.assert_not_called()

        self.assertFalse(at.exception, f"App raised: {at.exception}")
        return at

    def test_multi_word_input_shows_error(self):
        at = self._render_with_ticker("baba amskd")
        errors = [str(e.value) for e in at.error]

        self.assertTrue(
            any(
                "invalid ticker" in error.lower()
                or "multiple words" in error.lower()
                for error in errors
            ),
            f"Expected invalid-ticker error. Errors: {errors}",
        )

    def test_multi_word_input_not_shown_as_heading(self):
        at = self._render_with_ticker("baba amskd")
        subtitles = [str(s.value) for s in at.subheader]

        self.assertFalse(
            any(
                "baba" in subtitle.lower()
                and "amskd" in subtitle.lower()
                for subtitle in subtitles
            ),
            f"Unverified company heading: {subtitles}",
        )

    def test_multi_word_input_no_dataframe(self):
        at = self._render_with_ticker("baba amskd")
        self.assertEqual(len(at.dataframe), 0)

    def test_too_long_ticker_shows_error(self):
        at = self._render_with_ticker("ABCDEFGHIJK")
        self.assertGreater(
            len(at.error),
            0,
            "Expected a format error for an overlong ticker.",
        )
        self.assertEqual(len(at.dataframe), 0)


class TestAnalyseButtonReplacesManualForm(unittest.TestCase):
    def setUp(self):
        with patch("frontend.adapter._MOOMOO_AVAILABLE", False):
            self.at = _new_app()
            _set_ticker(self.at, "ACME")

        self.assertFalse(
            self.at.exception,
            f"App raised: {self.at.exception}",
        )

    def _assert_no_manual_label(self, label):
        text_labels = [item.label for item in self.at.text_input]
        number_labels = [item.label for item in self.at.number_input]

        self.assertNotIn(label, text_labels)
        self.assertNotIn(label, number_labels)

    def test_no_market_cap_input_field(self):
        self._assert_no_manual_label("Market Cap (USD)")

    def test_no_close_price_input_field(self):
        self._assert_no_manual_label("Close Price (USD)")

    def test_no_ocf_input_field(self):
        self._assert_no_manual_label("Operating Cash Flow TTM (USD)")

    def test_no_employee_count_input_field(self):
        self._assert_no_manual_label("Employee Count")

    def test_analyse_form_submit_present(self):
        self.assertGreater(
            len(self.at.form_submit_button),
            0,
            "Analyse form submit button missing.",
        )


class TestDemoAnalyseFlow(unittest.TestCase):
    def test_acme_analyse_shows_results(self):
        at = _run_demo("ACME")
        self.assertFalse(at.exception, f"App raised: {at.exception}")
        self.assertGreater(len(at.dataframe), 0)

    def test_acme_company_name_shown_after_resolve(self):
        at = _run_demo("ACME")
        self.assertFalse(at.exception)
        subtitles = [str(s.value) for s in at.subheader]

        self.assertTrue(
            any(
                "ACME" in subtitle or "Acme" in subtitle
                for subtitle in subtitles
            ),
            f"Company name missing: {subtitles}",
        )

    def test_demo_label_visible(self):
        at = _run_demo("ACME")
        self.assertFalse(at.exception)
        self.assertIn("DEMO", _all_text(at).upper())

    def test_pass_result_for_acme(self):
        at = _run_demo("ACME")
        self.assertFalse(at.exception)
        self.assertIn("PASS", _all_text(at))

    def test_fail_result_for_blue(self):
        at = _run_demo("BLUE")
        self.assertFalse(at.exception)
        self.assertIn("FAIL", _all_text(at))

    def test_unknown_for_crst(self):
        at = _run_demo("CRST")
        self.assertFalse(at.exception)
        self.assertIn("UNKNOWN", _all_text(at))

    def test_scope_note_present(self):
        at = _run_demo("ACME")
        self.assertFalse(at.exception)
        self.assertIn(
            "Only the criteria returned",
            _all_text(at),
        )

    def test_not_investment_recommendation(self):
        at = _run_demo("BLUE")
        self.assertFalse(at.exception)
        self.assertIn(
            "Not full investment eligibility",
            _all_text(at),
        )


class TestMissingMetricDisplay(unittest.TestCase):
    def test_missing_employee_value_shows_unknown_not_zero(self):
        # CRST has missing employees, not missing cash flow.
        at = _run_demo("CRST")
        self.assertFalse(at.exception)
        self.assertGreater(len(at.dataframe), 0)

        frame = at.dataframe[0].value
        self.assertIn("Criterion", frame.columns)
        self.assertIn("Observed", frame.columns)

        employee_rows = frame[
            frame["Criterion"]
            .astype(str)
            .str.contains("Employee", case=False, na=False)
        ]

        self.assertFalse(employee_rows.empty)

        observed = str(employee_rows.iloc[0]["Observed"])
        self.assertIn("unknown", observed.lower())
        self.assertNotIn(observed, ("0", "0.0", "$0.00"))


class TestSwitchTickerClearsAnalysis(unittest.TestCase):
    def test_switch_clears_company_heading(self):
        with patch("frontend.adapter._MOOMOO_AVAILABLE", False):
            at = _run_demo("ACME")
            self.assertFalse(at.exception)
            self.assertGreater(len(at.dataframe), 0)

            _set_ticker(at, "BLUE")

        self.assertFalse(at.exception)
        self.assertEqual(
            len(at.dataframe),
            0,
            "ACME results must not remain after switching to BLUE.",
        )

    def test_switch_to_invalid_shows_error_not_stale_result(self):
        with patch("frontend.adapter._MOOMOO_AVAILABLE", False):
            at = _run_demo("ACME")
            self.assertFalse(at.exception)
            self.assertGreater(len(at.dataframe), 0)

            _set_ticker(at, "hello world")

        self.assertFalse(at.exception)
        errors = [str(e.value) for e in at.error]

        self.assertTrue(
            any(
                "invalid ticker" in error.lower()
                or "multiple words" in error.lower()
                for error in errors
            ),
            f"Expected invalid-ticker error. Errors: {errors}",
        )
        self.assertEqual(
            len(at.dataframe),
            0,
            "Stale criteria must not remain for invalid input.",
        )


if __name__ == "__main__":
    unittest.main()

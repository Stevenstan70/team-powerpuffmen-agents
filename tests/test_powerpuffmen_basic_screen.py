"""
Unit tests for tools/powerpuffmen_basic_screen.py.

All tests call the underlying function via .fn() to stay self-contained
(no ADK runtime, no network, no cloud services).
"""

import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tools.powerpuffmen_basic_screen import powerpuffmen_basic_screen

# Synthetic baseline values that satisfy every rule
_GOOD = dict(
    market_cap_usd=10_000_000_000,       # USD 10B  → within 2B–100B
    close_price_usd=50.0,                # USD 50   → >= 10
    operating_cash_flow_ttm_usd=500_000, # positive → > 0
    employee_count=200,                  # 200      → >= 20
)

fn = powerpuffmen_basic_screen.fn


def _rule(result, name):
    """Return the rule dict with the given rule_name from a screen result."""
    return next(r for r in result["rules"] if r["rule_name"] == name)


class TestAllPass(unittest.TestCase):
    def test_aggregate_pass(self):
        result = fn(**_GOOD)
        self.assertEqual(result["basic_screen_status"], "PASS")

    def test_all_rules_pass(self):
        result = fn(**_GOOD)
        for rule in result["rules"]:
            self.assertEqual(rule["status"], "PASS", rule["rule_name"])

    def test_scope_note_present(self):
        result = fn(**_GOOD)
        self.assertIn("scope_note", result)
        self.assertIn("four screening rules", result["scope_note"])

    def test_four_rules_returned(self):
        result = fn(**_GOOD)
        self.assertEqual(len(result["rules"]), 4)


class TestMarketCapBoundaries(unittest.TestCase):
    def test_lower_boundary_inclusive(self):
        """USD 2B exactly must PASS."""
        result = fn(**{**_GOOD, "market_cap_usd": 2_000_000_000})
        self.assertEqual(_rule(result, "market_cap_range")["status"], "PASS")
        self.assertEqual(result["basic_screen_status"], "PASS")

    def test_upper_boundary_inclusive(self):
        """USD 100B exactly must PASS."""
        result = fn(**{**_GOOD, "market_cap_usd": 100_000_000_000})
        self.assertEqual(_rule(result, "market_cap_range")["status"], "PASS")
        self.assertEqual(result["basic_screen_status"], "PASS")

    def test_just_below_lower_boundary(self):
        """USD 1.99…B must FAIL."""
        result = fn(**{**_GOOD, "market_cap_usd": 1_999_999_999})
        self.assertEqual(_rule(result, "market_cap_range")["status"], "FAIL")
        self.assertEqual(result["basic_screen_status"], "FAIL")

    def test_just_above_upper_boundary(self):
        """USD 100B + 1 must FAIL."""
        result = fn(**{**_GOOD, "market_cap_usd": 100_000_000_001})
        self.assertEqual(_rule(result, "market_cap_range")["status"], "FAIL")
        self.assertEqual(result["basic_screen_status"], "FAIL")


class TestPriceBoundary(unittest.TestCase):
    def test_price_exactly_10(self):
        """USD 10.00 exactly must PASS."""
        result = fn(**{**_GOOD, "close_price_usd": 10.0})
        self.assertEqual(_rule(result, "min_close_price")["status"], "PASS")
        self.assertEqual(result["basic_screen_status"], "PASS")

    def test_price_below_10(self):
        """USD 9.99 must FAIL."""
        result = fn(**{**_GOOD, "close_price_usd": 9.99})
        self.assertEqual(_rule(result, "min_close_price")["status"], "FAIL")
        self.assertEqual(result["basic_screen_status"], "FAIL")


class TestEmployeeBoundary(unittest.TestCase):
    def test_employee_count_exactly_20(self):
        """Exactly 20 employees must PASS."""
        result = fn(**{**_GOOD, "employee_count": 20})
        self.assertEqual(_rule(result, "min_employee_count")["status"], "PASS")
        self.assertEqual(result["basic_screen_status"], "PASS")

    def test_employee_count_below_20(self):
        """19 employees must FAIL."""
        result = fn(**{**_GOOD, "employee_count": 19})
        self.assertEqual(_rule(result, "min_employee_count")["status"], "FAIL")
        self.assertEqual(result["basic_screen_status"], "FAIL")


class TestOperatingCashFlow(unittest.TestCase):
    def test_zero_cash_flow_fails(self):
        """Zero operating cash flow must FAIL (rule requires strictly > 0)."""
        result = fn(**{**_GOOD, "operating_cash_flow_ttm_usd": 0})
        self.assertEqual(_rule(result, "positive_operating_cash_flow")["status"], "FAIL")
        self.assertEqual(result["basic_screen_status"], "FAIL")

    def test_negative_cash_flow_fails(self):
        result = fn(**{**_GOOD, "operating_cash_flow_ttm_usd": -1})
        self.assertEqual(_rule(result, "positive_operating_cash_flow")["status"], "FAIL")

    def test_positive_cash_flow_passes(self):
        result = fn(**{**_GOOD, "operating_cash_flow_ttm_usd": 1})
        self.assertEqual(_rule(result, "positive_operating_cash_flow")["status"], "PASS")


class TestIndependentRuleFailures(unittest.TestCase):
    """Each rule must fail independently while all others pass."""

    def test_only_market_cap_fails(self):
        result = fn(**{**_GOOD, "market_cap_usd": 1_000_000})
        self.assertEqual(_rule(result, "market_cap_range")["status"], "FAIL")
        self.assertEqual(_rule(result, "min_close_price")["status"], "PASS")
        self.assertEqual(_rule(result, "positive_operating_cash_flow")["status"], "PASS")
        self.assertEqual(_rule(result, "min_employee_count")["status"], "PASS")
        self.assertEqual(result["basic_screen_status"], "FAIL")

    def test_only_price_fails(self):
        result = fn(**{**_GOOD, "close_price_usd": 5.0})
        self.assertEqual(_rule(result, "min_close_price")["status"], "FAIL")
        self.assertEqual(_rule(result, "market_cap_range")["status"], "PASS")
        self.assertEqual(_rule(result, "positive_operating_cash_flow")["status"], "PASS")
        self.assertEqual(_rule(result, "min_employee_count")["status"], "PASS")
        self.assertEqual(result["basic_screen_status"], "FAIL")

    def test_only_cash_flow_fails(self):
        result = fn(**{**_GOOD, "operating_cash_flow_ttm_usd": 0})
        self.assertEqual(_rule(result, "positive_operating_cash_flow")["status"], "FAIL")
        self.assertEqual(_rule(result, "market_cap_range")["status"], "PASS")
        self.assertEqual(_rule(result, "min_close_price")["status"], "PASS")
        self.assertEqual(_rule(result, "min_employee_count")["status"], "PASS")
        self.assertEqual(result["basic_screen_status"], "FAIL")

    def test_only_employees_fails(self):
        result = fn(**{**_GOOD, "employee_count": 5})
        self.assertEqual(_rule(result, "min_employee_count")["status"], "FAIL")
        self.assertEqual(_rule(result, "market_cap_range")["status"], "PASS")
        self.assertEqual(_rule(result, "min_close_price")["status"], "PASS")
        self.assertEqual(_rule(result, "positive_operating_cash_flow")["status"], "PASS")
        self.assertEqual(result["basic_screen_status"], "FAIL")


class TestMissingInputs(unittest.TestCase):
    def test_all_missing_is_unverified(self):
        result = fn()
        self.assertEqual(result["basic_screen_status"], "UNVERIFIED")
        for rule in result["rules"]:
            self.assertEqual(rule["status"], "UNVERIFIED", rule["rule_name"])
            self.assertIsNone(rule["observed_value"])

    def test_missing_market_cap_unverified(self):
        result = fn(
            close_price_usd=50.0,
            operating_cash_flow_ttm_usd=100_000,
            employee_count=50,
        )
        self.assertEqual(_rule(result, "market_cap_range")["status"], "UNVERIFIED")
        self.assertEqual(result["basic_screen_status"], "UNVERIFIED")

    def test_missing_price_unverified(self):
        result = fn(
            market_cap_usd=10_000_000_000,
            operating_cash_flow_ttm_usd=100_000,
            employee_count=50,
        )
        self.assertEqual(_rule(result, "min_close_price")["status"], "UNVERIFIED")
        self.assertEqual(result["basic_screen_status"], "UNVERIFIED")

    def test_missing_cash_flow_unverified(self):
        result = fn(
            market_cap_usd=10_000_000_000,
            close_price_usd=50.0,
            employee_count=50,
        )
        self.assertEqual(_rule(result, "positive_operating_cash_flow")["status"], "UNVERIFIED")
        self.assertEqual(result["basic_screen_status"], "UNVERIFIED")

    def test_missing_employees_unverified(self):
        result = fn(
            market_cap_usd=10_000_000_000,
            close_price_usd=50.0,
            operating_cash_flow_ttm_usd=100_000,
        )
        self.assertEqual(_rule(result, "min_employee_count")["status"], "UNVERIFIED")
        self.assertEqual(result["basic_screen_status"], "UNVERIFIED")


class TestFailPrecedenceOverUnverified(unittest.TestCase):
    """A FAIL on any rule must override UNVERIFIED on other rules."""

    def test_one_fail_one_unverified_is_fail(self):
        # market cap missing (UNVERIFIED), price below threshold (FAIL)
        result = fn(
            close_price_usd=1.0,   # FAIL
            operating_cash_flow_ttm_usd=100_000,
            employee_count=50,
            # market_cap_usd omitted → UNVERIFIED
        )
        self.assertEqual(result["basic_screen_status"], "FAIL")

    def test_fail_beats_all_unverified(self):
        # only cash flow provided and it fails; all others unverified
        result = fn(operating_cash_flow_ttm_usd=0)
        self.assertEqual(result["basic_screen_status"], "FAIL")


class TestInvalidInputRejection(unittest.TestCase):
    """Invalid inputs must raise ValueError."""

    def test_boolean_market_cap_rejected(self):
        with self.assertRaises(ValueError):
            fn(market_cap_usd=True)

    def test_boolean_price_rejected(self):
        with self.assertRaises(ValueError):
            fn(close_price_usd=False)

    def test_string_value_rejected(self):
        with self.assertRaises(ValueError):
            fn(close_price_usd="50")

    def test_nan_rejected(self):
        import math
        with self.assertRaises(ValueError):
            fn(market_cap_usd=float("nan"))

    def test_positive_infinity_rejected(self):
        with self.assertRaises(ValueError):
            fn(operating_cash_flow_ttm_usd=float("inf"))

    def test_negative_infinity_rejected(self):
        with self.assertRaises(ValueError):
            fn(operating_cash_flow_ttm_usd=float("-inf"))

    def test_fractional_employee_count_rejected(self):
        with self.assertRaises(ValueError):
            fn(employee_count=20.5)

    def test_none_values_are_not_invalid(self):
        """Explicit None must be treated as missing, not invalid."""
        result = fn(
            market_cap_usd=None,
            close_price_usd=None,
            operating_cash_flow_ttm_usd=None,
            employee_count=None,
        )
        self.assertEqual(result["basic_screen_status"], "UNVERIFIED")


if __name__ == "__main__":
    unittest.main()

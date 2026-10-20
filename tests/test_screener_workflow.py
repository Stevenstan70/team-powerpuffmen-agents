"""
tests/test_screener_workflow.py

Tests for the safety-updated frontend adapter.

Coverage:
- Explicit demo selection and rejection of implicit demo fallback.
- Supplied/live/cached provenance labels.
- Screening outcomes and error handling.
- Actual adapter change detection.
- Policy, company, currency, and mode comparison safeguards.
- A test-only approval reference model.
- Simulated-change fixture integrity and result isolation.

No live Moomoo or Orchestrate requests are required.

IMPORTANT:
ApprovalStateMachine below is a reference model, not an import of
the production Streamlit approval implementation. Its tests validate
the model only. Production approval still needs UI/integration tests.
"""

from __future__ import annotations

import copy
import os
import sys
import unittest
from unittest.mock import patch


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from frontend.adapter import (
    evaluate_company,
    analyse_company,
    check_for_changes,
    get_simulated_change_scenario,
    _rule_to_criterion,
    _aggregate_from_criteria,
)


GOOD_INPUTS = {
    "market_cap_usd": 15_000_000_000,
    "close_price_usd": 42.50,
    "operating_cash_flow_ttm_usd": 850_000_000,
    "employee_count": 3200,
}

TS_1 = "2025-06-01T12:00:00Z"
TS_2 = "2025-06-02T12:00:00Z"


def _criterion(rule_name, observed, status):
    thresholds = {
        "market_cap_range":
            "2,000,000,000 <= x <= 100,000,000,000",
        "min_close_price": "x >= 10",
        "positive_operating_cash_flow": "x > 0",
        "min_employee_count": "x >= 20",
    }

    status_map = {
        "pass": "PASS",
        "fail": "FAIL",
        "unknown": "UNVERIFIED",
    }

    return {
        "rule_name": rule_name,
        "observed_value": observed,
        "threshold": thresholds.get(rule_name, "?"),
        "status": status_map.get(status, str(status).upper()),
        "explanation": f"Test rule {rule_name}",
    }


def _make_entry(ticker, evaluation):
    return {
        "ticker": ticker,
        "saved_at": TS_1,
        "evaluation": copy.deepcopy(evaluation),
    }


def _evaluate(ticker="TST", inputs=None, **kwargs):
    """Evaluate explicit synthetic test inputs, never implicit demo."""
    values = dict(GOOD_INPUTS) if inputs is None else dict(inputs)

    return evaluate_company(
        ticker,
        values,
        **kwargs,
    )


def _by_id(evaluation, criterion_id):
    return next(
        c for c in evaluation["criteria"]
        if c["id"] == criterion_id
    )


class EvaluationTestCase(unittest.TestCase):
    """Helpers shared by tests that need the real local screening tool."""

    def make_evaluation(self, ticker="TST", inputs=None, **kwargs):
        result = _evaluate(ticker, inputs, **kwargs)
        self.assertIsNone(result["error"], result["error"])
        self.assertEqual(len(result["criteria"]), 4)
        return result

    def compare_inputs(self, old_inputs=None, new_inputs=None):
        old_values = (
            dict(GOOD_INPUTS)
            if old_inputs is None
            else dict(old_inputs)
        )
        new_values = (
            dict(old_values)
            if new_inputs is None
            else dict(new_inputs)
        )

        baseline = self.make_evaluation(
            "TST",
            old_values,
            data_timestamp=TS_1,
        )

        result = check_for_changes(
            "TST",
            _make_entry("TST", baseline),
            new_values,
            source_mode="supplied",
            data_timestamp=TS_2,
        )

        self.assertIsNone(result["error"], result["error"])
        self.assertTrue(
            result["comparable"],
            result["not_comparable_reason"],
        )

        return result


# ---------------------------------------------------------------------------
# 1. Explicit demo behaviour
# ---------------------------------------------------------------------------

class TestEvaluateCompanyDemo(unittest.TestCase):
    def test_acme_demo_mode(self):
        result = evaluate_company(
            "ACME",
            None,
            demo_override="ACME",
        )

        self.assertIsNone(result["error"])
        self.assertEqual(result["mode"], "demo")
        self.assertFalse(result["is_live"])
        self.assertEqual(result["aggregate_status"], "pass")

    def test_blue_demo_fail(self):
        result = evaluate_company(
            "BLUE",
            None,
            demo_override="BLUE",
        )

        self.assertIsNone(result["error"])
        self.assertEqual(result["aggregate_status"], "fail")
        self.assertFalse(result["is_live"])

    def test_crst_demo_unknown(self):
        result = evaluate_company(
            "CRST",
            None,
            demo_override="CRST",
        )

        self.assertIsNone(result["error"])
        self.assertEqual(result["aggregate_status"], "unknown")
        self.assertNotEqual(result["aggregate_status"], "fail")

    def test_criteria_list_not_empty(self):
        result = evaluate_company(
            "ACME",
            None,
            demo_override="ACME",
        )

        self.assertEqual(len(result["criteria"]), 4)

    def test_criteria_have_required_keys(self):
        result = evaluate_company(
            "ACME",
            None,
            demo_override="ACME",
        )

        required_keys = {
            "id",
            "label",
            "operator",
            "threshold",
            "unit",
            "reporting_period",
            "observed_value",
            "observed_fmt",
            "status",
        }

        for criterion in result["criteria"]:
            self.assertTrue(
                required_keys.issubset(criterion),
                f"Missing keys in {criterion}",
            )

    def test_unknown_demo_fixture_is_rejected(self):
        result = evaluate_company(
            "XYZ",
            None,
            demo_override="NONEXISTENT",
        )

        self.assertEqual(result["mode"], "error")
        self.assertIsNotNone(result["error"])
        self.assertEqual(result["criteria"], [])
        self.assertEqual(result["aggregate_status"], "unknown")
        self.assertFalse(result["is_live"])

    def test_none_inputs_returns_error_not_demo(self):
        result = evaluate_company("AAPL", None)

        self.assertEqual(result["mode"], "error")
        self.assertEqual(result["criteria"], [])
        self.assertEqual(result["aggregate_status"], "unknown")
        self.assertFalse(result["is_live"])
        self.assertIn(
            "No screening inputs supplied",
            result["error"],
        )

    def test_demo_does_not_call_screening_backend(self):
        with patch("frontend.adapter._screen_fn") as screen:
            result = evaluate_company(
                "ACME",
                None,
                demo_override="ACME",
            )

        self.assertEqual(result["mode"], "demo")
        screen.assert_not_called()

    def test_demo_observation_time_not_replaced_by_now(self):
        result = evaluate_company(
            "ACME",
            None,
            demo_override="ACME",
        )

        self.assertEqual(
            result["data_timestamp"],
            "2025-01-01T00:00:00Z",
        )
        self.assertIsNotNone(result["evaluated_at"])


# ---------------------------------------------------------------------------
# 2. Local screening and provenance
# ---------------------------------------------------------------------------

class TestEvaluateCompanyLive(EvaluationTestCase):
    """
    Historical class name retained.

    These tests exercise the local screening function.
    Explicit source_mode='live' tests label propagation only:
    it is not evidence of a real provider request.
    """

    def test_supplied_all_pass(self):
        result = self.make_evaluation()

        self.assertEqual(result["mode"], "supplied")
        self.assertFalse(result["is_live"])
        self.assertEqual(result["aggregate_status"], "pass")

    def test_explicit_live_label_preserved(self):
        result = self.make_evaluation(
            source_mode="live",
            data_timestamp=TS_1,
            company_name="Synthetic Test Company",
        )

        self.assertEqual(result["mode"], "live")
        self.assertTrue(result["is_live"])
        self.assertEqual(result["data_timestamp"], TS_1)
        self.assertEqual(
            result["company_name"],
            "Synthetic Test Company",
        )

    def test_cached_inputs_not_labelled_live(self):
        result = self.make_evaluation(
            source_mode="cached",
            data_timestamp=TS_1,
        )

        self.assertEqual(result["mode"], "cached")
        self.assertFalse(result["is_live"])
        self.assertEqual(result["data_timestamp"], TS_1)

    def test_ocf_fail(self):
        inputs = {
            **GOOD_INPUTS,
            "operating_cash_flow_ttm_usd": -1,
        }
        result = self.make_evaluation(inputs=inputs)

        self.assertEqual(result["aggregate_status"], "fail")
        self.assertEqual(
            _by_id(
                result,
                "positive_operating_cash_flow",
            )["status"],
            "fail",
        )

    def test_zero_ocf_fails_strict_positive_rule(self):
        inputs = {
            **GOOD_INPUTS,
            "operating_cash_flow_ttm_usd": 0,
        }
        result = self.make_evaluation(inputs=inputs)

        self.assertEqual(
            _by_id(
                result,
                "positive_operating_cash_flow",
            )["status"],
            "fail",
        )

    def test_missing_employee_is_unknown_not_fail(self):
        inputs = {**GOOD_INPUTS, "employee_count": None}
        result = self.make_evaluation(inputs=inputs)
        employee = _by_id(result, "min_employee_count")

        self.assertEqual(employee["status"], "unknown")
        self.assertIsNone(employee["observed_value"])
        self.assertEqual(result["aggregate_status"], "unknown")

    def test_missing_ocf_is_unknown_not_fail(self):
        inputs = {
            **GOOD_INPUTS,
            "operating_cash_flow_ttm_usd": None,
        }
        result = self.make_evaluation(inputs=inputs)
        cash_flow = _by_id(
            result,
            "positive_operating_cash_flow",
        )

        self.assertEqual(cash_flow["status"], "unknown")
        self.assertIsNone(cash_flow["observed_value"])
        self.assertEqual(result["aggregate_status"], "unknown")

    def test_invalid_numbers_become_unknown(self):
        for invalid in (
            float("nan"),
            float("inf"),
            "unavailable",
        ):
            with self.subTest(value=invalid):
                inputs = {
                    **GOOD_INPUTS,
                    "market_cap_usd": invalid,
                }
                result = self.make_evaluation(inputs=inputs)
                criterion = _by_id(result, "market_cap_range")

                self.assertIsNone(criterion["observed_value"])
                self.assertEqual(criterion["status"], "unknown")

    def test_input_dictionary_not_modified(self):
        inputs = dict(GOOD_INPUTS)
        original = copy.deepcopy(inputs)

        self.make_evaluation(inputs=inputs)

        self.assertEqual(inputs, original)

    def test_unspecified_observation_time_stays_unknown(self):
        result = self.make_evaluation()

        self.assertIsNone(result["data_timestamp"])
        self.assertIsNotNone(result["evaluated_at"])

    def test_invalid_source_mode_returns_error(self):
        result = evaluate_company(
            "TST",
            dict(GOOD_INPUTS),
            source_mode="invented",
        )

        self.assertEqual(result["mode"], "error")
        self.assertIsNotNone(result["error"])
        self.assertEqual(result["criteria"], [])

    def test_invalid_inputs_type_returns_error(self):
        result = evaluate_company("TST", ["not", "a", "dict"])

        self.assertEqual(result["mode"], "error")
        self.assertIsNotNone(result["error"])


class TestEvaluateCompanyErrorPaths(unittest.TestCase):
    def test_unavailable_backend_returns_error(self):
        with patch(
            "frontend.adapter._SCREEN_BACKEND_AVAILABLE",
            False,
        ):
            result = evaluate_company(
                "TST",
                dict(GOOD_INPUTS),
            )

        self.assertEqual(result["mode"], "error")
        self.assertIsNotNone(result["error"])
        self.assertEqual(result["criteria"], [])
        self.assertEqual(result["aggregate_status"], "unknown")

    def test_backend_exception_returns_error(self):
        with (
            patch(
                "frontend.adapter._SCREEN_BACKEND_AVAILABLE",
                True,
            ),
            patch(
                "frontend.adapter._screen_fn",
                side_effect=RuntimeError("test backend failure"),
            ),
        ):
            result = evaluate_company(
                "TST",
                dict(GOOD_INPUTS),
            )

        self.assertEqual(result["mode"], "error")
        self.assertIn("test backend failure", result["error"])
        self.assertEqual(result["criteria"], [])

    def test_empty_backend_rules_rejected(self):
        with (
            patch(
                "frontend.adapter._SCREEN_BACKEND_AVAILABLE",
                True,
            ),
            patch(
                "frontend.adapter._screen_fn",
                return_value={"rules": []},
            ),
        ):
            result = evaluate_company(
                "TST",
                dict(GOOD_INPUTS),
            )

        self.assertEqual(result["mode"], "error")
        self.assertEqual(result["aggregate_status"], "unknown")


class TestEvaluateCompanyTicker(EvaluationTestCase):
    def test_supplied_ticker_preserved(self):
        result = self.make_evaluation("MYMOO")

        self.assertEqual(result["ticker"], "MYMOO")

    def test_demo_identity_preserved_separately(self):
        result = evaluate_company(
            "MYMOO",
            None,
            demo_override="ACME",
        )

        self.assertEqual(result["ticker"], "ACME")
        self.assertEqual(result["requested_ticker"], "MYMOO")
        self.assertIn("Demo", result["company_name"])

    def test_switching_ticker_uses_independent_results(self):
        first = self.make_evaluation("T1")
        second = self.make_evaluation(
            "T2",
            {
                **GOOD_INPUTS,
                "operating_cash_flow_ttm_usd": -1,
            },
        )

        self.assertEqual(first["ticker"], "T1")
        self.assertEqual(second["ticker"], "T2")
        self.assertEqual(first["aggregate_status"], "pass")
        self.assertEqual(second["aggregate_status"], "fail")


# ---------------------------------------------------------------------------
# 3. Formatting and aggregation
# ---------------------------------------------------------------------------

class TestCriterionAndAggregate(unittest.TestCase):
    def test_missing_value_overrides_incorrect_pass(self):
        criterion = _rule_to_criterion(
            _criterion("min_employee_count", None, "pass")
        )

        self.assertEqual(criterion["status"], "unknown")
        self.assertEqual(criterion["observed_fmt"], "Unknown")

    def test_empty_criteria_is_unknown(self):
        self.assertEqual(_aggregate_from_criteria([]), "unknown")

    def test_all_pass_is_pass(self):
        self.assertEqual(
            _aggregate_from_criteria([
                {"status": "pass"},
                {"status": "pass"},
            ]),
            "pass",
        )

    def test_unknown_prevents_all_pass(self):
        self.assertEqual(
            _aggregate_from_criteria([
                {"status": "pass"},
                {"status": "unknown"},
            ]),
            "unknown",
        )

    def test_confirmed_failure_is_fail_even_with_unknown(self):
        self.assertEqual(
            _aggregate_from_criteria([
                {"status": "fail"},
                {"status": "unknown"},
            ]),
            "fail",
        )

    def test_unrecognised_status_is_unknown(self):
        self.assertEqual(
            _aggregate_from_criteria([{"status": "unexpected"}]),
            "unknown",
        )


# ---------------------------------------------------------------------------
# 4. Agent connection remains explicitly unavailable
# ---------------------------------------------------------------------------

class TestAnalyseCompany(unittest.TestCase):
    def test_returns_not_connected(self):
        result = analyse_company("ACME", {})

        self.assertFalse(result["connected"])
        self.assertIsNone(result["content"])
        self.assertIsNotNone(result["error"])

    def test_error_message_is_informative(self):
        result = analyse_company("ACME", {})

        self.assertIn("not", result["error"].lower())
        self.assertGreater(len(result["error"]), 10)

    def test_no_fabricated_output(self):
        result = analyse_company("ACME", {})

        self.assertFalse(result["connected"])
        self.assertIsNone(result["content"])


# ---------------------------------------------------------------------------
# 5. Actual adapter comparison logic
# ---------------------------------------------------------------------------

class TestCheckForChangesNoChange(EvaluationTestCase):
    def test_identical_eval_produces_no_changes(self):
        result = self.compare_inputs()

        self.assertEqual(result["changes"], [])
        self.assertEqual(
            result["new_evaluation"]["aggregate_status"],
            "pass",
        )


class TestCheckForChangesValueChanged(EvaluationTestCase):
    def test_value_change_same_status(self):
        result = self.compare_inputs(
            new_inputs={
                **GOOD_INPUTS,
                "market_cap_usd": 12_000_000_000,
            }
        )

        self.assertEqual(len(result["changes"]), 1)
        change = result["changes"][0]

        self.assertEqual(change["criterion_id"], "market_cap_range")
        self.assertEqual(change["change_type"], "value_changed")
        self.assertEqual(change["old_status"], "pass")
        self.assertEqual(change["new_status"], "pass")


class TestCheckForChangesStatusTransition(EvaluationTestCase):
    def test_pass_to_fail_detected(self):
        result = self.compare_inputs(
            new_inputs={
                **GOOD_INPUTS,
                "operating_cash_flow_ttm_usd": -100_000,
            }
        )

        self.assertEqual(len(result["changes"]), 1)
        change = result["changes"][0]

        self.assertEqual(change["change_type"], "status_transition")
        self.assertEqual(change["old_status"], "pass")
        self.assertEqual(change["new_status"], "fail")

    def test_fail_to_pass_detected(self):
        result = self.compare_inputs(
            old_inputs={
                **GOOD_INPUTS,
                "close_price_usd": 5.0,
            },
            new_inputs=dict(GOOD_INPUTS),
        )

        self.assertEqual(len(result["changes"]), 1)
        change = result["changes"][0]

        self.assertEqual(change["change_type"], "status_transition")
        self.assertEqual(change["old_status"], "fail")
        self.assertEqual(change["new_status"], "pass")


class TestCheckForChangesMissingData(EvaluationTestCase):
    def test_missing_data_is_data_unavailable_not_fail(self):
        result = self.compare_inputs(
            new_inputs={
                **GOOD_INPUTS,
                "employee_count": None,
            }
        )

        self.assertEqual(len(result["changes"]), 1)
        change = result["changes"][0]

        self.assertEqual(change["change_type"], "data_unavailable")
        self.assertEqual(change["new_status"], "unknown")
        self.assertNotEqual(change["new_status"], "fail")

    def test_missing_displayed_as_unavailable_not_zero(self):
        result = self.compare_inputs(
            new_inputs={
                **GOOD_INPUTS,
                "employee_count": None,
            }
        )
        display = result["changes"][0]["new_value_fmt"]

        self.assertNotIn(display, ("0", "$0.00", "0.0"))
        self.assertIn("unavailable", display.lower())

    def test_data_becoming_available_detected(self):
        result = self.compare_inputs(
            old_inputs={
                **GOOD_INPUTS,
                "employee_count": None,
            },
            new_inputs=dict(GOOD_INPUTS),
        )

        self.assertEqual(len(result["changes"]), 1)
        change = result["changes"][0]

        self.assertEqual(change["change_type"], "status_transition")
        self.assertEqual(change["old_status"], "unknown")
        self.assertEqual(change["new_status"], "pass")


class TestCheckForChangesCriteriaChanged(EvaluationTestCase):
    def setUp(self):
        self.baseline = self.make_evaluation("TST")

    def compare_modified_baseline(self, evaluation):
        return check_for_changes(
            "TST",
            _make_entry("TST", evaluation),
            dict(GOOD_INPUTS),
        )

    def test_different_criteria_sets_not_comparable(self):
        baseline = copy.deepcopy(self.baseline)
        baseline["criteria"].pop()

        result = self.compare_modified_baseline(baseline)

        self.assertFalse(result["comparable"])
        self.assertEqual(result["changes"], [])
        self.assertIsNotNone(result["not_comparable_reason"])

    def test_same_policy_is_comparable(self):
        result = self.compare_modified_baseline(self.baseline)

        self.assertTrue(
            result["comparable"],
            result["not_comparable_reason"],
        )

    def test_changed_threshold_not_comparable(self):
        baseline = copy.deepcopy(self.baseline)
        baseline["criteria"][0]["threshold"] = "x >= 1"

        result = self.compare_modified_baseline(baseline)

        self.assertFalse(result["comparable"])
        self.assertEqual(result["changes"], [])

    def test_changed_unit_not_comparable(self):
        baseline = copy.deepcopy(self.baseline)
        baseline["criteria"][0]["unit"] = "USD millions"

        result = self.compare_modified_baseline(baseline)

        self.assertFalse(result["comparable"])

    def test_changed_operator_not_comparable(self):
        baseline = copy.deepcopy(self.baseline)
        baseline["criteria"][0]["operator"] = ">"

        result = self.compare_modified_baseline(baseline)

        self.assertFalse(result["comparable"])

    def test_changed_reporting_period_not_comparable(self):
        baseline = copy.deepcopy(self.baseline)
        baseline["criteria"][0]["reporting_period"] = "prior year"

        result = self.compare_modified_baseline(baseline)

        self.assertFalse(result["comparable"])

    def test_changed_version_not_comparable(self):
        baseline = copy.deepcopy(self.baseline)
        baseline["criteria_version"] = "different-policy"

        result = self.compare_modified_baseline(baseline)

        self.assertFalse(result["comparable"])

    def test_missing_version_not_comparable(self):
        baseline = copy.deepcopy(self.baseline)
        baseline.pop("criteria_version")

        result = self.compare_modified_baseline(baseline)

        self.assertFalse(result["comparable"])

    def test_duplicate_ids_not_comparable(self):
        baseline = copy.deepcopy(self.baseline)
        baseline["criteria"].append(
            copy.deepcopy(baseline["criteria"][0])
        )

        result = self.compare_modified_baseline(baseline)

        self.assertFalse(result["comparable"])

    def test_changed_label_alone_does_not_change_policy(self):
        baseline = copy.deepcopy(self.baseline)
        baseline["criteria"][0]["label"] = "Older display label"

        result = self.compare_modified_baseline(baseline)

        self.assertTrue(
            result["comparable"],
            result["not_comparable_reason"],
        )
        self.assertEqual(result["changes"], [])


class TestCheckForChangesViaAdapter(EvaluationTestCase):
    def test_missing_inputs_returns_structure_and_error(self):
        baseline = evaluate_company(
            "ACME",
            None,
            demo_override="ACME",
        )

        result = check_for_changes(
            "ACME",
            _make_entry("ACME", baseline),
            None,
        )

        required = {
            "changes",
            "checked_at",
            "comparable",
            "new_evaluation",
            "error",
            "not_comparable_reason",
        }

        self.assertTrue(required.issubset(result))
        self.assertFalse(result["comparable"])
        self.assertEqual(result["changes"], [])
        self.assertIn(
            "No screening inputs supplied",
            result["error"],
        )

    def test_comparable_flag_true_for_same_criteria(self):
        result = self.compare_inputs()

        self.assertTrue(result["comparable"])
        self.assertEqual(result["changes"], [])

    def test_demo_baseline_not_compared_with_supplied_data(self):
        baseline = evaluate_company(
            "ACME",
            None,
            demo_override="ACME",
        )

        result = check_for_changes(
            "ACME",
            _make_entry("ACME", baseline),
            dict(GOOD_INPUTS),
        )

        self.assertFalse(result["comparable"])
        self.assertIn(
            "mode",
            result["not_comparable_reason"].lower(),
        )

    def test_different_company_not_comparable(self):
        baseline = self.make_evaluation("FIRST")

        result = check_for_changes(
            "SECOND",
            _make_entry("FIRST", baseline),
            dict(GOOD_INPUTS),
        )

        self.assertFalse(result["comparable"])
        self.assertIn(
            "company",
            result["not_comparable_reason"].lower(),
        )

    def test_changed_currency_not_comparable(self):
        baseline = self.make_evaluation("TST")
        baseline["currency"] = "HKD"

        result = check_for_changes(
            "TST",
            _make_entry("TST", baseline),
            dict(GOOD_INPUTS),
        )

        self.assertFalse(result["comparable"])

    def test_invalid_baseline_rejected(self):
        result = check_for_changes(
            "TST",
            None,
            dict(GOOD_INPUTS),
        )

        self.assertFalse(result["comparable"])
        self.assertIsNotNone(result["not_comparable_reason"])

    def test_baseline_not_mutated(self):
        baseline = self.make_evaluation("TST")
        entry = _make_entry("TST", baseline)
        before = copy.deepcopy(entry)

        result = check_for_changes(
            "TST",
            entry,
            {
                **GOOD_INPUTS,
                "employee_count": None,
            },
        )

        self.assertTrue(result["comparable"])
        self.assertEqual(entry, before)

    def test_failed_new_evaluation_not_comparable(self):
        baseline = self.make_evaluation("TST")

        with patch(
            "frontend.adapter._SCREEN_BACKEND_AVAILABLE",
            False,
        ):
            result = check_for_changes(
                "TST",
                _make_entry("TST", baseline),
                dict(GOOD_INPUTS),
            )

        self.assertFalse(result["comparable"])
        self.assertIsNotNone(result["error"])
        self.assertEqual(result["changes"], [])


# ---------------------------------------------------------------------------
# 6. Test-only approval reference model
# ---------------------------------------------------------------------------

class ApprovalStateMachine:
    """
    Test-only reference model retained from the original test file.

    Not production code. Passing these model tests does not establish
    that app.py implements the same safeguards.
    """

    def __init__(self):
        self.qualified_list = set()
        self.needs_review_list = set()
        self.pending_approval = None
        self.action_log = []

    def save_ticker(self, ticker):
        if (
            ticker not in self.qualified_list
            and ticker not in self.needs_review_list
        ):
            self.qualified_list.add(ticker)

        self.action_log.append({
            "action": "saved_baseline",
            "ticker": ticker,
        })

    def queue_approval(self, ticker, eval_id, change_result):
        self.pending_approval = {
            "ticker": ticker,
            "eval_id": eval_id,
            "change_result": change_result,
        }

    def _eval_id(self, evaluation):
        return (
            f"{evaluation.get('ticker', '')}"
            f"@{evaluation.get('data_timestamp', '')}"
        )

    def approve(self):
        if self.pending_approval is None:
            return "no_pending"

        pending = self.pending_approval
        ticker = pending["ticker"]
        new_eval = pending["change_result"].get(
            "new_evaluation",
            {},
        )

        if self._eval_id(new_eval) != pending["eval_id"]:
            self.pending_approval = None
            return "invalidated"

        self.qualified_list.discard(ticker)
        self.needs_review_list.add(ticker)

        self.action_log.append({
            "action": "approved_needs_review",
            "ticker": ticker,
        })

        self.pending_approval = None
        return "approved"

    def reject(self):
        if self.pending_approval is None:
            return "no_pending"

        ticker = self.pending_approval["ticker"]

        self.action_log.append({
            "action": "rejected_keep_current",
            "ticker": ticker,
        })

        self.pending_approval = None
        return "rejected"


def _make_change_result(ticker, timestamp, changes):
    return {
        "changes": changes,
        "checked_at": timestamp,
        "new_evaluation": {
            "ticker": ticker,
            "data_timestamp": timestamp,
            "criteria": [],
        },
    }


class TestApprovalApprove(unittest.TestCase):
    def setUp(self):
        self.sm = ApprovalStateMachine()
        self.sm.save_ticker("ACME")

        change = _make_change_result("ACME", TS_1, [])
        self.sm.queue_approval(
            "ACME",
            f"ACME@{TS_1}",
            change,
        )

    def test_approve_moves_to_needs_review(self):
        self.assertEqual(self.sm.approve(), "approved")
        self.assertIn("ACME", self.sm.needs_review_list)

    def test_approve_removes_from_qualified(self):
        self.sm.approve()
        self.assertNotIn("ACME", self.sm.qualified_list)

    def test_approve_clears_pending(self):
        self.sm.approve()
        self.assertIsNone(self.sm.pending_approval)

    def test_approve_logs_action(self):
        self.sm.approve()

        self.assertIn(
            {
                "action": "approved_needs_review",
                "ticker": "ACME",
            },
            self.sm.action_log,
        )

    def test_second_approve_has_no_pending(self):
        self.sm.approve()
        self.assertEqual(self.sm.approve(), "no_pending")


class TestApprovalReject(unittest.TestCase):
    def setUp(self):
        self.sm = ApprovalStateMachine()
        self.sm.save_ticker("BLUE")

        change = _make_change_result("BLUE", TS_1, [])
        self.sm.queue_approval(
            "BLUE",
            f"BLUE@{TS_1}",
            change,
        )

    def test_reject_leaves_lists_unchanged(self):
        qualified = set(self.sm.qualified_list)
        review = set(self.sm.needs_review_list)

        self.assertEqual(self.sm.reject(), "rejected")
        self.assertEqual(self.sm.qualified_list, qualified)
        self.assertEqual(self.sm.needs_review_list, review)

    def test_reject_clears_pending(self):
        self.sm.reject()
        self.assertIsNone(self.sm.pending_approval)

    def test_reject_logs_action(self):
        self.sm.reject()

        self.assertIn(
            {
                "action": "rejected_keep_current",
                "ticker": "BLUE",
            },
            self.sm.action_log,
        )

    def test_second_reject_has_no_pending(self):
        self.sm.reject()
        self.assertEqual(self.sm.reject(), "no_pending")


class TestApprovalInvalidation(unittest.TestCase):
    def test_changed_eval_id_invalidates_approval(self):
        sm = ApprovalStateMachine()
        sm.save_ticker("CRST")

        change = _make_change_result("CRST", TS_2, [])
        sm.queue_approval(
            "CRST",
            f"CRST@{TS_1}",
            change,
        )

        self.assertEqual(sm.approve(), "invalidated")
        self.assertNotIn("CRST", sm.needs_review_list)
        self.assertIn("CRST", sm.qualified_list)
        self.assertIsNone(sm.pending_approval)

    def test_changed_evaluation_ticker_invalidates_approval(self):
        sm = ApprovalStateMachine()
        sm.save_ticker("A")
        sm.save_ticker("B")

        change = _make_change_result("B", TS_1, [])
        sm.queue_approval("A", f"A@{TS_1}", change)

        self.assertEqual(sm.approve(), "invalidated")
        self.assertEqual(sm.qualified_list, {"A", "B"})
        self.assertEqual(sm.needs_review_list, set())

    def test_removal_then_rejection_clears_pending(self):
        # This tests rejection cleanup only, not automatic invalidation
        # on removal in the production app.
        sm = ApprovalStateMachine()
        sm.save_ticker("SMCHG")

        change = _make_change_result("SMCHG", TS_1, [])
        sm.queue_approval(
            "SMCHG",
            f"SMCHG@{TS_1}",
            change,
        )

        sm.qualified_list.discard("SMCHG")
        sm.needs_review_list.discard("SMCHG")

        self.assertEqual(sm.reject(), "rejected")
        self.assertIsNone(sm.pending_approval)
        self.assertNotIn("SMCHG", sm.qualified_list)
        self.assertNotIn("SMCHG", sm.needs_review_list)

    def test_only_intended_company_updated_on_approve(self):
        sm = ApprovalStateMachine()
        sm.save_ticker("A")
        sm.save_ticker("B")

        change = _make_change_result("A", TS_1, [])
        sm.queue_approval("A", f"A@{TS_1}", change)

        self.assertEqual(sm.approve(), "approved")
        self.assertEqual(sm.needs_review_list, {"A"})
        self.assertEqual(sm.qualified_list, {"B"})


class TestApprovalNoWriteBeforeApproval(unittest.TestCase):
    def test_queuing_does_not_change_lists(self):
        sm = ApprovalStateMachine()
        sm.save_ticker("T")

        qualified = set(sm.qualified_list)
        review = set(sm.needs_review_list)

        change = _make_change_result("T", TS_1, [])
        sm.queue_approval("T", f"T@{TS_1}", change)

        self.assertEqual(sm.qualified_list, qualified)
        self.assertEqual(sm.needs_review_list, review)
        self.assertIsNotNone(sm.pending_approval)


# ---------------------------------------------------------------------------
# 7. Simulated-change fixtures
# ---------------------------------------------------------------------------

class TestSimulatedChangeScenario(unittest.TestCase):
    def setUp(self):
        self.scenario = get_simulated_change_scenario()

    def test_returns_baseline_and_changed(self):
        self.assertIn("baseline", self.scenario)
        self.assertIn("changed", self.scenario)

    def test_baseline_all_pass(self):
        self.assertEqual(
            self.scenario["baseline"]["aggregate_status"],
            "pass",
        )

    def test_changed_is_fail(self):
        self.assertEqual(
            self.scenario["changed"]["aggregate_status"],
            "fail",
        )

    def test_both_are_demo(self):
        for evaluation in self.scenario.values():
            self.assertEqual(evaluation["mode"], "demo")
            self.assertFalse(evaluation["is_live"])

    def test_ocf_flips_from_pass_to_fail(self):
        baseline = _by_id(
            self.scenario["baseline"],
            "positive_operating_cash_flow",
        )
        changed = _by_id(
            self.scenario["changed"],
            "positive_operating_cash_flow",
        )

        self.assertEqual(baseline["status"], "pass")
        self.assertGreater(baseline["observed_value"], 0)
        self.assertEqual(changed["status"], "fail")
        self.assertLess(changed["observed_value"], 0)

    def test_non_ocf_criteria_unchanged(self):
        for criterion_id in (
            "market_cap_range",
            "min_close_price",
            "min_employee_count",
        ):
            with self.subTest(criterion=criterion_id):
                self.assertEqual(
                    _by_id(
                        self.scenario["baseline"],
                        criterion_id,
                    ),
                    _by_id(
                        self.scenario["changed"],
                        criterion_id,
                    ),
                )

    def test_baseline_and_changed_do_not_share_mutable_state(self):
        original = copy.deepcopy(self.scenario["baseline"])

        self.scenario["changed"]["criteria"][0]["label"] = "Edited"

        self.assertEqual(self.scenario["baseline"], original)

    def test_repeated_calls_return_independent_fixtures(self):
        first = get_simulated_change_scenario()
        second = get_simulated_change_scenario()
        original = copy.deepcopy(second)

        first["changed"]["criteria"][0]["observed_value"] = -999

        self.assertEqual(second, original)


# ---------------------------------------------------------------------------
# 8. Acceptance checks
# ---------------------------------------------------------------------------

class TestAcceptanceChecks(EvaluationTestCase):
    def test_switching_tickers_does_not_share_state(self):
        first = self.make_evaluation("T1")
        second = self.make_evaluation(
            "T2",
            {
                **GOOD_INPUTS,
                "operating_cash_flow_ttm_usd": -1,
            },
        )

        original_second = copy.deepcopy(second)

        self.assertEqual(first["ticker"], "T1")
        self.assertEqual(second["ticker"], "T2")
        self.assertNotEqual(
            first["aggregate_status"],
            second["aggregate_status"],
        )

        first["criteria"][0]["label"] = "Mutated"
        first["criteria"][0]["observed_value"] = -999

        self.assertEqual(second, original_second)

    def test_demo_calls_do_not_share_state(self):
        first = evaluate_company(
            "ACME",
            None,
            demo_override="ACME",
        )
        second = evaluate_company(
            "ACME",
            None,
            demo_override="ACME",
        )
        original_second = copy.deepcopy(second)

        first["criteria"][0]["label"] = "Mutated"

        self.assertEqual(second, original_second)

    def test_missing_metrics_display_unknown(self):
        result = evaluate_company(
            "CRST",
            None,
            demo_override="CRST",
        )
        employee = _by_id(result, "min_employee_count")

        self.assertEqual(employee["status"], "unknown")
        self.assertIsNone(employee["observed_value"])
        self.assertIn(
            "unknown",
            employee["observed_fmt"].lower(),
        )

    def test_criterion_label_comes_from_adapter_metadata(self):
        # This verifies metadata conversion, not the UI layout itself.
        with patch.dict(
            "frontend.adapter._RULE_META",
            {
                "market_cap_range": {
                    "label": "Custom market-cap label",
                    "operator": "between",
                    "unit": "USD",
                    "reporting_period": "latest",
                }
            },
        ):
            result = evaluate_company(
                "ACME",
                None,
                demo_override="ACME",
            )

        self.assertEqual(
            _by_id(result, "market_cap_range")["label"],
            "Custom market-cap label",
        )

    def test_rejection_leaves_list_unchanged(self):
        sm = ApprovalStateMachine()
        sm.save_ticker("X")

        qualified = set(sm.qualified_list)
        review = set(sm.needs_review_list)

        change = _make_change_result("X", TS_1, [])
        sm.queue_approval("X", f"X@{TS_1}", change)
        sm.reject()

        self.assertEqual(sm.qualified_list, qualified)
        self.assertEqual(sm.needs_review_list, review)

    def test_approval_updates_only_intended_company(self):
        sm = ApprovalStateMachine()

        for ticker in ("A", "B", "C"):
            sm.save_ticker(ticker)

        change = _make_change_result("A", TS_1, [])
        sm.queue_approval("A", f"A@{TS_1}", change)
        sm.approve()

        self.assertEqual(sm.needs_review_list, {"A"})
        self.assertEqual(sm.qualified_list, {"B", "C"})

    def test_demo_mode_not_live(self):
        result = evaluate_company(
            "ACME",
            None,
            demo_override="ACME",
        )

        self.assertFalse(result["is_live"])
        self.assertEqual(result["mode"], "demo")

    def test_unavailable_agent_returns_no_fabricated_response(self):
        result = analyse_company("ACME", {})

        self.assertFalse(result["connected"])
        self.assertIsNone(result["content"])
        self.assertIsNotNone(result["error"])
        self.assertGreater(len(result["error"]), 10)


if __name__ == "__main__":
    unittest.main()

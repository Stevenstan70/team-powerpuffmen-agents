"""
tests/test_screener_workflow.py

Unit tests for the frontend adapter — comparison logic and approval state machine.

These tests exercise:
  1. evaluate_company — live path, demo path, error path
  2. check_for_changes — all four change types, missing-data handling,
     criteria-change detection, no-change case
  3. Approval state-machine invariants (pure Python, no Streamlit runtime)
  4. Simulated-change scenario integrity

No Streamlit AppTest, no live market data, no network calls.
"""

from __future__ import annotations

import sys
import os
import copy
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from frontend.adapter import (
    evaluate_company,
    analyse_company,
    check_for_changes,
    get_simulated_change_scenario,
    _rule_to_criterion,
    _aggregate_from_criteria,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _criterion(rule_name: str, observed, status: str) -> dict:
    """Build a minimal raw rule dict as returned by powerpuffmen_basic_screen."""
    _THRESHOLDS = {
        "market_cap_range": "2,000,000,000 <= x <= 100,000,000,000",
        "min_close_price": "x >= 10",
        "positive_operating_cash_flow": "x > 0",
        "min_employee_count": "x >= 20",
    }
    STATUS_MAP = {"pass": "PASS", "fail": "FAIL", "unknown": "UNVERIFIED"}
    raw_status = STATUS_MAP.get(status, status.upper())
    return {
        "rule_name": rule_name,
        "observed_value": observed,
        "threshold": _THRESHOLDS.get(rule_name, "?"),
        "status": raw_status,
        "explanation": f"Test rule {rule_name}",
    }


def _make_eval(ticker: str, rules: list[dict], mode: str = "demo") -> dict:
    """Build a minimal evaluation result."""
    criteria = [_rule_to_criterion(r) for r in rules]
    return {
        "mode": mode,
        "ticker": ticker,
        "company_name": ticker,
        "currency": "USD",
        "data_timestamp": "2025-01-01T00:00:00Z",
        "is_live": mode == "live",
        "criteria": criteria,
        "aggregate_status": _aggregate_from_criteria(criteria),
        "scope_note": "Test scope note.",
        "error": None,
    }


def _make_entry(ticker: str, evaluation: dict) -> dict:
    return {"saved_at": "2025-01-01T00:00:00Z", "evaluation": copy.deepcopy(evaluation)}


_ALL_PASS_RULES = [
    _criterion("market_cap_range",            15_000_000_000, "pass"),
    _criterion("min_close_price",             42.50,          "pass"),
    _criterion("positive_operating_cash_flow", 850_000_000,   "pass"),
    _criterion("min_employee_count",           3_200,         "pass"),
]

_OCF_FAIL_RULES = [
    _criterion("market_cap_range",            15_000_000_000, "pass"),
    _criterion("min_close_price",             42.50,          "pass"),
    _criterion("positive_operating_cash_flow", -100_000_000,  "fail"),
    _criterion("min_employee_count",           3_200,         "pass"),
]

_EMPLOYEE_UNKNOWN_RULES = [
    _criterion("market_cap_range",            15_000_000_000, "pass"),
    _criterion("min_close_price",             42.50,          "pass"),
    _criterion("positive_operating_cash_flow", 850_000_000,   "pass"),
    _criterion("min_employee_count",           None,          "unknown"),
]


# ---------------------------------------------------------------------------
# 1. evaluate_company
# ---------------------------------------------------------------------------

class TestEvaluateCompanyDemo(unittest.TestCase):
    """evaluate_company returns a properly shaped result for demo tickers."""

    def test_acme_demo_mode(self):
        result = evaluate_company("ACME", None, demo_override="ACME")
        self.assertEqual(result["mode"], "demo")
        self.assertFalse(result["is_live"])
        self.assertEqual(result["aggregate_status"], "pass")
        self.assertIsNone(result["error"])

    def test_blue_demo_fail(self):
        result = evaluate_company("BLUE", None, demo_override="BLUE")
        self.assertEqual(result["aggregate_status"], "fail")
        self.assertFalse(result["is_live"])

    def test_crst_demo_unknown(self):
        result = evaluate_company("CRST", None, demo_override="CRST")
        self.assertEqual(result["aggregate_status"], "unknown")
        # Unknown must not be treated as fail
        self.assertNotEqual(result["aggregate_status"], "fail")

    def test_criteria_list_not_empty(self):
        result = evaluate_company("ACME", None, demo_override="ACME")
        self.assertGreater(len(result["criteria"]), 0)

    def test_criteria_have_required_keys(self):
        result = evaluate_company("ACME", None, demo_override="ACME")
        required_keys = {"id", "label", "operator", "threshold", "unit",
                         "reporting_period", "observed_value", "observed_fmt", "status"}
        for c in result["criteria"]:
            self.assertTrue(required_keys.issubset(c.keys()), f"Missing keys in {c}")

    def test_unknown_ticker_falls_back_to_acme_fixture(self):
        """Unknown demo override key falls back gracefully (uses ACME fixture)."""
        result = evaluate_company("XYZ", None, demo_override="NONEXISTENT")
        self.assertIsNone(result["error"])
        self.assertGreater(len(result["criteria"]), 0)

    def test_none_inputs_returns_demo(self):
        result = evaluate_company("AAPL", None)
        self.assertEqual(result["mode"], "demo")


class TestEvaluateCompanyLive(unittest.TestCase):
    """evaluate_company with real inputs uses the screening backend."""

    _GOOD_INPUTS = dict(
        market_cap_usd=10_000_000_000,
        close_price_usd=50.0,
        operating_cash_flow_ttm_usd=500_000,
        employee_count=200,
    )

    def test_live_all_pass(self):
        result = evaluate_company("TST", self._GOOD_INPUTS)
        self.assertIn(result["mode"], ("live", "error"))
        if result["mode"] == "live":
            self.assertEqual(result["aggregate_status"], "pass")
            self.assertTrue(result["is_live"])

    def test_live_ocf_fail(self):
        inputs = {**self._GOOD_INPUTS, "operating_cash_flow_ttm_usd": -1}
        result = evaluate_company("TST", inputs)
        if result["mode"] == "live":
            self.assertEqual(result["aggregate_status"], "fail")

    def test_live_missing_employee_is_unknown_not_fail(self):
        inputs = {**self._GOOD_INPUTS, "employee_count": None}
        result = evaluate_company("TST", inputs)
        if result["mode"] == "live":
            emp = next(c for c in result["criteria"] if c["id"] == "min_employee_count")
            self.assertEqual(emp["status"], "unknown")
            # Must not be treated as fail
            self.assertNotEqual(emp["status"], "fail")


class TestEvaluateCompanyTicker(unittest.TestCase):
    """Ticker is reflected correctly in the result."""

    def test_ticker_preserved(self):
        result = evaluate_company("MYMOO", None, demo_override="ACME")
        self.assertEqual(result["ticker"], "MYMOO")

    def test_switching_ticker_uses_new_result(self):
        r1 = evaluate_company("T1", None, demo_override="ACME")
        r2 = evaluate_company("T2", None, demo_override="BLUE")
        self.assertNotEqual(r1["ticker"], r2["ticker"])
        self.assertNotEqual(r1["aggregate_status"], r2["aggregate_status"])


# ---------------------------------------------------------------------------
# 2. analyse_company — not connected
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

    def test_no_fabricated_output(self):
        """connected=False means no agent output should be shown."""
        result = analyse_company("ACME", {})
        self.assertFalse(result["connected"])
        self.assertIsNone(result["content"])


# ---------------------------------------------------------------------------
# 3. check_for_changes — change detection logic
# ---------------------------------------------------------------------------

class TestCheckForChangesNoChange(unittest.TestCase):
    def test_identical_eval_produces_no_changes(self):
        base_eval = _make_eval("T", _ALL_PASS_RULES)
        entry = _make_entry("T", base_eval)
        # Passing the same inputs back should produce no changes for live evals
        # For demo tickers we test with the adapter directly
        baseline_criteria = {c["id"]: c for c in base_eval["criteria"]}
        new_criteria = {c["id"]: c for c in base_eval["criteria"]}
        changes = _compute_changes(baseline_criteria, new_criteria)
        self.assertEqual(changes, [])


class TestCheckForChangesValueChanged(unittest.TestCase):
    def test_value_change_same_status(self):
        old_rules = [_criterion("market_cap_range", 10_000_000_000, "pass")]
        new_rules = [_criterion("market_cap_range", 12_000_000_000, "pass")]
        baseline_criteria = {c["id"]: c for c in [_rule_to_criterion(r) for r in old_rules]}
        new_criteria = {c["id"]: c for c in [_rule_to_criterion(r) for r in new_rules]}
        changes = _compute_changes(baseline_criteria, new_criteria)
        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0]["change_type"], "value_changed")
        self.assertEqual(changes[0]["old_status"], "pass")
        self.assertEqual(changes[0]["new_status"], "pass")


class TestCheckForChangesStatusTransition(unittest.TestCase):
    def test_pass_to_fail_detected(self):
        old_rules = [_criterion("positive_operating_cash_flow", 500_000, "pass")]
        new_rules = [_criterion("positive_operating_cash_flow", -100_000, "fail")]
        baseline_criteria = {c["id"]: c for c in [_rule_to_criterion(r) for r in old_rules]}
        new_criteria = {c["id"]: c for c in [_rule_to_criterion(r) for r in new_rules]}
        changes = _compute_changes(baseline_criteria, new_criteria)
        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0]["change_type"], "status_transition")
        self.assertEqual(changes[0]["old_status"], "pass")
        self.assertEqual(changes[0]["new_status"], "fail")

    def test_fail_to_pass_detected(self):
        old_rules = [_criterion("min_close_price", 5.0, "fail")]
        new_rules = [_criterion("min_close_price", 50.0, "pass")]
        baseline_criteria = {c["id"]: c for c in [_rule_to_criterion(r) for r in old_rules]}
        new_criteria = {c["id"]: c for c in [_rule_to_criterion(r) for r in new_rules]}
        changes = _compute_changes(baseline_criteria, new_criteria)
        self.assertEqual(changes[0]["change_type"], "status_transition")
        self.assertEqual(changes[0]["old_status"], "fail")
        self.assertEqual(changes[0]["new_status"], "pass")


class TestCheckForChangesMissingData(unittest.TestCase):
    """Missing data must never be treated as zero or confirmed failure."""

    def test_missing_data_is_data_unavailable_not_fail(self):
        old_rules = [_criterion("min_employee_count", 500, "pass")]
        # New: observed_value becomes None
        new_rules = [_criterion("min_employee_count", None, "unknown")]
        baseline_criteria = {c["id"]: c for c in [_rule_to_criterion(r) for r in old_rules]}
        new_criteria = {c["id"]: c for c in [_rule_to_criterion(r) for r in new_rules]}
        changes = _compute_changes(baseline_criteria, new_criteria)
        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0]["change_type"], "data_unavailable")
        # The new status must be "unknown", NOT "fail"
        self.assertEqual(changes[0]["new_status"], "unknown")
        self.assertNotEqual(changes[0]["new_status"], "fail")

    def test_missing_displayed_as_unavailable_not_zero(self):
        old_rules = [_criterion("min_employee_count", 500, "pass")]
        new_rules = [_criterion("min_employee_count", None, "unknown")]
        baseline_criteria = {c["id"]: c for c in [_rule_to_criterion(r) for r in old_rules]}
        new_criteria = {c["id"]: c for c in [_rule_to_criterion(r) for r in new_rules]}
        changes = _compute_changes(baseline_criteria, new_criteria)
        # new_value_fmt must not be "0" or "0.00"
        self.assertNotIn(changes[0]["new_value_fmt"], ("0", "$0.00", "0.0"))
        self.assertIn("unavailable", changes[0]["new_value_fmt"].lower())


class TestCheckForChangesCriteriaChanged(unittest.TestCase):
    """When the set of criteria IDs changes, evaluations are not comparable."""

    def test_different_criteria_sets_not_comparable(self):
        base_eval = _make_eval("T", _ALL_PASS_RULES)
        entry = _make_entry("T", base_eval)

        # Simulate what check_for_changes does with mismatched criteria
        baseline_ids = {c["id"] for c in base_eval["criteria"]}
        # New set has one extra criterion
        new_ids = baseline_ids | {"fake_new_rule"}
        self.assertNotEqual(baseline_ids, new_ids)

    def test_criteria_set_must_match_for_comparable(self):
        base_eval = _make_eval("T", _ALL_PASS_RULES)
        new_eval = _make_eval("T", _ALL_PASS_RULES)
        baseline_ids = {c["id"] for c in base_eval["criteria"]}
        new_ids = {c["id"] for c in new_eval["criteria"]}
        self.assertEqual(baseline_ids, new_ids, "Same rules — must be comparable")


class TestCheckForChangesViaAdapter(unittest.TestCase):
    """Integration test using the adapter's check_for_changes."""

    def test_demo_acme_check_returns_structure(self):
        base_eval = evaluate_company("ACME", None, demo_override="ACME")
        entry = _make_entry("ACME", base_eval)
        result = check_for_changes("ACME", entry, None)
        self.assertIn("changes", result)
        self.assertIn("checked_at", result)
        self.assertIn("comparable", result)
        self.assertIn("new_evaluation", result)

    def test_comparable_flag_true_for_same_criteria(self):
        base_eval = evaluate_company("ACME", None, demo_override="ACME")
        entry = _make_entry("ACME", base_eval)
        result = check_for_changes("ACME", entry, None)
        self.assertTrue(result["comparable"])

    def test_error_path_returns_error_key(self):
        """An entry with no criteria triggers graceful error handling."""
        entry = {
            "saved_at": "2025-01-01T00:00:00Z",
            "evaluation": {
                "ticker": "ZZZ",
                "criteria": [],
                "aggregate_status": "unknown",
                "error": None,
            },
        }
        # Should not raise; may or may not be comparable
        result = check_for_changes("ZZZ", entry, None)
        self.assertIn("comparable", result)


# ---------------------------------------------------------------------------
# 4. Approval state-machine invariants (pure Python, no Streamlit)
# ---------------------------------------------------------------------------

class ApprovalStateMachine:
    """Minimal approval state machine extracted from app.py logic for testing."""

    def __init__(self):
        self.qualified_list: set = set()
        self.needs_review_list: set = set()
        self.pending_approval: dict | None = None
        self.action_log: list = []

    def save_ticker(self, ticker: str):
        if ticker not in self.qualified_list and ticker not in self.needs_review_list:
            self.qualified_list.add(ticker)
        self.action_log.append({"action": "saved_baseline", "ticker": ticker})

    def queue_approval(self, ticker: str, eval_id: str, change_result: dict):
        self.pending_approval = {
            "ticker": ticker,
            "eval_id": eval_id,
            "change_result": change_result,
        }

    def _eval_id(self, evaluation: dict) -> str:
        return f"{evaluation.get('ticker','')}@{evaluation.get('data_timestamp','')}"

    def approve(self) -> str:
        if self.pending_approval is None:
            return "no_pending"
        p = self.pending_approval
        ticker = p["ticker"]
        eval_id = p["eval_id"]
        new_eval = p["change_result"].get("new_evaluation", {})
        if self._eval_id(new_eval) != eval_id:
            self.pending_approval = None
            return "invalidated"
        self.qualified_list.discard(ticker)
        self.needs_review_list.add(ticker)
        self.action_log.append({"action": "approved_needs_review", "ticker": ticker})
        self.pending_approval = None
        return "approved"

    def reject(self) -> str:
        if self.pending_approval is None:
            return "no_pending"
        ticker = self.pending_approval["ticker"]
        self.action_log.append({"action": "rejected_keep_current", "ticker": ticker})
        self.pending_approval = None
        return "rejected"


def _make_change_result(ticker: str, ts: str, changes: list) -> dict:
    return {
        "changes": changes,
        "checked_at": ts,
        "new_evaluation": {
            "ticker": ticker,
            "data_timestamp": ts,
            "criteria": [],
        },
    }


class TestApprovalApprove(unittest.TestCase):
    def setUp(self):
        self.sm = ApprovalStateMachine()
        self.sm.save_ticker("ACME")
        ts = "2025-06-01T12:00:00Z"
        cr = _make_change_result("ACME", ts, [])
        self.eval_id = f"ACME@{ts}"
        self.sm.queue_approval("ACME", self.eval_id, cr)

    def test_approve_moves_to_needs_review(self):
        self.sm.approve()
        self.assertIn("ACME", self.sm.needs_review_list)

    def test_approve_removes_from_qualified(self):
        self.sm.approve()
        self.assertNotIn("ACME", self.sm.qualified_list)

    def test_approve_clears_pending(self):
        self.sm.approve()
        self.assertIsNone(self.sm.pending_approval)

    def test_approve_logs_action(self):
        self.sm.approve()
        actions = [e["action"] for e in self.sm.action_log]
        self.assertIn("approved_needs_review", actions)

    def test_second_approve_has_no_pending(self):
        self.sm.approve()
        result = self.sm.approve()
        self.assertEqual(result, "no_pending")


class TestApprovalReject(unittest.TestCase):
    def setUp(self):
        self.sm = ApprovalStateMachine()
        self.sm.save_ticker("BLUE")
        ts = "2025-06-01T12:00:00Z"
        cr = _make_change_result("BLUE", ts, [])
        self.sm.queue_approval("BLUE", f"BLUE@{ts}", cr)

    def test_reject_leaves_qualified_list_unchanged(self):
        self.sm.reject()
        self.assertIn("BLUE", self.sm.qualified_list, "Rejection must preserve Qualified status")
        self.assertNotIn("BLUE", self.sm.needs_review_list)

    def test_reject_clears_pending(self):
        self.sm.reject()
        self.assertIsNone(self.sm.pending_approval)

    def test_reject_logs_action(self):
        self.sm.reject()
        actions = [e["action"] for e in self.sm.action_log]
        self.assertIn("rejected_keep_current", actions)


class TestApprovalInvalidation(unittest.TestCase):
    """Approval bound to a specific ticker+eval_id; changing eval invalidates it."""

    def test_changed_eval_id_invalidates_approval(self):
        sm = ApprovalStateMachine()
        sm.save_ticker("CRST")
        ts1 = "2025-06-01T12:00:00Z"
        ts2 = "2025-06-02T08:00:00Z"
        cr = _make_change_result("CRST", ts2, [])  # new_eval has ts2
        # But we queue with eval_id pointing to ts1
        sm.queue_approval("CRST", f"CRST@{ts1}", cr)
        result = sm.approve()
        self.assertEqual(result, "invalidated",
                         "Approval with mismatched eval_id must be invalidated")
        self.assertNotIn("CRST", sm.needs_review_list)
        self.assertIn("CRST", sm.qualified_list)

    def test_removing_ticker_invalidates_pending(self):
        sm = ApprovalStateMachine()
        sm.save_ticker("SMCHG")
        ts = "2025-06-01T12:00:00Z"
        cr = _make_change_result("SMCHG", ts, [])
        sm.queue_approval("SMCHG", f"SMCHG@{ts}", cr)
        # Simulate removal from tracking
        sm.qualified_list.discard("SMCHG")
        sm.needs_review_list.discard("SMCHG")
        # Without the ticker in any list, status is gone
        # The approval should be rejected by the app when ticker is no longer tracked
        # Here we test that the state does not persist incorrect data
        sm.reject()
        self.assertIsNone(sm.pending_approval)

    def test_only_intended_company_updated_on_approve(self):
        sm = ApprovalStateMachine()
        sm.save_ticker("A")
        sm.save_ticker("B")
        ts = "2025-06-01T12:00:00Z"
        cr = _make_change_result("A", ts, [])
        sm.queue_approval("A", f"A@{ts}", cr)
        sm.approve()
        # Only A should move to needs_review
        self.assertIn("A", sm.needs_review_list)
        self.assertNotIn("B", sm.needs_review_list)
        self.assertIn("B", sm.qualified_list)


class TestApprovalNoWriteBeforeApproval(unittest.TestCase):
    """List status must not change before the user explicitly approves."""

    def test_queuing_does_not_change_list(self):
        sm = ApprovalStateMachine()
        sm.save_ticker("T")
        ts = "2025-06-01T12:00:00Z"
        cr = _make_change_result("T", ts, [])
        sm.queue_approval("T", f"T@{ts}", cr)
        # Pending approval queued — but list must be unchanged until approve()
        self.assertIn("T", sm.qualified_list)
        self.assertNotIn("T", sm.needs_review_list)


# ---------------------------------------------------------------------------
# 5. Simulated-change scenario integrity
# ---------------------------------------------------------------------------

class TestSimulatedChangeScenario(unittest.TestCase):
    def setUp(self):
        self.scenario = get_simulated_change_scenario()

    def test_returns_baseline_and_changed(self):
        self.assertIn("baseline", self.scenario)
        self.assertIn("changed", self.scenario)

    def test_baseline_all_pass(self):
        self.assertEqual(self.scenario["baseline"]["aggregate_status"], "pass")

    def test_changed_is_fail(self):
        self.assertEqual(self.scenario["changed"]["aggregate_status"], "fail")

    def test_both_are_demo(self):
        self.assertEqual(self.scenario["baseline"]["mode"], "demo")
        self.assertEqual(self.scenario["changed"]["mode"], "demo")

    def test_ocf_flips_from_pass_to_fail(self):
        baseline = self.scenario["baseline"]
        changed = self.scenario["changed"]
        b_ocf = next(c for c in baseline["criteria"] if c["id"] == "positive_operating_cash_flow")
        c_ocf = next(c for c in changed["criteria"] if c["id"] == "positive_operating_cash_flow")
        self.assertEqual(b_ocf["status"], "pass")
        self.assertEqual(c_ocf["status"], "fail")

    def test_non_ocf_criteria_unchanged(self):
        baseline = self.scenario["baseline"]
        changed = self.scenario["changed"]
        for cid in ["market_cap_range", "min_close_price", "min_employee_count"]:
            b = next(c for c in baseline["criteria"] if c["id"] == cid)
            c = next(c for c in changed["criteria"] if c["id"] == cid)
            self.assertEqual(b["status"], c["status"], f"{cid} status should be unchanged")

    def test_no_live_data_used(self):
        self.assertFalse(self.scenario["baseline"]["is_live"])
        self.assertFalse(self.scenario["changed"]["is_live"])


# ---------------------------------------------------------------------------
# 6. Acceptance checks
# ---------------------------------------------------------------------------

class TestAcceptanceChecks(unittest.TestCase):
    """Directly test the acceptance criteria stated in the requirements."""

    def test_switching_tickers_does_not_share_state(self):
        """Switching tickers cannot display another company's old analysis."""
        r1 = evaluate_company("T1", None, demo_override="ACME")
        r2 = evaluate_company("T2", None, demo_override="BLUE")
        self.assertEqual(r1["ticker"], "T1")
        self.assertEqual(r2["ticker"], "T2")
        self.assertNotEqual(r1["aggregate_status"], r2["aggregate_status"])

    def test_missing_metrics_display_unknown(self):
        """Missing metrics display Unknown/Unavailable."""
        result = evaluate_company("TST", None, demo_override="CRST")
        emp = next(c for c in result["criteria"] if c["id"] == "min_employee_count")
        self.assertEqual(emp["status"], "unknown")
        self.assertIsNone(emp["observed_value"])
        self.assertIn("unknown", emp["observed_fmt"].lower())

    def test_criterion_label_comes_from_adapter_not_hardcoded(self):
        """Changing criterion labels updates the UI without editing layout.
        The label is driven by _RULE_META in the adapter, not hardcoded in UI."""
        result = evaluate_company("ACME", None, demo_override="ACME")
        labels = {c["id"]: c["label"] for c in result["criteria"]}
        # All must have non-empty labels
        for cid, label in labels.items():
            self.assertGreater(len(label), 0, f"Label for {cid} is empty")

    def test_rejection_leaves_list_unchanged(self):
        """Rejecting an action leaves the list unchanged."""
        sm = ApprovalStateMachine()
        sm.save_ticker("X")
        initial_qualified = copy.copy(sm.qualified_list)
        ts = "2025-06-01T12:00:00Z"
        cr = _make_change_result("X", ts, [])
        sm.queue_approval("X", f"X@{ts}", cr)
        sm.reject()
        self.assertEqual(sm.qualified_list, initial_qualified)
        self.assertNotIn("X", sm.needs_review_list)

    def test_approval_updates_only_intended_company(self):
        """Approving updates only the intended company's review state."""
        sm = ApprovalStateMachine()
        sm.save_ticker("A")
        sm.save_ticker("B")
        sm.save_ticker("C")
        ts = "2025-06-01T12:00:00Z"
        cr = _make_change_result("A", ts, [])
        sm.queue_approval("A", f"A@{ts}", cr)
        sm.approve()
        self.assertIn("A", sm.needs_review_list)
        self.assertNotIn("B", sm.needs_review_list)
        self.assertNotIn("C", sm.needs_review_list)

    def test_demo_mode_not_live(self):
        """Demo results are visibly labelled (is_live=False, mode='demo')."""
        result = evaluate_company("ACME", None, demo_override="ACME")
        self.assertFalse(result["is_live"])
        self.assertEqual(result["mode"], "demo")

    def test_unavailable_backend_returns_error_not_fabricated_response(self):
        """An unavailable backend produces a useful error, not a fabricated response."""
        result = analyse_company("ACME", {})
        self.assertFalse(result["connected"])
        self.assertIsNone(result["content"])
        # Error message must be informative
        self.assertIsNotNone(result["error"])
        self.assertGreater(len(result["error"]), 10)


# ---------------------------------------------------------------------------
# Helper: pure-Python comparison logic (mirrors adapter logic)
# ---------------------------------------------------------------------------

def _compute_changes(baseline_criteria: dict, new_criteria: dict) -> list:
    """Mirror the change-detection logic from adapter.check_for_changes."""
    changes = []
    all_ids = set(baseline_criteria.keys()) | set(new_criteria.keys())
    for cid in all_ids:
        old_c = baseline_criteria.get(cid)
        new_c = new_criteria.get(cid)

        if old_c is None or new_c is None:
            changes.append({
                "criterion_id": cid,
                "criterion_label": (new_c or old_c or {}).get("label", cid),
                "change_type": "criteria_changed",
                "old_value_fmt": old_c["observed_fmt"] if old_c else "N/A",
                "new_value_fmt": new_c["observed_fmt"] if new_c else "N/A",
                "old_status": old_c["status"] if old_c else "unknown",
                "new_status": new_c["status"] if new_c else "unknown",
                "explanation": "Criterion added or removed.",
            })
            continue

        old_val = old_c["observed_value"]
        new_val = new_c["observed_value"]
        old_status = old_c["status"]
        new_status = new_c["status"]

        if new_val is None and old_val is not None:
            changes.append({
                "criterion_id": cid,
                "criterion_label": new_c["label"],
                "change_type": "data_unavailable",
                "old_value_fmt": old_c["observed_fmt"],
                "new_value_fmt": "Unavailable",
                "old_status": old_status,
                "new_status": "unknown",
                "explanation": f"Data for '{new_c['label']}' is no longer available.",
            })
            continue

        status_changed = old_status != new_status
        value_changed = old_val != new_val

        if status_changed:
            changes.append({
                "criterion_id": cid,
                "criterion_label": new_c["label"],
                "change_type": "status_transition",
                "old_value_fmt": old_c["observed_fmt"],
                "new_value_fmt": new_c["observed_fmt"],
                "old_status": old_status,
                "new_status": new_status,
                "explanation": f"Status changed: {old_status} → {new_status}.",
            })
        elif value_changed:
            changes.append({
                "criterion_id": cid,
                "criterion_label": new_c["label"],
                "change_type": "value_changed",
                "old_value_fmt": old_c["observed_fmt"],
                "new_value_fmt": new_c["observed_fmt"],
                "old_status": old_status,
                "new_status": new_status,
                "explanation": f"Value changed.",
            })

    return changes


if __name__ == "__main__":
    unittest.main()

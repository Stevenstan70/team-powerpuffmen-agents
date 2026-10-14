import unittest
import sys
import os

# Ensure the workspace root is on the path so `tools` is importable.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tools.health_check import health_check


class TestHealthCheck(unittest.TestCase):
    """Unit tests for the health_check tool.

    Calls the underlying function directly via health_check.fn() to avoid
    any ADK runtime overhead and keep the test self-contained.
    """

    def test_status_is_ok(self):
        """The returned 'status' field must always be 'ok'."""
        result = health_check.fn(message="ping")
        self.assertEqual(result["status"], "ok")

    def test_message_returned_unchanged(self):
        """The returned 'message' field must equal the supplied string exactly."""
        payload = "hello from smoke-test"
        result = health_check.fn(message=payload)
        self.assertEqual(result["message"], payload)

    def test_empty_message(self):
        """An empty string is a valid message and must be returned unchanged."""
        result = health_check.fn(message="")
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["message"], "")


if __name__ == "__main__":
    unittest.main()

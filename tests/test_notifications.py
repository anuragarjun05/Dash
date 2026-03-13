"""Tests for utils.notifications module."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from utils.notifications import build_alert_message, log_notification


class TestBuildAlertMessage(unittest.TestCase):
    """Tests for alert message formatting."""

    def test_contains_equipment_id(self):
        msg = build_alert_message("PUMP-A-101", "Alice", "High vibration")
        self.assertIn("PUMP-A-101", msg)

    def test_contains_engineer_name(self):
        msg = build_alert_message("PUMP-A-101", "Alice", "High vibration")
        self.assertIn("Alice", msg)

    def test_contains_details(self):
        msg = build_alert_message("PUMP-A-101", "Alice", "High vibration")
        self.assertIn("High vibration", msg)

    def test_contains_alert_header(self):
        msg = build_alert_message("PUMP-A-101", "Alice", "High vibration")
        self.assertIn("ABNORMALITY ALERT", msg)


class TestLogNotification(unittest.TestCase):
    """Tests for logging notifications to JSON."""

    def setUp(self):
        self._tmpdir = tempfile.mkdtemp()
        # Patch DATA_DIR to use a temp directory
        self._patcher = mock.patch(
            "utils.notifications.DATA_DIR", Path(self._tmpdir)
        )
        self._patcher.start()

    def tearDown(self):
        self._patcher.stop()
        # Clean up
        import shutil
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def test_creates_notification_file(self):
        log_notification("PUMP-A-101", "Alice", "High vibration")
        path = Path(self._tmpdir) / "notifications.json"
        self.assertTrue(path.exists())

    def test_notification_structure(self):
        result = log_notification("PUMP-A-101", "Alice", "High vibration")
        self.assertEqual(result["equipment_id"], "PUMP-A-101")
        self.assertEqual(result["engineer_name"], "Alice")
        self.assertEqual(result["abnormality_details"], "High vibration")
        self.assertFalse(result["acknowledged"])
        self.assertIn("timestamp", result)

    def test_appends_multiple_notifications(self):
        log_notification("PUMP-A-101", "Alice", "High vibration")
        log_notification("MOTOR-B-202", "Bob", "Overheating")

        path = Path(self._tmpdir) / "notifications.json"
        with open(path) as fh:
            data = json.load(fh)
        self.assertEqual(len(data), 2)
        self.assertEqual(data[0]["equipment_id"], "PUMP-A-101")
        self.assertEqual(data[1]["equipment_id"], "MOTOR-B-202")

    def test_handles_corrupt_file(self):
        path = Path(self._tmpdir) / "notifications.json"
        path.write_text("not valid json")
        # Should not raise — starts fresh
        result = log_notification("PUMP-A-101", "Alice", "Issue")
        self.assertEqual(result["equipment_id"], "PUMP-A-101")


if __name__ == "__main__":
    unittest.main()

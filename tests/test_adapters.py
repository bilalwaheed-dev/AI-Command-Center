"""Tests for Worker Adapters and Protocol envelopes."""
from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

# Add root directory to sys.path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from adapters import AntigravityAdapter, HttpDaemonAdapter, MockWorkerAdapter


class TestWorkerAdapters(unittest.TestCase):
    """Test suite for worker adapters and communication contracts."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_antigravity_envelope_formatting(self):
        adapter = AntigravityAdapter()
        worker = {
            "id": "PC-W1",
            "name": "Big PC Windows Native",
            "machine": "BIG-PC",
            "environment": "WINDOWS-NATIVE",
        }
        task = {
            "id": "TASK-001",
            "title": "Build Architecture Document",
            "description": "Create ARCHITECTURE.md with system diagrams",
            "prompt_payload": "Write full specification for supervisor",
            "priority": "urgent",
        }
        project = {
            "name": "AI-Command-Center",
            "path": self.test_dir,
        }

        envelope = adapter.format_task_envelope(worker, task, project)
        self.assertIn("WORKER: PC-W1", envelope)
        self.assertIn("MACHINE: BIG-PC", envelope)
        self.assertIn("TASK ID: TASK-001", envelope)
        self.assertIn("PRIORITY: URGENT", envelope)
        self.assertIn("POST /api/v1/tasks/TASK-001/complete", envelope)

    def test_antigravity_mailbox_dispatch(self):
        adapter = AntigravityAdapter({"mailbox_dirname": ".test_mailbox"})
        worker = {"id": "PC-W1", "machine": "BIG-PC", "environment": "WINDOWS-NATIVE"}
        task = {
            "id": "TASK-DROP-01",
            "title": "Drop Task",
            "project_path": self.test_dir,
            "prompt_payload": "Execute dropped instructions",
        }

        success = adapter.dispatch_task(worker, task)
        self.assertTrue(success)

        mailbox_dir = Path(self.test_dir) / ".test_mailbox"
        self.assertTrue(mailbox_dir.exists())
        self.assertTrue((mailbox_dir / "CURRENT_TASK_TASK-DROP-01.txt").exists())
        self.assertTrue((mailbox_dir / "active_task.json").exists())

        # Test cancel
        cancel_success = adapter.cancel_task(worker, task)
        self.assertTrue(cancel_success)
        self.assertTrue((mailbox_dir / "CANCEL_TASK-DROP-01.flag").exists())

    def test_mock_adapter(self):
        mock = MockWorkerAdapter()
        worker = {"id": "MOCK-W1", "status": "idle"}
        task = {"id": "MOCK-T1", "title": "Test"}

        self.assertTrue(mock.dispatch_task(worker, task))
        self.assertEqual(len(mock.dispatched_tasks), 1)

        poll = mock.poll_status(worker)
        self.assertEqual(poll["status"], "idle")

        self.assertTrue(mock.cancel_task(worker, task))
        self.assertEqual(len(mock.cancelled_tasks), 1)


if __name__ == "__main__":
    unittest.main()

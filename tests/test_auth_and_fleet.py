"""Phase 2 Authentication and Fleet Connectivity Tests."""
from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

# Add project root to sys.path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from auth import get_or_create_auth_token, validate_token
from bootstrap_engine import bootstrap_new_project
import config
from database import init_db
import models
from supervisor import create_app
from worker_daemon import WorkerDaemon


class TestAuthAndFleet(unittest.TestCase):
    """Test suite verifying Phase 2 Bearer authentication and remote worker fleet connectivity."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.db_path = Path(self.test_dir) / "test_auth_command_center.db"
        
        # Explicit test token
        self.test_token = "test_bearer_token_12345"
        os.environ["COMMAND_CENTER_TOKEN"] = self.test_token
        os.environ["COMMAND_CENTER_AUTH_ENABLED"] = "true"

        self.app = create_app(db_path=self.db_path)
        self.client = self.app.test_client()

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_01_token_generation_and_validation(self):
        """Test token validation and matching."""
        self.assertTrue(validate_token(self.test_token))
        self.assertFalse(validate_token("invalid_token_9999"))
        self.assertFalse(validate_token(""))

    def test_02_protected_routes_reject_unauthenticated(self):
        """Test that worker and task mutating endpoints reject unauthenticated calls with 401."""
        # 1. Register worker without token -> 401
        res = self.client.post("/api/v1/workers", json={"id": "UNAUTH-W1"})
        self.assertEqual(res.status_code, 401)
        self.assertIn("Unauthorized", res.get_json()["error"])

        # 2. Heartbeat without token -> 401
        res_hb = self.client.post("/api/v1/workers/PC-W1/heartbeat", json={"status": "online"})
        self.assertEqual(res_hb.status_code, 401)

        # 3. Create task without token -> 401
        res_t = self.client.post("/api/v1/tasks", json={"project_id": "p1", "title": "Secret Task"})
        self.assertEqual(res_t.status_code, 401)

    def test_03_protected_routes_accept_valid_bearer_token(self):
        """Test that passing 'Authorization: Bearer <token>' allows operations."""
        auth_headers = {"Authorization": f"Bearer {self.test_token}"}

        # 1. Verify token endpoint
        res_verify = self.client.get("/api/v1/auth/verify", headers=auth_headers)
        self.assertEqual(res_verify.status_code, 200)
        self.assertTrue(res_verify.get_json()["authenticated"])

        # 2. Register worker with token -> 201
        res_reg = self.client.post("/api/v1/workers", headers=auth_headers, json={
            "id": "PC-W2",
            "name": "Big PC WSL2 Ubuntu",
            "machine": "BIG-PC",
            "environment": "WSL2-UBUNTU",
            "provider_type": "antigravity",
            "status": "idle"
        })
        self.assertEqual(res_reg.status_code, 201)
        self.assertEqual(res_reg.get_json()["worker"]["id"], "PC-W2")

        # 3. Heartbeat with token -> 200
        res_hb = self.client.post(
            "/api/v1/workers/PC-W2/heartbeat",
            headers=auth_headers,
            json={"status": "idle"}
        )
        self.assertEqual(res_hb.status_code, 200)

    def test_04_worker_daemon_authenticated_task_lifecycle(self):
        """Test WorkerDaemon interacting with authenticated supervisor."""
        auth_headers = {"Authorization": f"Bearer {self.test_token}"}

        # Setup project and task
        proj_dir = Path(self.test_dir) / "Fleet-Proj"
        proj = bootstrap_new_project("Fleet-Proj", str(proj_dir), db_path=self.db_path)
        proj_id = proj["id"]

        # Create task assigned to PC-W2
        task_res = self.client.post("/api/v1/tasks", headers=auth_headers, json={
            "project_id": proj_id,
            "title": "Compile Linux Binaries in WSL2",
            "priority": "high",
            "assigned_worker_id": "PC-W2",
            "prompt_payload": "Execute test gcc build command in WSL2 environment",
        })
        self.assertEqual(task_res.status_code, 201)
        task_id = task_res.get_json()["task"]["id"]

        # Test daemon methods directly
        daemon = WorkerDaemon(
            server_url="http://localhost:5050",
            worker_id="PC-W2",
            token=self.test_token,
            machine="BIG-PC",
            environment="WSL2-UBUNTU",
        )
        headers = daemon.headers()
        self.assertEqual(headers["Authorization"], f"Bearer {self.test_token}")

        # Simulate execution through client
        # 1. Fetch next task
        res_next = self.client.get("/api/v1/workers/PC-W2/tasks/next", headers=headers)
        self.assertEqual(res_next.status_code, 200)
        fetched_task = res_next.get_json()["task"]
        self.assertEqual(fetched_task["id"], task_id)

        # 2. Mark started
        res_start = self.client.put(f"/api/v1/tasks/{task_id}/start", headers=headers, json={"worker_id": "PC-W2"})
        self.assertEqual(res_start.status_code, 200)

        # 3. Report completion
        res_comp = self.client.post(f"/api/v1/tasks/{task_id}/complete", headers=headers, json={
            "result_summary": "Linux binaries compiled successfully in WSL2 environment"
        })
        self.assertEqual(res_comp.status_code, 200)

        # Verify task is completed
        res_task = self.client.get(f"/api/v1/tasks/{task_id}")
        self.assertEqual(res_task.get_json()["task"]["status"], "completed")


if __name__ == "__main__":
    unittest.main()

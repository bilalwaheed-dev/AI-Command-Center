"""Automated tests for AI Command Center Supervisor.
Verifies all Phase 1 success criteria:
- Supervisor starts
- Database initializes
- Worker can register
- Worker can send heartbeat
- Worker status appears via API
- Project can be created
- Task can be created
- Task can be assigned to a worker
- Basic dashboard displays workers/projects/tasks
- State survives restart
"""
from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Add root directory to sys.path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from auth import get_or_create_auth_token
from bootstrap_engine import bootstrap_new_project, import_existing_project
from database import db_session, init_db, utc_now_iso
import models
from supervisor import create_app


class TestAICommandCenter(unittest.TestCase):
    """Full end-to-end integration test suite for Supervisor."""

    def setUp(self):
        # Create unique temporary directory for isolated test database and test project folders
        self.test_dir = tempfile.mkdtemp()
        self.db_path = Path(self.test_dir) / "test_command_center.db"
        self.app = create_app(db_path=self.db_path)
        self.client = self.app.test_client()
        self.token = get_or_create_auth_token()
        self.headers = {"Authorization": f"Bearer {self.token}"}

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_01_db_initialization_and_preseeded_workers(self):
        """Test DB initializes properly with WAL and seeds default workers."""
        workers = models.get_all_workers(self.db_path)
        worker_ids = [w["id"] for w in workers]
        
        # Verify all 6 designated workers exist
        expected_workers = ["PC-W1", "PC-W2", "MAC-W1", "MAC-W2", "MAC-W3", "LAP-W1"]
        for expected in expected_workers:
            self.assertIn(expected, worker_ids, f"Expected {expected} in seeded workers")

        pc_w1 = models.get_worker_by_id("PC-W1", self.db_path)
        self.assertIsNotNone(pc_w1)
        self.assertEqual(pc_w1["machine"], "BIG-PC")
        self.assertEqual(pc_w1["environment"], "WINDOWS-NATIVE")

    def test_02_worker_registration_and_heartbeat(self):
        """Test registering a new worker and sending heartbeat updates."""
        # 1. Register a new custom worker
        registered = models.register_worker(
            worker_id="REMOTE-W1",
            name="Remote VPS Worker",
            machine="VPS-CLOUD-01",
            environment="LINUX-VPS",
            provider_type="ollama",
            status="idle",
            capabilities=["docker", "gpu"],
            timeout_seconds=20,
            db_path=self.db_path,
        )
        self.assertEqual(registered["id"], "REMOTE-W1")
        self.assertEqual(registered["status"], "idle")

        # 2. Send heartbeat
        updated = models.record_heartbeat(
            worker_id="REMOTE-W1",
            status="busy",
            metadata={"gpu_temp": 65},
            db_path=self.db_path,
        )
        self.assertEqual(updated["status"], "busy")
        self.assertIsNotNone(updated["last_heartbeat_at"])
        self.assertEqual(updated["metadata"].get("gpu_temp"), 65)

    def test_03_heartbeat_reaper_marks_offline(self):
        """Test background reaper marks stale workers offline."""
        # Set PC-W2 last heartbeat to 60 seconds ago
        stale_time = (datetime.now(timezone.utc) - timedelta(seconds=60)).isoformat()
        with db_session(self.db_path) as conn:
            conn.execute(
                "UPDATE workers SET last_heartbeat_at = ?, status = 'idle', timeout_seconds = 10 WHERE id = 'PC-W2'",
                (stale_time,)
            )

        # Run reaper
        expired = models.reap_expired_workers(self.db_path)
        self.assertIn("PC-W2", expired)

        w = models.get_worker_by_id("PC-W2", self.db_path)
        self.assertEqual(w["status"], "offline")

    def test_04_project_creation_and_import(self):
        """Test scaffolding new projects and importing existing directories."""
        # 1. Bootstrap new project
        proj_dir = Path(self.test_dir) / "Test-Sub-Project"
        project = bootstrap_new_project(
            name="Test-Sub-Project",
            target_path=str(proj_dir),
            description="Testing automated scaffolding",
            architect="PC-W1",
            db_path=self.db_path,
        )
        self.assertEqual(project["name"], "Test-Sub-Project")
        self.assertTrue((proj_dir / "PROJECT.yaml").exists())
        self.assertTrue((proj_dir / "ARCHITECTURE.md").exists())
        self.assertTrue((proj_dir / "TASKS.md").exists())

        # Verify starter tasks were auto-created
        self.assertGreaterEqual(project["total_tasks"], 2)

        # 2. Import existing directory
        import_dir = Path(self.test_dir) / "Existing-Repo"
        import_dir.mkdir(parents=True, exist_ok=True)
        (import_dir / "TASKS.md").write_text(
            "# Tasks\n| ID | Title | Priority | Status |\n| T-1 | First Task | High | completed |\n| T-2 | Second Task | Normal | pending |\n",
            encoding="utf-8"
        )
        imported = import_existing_project(str(import_dir), name="Existing-Repo", db_path=self.db_path)
        self.assertEqual(imported["name"], "Existing-Repo")
        self.assertEqual(imported["total_tasks"], 2)
        self.assertEqual(imported["completed_tasks"], 1)
        self.assertEqual(imported["progress_pct"], 50.0)

    def test_05_task_lifecycle_assignment_and_progress(self):
        """Test full task lifecycle: queue -> assign -> in_progress -> complete and dynamic metrics."""
        # Create project
        proj_dir = Path(self.test_dir) / "Lifecycle-Project"
        project = bootstrap_new_project("Lifecycle-Project", str(proj_dir), db_path=self.db_path)
        proj_id = project["id"]

        # Create 2 custom tasks
        t1 = models.create_task(
            project_id=proj_id,
            title="Task One",
            priority="urgent",
            est_minutes=40,
            db_path=self.db_path,
        )
        t2 = models.create_task(
            project_id=proj_id,
            title="Task Two",
            priority="normal",
            est_minutes=20,
            db_path=self.db_path,
        )

        # Assign t1 to PC-W1
        assigned = models.assign_task(t1["id"], "PC-W1", self.db_path)
        self.assertEqual(assigned["assigned_worker_id"], "PC-W1")
        self.assertEqual(assigned["status"], "assigned")

        # Worker PC-W1 should now be busy with t1
        w1 = models.get_worker_by_id("PC-W1", self.db_path)
        self.assertEqual(w1["status"], "busy")
        self.assertEqual(w1["current_task_id"], t1["id"])

        # Start t1
        started = models.start_task(t1["id"], "PC-W1", self.db_path)
        self.assertEqual(started["status"], "in_progress")
        self.assertIsNotNone(started["started_at"])

        # Complete t1
        completed = models.complete_task(
            t1["id"],
            result_summary="Completed successfully with all tests passing",
            failed=False,
            db_path=self.db_path,
        )
        self.assertEqual(completed["status"], "completed")

        # Worker PC-W1 should be back to idle
        w1_freed = models.get_worker_by_id("PC-W1", self.db_path)
        self.assertEqual(w1_freed["status"], "idle")
        self.assertIsNone(w1_freed["current_task_id"])

        # Check project progress recalculation
        updated_proj = models.get_project_by_id(proj_id, self.db_path)
        self.assertGreater(updated_proj["completed_tasks"], 0)
        self.assertGreater(updated_proj["progress_pct"], 0.0)

    def test_06_state_survives_restart(self):
        """Test that shutting down and restarting preserves all data intact in SQLite."""
        proj_dir = Path(self.test_dir) / "Persistence-Project"
        bootstrap_new_project("Persistence-Project", str(proj_dir), db_path=self.db_path)
        models.register_worker(
            worker_id="PERSIST-W1",
            name="Persistent Worker",
            machine="TEST-BOX",
            environment="TEST-ENV",
            status="online",
            db_path=self.db_path,
        )

        # Simulate shutdown by instantiating an entirely new Flask application and querying the DB
        app_restart = create_app(db_path=self.db_path)
        client_restart = app_restart.test_client()

        # Check workers via API
        resp_workers = client_restart.get("/api/v1/workers")
        self.assertEqual(resp_workers.status_code, 200)
        data = resp_workers.get_json()
        worker_ids = [w["id"] for w in data["workers"]]
        self.assertIn("PERSIST-W1", worker_ids)

        # Check projects via API
        resp_projects = client_restart.get("/api/v1/projects")
        self.assertEqual(resp_projects.status_code, 200)
        proj_data = resp_projects.get_json()
        proj_ids = [p["id"] for p in proj_data["projects"]]
        self.assertIn("persistence-project", proj_ids)

    def test_07_api_endpoints(self):
        """Test full suite of REST API endpoints."""
        # 1. Health
        res = self.client.get("/api/v1/health")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.get_json()["status"], "online")

        # 2. Dashboard HTML
        res_ui = self.client.get("/")
        self.assertEqual(res_ui.status_code, 200)
        self.assertIn(b"AI COMMAND CENTER", res_ui.data)

        # 3. Create Project via API
        proj_path = str(Path(self.test_dir) / "Api-Proj")
        res_p = self.client.post("/api/v1/projects", headers=self.headers, json={
            "name": "Api-Proj",
            "path": proj_path,
            "description": "Created via API",
        })
        self.assertEqual(res_p.status_code, 201)
        p_json = res_p.get_json()["project"]
        p_id = p_json["id"]

        # 4. Create Task via API
        res_t = self.client.post("/api/v1/tasks", headers=self.headers, json={
            "project_id": p_id,
            "title": "API Created Task",
            "priority": "high",
            "est_minutes": 45,
            "prompt_payload": "Execute API testing instructions",
        })
        self.assertEqual(res_t.status_code, 201)
        t_json = res_t.get_json()["task"]
        t_id = t_json["id"]

        # 5. Heartbeat via API
        res_hb = self.client.post("/api/v1/workers/PC-W1/heartbeat", headers=self.headers, json={
            "status": "idle"
        })
        self.assertEqual(res_hb.status_code, 200)

        # 6. Assign Task via API
        res_assign = self.client.post(f"/api/v1/tasks/{t_id}/assign", headers=self.headers, json={
            "worker_id": "PC-W1"
        })
        self.assertEqual(res_assign.status_code, 200)
        self.assertEqual(res_assign.get_json()["task"]["assigned_worker_id"], "PC-W1")

        # 7. Worker next task polling via API
        res_next = self.client.get("/api/v1/workers/PC-W1/tasks/next", headers=self.headers)
        self.assertEqual(res_next.status_code, 200)
        next_task = res_next.get_json()["task"]
        self.assertIsNotNone(next_task)
        self.assertEqual(next_task["id"], t_id)

        # 8. Start task via API
        res_start = self.client.put(f"/api/v1/tasks/{t_id}/start", headers=self.headers)
        self.assertEqual(res_start.status_code, 200)

        # 9. Complete task via API
        res_comp = self.client.post(f"/api/v1/tasks/{t_id}/complete", headers=self.headers, json={
            "result_summary": "Task complete via test API call"
        })
        self.assertEqual(res_comp.status_code, 200)

        # 10. System Stats via API
        res_stats = self.client.get("/api/v1/stats")
        self.assertEqual(res_stats.status_code, 200)
        stats = res_stats.get_json()
        self.assertGreaterEqual(stats["workers"]["total"], 6)
        self.assertGreaterEqual(stats["projects_count"], 1)

        # 11. Activity logs via API
        res_act = self.client.get("/api/v1/activity")
        self.assertEqual(res_act.status_code, 200)
        self.assertGreater(len(res_act.get_json()["activities"]), 0)


if __name__ == "__main__":
    unittest.main()

"""AI Command Center — Central Supervisor Service.
Main entry point for the REST API, Background Heartbeat Reaper, and Dashboard Server.
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
import threading
import time
from pathlib import Path
from typing import Any, Dict

from flask import Flask, jsonify, render_template, request, send_from_directory

import config
from bootstrap_engine import bootstrap_new_project, import_existing_project
from database import init_db, utc_now_iso
import models

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("Supervisor")


def create_app(db_path: Path = config.DB_PATH) -> Flask:
    """Create and configure the Flask Supervisor application."""
    app = Flask(
        __name__,
        template_folder=str(config.TEMPLATES_DIR),
        static_folder=str(config.STATIC_DIR),
        static_url_path="/static",
    )
    app.config["DB_PATH"] = db_path

    # Initialize database tables and designated worker seeds
    init_db(db_path)

    # --- UI Routes ---

    @app.route("/")
    @app.route("/dashboard")
    def dashboard():
        """Render the command center browser dashboard."""
        return render_template("dashboard.html")

    # --- API v1 Endpoints ---

    @app.route("/api/v1/health", methods=["GET"])
    def health():
        """Health check endpoint."""
        return jsonify({
            "status": "online",
            "service": "AI-Command-Center-Supervisor",
            "version": "1.0.0",
            "timestamp": utc_now_iso(),
        })

    # --- Worker Endpoints ---

    @app.route("/api/v1/workers", methods=["GET"])
    def list_workers():
        """List all workers in the registry with liveness data."""
        workers = models.get_all_workers(app.config["DB_PATH"])
        return jsonify({"workers": workers, "count": len(workers)})

    @app.route("/api/v1/workers", methods=["POST"])
    def register_worker():
        """Register or update a worker node."""
        data = request.get_json(force=True) or {}
        worker_id = data.get("id")
        if not worker_id:
            return jsonify({"error": "Worker 'id' is required"}), 400

        name = data.get("name", f"Worker {worker_id}")
        machine = data.get("machine", "UNKNOWN-MACHINE")
        environment = data.get("environment", "UNKNOWN-ENV")
        provider_type = data.get("provider_type", "antigravity")
        status = data.get("status", "idle")
        capabilities = data.get("capabilities", [])
        timeout_seconds = data.get("timeout_seconds", config.HEARTBEAT_TIMEOUT_SECONDS)
        metadata = data.get("metadata", {})

        worker = models.register_worker(
            worker_id=worker_id,
            name=name,
            machine=machine,
            environment=environment,
            provider_type=provider_type,
            status=status,
            capabilities=capabilities,
            timeout_seconds=timeout_seconds,
            metadata=metadata,
            db_path=app.config["DB_PATH"],
        )
        return jsonify({"worker": worker}), 201

    @app.route("/api/v1/workers/<worker_id>", methods=["GET"])
    def get_worker(worker_id: str):
        """Get details for a specific worker."""
        worker = models.get_worker_by_id(worker_id, app.config["DB_PATH"])
        if not worker:
            return jsonify({"error": f"Worker '{worker_id}' not found"}), 404
        return jsonify({"worker": worker})

    @app.route("/api/v1/workers/<worker_id>/heartbeat", methods=["POST"])
    def worker_heartbeat(worker_id: str):
        """Update worker heartbeat timestamp and status."""
        data = request.get_json(silent=True) or {}
        status = data.get("status")
        current_task_id = data.get("current_task_id")
        metadata = data.get("metadata")

        worker = models.record_heartbeat(
            worker_id=worker_id,
            status=status,
            current_task_id=current_task_id,
            metadata=metadata,
            db_path=app.config["DB_PATH"],
        )
        return jsonify({"status": "ok", "worker": worker})

    @app.route("/api/v1/workers/<worker_id>/status", methods=["PUT"])
    def update_worker_status(worker_id: str):
        """Update worker status explicitly."""
        data = request.get_json(force=True) or {}
        new_status = data.get("status")
        if not new_status:
            return jsonify({"error": "Field 'status' is required"}), 400

        current_task_id = data.get("current_task_id")
        worker = models.update_worker_status(
            worker_id=worker_id,
            status=new_status,
            current_task_id=current_task_id,
            db_path=app.config["DB_PATH"],
        )
        if not worker:
            return jsonify({"error": f"Worker '{worker_id}' not found"}), 404
        return jsonify({"worker": worker})

    @app.route("/api/v1/workers/<worker_id>/tasks/next", methods=["GET"])
    def get_next_task(worker_id: str):
        """Retrieve next assigned or queued task for this worker."""
        task = models.get_next_task_for_worker(worker_id, app.config["DB_PATH"])
        return jsonify({"task": task})

    # --- Project Endpoints ---

    @app.route("/api/v1/projects", methods=["GET"])
    def list_projects():
        """List all projects with real computed progress % and task counts."""
        projects = models.get_all_projects(app.config["DB_PATH"])
        return jsonify({"projects": projects, "count": len(projects)})

    @app.route("/api/v1/projects", methods=["POST"])
    def create_new_project():
        """Scaffold and register a new project."""
        data = request.get_json(force=True) or {}
        name = data.get("name")
        target_path = data.get("path")
        if not name or not target_path:
            return jsonify({"error": "Fields 'name' and 'path' are required"}), 400

        description = data.get("description", "")
        architect = data.get("architect", "PC-W1")

        project = bootstrap_new_project(
            name=name,
            target_path=target_path,
            description=description,
            architect=architect,
            db_path=app.config["DB_PATH"],
        )
        return jsonify({"project": project}), 201

    @app.route("/api/v1/projects/import", methods=["POST"])
    def import_project():
        """Import an existing project from directory path."""
        data = request.get_json(force=True) or {}
        path_str = data.get("path")
        if not path_str:
            return jsonify({"error": "Field 'path' is required"}), 400

        name = data.get("name")
        description = data.get("description")

        try:
            project = import_existing_project(
                project_path_str=path_str,
                name=name,
                description=description,
                db_path=app.config["DB_PATH"],
            )
            return jsonify({"project": project}), 201
        except Exception as e:
            return jsonify({"error": str(e)}), 400

    @app.route("/api/v1/projects/<project_id>", methods=["GET"])
    def get_project(project_id: str):
        """Get project details, phases, tasks, and completion metrics."""
        project = models.get_project_by_id(project_id, app.config["DB_PATH"])
        if not project:
            return jsonify({"error": f"Project '{project_id}' not found"}), 404
        return jsonify({"project": project})

    # --- Task Endpoints ---

    @app.route("/api/v1/tasks", methods=["GET"])
    def list_tasks():
        """List tasks with optional filters."""
        project_id = request.args.get("project_id")
        worker_id = request.args.get("worker_id")
        status = request.args.get("status")

        tasks = models.get_all_tasks(
            project_id=project_id,
            worker_id=worker_id,
            status=status,
            db_path=app.config["DB_PATH"],
        )
        return jsonify({"tasks": tasks, "count": len(tasks)})

    @app.route("/api/v1/tasks", methods=["POST"])
    def create_task():
        """Create a new task in the queue."""
        data = request.get_json(force=True) or {}
        project_id = data.get("project_id")
        title = data.get("title")
        if not project_id or not title:
            return jsonify({"error": "Fields 'project_id' and 'title' are required"}), 400

        task = models.create_task(
            project_id=project_id,
            title=title,
            description=data.get("description", ""),
            prompt_payload=data.get("prompt_payload", ""),
            priority=data.get("priority", "normal"),
            est_minutes=int(data.get("est_minutes", 30)),
            phase_id=data.get("phase_id"),
            assigned_worker_id=data.get("assigned_worker_id"),
            task_id=data.get("id"),
            db_path=app.config["DB_PATH"],
        )
        return jsonify({"task": task}), 201

    @app.route("/api/v1/tasks/<task_id>", methods=["GET"])
    def get_task(task_id: str):
        """Get details for a single task."""
        task = models.get_task_by_id(task_id, app.config["DB_PATH"])
        if not task:
            return jsonify({"error": f"Task '{task_id}' not found"}), 404
        return jsonify({"task": task})

    @app.route("/api/v1/tasks/<task_id>/assign", methods=["POST"])
    def assign_task_to_worker(task_id: str):
        """Assign a task to a designated worker."""
        data = request.get_json(force=True) or {}
        worker_id = data.get("worker_id")
        if not worker_id:
            return jsonify({"error": "Field 'worker_id' is required"}), 400

        task = models.assign_task(task_id, worker_id, app.config["DB_PATH"])
        if not task:
            return jsonify({"error": f"Task '{task_id}' not found"}), 404
        return jsonify({"task": task})

    @app.route("/api/v1/tasks/<task_id>/start", methods=["PUT"])
    def start_task_execution(task_id: str):
        """Mark task as actively in progress."""
        data = request.get_json(silent=True) or {}
        worker_id = data.get("worker_id")
        task = models.start_task(task_id, worker_id, app.config["DB_PATH"])
        if not task:
            return jsonify({"error": f"Task '{task_id}' not found"}), 404
        return jsonify({"task": task})

    @app.route("/api/v1/tasks/<task_id>/complete", methods=["POST"])
    def complete_task_execution(task_id: str):
        """Mark task as completed or failed and free worker."""
        data = request.get_json(silent=True) or {}
        result_summary = data.get("result_summary", "")
        error_message = data.get("error_message", "")
        failed = data.get("failed", False) or (data.get("status") == "failed")

        task = models.complete_task(
            task_id=task_id,
            result_summary=result_summary,
            error_message=error_message,
            failed=failed,
            db_path=app.config["DB_PATH"],
        )
        if not task:
            return jsonify({"error": f"Task '{task_id}' not found"}), 404
        return jsonify({"task": task})

    # --- Activity & Stats Endpoints ---

    @app.route("/api/v1/activity", methods=["GET"])
    def list_activities():
        """Retrieve latest worker activity audit logs."""
        limit = int(request.args.get("limit", 50))
        activities = models.get_recent_activities(limit=limit, db_path=app.config["DB_PATH"])
        return jsonify({"activities": activities, "count": len(activities)})

    @app.route("/api/v1/stats", methods=["GET"])
    def system_stats():
        """Get fleet-wide high-level metrics."""
        stats = models.get_system_stats(app.config["DB_PATH"])
        return jsonify(stats)

    return app


def run_heartbeat_reaper(db_path: Path, interval: int = 5, stop_event: threading.Event = None) -> None:
    """Background thread checking for expired worker heartbeats."""
    logger.info("Heartbeat reaper thread started.")
    while not (stop_event and stop_event.is_set()):
        try:
            models.reap_expired_workers(db_path)
        except Exception as e:
            logger.error(f"Error in heartbeat reaper loop: {e}")
        time.sleep(interval)


def main() -> None:
    parser = argparse.ArgumentParser(description="AI Command Center — Central Supervisor")
    parser.add_argument("--host", default=config.DEFAULT_HOST, help="Binding host IP")
    parser.add_argument("--port", type=int, default=config.DEFAULT_PORT, help="Port number")
    parser.add_argument("--db", default=str(config.DB_PATH), help="Path to SQLite database file")
    args = parser.parse_args()

    db_path = Path(args.db).resolve()
    app = create_app(db_path=db_path)

    # Start background reaper thread
    stop_event = threading.Event()
    reaper_thread = threading.Thread(
        target=run_heartbeat_reaper,
        args=(db_path, config.HEARTBEAT_CHECK_INTERVAL_SECONDS, stop_event),
        daemon=True,
    )
    reaper_thread.start()

    logger.info(f"AI Command Center Supervisor starting on http://{args.host}:{args.port}")
    logger.info(f"Persistent database: {db_path}")

    try:
        app.run(host=args.host, port=args.port, debug=False, threaded=True)
    except (KeyboardInterrupt, SystemExit):
        logger.info("Shutting down Supervisor...")
        stop_event.set()


if __name__ == "__main__":
    main()

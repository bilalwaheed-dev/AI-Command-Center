"""Domain models and business logic for workers, projects, and tasks."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
import uuid

from database import db_session, log_activity, row_to_dict, utc_now_iso


# --- Worker Operations ---

def get_all_workers(db_path: Optional[Path] = None) -> List[Dict[str, Any]]:
    """Retrieve all workers with computed liveness."""
    now_dt = datetime.now(timezone.utc)
    with db_session(db_path) as conn:
        rows = conn.execute("""
            SELECT w.*, t.title as current_task_title 
            FROM workers w 
            LEFT JOIN tasks t ON w.current_task_id = t.id 
            ORDER BY w.id ASC
        """).fetchall()

        workers = []
        for r in rows:
            w = row_to_dict(r)
            last_hb = w.get("last_heartbeat_at")
            if last_hb:
                try:
                    hb_dt = datetime.fromisoformat(last_hb)
                    w["heartbeat_age_seconds"] = max(0, int((now_dt - hb_dt).total_seconds()))
                except Exception:
                    w["heartbeat_age_seconds"] = None
            else:
                w["heartbeat_age_seconds"] = None
            workers.append(w)
        return workers


def get_worker_by_id(worker_id: str, db_path: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    """Get a worker by its unique identifier."""
    with db_session(db_path) as conn:
        row = conn.execute("SELECT * FROM workers WHERE id = ?", (worker_id,)).fetchone()
        return row_to_dict(row) if row else None


def register_worker(
    worker_id: str,
    name: str,
    machine: str,
    environment: str,
    provider_type: str = "antigravity",
    status: str = "online",
    capabilities: Optional[List[str]] = None,
    timeout_seconds: int = 30,
    metadata: Optional[Dict[str, Any]] = None,
    db_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Register or update a worker node."""
    now = utc_now_iso()
    cap_json = json.dumps(capabilities or [])
    meta_json = json.dumps(metadata or {})

    with db_session(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM workers WHERE id = ?", (worker_id,))
        exists = cursor.fetchone()

        if exists:
            cursor.execute("""
                UPDATE workers SET
                    name = ?, machine = ?, environment = ?, provider_type = ?,
                    status = ?, timeout_seconds = ?, capabilities = ?, metadata = ?,
                    last_heartbeat_at = ?, updated_at = ?
                WHERE id = ?
            """, (
                name, machine, environment, provider_type, status,
                timeout_seconds, cap_json, meta_json, now, now, worker_id
            ))
            event_type = "worker_updated"
            msg = f"Worker {worker_id} updated: {status}"
        else:
            cursor.execute("""
                INSERT INTO workers (
                    id, name, machine, environment, provider_type, status,
                    timeout_seconds, capabilities, metadata, last_heartbeat_at,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                worker_id, name, machine, environment, provider_type, status,
                timeout_seconds, cap_json, meta_json, now, now, now
            ))
            event_type = "worker_registered"
            msg = f"Worker {worker_id} ({name}) registered on {machine} [{environment}]"

    log_activity(event_type, msg, worker_id=worker_id, payload={"status": status}, db_path=db_path)
    return get_worker_by_id(worker_id, db_path)  # type: ignore


def record_heartbeat(
    worker_id: str,
    status: Optional[str] = None,
    current_task_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    db_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Record a worker heartbeat and keep status alive."""
    now = utc_now_iso()
    with db_session(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, status, current_task_id, metadata FROM workers WHERE id = ?", (worker_id,))
        row = cursor.fetchone()
        if not row:
            # Auto-register minimal worker
            cursor.execute("""
                INSERT INTO workers (
                    id, name, machine, environment, provider_type, status,
                    last_heartbeat_at, timeout_seconds, capabilities, metadata,
                    created_at, updated_at
                ) VALUES (?, ?, 'UNKNOWN', 'UNKNOWN', 'antigravity', 'online', ?, 30, '[]', '{}', ?, ?)
            """, (worker_id, worker_id, now, now, now))
            new_status = status or "online"
        else:
            current_status = row["status"]
            # If status explicitly provided, use it; otherwise restore to idle or online if it was offline
            if status:
                new_status = status
            elif current_status == "offline":
                new_status = "idle"
            else:
                new_status = current_status

        # Merge metadata if supplied
        meta_json = json.dumps(metadata) if metadata else None
        if meta_json:
            cursor.execute("""
                UPDATE workers SET
                    last_heartbeat_at = ?,
                    status = ?,
                    current_task_id = COALESCE(?, current_task_id),
                    metadata = ?,
                    updated_at = ?
                WHERE id = ?
            """, (now, new_status, current_task_id, meta_json, now, worker_id))
        else:
            cursor.execute("""
                UPDATE workers SET
                    last_heartbeat_at = ?,
                    status = ?,
                    current_task_id = COALESCE(?, current_task_id),
                    updated_at = ?
                WHERE id = ?
            """, (now, new_status, current_task_id, now, worker_id))

    return get_worker_by_id(worker_id, db_path)  # type: ignore


def update_worker_status(
    worker_id: str,
    status: str,
    current_task_id: Optional[str] = None,
    db_path: Optional[Path] = None,
) -> Optional[Dict[str, Any]]:
    """Explicitly change a worker's status."""
    now = utc_now_iso()
    with db_session(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT status FROM workers WHERE id = ?", (worker_id,))
        row = cursor.fetchone()
        if not row:
            return None
        old_status = row["status"]
        cursor.execute("""
            UPDATE workers 
            SET status = ?, current_task_id = ?, updated_at = ?
            WHERE id = ?
        """, (status, current_task_id, now, worker_id))

    if old_status != status:
        log_activity(
            "worker_status_change",
            f"Worker {worker_id} status changed from {old_status} to {status}",
            worker_id=worker_id,
            task_id=current_task_id,
            payload={"old_status": old_status, "new_status": status},
            db_path=db_path,
        )
    return get_worker_by_id(worker_id, db_path)


def reap_expired_workers(db_path: Optional[Path] = None) -> List[str]:
    """Background task: mark workers whose heartbeats have expired as offline."""
    now_dt = datetime.now(timezone.utc)
    expired_workers = []

    with db_session(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, last_heartbeat_at, timeout_seconds, status 
            FROM workers 
            WHERE status != 'offline'
        """)
        rows = cursor.fetchall()
        for row in rows:
            worker_id = row["id"]
            last_hb_str = row["last_heartbeat_at"]
            timeout = row["timeout_seconds"] or 30

            if not last_hb_str:
                expired = True
            else:
                try:
                    hb_dt = datetime.fromisoformat(last_hb_str)
                    age = (now_dt - hb_dt).total_seconds()
                    expired = age > timeout
                except Exception:
                    expired = True

            if expired:
                cursor.execute("""
                    UPDATE workers SET status = 'offline', updated_at = ? WHERE id = ?
                """, (utc_now_iso(), worker_id))
                expired_workers.append(worker_id)

    for w_id in expired_workers:
        log_activity(
            "worker_offline",
            f"Worker {w_id} marked OFFLINE due to heartbeat timeout",
            worker_id=w_id,
            db_path=db_path,
        )

    return expired_workers


# --- Project Operations ---

def get_all_projects(db_path: Optional[Path] = None) -> List[Dict[str, Any]]:
    """Retrieve all projects with dynamically computed progress % and task counts."""
    with db_session(db_path) as conn:
        projects_rows = conn.execute("SELECT * FROM projects ORDER BY created_at DESC").fetchall()
        projects = []
        for p_row in projects_rows:
            p = row_to_dict(p_row)
            p_id = p["id"]

            # Aggregate task counts
            task_counts = conn.execute("""
                SELECT 
                    COUNT(*) as total_tasks,
                    SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed_tasks,
                    SUM(CASE WHEN status = 'in_progress' THEN 1 ELSE 0 END) as in_progress_tasks,
                    SUM(CASE WHEN status IN ('pending', 'queued', 'assigned') THEN 1 ELSE 0 END) as pending_tasks,
                    SUM(CASE WHEN status = 'blocked' THEN 1 ELSE 0 END) as blocked_tasks,
                    SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed_tasks,
                    SUM(CASE WHEN status != 'completed' THEN est_minutes ELSE 0 END) as remaining_est_minutes
                FROM tasks WHERE project_id = ?
            """, (p_id,)).fetchone()

            total = task_counts["total_tasks"] or 0
            completed = task_counts["completed_tasks"] or 0
            p["total_tasks"] = total
            p["completed_tasks"] = completed
            p["in_progress_tasks"] = task_counts["in_progress_tasks"] or 0
            p["pending_tasks"] = task_counts["pending_tasks"] or 0
            p["blocked_tasks"] = task_counts["blocked_tasks"] or 0
            p["failed_tasks"] = task_counts["failed_tasks"] or 0
            p["remaining_tasks"] = max(0, total - completed)
            p["remaining_est_minutes"] = task_counts["remaining_est_minutes"] or 0
            p["progress_pct"] = round((completed / total) * 100.0, 1) if total > 0 else 0.0

            projects.append(p)
        return projects


def get_project_by_id(project_id: str, db_path: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    """Retrieve project details, including its phases and tasks."""
    with db_session(db_path) as conn:
        p_row = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
        if not p_row:
            return None
        project = row_to_dict(p_row)

        # Phases
        phases = conn.execute(
            "SELECT * FROM phases WHERE project_id = ? ORDER BY order_index ASC", (project_id,)
        ).fetchall()
        project["phases"] = [row_to_dict(ph) for ph in phases]

        # Tasks
        tasks = conn.execute(
            "SELECT * FROM tasks WHERE project_id = ? ORDER BY created_at ASC", (project_id,)
        ).fetchall()
        project["tasks"] = [row_to_dict(t) for t in tasks]

        # Dynamic metrics
        total = len(project["tasks"])
        completed = sum(1 for t in project["tasks"] if t["status"] == "completed")
        project["total_tasks"] = total
        project["completed_tasks"] = completed
        project["remaining_tasks"] = max(0, total - completed)
        project["progress_pct"] = round((completed / total) * 100.0, 1) if total > 0 else 0.0
        project["remaining_est_minutes"] = sum(
            t.get("est_minutes", 0) for t in project["tasks"] if t["status"] != "completed"
        )
        return project


def create_project(
    project_id: str,
    name: str,
    path: str,
    description: str = "",
    status: str = "active",
    current_phase: str = "Phase 1 - Kickoff",
    eta_target: str = "",
    db_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Create a new project record and default phase."""
    now = utc_now_iso()
    with db_session(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO projects (id, name, description, path, status, current_phase, eta_target, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (project_id, name, description, path, status, current_phase, eta_target, now, now))

        # Default Phase
        phase_id = f"{project_id}-phase-1"
        cursor.execute("""
            INSERT INTO phases (id, project_id, name, order_index, status, created_at)
            VALUES (?, ?, ?, 1, 'in_progress', ?)
        """, (phase_id, project_id, current_phase, now))

    log_activity(
        "project_created",
        f"Project created: {name} ({project_id}) at {path}",
        project_id=project_id,
        db_path=db_path,
    )
    return get_project_by_id(project_id, db_path)  # type: ignore


# --- Task Operations ---

def get_all_tasks(
    project_id: Optional[str] = None,
    worker_id: Optional[str] = None,
    status: Optional[str] = None,
    db_path: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    """Retrieve tasks with optional filters."""
    query = """
        SELECT t.*, p.name as project_name, w.name as worker_name
        FROM tasks t
        JOIN projects p ON t.project_id = p.id
        LEFT JOIN workers w ON t.assigned_worker_id = w.id
        WHERE 1=1
    """
    params: List[Any] = []
    if project_id:
        query += " AND t.project_id = ?"
        params.append(project_id)
    if worker_id:
        query += " AND t.assigned_worker_id = ?"
        params.append(worker_id)
    if status:
        query += " AND t.status = ?"
        params.append(status)

    query += " ORDER BY CASE t.priority WHEN 'urgent' THEN 1 WHEN 'high' THEN 2 WHEN 'normal' THEN 3 ELSE 4 END, t.created_at ASC"

    with db_session(db_path) as conn:
        rows = conn.execute(query, params).fetchall()
        return [row_to_dict(r) for r in rows]


def get_task_by_id(task_id: str, db_path: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    """Get single task details."""
    with db_session(db_path) as conn:
        row = conn.execute("""
            SELECT t.*, p.name as project_name, w.name as worker_name
            FROM tasks t
            JOIN projects p ON t.project_id = p.id
            LEFT JOIN workers w ON t.assigned_worker_id = w.id
            WHERE t.id = ?
        """, (task_id,)).fetchone()
        return row_to_dict(row) if row else None


def create_task(
    project_id: str,
    title: str,
    description: str = "",
    prompt_payload: str = "",
    priority: str = "normal",
    est_minutes: int = 30,
    phase_id: Optional[str] = None,
    assigned_worker_id: Optional[str] = None,
    task_id: Optional[str] = None,
    db_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Create a new task in the queue."""
    tid = task_id or f"TASK-{uuid.uuid4().hex[:8].upper()}"
    now = utc_now_iso()
    status = "assigned" if assigned_worker_id else "queued"

    with db_session(db_path) as conn:
        conn.execute("""
            INSERT INTO tasks (
                id, project_id, phase_id, title, description, prompt_payload,
                status, assigned_worker_id, priority, est_minutes, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            tid, project_id, phase_id, title, description, prompt_payload,
            status, assigned_worker_id, priority, est_minutes, now, now
        ))

        # If assigned immediately, update worker
        if assigned_worker_id:
            conn.execute("""
                UPDATE workers SET current_task_id = ?, status = 'busy', updated_at = ? WHERE id = ?
            """, (tid, now, assigned_worker_id))

    log_activity(
        "task_created",
        f"Task {tid} created: '{title}' [{priority}]" + (f" -> Assigned to {assigned_worker_id}" if assigned_worker_id else ""),
        worker_id=assigned_worker_id,
        task_id=tid,
        project_id=project_id,
        db_path=db_path,
    )
    return get_task_by_id(tid, db_path)  # type: ignore


def assign_task(
    task_id: str,
    worker_id: str,
    db_path: Optional[Path] = None,
) -> Optional[Dict[str, Any]]:
    """Assign a task to a designated worker."""
    now = utc_now_iso()
    with db_session(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, project_id, title FROM tasks WHERE id = ?", (task_id,))
        task_row = cursor.fetchone()
        if not task_row:
            return None

        # Update task
        cursor.execute("""
            UPDATE tasks SET assigned_worker_id = ?, status = 'assigned', updated_at = ? WHERE id = ?
        """, (worker_id, now, task_id))

        # Update worker
        cursor.execute("""
            UPDATE workers SET current_task_id = ?, status = 'busy', updated_at = ? WHERE id = ?
        """, (task_id, now, worker_id))

    log_activity(
        "task_assigned",
        f"Task {task_id} assigned to worker {worker_id}",
        worker_id=worker_id,
        task_id=task_id,
        project_id=task_row["project_id"],
        db_path=db_path,
    )
    return get_task_by_id(task_id, db_path)


def start_task(task_id: str, worker_id: Optional[str] = None, db_path: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    """Mark a task as actively in progress."""
    now = utc_now_iso()
    with db_session(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, project_id, assigned_worker_id FROM tasks WHERE id = ?", (task_id,))
        task_row = cursor.fetchone()
        if not task_row:
            return None

        assigned = worker_id or task_row["assigned_worker_id"]
        cursor.execute("""
            UPDATE tasks 
            SET status = 'in_progress', started_at = COALESCE(started_at, ?), updated_at = ?
            WHERE id = ?
        """, (now, now, task_id))

        if assigned:
            cursor.execute("""
                UPDATE workers SET current_task_id = ?, status = 'busy', updated_at = ? WHERE id = ?
            """, (task_id, now, assigned))

    log_activity(
        "task_started",
        f"Task {task_id} execution started by worker {assigned or 'UNKNOWN'}",
        worker_id=assigned,
        task_id=task_id,
        project_id=task_row["project_id"],
        db_path=db_path,
    )
    return get_task_by_id(task_id, db_path)


def complete_task(
    task_id: str,
    result_summary: str = "",
    error_message: str = "",
    failed: bool = False,
    db_path: Optional[Path] = None,
) -> Optional[Dict[str, Any]]:
    """Complete or fail a task, freeing the worker."""
    now = utc_now_iso()
    final_status = "failed" if failed else "completed"

    with db_session(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, project_id, assigned_worker_id, title FROM tasks WHERE id = ?", (task_id,))
        task_row = cursor.fetchone()
        if not task_row:
            return None

        assigned = task_row["assigned_worker_id"]

        cursor.execute("""
            UPDATE tasks 
            SET status = ?, result_summary = ?, error_message = ?, completed_at = ?, updated_at = ?
            WHERE id = ?
        """, (final_status, result_summary, error_message, now, now, task_id))

        # Free the assigned worker back to idle
        if assigned:
            cursor.execute("""
                UPDATE workers 
                SET current_task_id = NULL, status = 'idle', updated_at = ? 
                WHERE id = ? AND current_task_id = ?
            """, (now, assigned, task_id))

    event_type = "task_failed" if failed else "task_completed"
    msg = f"Task {task_id} marked {final_status}: {result_summary or error_message or task_row['title']}"
    log_activity(
        event_type,
        msg,
        worker_id=assigned,
        task_id=task_id,
        project_id=task_row["project_id"],
        payload={"result": result_summary, "error": error_message},
        db_path=db_path,
    )
    return get_task_by_id(task_id, db_path)


def get_next_task_for_worker(worker_id: str, db_path: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    """Retrieve the next queued or assigned task for a specific worker."""
    with db_session(db_path) as conn:
        # First check if this worker has an assigned task waiting
        row = conn.execute("""
            SELECT * FROM tasks 
            WHERE assigned_worker_id = ? AND status IN ('assigned', 'in_progress')
            ORDER BY CASE priority WHEN 'urgent' THEN 1 WHEN 'high' THEN 2 WHEN 'normal' THEN 3 ELSE 4 END, created_at ASC
            LIMIT 1
        """, (worker_id,)).fetchone()

        if row:
            return row_to_dict(row)

        # Otherwise check for queued unassigned tasks
        row = conn.execute("""
            SELECT * FROM tasks 
            WHERE assigned_worker_id IS NULL AND status = 'queued'
            ORDER BY CASE priority WHEN 'urgent' THEN 1 WHEN 'high' THEN 2 WHEN 'normal' THEN 3 ELSE 4 END, created_at ASC
            LIMIT 1
        """).fetchone()

        if row:
            # Auto-assign to this worker
            task_dict = row_to_dict(row)
            return assign_task(task_dict["id"], worker_id, db_path)

        return None


# --- Activity Feed & System Stats ---

def get_recent_activities(limit: int = 50, db_path: Optional[Path] = None) -> List[Dict[str, Any]]:
    """Get the latest audit activity events."""
    with db_session(db_path) as conn:
        rows = conn.execute("""
            SELECT * FROM worker_activities ORDER BY created_at DESC, id DESC LIMIT ?
        """, (limit,)).fetchall()
        return [row_to_dict(r) for r in rows]


def get_system_stats(db_path: Optional[Path] = None) -> Dict[str, Any]:
    """Calculate fleet-wide aggregated metrics."""
    with db_session(db_path) as conn:
        worker_counts = conn.execute("""
            SELECT
                COUNT(*) as total_workers,
                SUM(CASE WHEN status = 'online' THEN 1 ELSE 0 END) as online_workers,
                SUM(CASE WHEN status = 'idle' THEN 1 ELSE 0 END) as idle_workers,
                SUM(CASE WHEN status = 'busy' THEN 1 ELSE 0 END) as busy_workers,
                SUM(CASE WHEN status = 'blocked' THEN 1 ELSE 0 END) as blocked_workers,
                SUM(CASE WHEN status = 'offline' THEN 1 ELSE 0 END) as offline_workers
            FROM workers
        """).fetchone()

        task_counts = conn.execute("""
            SELECT
                COUNT(*) as total_tasks,
                SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed_tasks,
                SUM(CASE WHEN status = 'in_progress' THEN 1 ELSE 0 END) as in_progress_tasks,
                SUM(CASE WHEN status IN ('pending', 'queued', 'assigned') THEN 1 ELSE 0 END) as pending_tasks,
                SUM(CASE WHEN status = 'blocked' THEN 1 ELSE 0 END) as blocked_tasks,
                SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed_tasks
            FROM tasks
        """).fetchone()

        project_count = conn.execute("SELECT COUNT(*) as count FROM projects").fetchone()["count"]

        total_t = task_counts["total_tasks"] or 0
        comp_t = task_counts["completed_tasks"] or 0
        overall_progress = round((comp_t / total_t) * 100.0, 1) if total_t > 0 else 0.0

        return {
            "workers": {
                "total": worker_counts["total_workers"] or 0,
                "online": worker_counts["online_workers"] or 0,
                "idle": worker_counts["idle_workers"] or 0,
                "busy": worker_counts["busy_workers"] or 0,
                "blocked": worker_counts["blocked_workers"] or 0,
                "offline": worker_counts["offline_workers"] or 0,
            },
            "tasks": {
                "total": total_t,
                "completed": comp_t,
                "in_progress": task_counts["in_progress_tasks"] or 0,
                "pending": task_counts["pending_tasks"] or 0,
                "blocked": task_counts["blocked_tasks"] or 0,
                "failed": task_counts["failed_tasks"] or 0,
                "remaining": max(0, total_t - comp_t),
            },
            "projects_count": project_count,
            "overall_progress_pct": overall_progress,
        }

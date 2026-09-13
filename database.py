"""SQLite persistent database layer for AI Command Center.
Configured with Write-Ahead Logging (WAL) for high concurrency and restart safety.
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional

from config import DB_PATH, DEFAULT_WORKERS


def utc_now_iso() -> str:
    """Return current UTC time in ISO format."""
    return datetime.now(timezone.utc).isoformat()


def get_connection(db_path: Optional[Path] = None) -> sqlite3.Connection:
    """Get a configured SQLite database connection."""
    target_path = db_path or DB_PATH
    target_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(target_path), check_same_thread=False, timeout=30.0)
    conn.row_factory = sqlite3.Row

    # Performance and concurrency pragmas
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA busy_timeout = 30000;")
    return conn


@contextmanager
def db_session(db_path: Optional[Path] = None) -> Generator[sqlite3.Connection, None, None]:
    """Context manager for safe database transactions."""
    conn = get_connection(db_path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db(db_path: Optional[Path] = None) -> None:
    """Initialize database tables and seed initial worker records."""
    with db_session(db_path) as conn:
        cursor = conn.cursor()

        # 1. Workers table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS workers (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                machine TEXT NOT NULL,
                environment TEXT NOT NULL,
                provider_type TEXT NOT NULL DEFAULT 'antigravity',
                status TEXT NOT NULL DEFAULT 'offline',
                current_task_id TEXT,
                last_heartbeat_at TEXT,
                timeout_seconds INTEGER NOT NULL DEFAULT 30,
                capabilities TEXT NOT NULL DEFAULT '[]',
                metadata TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
        """)

        # 2. Projects table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS projects (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT DEFAULT '',
                path TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'planning',
                current_phase TEXT DEFAULT 'Phase 1 - Kickoff',
                eta_target TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
        """)

        # 3. Phases table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS phases (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                name TEXT NOT NULL,
                order_index INTEGER NOT NULL DEFAULT 1,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL,
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
            );
        """)

        # 4. Tasks table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                phase_id TEXT,
                title TEXT NOT NULL,
                description TEXT DEFAULT '',
                prompt_payload TEXT DEFAULT '',
                status TEXT NOT NULL DEFAULT 'pending',
                assigned_worker_id TEXT,
                priority TEXT NOT NULL DEFAULT 'normal',
                est_minutes INTEGER NOT NULL DEFAULT 30,
                result_summary TEXT DEFAULT '',
                error_message TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                started_at TEXT,
                completed_at TEXT,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
                FOREIGN KEY (assigned_worker_id) REFERENCES workers(id) ON DELETE SET NULL
            );
        """)

        # 5. Worker Activity Audit Log
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS worker_activities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                worker_id TEXT,
                task_id TEXT,
                project_id TEXT,
                event_type TEXT NOT NULL,
                message TEXT NOT NULL,
                payload TEXT DEFAULT '{}',
                created_at TEXT NOT NULL
            );
        """)

        # Indexes for fast dashboard and task queries
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_project ON tasks(project_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_worker ON tasks(assigned_worker_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_activities_worker ON worker_activities(worker_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_activities_time ON worker_activities(created_at);")

        # Pre-seed default designated workers if not existing
        now = utc_now_iso()
        for w in DEFAULT_WORKERS:
            cursor.execute("SELECT id FROM workers WHERE id = ?", (w["id"],))
            if not cursor.fetchone():
                cursor.execute("""
                    INSERT INTO workers (
                        id, name, machine, environment, provider_type, status,
                        last_heartbeat_at, timeout_seconds, capabilities, metadata,
                        created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    w["id"],
                    w["name"],
                    w["machine"],
                    w["environment"],
                    w["provider_type"],
                    w["status"],
                    now if w["status"] in ("online", "idle") else None,
                    w.get("timeout_seconds", 30),
                    json.dumps(w.get("capabilities", [])),
                    json.dumps({}),
                    now,
                    now
                ))

                # Log activity
                cursor.execute("""
                    INSERT INTO worker_activities (worker_id, event_type, message, payload, created_at)
                    VALUES (?, 'seed', ?, ?, ?)
                """, (
                    w["id"],
                    f"Worker {w['id']} initialized in registry ({w['name']})",
                    json.dumps(w),
                    now
                ))


# --- Data Access Helpers ---

def row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    """Convert sqlite3.Row to dictionary with JSON fields parsed."""
    d = dict(row)
    for json_field in ("capabilities", "metadata", "payload"):
        if json_field in d and isinstance(d[json_field], str):
            try:
                d[json_field] = json.loads(d[json_field])
            except Exception:
                pass
    return d


def log_activity(
    event_type: str,
    message: str,
    worker_id: Optional[str] = None,
    task_id: Optional[str] = None,
    project_id: Optional[str] = None,
    payload: Optional[Dict[str, Any]] = None,
    db_path: Optional[Path] = None,
) -> None:
    """Record an audit log entry in the activity table."""
    now = utc_now_iso()
    payload_str = json.dumps(payload or {})
    with db_session(db_path) as conn:
        conn.execute("""
            INSERT INTO worker_activities (worker_id, task_id, project_id, event_type, message, payload, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (worker_id, task_id, project_id, event_type, message, payload_str, now))

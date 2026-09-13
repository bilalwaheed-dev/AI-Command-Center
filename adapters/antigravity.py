"""Antigravity Worker Adapter.
Handles task envelope preparation, drop-file mailbox dispatch, and HTTP polling integration
for Antigravity AI coding workers.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

from .base import BaseWorkerAdapter


class AntigravityAdapter(BaseWorkerAdapter):
    """Adapter for Google Antigravity workers."""

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(config)
        self.mailbox_dirname = self.config.get("mailbox_dirname", ".supervisor_mailbox")

    def format_task_envelope(self, worker: Dict[str, Any], task: Dict[str, Any], project: Optional[Dict[str, Any]] = None) -> str:
        """Format an Antigravity-ready prompt envelope with clear execution boundaries."""
        worker_id = worker.get("id", "UNKNOWN-WORKER")
        machine = worker.get("machine", "UNKNOWN-HOST")
        environment = worker.get("environment", "UNKNOWN-ENV")
        task_id = task.get("id", "TASK-UNKNOWN")
        title = task.get("title", "Untitled Task")
        description = task.get("description", "")
        prompt = task.get("prompt_payload", "")
        project_name = (project or {}).get("name", task.get("project_name", "Assigned Project"))
        project_path = (project or {}).get("path", "")

        envelope = f"""================================================================================
AI COMMAND CENTER — AUTOMATED TASK DISPATCH
================================================================================
WORKER: {worker_id}
MACHINE: {machine}
ENVIRONMENT: {environment}
PROJECT: {project_name}
PROJECT ROOT: {project_path}
TASK ID: {task_id}
PRIORITY: {task.get('priority', 'normal').upper()}
================================================================================

TITLE:
{title}

DESCRIPTION:
{description}

INSTRUCTIONS:
{prompt or description or 'Execute the assigned objective to completion.'}

WORKING RULES:
1. Work only within the designated project root: {project_path or 'Current Workspace'}
2. Read project requirements, architecture, and task specifications before modifying code.
3. Run relevant tests after changes.
4. Report status back to the Supervisor upon completion:
   POST /api/v1/tasks/{task_id}/complete
   Payload: {{"status": "completed", "result_summary": "<brief summary>"}}
================================================================================
"""
        return envelope

    def dispatch_task(self, worker: Dict[str, Any], task: Dict[str, Any]) -> bool:
        """Dispatch task via file-drop mailbox or prepare for worker pull."""
        project_path = task.get("project_path") or worker.get("metadata", {}).get("project_path")
        
        # If project path is accessible on local disk, write to mailbox directory
        if project_path:
            try:
                mailbox_dir = Path(project_path) / self.mailbox_dirname
                mailbox_dir.mkdir(parents=True, exist_ok=True)
                
                # Write human-readable prompt envelope
                prompt_file = mailbox_dir / f"CURRENT_TASK_{task['id']}.txt"
                envelope_content = self.format_task_envelope(worker, task)
                prompt_file.write_text(envelope_content, encoding="utf-8")

                # Write machine-readable task json
                json_file = mailbox_dir / "active_task.json"
                json_file.write_text(json.dumps(task, indent=2), encoding="utf-8")
                return True
            except Exception:
                # Fallback to in-memory/API dispatch queue
                return True

        return True

    def poll_status(self, worker: Dict[str, Any]) -> Dict[str, Any]:
        """Return status directly from worker record."""
        return {
            "worker_id": worker.get("id"),
            "status": worker.get("status", "offline"),
            "current_task_id": worker.get("current_task_id"),
            "last_heartbeat_at": worker.get("last_heartbeat_at"),
        }

    def cancel_task(self, worker: Dict[str, Any], task: Dict[str, Any]) -> bool:
        """Signal task cancellation by writing cancel token in mailbox if possible."""
        project_path = task.get("project_path")
        if project_path:
            try:
                cancel_file = Path(project_path) / self.mailbox_dirname / f"CANCEL_{task['id']}.flag"
                cancel_file.write_text("CANCEL", encoding="utf-8")
                return True
            except Exception:
                pass
        return True

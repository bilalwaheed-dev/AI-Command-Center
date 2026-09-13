"""HTTP Daemon Worker Adapter.
Interfaces with remote or local worker daemons running `worker_daemon.py`.
"""
from __future__ import annotations

from typing import Any, Dict, Optional
import requests

from .base import BaseWorkerAdapter


class HttpDaemonAdapter(BaseWorkerAdapter):
    """Adapter for headless Python daemon workers."""

    def dispatch_task(self, worker: Dict[str, Any], task: Dict[str, Any]) -> bool:
        """If worker has a direct callback URL, push task; otherwise it pulls via API."""
        endpoint = worker.get("metadata", {}).get("webhook_url")
        if endpoint:
            try:
                resp = requests.post(endpoint, json={"task": task}, timeout=5.0)
                return resp.status_code in (200, 201, 202)
            except Exception:
                return False
        # If no push endpoint, worker will pull from /api/v1/workers/{id}/tasks/next
        return True

    def poll_status(self, worker: Dict[str, Any]) -> Dict[str, Any]:
        """Poll worker daemon directly if URL provided."""
        endpoint = worker.get("metadata", {}).get("status_url")
        if endpoint:
            try:
                resp = requests.get(endpoint, timeout=3.0)
                if resp.status_code == 200:
                    return resp.json()
            except Exception:
                pass
        return {
            "worker_id": worker.get("id"),
            "status": worker.get("status", "offline"),
            "current_task_id": worker.get("current_task_id"),
        }

    def cancel_task(self, worker: Dict[str, Any], task: Dict[str, Any]) -> bool:
        """Send cancel request to worker daemon."""
        endpoint = worker.get("metadata", {}).get("cancel_url")
        if endpoint:
            try:
                resp = requests.post(endpoint, json={"task_id": task.get("id")}, timeout=3.0)
                return resp.status_code == 200
            except Exception:
                return False
        return True

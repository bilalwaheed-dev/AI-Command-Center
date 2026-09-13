"""Mock Worker Adapter for unit tests and local simulations."""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from .base import BaseWorkerAdapter


class MockWorkerAdapter(BaseWorkerAdapter):
    """In-memory mock adapter tracking calls."""

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(config)
        self.dispatched_tasks: List[Dict[str, Any]] = []
        self.cancelled_tasks: List[Dict[str, Any]] = []

    def dispatch_task(self, worker: Dict[str, Any], task: Dict[str, Any]) -> bool:
        self.dispatched_tasks.append({"worker": worker, "task": task})
        return True

    def poll_status(self, worker: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "worker_id": worker.get("id"),
            "status": worker.get("status", "idle"),
            "mock": True,
        }

    def cancel_task(self, worker: Dict[str, Any], task: Dict[str, Any]) -> bool:
        self.cancelled_tasks.append({"worker": worker, "task": task})
        return True

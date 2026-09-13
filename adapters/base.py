"""Abstract base class for all worker adapters in AI Command Center."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


class BaseWorkerAdapter(ABC):
    """Abstract interface defining the communication contract with worker runtimes."""

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        self.config = config or {}

    @abstractmethod
    def dispatch_task(self, worker: Dict[str, Any], task: Dict[str, Any]) -> bool:
        """Deliver or prepare a task for execution by the worker.
        
        Args:
            worker: Dictionary containing worker metadata, host, environment.
            task: Dictionary containing task id, prompt payload, project info.
            
        Returns:
            True if successfully dispatched/queued, False otherwise.
        """
        pass

    @abstractmethod
    def poll_status(self, worker: Dict[str, Any]) -> Dict[str, Any]:
        """Query the current operational status of the worker.
        
        Returns:
            Dictionary with at least {"status": "online"|"idle"|"busy"|"blocked"|"offline"}.
        """
        pass

    @abstractmethod
    def cancel_task(self, worker: Dict[str, Any], task: Dict[str, Any]) -> bool:
        """Request cancellation of an active task on the worker.
        
        Returns:
            True if cancelled or signal sent, False otherwise.
        """
        pass

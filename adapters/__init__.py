"""Worker adapters for AI Command Center."""
from .base import BaseWorkerAdapter
from .antigravity import AntigravityAdapter
from .http_daemon import HttpDaemonAdapter
from .mock import MockWorkerAdapter

__all__ = [
    "BaseWorkerAdapter",
    "AntigravityAdapter",
    "HttpDaemonAdapter",
    "MockWorkerAdapter",
]

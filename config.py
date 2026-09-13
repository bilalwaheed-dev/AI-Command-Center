"""Configuration module for AI Command Center."""
from __future__ import annotations

import os
from pathlib import Path

# Base directories
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"
PROJECTS_ROOT = BASE_DIR.parent  # Default root for sibling projects

DATA_DIR.mkdir(parents=True, exist_ok=True)
TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
STATIC_DIR.mkdir(parents=True, exist_ok=True)

# Server settings
DEFAULT_HOST = os.getenv("COMMAND_CENTER_HOST", "127.0.0.1")
DEFAULT_PORT = int(os.getenv("COMMAND_CENTER_PORT", "5050"))
DEBUG = os.getenv("COMMAND_CENTER_DEBUG", "False").lower() in ("true", "1", "yes")

# Database settings
DB_PATH = Path(os.getenv("COMMAND_CENTER_DB", str(DATA_DIR / "command_center.db")))

# Heartbeat & Reaper settings
HEARTBEAT_TIMEOUT_SECONDS = int(os.getenv("HEARTBEAT_TIMEOUT_SECONDS", "30"))
HEARTBEAT_CHECK_INTERVAL_SECONDS = int(os.getenv("HEARTBEAT_CHECK_INTERVAL_SECONDS", "5"))

# Pre-seeded Designated Workers
DEFAULT_WORKERS = [
    {
        "id": "PC-W1",
        "name": "Big PC Windows Native",
        "machine": "BIG-PC",
        "environment": "WINDOWS-NATIVE",
        "provider_type": "antigravity",
        "capabilities": ["code", "architect", "supervisor_host", "windows_native"],
        "status": "idle",
        "timeout_seconds": 30,
    },
    {
        "id": "PC-W2",
        "name": "Big PC WSL2 Ubuntu",
        "machine": "BIG-PC",
        "environment": "WSL2-UBUNTU",
        "provider_type": "antigravity",
        "capabilities": ["code", "linux_native", "bash", "docker", "python"],
        "status": "offline",
        "timeout_seconds": 30,
    },
    {
        "id": "MAC-W1",
        "name": "Mac Worker 1",
        "machine": "MACBOOK-1",
        "environment": "DARWIN-NATIVE",
        "provider_type": "antigravity",
        "capabilities": ["code", "macos_native", "darwin_builds"],
        "status": "offline",
        "timeout_seconds": 30,
    },
    {
        "id": "MAC-W2",
        "name": "Mac Worker 2",
        "machine": "MACBOOK-2",
        "environment": "DARWIN-NATIVE",
        "provider_type": "antigravity",
        "capabilities": ["code", "macos_native", "frontend", "testing"],
        "status": "offline",
        "timeout_seconds": 30,
    },
    {
        "id": "MAC-W3",
        "name": "Mac Worker 3",
        "machine": "MACBOOK-3",
        "environment": "DARWIN-NATIVE",
        "provider_type": "antigravity",
        "capabilities": ["code", "macos_native", "research", "scraping"],
        "status": "offline",
        "timeout_seconds": 30,
    },
    {
        "id": "LAP-W1",
        "name": "Field Laptop Worker",
        "machine": "LAPTOP-1",
        "environment": "WINDOWS-PORTABLE",
        "provider_type": "antigravity",
        "capabilities": ["code", "remote_ops"],
        "status": "offline",
        "timeout_seconds": 30,
    },
]

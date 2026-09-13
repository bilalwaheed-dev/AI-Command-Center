"""Headless Worker Daemon Client for AI Command Center.
Can be executed on Windows Native, WSL2 Ubuntu, macOS, or remote VPS workers.
Communicates with the Central Supervisor over HTTP using Bearer token authentication.
"""
from __future__ import annotations

import argparse
import os
import platform
import signal
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional
import requests


class WorkerDaemon:
    """Daemon running on a worker node, reporting heartbeat, polling and executing tasks."""

    def __init__(
        self,
        server_url: str,
        worker_id: str,
        token: Optional[str] = None,
        name: Optional[str] = None,
        machine: Optional[str] = None,
        environment: Optional[str] = None,
        provider_type: str = "antigravity",
        poll_interval: int = 5,
        heartbeat_interval: int = 10,
    ) -> None:
        self.server_url = server_url.rstrip("/")
        self.worker_id = worker_id
        self.name = name or f"Worker {worker_id}"
        self.machine = machine or platform.node() or "UNKNOWN-HOST"
        self.environment = environment or f"{platform.system().upper()}-NATIVE"
        self.provider_type = provider_type
        self.poll_interval = poll_interval
        self.heartbeat_interval = heartbeat_interval
        self.running = False
        self.current_task: Optional[Dict[str, Any]] = None
        self.status = "idle"

        # Resolve token
        self.token = token or os.getenv("COMMAND_CENTER_TOKEN")
        if not self.token:
            # Check local file fallback if on same host
            secret_file = Path(__file__).resolve().parent / "data" / "auth_token.secret"
            if secret_file.exists():
                try:
                    self.token = secret_file.read_text(encoding="utf-8").strip()
                except Exception:
                    pass

    def headers(self) -> Dict[str, str]:
        """Generate HTTP headers including Bearer authorization."""
        h = {"Content-Type": "application/json"}
        if self.token:
            h["Authorization"] = f"Bearer {self.token}"
            h["X-Worker-Token"] = self.token
        return h

    def api_url(self, path: str) -> str:
        return f"{self.server_url}/api/v1{path}"

    def register(self) -> bool:
        """Register worker with the central supervisor."""
        payload = {
            "id": self.worker_id,
            "name": self.name,
            "machine": self.machine,
            "environment": self.environment,
            "provider_type": self.provider_type,
            "status": self.status,
            "capabilities": ["code", "terminal", "python", self.environment.lower()],
            "timeout_seconds": self.heartbeat_interval * 3,
            "metadata": {
                "os": platform.platform(),
                "python_version": platform.python_version(),
                "pid": os.getpid(),
            }
        }
        try:
            resp = requests.post(
                self.api_url("/workers"),
                json=payload,
                headers=self.headers(),
                timeout=5.0
            )
            if resp.status_code in (200, 201):
                print(f"[{self.worker_id}] Successfully registered with Supervisor at {self.server_url}")
                return True
            else:
                print(f"[{self.worker_id}] Registration failed: HTTP {resp.status_code} - {resp.text}")
                return False
        except Exception as e:
            print(f"[{self.worker_id}] Cannot reach Supervisor at {self.server_url}: {e}")
            return False

    def send_heartbeat(self) -> bool:
        """Send heartbeat ping to maintain online/idle/busy status."""
        payload = {
            "status": self.status,
            "current_task_id": self.current_task.get("id") if self.current_task else None,
            "metadata": {"timestamp": time.time()},
        }
        try:
            resp = requests.post(
                self.api_url(f"/workers/{self.worker_id}/heartbeat"),
                json=payload,
                headers=self.headers(),
                timeout=5.0
            )
            return resp.status_code == 200
        except Exception as e:
            print(f"[{self.worker_id}] Heartbeat ping failed: {e}")
            return False

    def report_status(self, new_status: str, error_message: str = "") -> bool:
        """Explicitly report worker operational state (idle, busy, blocked)."""
        self.status = new_status
        payload = {
            "status": new_status,
            "current_task_id": self.current_task.get("id") if self.current_task else None,
            "metadata": {"error": error_message} if error_message else {},
        }
        try:
            resp = requests.put(
                self.api_url(f"/workers/{self.worker_id}/status"),
                json=payload,
                headers=self.headers(),
                timeout=5.0
            )
            return resp.status_code == 200
        except Exception as e:
            print(f"[{self.worker_id}] Status update failed: {e}")
            return False

    def fetch_next_task(self) -> Optional[Dict[str, Any]]:
        """Poll supervisor for next assigned or queued task."""
        try:
            resp = requests.get(
                self.api_url(f"/workers/{self.worker_id}/tasks/next"),
                headers=self.headers(),
                timeout=5.0
            )
            if resp.status_code == 200:
                data = resp.json()
                return data.get("task")
            elif resp.status_code == 401:
                print(f"[{self.worker_id}] Authentication failed: invalid Bearer token")
            return None
        except Exception:
            return None

    def execute_task(self, task: Dict[str, Any]) -> bool:
        """Process an assigned task and report completion."""
        task_id = task["id"]
        title = task.get("title", "")
        print(f"\n[{self.worker_id}] === STARTING TASK {task_id}: '{title}' ===")
        self.status = "busy"
        self.current_task = task

        # Notify supervisor that execution started
        try:
            requests.put(
                self.api_url(f"/tasks/{task_id}/start"),
                json={"worker_id": self.worker_id},
                headers=self.headers(),
                timeout=5.0
            )
        except Exception as e:
            print(f"[{self.worker_id}] Warning: could not notify start: {e}")

        prompt = task.get("prompt_payload") or task.get("description") or "No prompt details"
        print(f"[{self.worker_id}] Prompt Instructions:\n{prompt}")

        # Simulated execution hook
        time.sleep(1.5)

        # Report completion
        result_summary = f"Task completed successfully by {self.worker_id} on {self.machine} [{self.environment}]"
        success = True
        try:
            resp = requests.post(
                self.api_url(f"/tasks/{task_id}/complete"),
                json={"result_summary": result_summary, "status": "completed"},
                headers=self.headers(),
                timeout=5.0
            )
            if resp.status_code == 200:
                print(f"[{self.worker_id}] Task {task_id} completed and reported to Supervisor.")
            else:
                print(f"[{self.worker_id}] Failed to report completion: {resp.text}")
                success = False
        except Exception as e:
            print(f"[{self.worker_id}] Error reporting completion: {e}")
            success = False
        finally:
            self.current_task = None
            self.status = "idle"
            self.send_heartbeat()

        return success

    def run(self, once: bool = False) -> None:
        """Main daemon loop."""
        self.running = True
        print(f"Starting Worker Daemon {self.worker_id} [{self.environment}] on {self.machine}...")
        if self.token:
            print(f"[{self.worker_id}] Authenticated with Bearer token: {self.token[:8]}...")
        else:
            print(f"[{self.worker_id}] Warning: No Bearer token configured")

        if not self.register():
            print("Initial registration failed; will continue heartbeat attempts...")

        last_hb = 0.0
        while self.running:
            now = time.time()
            # Heartbeat check
            if now - last_hb >= self.heartbeat_interval:
                self.send_heartbeat()
                last_hb = now

            # Task polling (only if idle)
            if self.status == "idle":
                task = self.fetch_next_task()
                if task:
                    self.execute_task(task)
                    if once:
                        break

            if once:
                break

            time.sleep(self.poll_interval)

    def shutdown(self) -> None:
        """Gracefully disconnect worker."""
        print(f"\n[{self.worker_id}] Shutting down...")
        self.running = False
        try:
            requests.put(
                self.api_url(f"/workers/{self.worker_id}/status"),
                json={"status": "offline"},
                headers=self.headers(),
                timeout=3.0
            )
        except Exception:
            pass


def main() -> None:
    parser = argparse.ArgumentParser(description="AI Command Center — Worker Daemon")
    parser.add_argument("--server", default="http://127.0.0.1:5050", help="Supervisor server base URL")
    parser.add_argument("--worker-id", default="PC-W1", help="Worker unique identifier (e.g. PC-W1, PC-W2, MAC-W1)")
    parser.add_argument("--token", default=None, help="Bearer authentication token")
    parser.add_argument("--name", default=None, help="Human-readable worker name")
    parser.add_argument("--machine", default=None, help="Machine name (e.g. BIG-PC, MACBOOK)")
    parser.add_argument("--env", default=None, help="Environment name (e.g. WINDOWS-NATIVE, WSL2-UBUNTU)")
    parser.add_argument("--provider", default="antigravity", help="Worker provider type")
    parser.add_argument("--poll-interval", type=int, default=3, help="Seconds between task polls")
    parser.add_argument("--heartbeat-interval", type=int, default=10, help="Seconds between heartbeats")
    parser.add_argument("--once", action="store_true", help="Run a single poll/execution cycle and exit")
    args = parser.parse_args()

    daemon = WorkerDaemon(
        server_url=args.server,
        worker_id=args.worker_id,
        token=args.token,
        name=args.name,
        machine=args.machine,
        environment=args.env,
        provider_type=args.provider,
        poll_interval=args.poll_interval,
        heartbeat_interval=args.heartbeat_interval,
    )

    def sig_handler(sig, frame):
        daemon.shutdown()
        sys.exit(0)

    signal.signal(signal.SIGINT, sig_handler)
    signal.signal(signal.SIGTERM, sig_handler)

    daemon.run(once=args.once)


if __name__ == "__main__":
    main()

# AI Command Center — System Requirements Specification (SRS)

**Document Version:** 1.0.0  
**Status:** Approved  
**Author:** PC-W1 (Bootstrap Architect)

---

## 1. Functional Requirements (FR)

### FR-01: Central Supervisor Service
- **FR-01.1:** The supervisor must run as a standalone, self-contained HTTP service.
- **FR-01.2:** It must support binding to `127.0.0.1` or `0.0.0.0` on a configurable port (default: 5050).
- **FR-01.3:** It must start cleanly, handle graceful shutdown, and recover full state upon restart.

### FR-02: Worker Registry & Identification
- **FR-02.1:** Each worker must possess a globally unique identifier (e.g., `PC-W1`, `PC-W2`, `MAC-W1`, `MAC-W2`, `MAC-W3`, `LAP-W1`).
- **FR-02.2:** Workers must register metadata: human-readable name, machine host (`BIG-PC`, `MACBOOK-PRO`, etc.), environment (`WINDOWS-NATIVE`, `WSL2-UBUNTU`, `DARWIN-NATIVE`, `LINUX-VPS`), provider type (`antigravity`, `ollama`, `gemini`, `claude`, `openai`, `custom_script`, `human`), and declared capabilities.
- **FR-02.3:** The registry must allow dynamic registration of new workers and updating of existing worker configurations.

### FR-03: Worker Heartbeat & Lifecycle State
- **FR-03.1:** Workers must report periodic heartbeats via HTTP POST `/api/v1/workers/{worker_id}/heartbeat`.
- **FR-03.2:** Supported worker operational states:
  - `online` — Heartbeat active, connected.
  - `offline` — Heartbeat expired beyond threshold (e.g., >30 seconds).
  - `idle` — Ready to accept assigned tasks.
  - `busy` — Currently executing a task.
  - `blocked` — Execution stopped due to missing input, human review, or error.
- **FR-03.3:** The supervisor must run a background liveness loop that marks dead workers as `offline` without hanging HTTP requests.

### FR-04: Task Queue & Assignment
- **FR-04.1:** Tasks must support status transitions: `pending` -> `queued` -> `assigned` -> `in_progress` -> `completed` / `failed` / `blocked`.
- **FR-04.2:** Each task must include: ID, Project ID, Phase ID, Title, Description, Prompt Payload, Priority (`low`, `normal`, `high`, `urgent`), Estimated Minutes, Assigned Worker, and Completion Timestamps.
- **FR-04.3:** Tasks can be assigned manually via the dashboard/API or auto-dispatched to idle eligible workers.
- **FR-04.4:** Workers must be able to fetch their next pending task via `/api/v1/workers/{worker_id}/tasks/next`.
- **FR-04.5:** Workers must submit task results, execution logs, and completion/failure statuses via dedicated endpoints.

### FR-05: Project Registry & Project Bootstrap Engine
- **FR-05.1:** Projects must store: ID, Name, Description, Project Path, Status (`planning`, `active`, `paused`, `completed`, `archived`), Current Phase, and Target ETA.
- **FR-05.2:** Project Creation: The system must provide a project generator that sets up a standardized directory structure with `PROJECT.yaml`, `ARCHITECTURE.md`, `ROADMAP.md`, `TASKS.md`, and `REQUIREMENTS.md`.
- **FR-05.3:** Project Import: The system must accept an existing filesystem path and register it into the supervisor database, automatically parsing existing task files or `PROJECT.yaml` if present.

### FR-06: Real Task-Based Progress Tracking & ETA
- **FR-06.1:** Project completion percentage must be computed dynamically:
  $$\text{Progress \%} = \left( \frac{\text{Completed Tasks}}{\text{Total Tasks}} \right) \times 100$$
  If total tasks is 0, progress is 0.0%.
- **FR-06.2:** The system must calculate remaining work count:
  $$\text{Remaining Tasks} = \text{Total Tasks} - \text{Completed Tasks}$$
- **FR-06.3:** The system must compute estimated remaining time based on task `est_minutes` sum for incomplete tasks.

### FR-07: Worker Activity & Audit Log Events
- **FR-07.1:** An immutable activity log must capture all critical occurrences: registrations, heartbeat timeouts, state changes, task assignments, task starts, completions, and failures.
- **FR-07.2:** The log must be queryable via API with pagination/limit and streamed to the dashboard in real-time.

### FR-08: Persistent Database & Restart Safety
- **FR-08.1:** All state (workers, projects, phases, tasks, activity logs) must persist in a local SQLite database (`data/command_center.db`).
- **FR-08.2:** SQLite must operate in WAL (Write-Ahead Logging) mode for concurrent access and corruption resistance.
- **FR-08.3:** Stopping and restarting the supervisor must resume existing state with zero data loss.

### FR-09: Web API Specification
- **FR-09.1:** RESTful JSON API under `/api/v1/*`.
- **FR-09.2:** Endpoints for health, workers, projects, tasks, activities, statistics, and project bootstrap/import.

### FR-10: Browser Dashboard
- **FR-10.1:** Clean, responsive, dark-themed dashboard accessible at `http://127.0.0.1:5050/`.
- **FR-10.2:** Displays worker fleet status cards, project progress meters, active task queue, and live activity stream.
- **FR-10.3:** Supports quick actions: create task, assign task, register worker, create/import project.

### FR-11: Worker Adapter Interface & Antigravity Support
- **FR-11.1:** Modular adapter class structure allowing distinct protocols per provider.
- **FR-11.2:** Antigravity adapter supporting mailbox prompt drop, webhook callback, and HTTP polling.
- **FR-11.3:** Standalone worker daemon script (`worker_daemon.py`) for standard headless execution across Windows, Linux, and macOS.

---

## 2. Non-Functional Requirements (NFR)

- **NFR-01 (Portability):** Must run on Python 3.10+ across Windows Native, WSL2, macOS, and Linux without native binary compilation.
- **NFR-02 (Lightweight Dependencies):** Standard Python libraries plus minimal web dependencies (Flask, Werkzeug, Jinja2, PyYAML).
- **NFR-03 (Fault Tolerance):** Invalid inputs or network drops from remote workers must never crash the supervisor daemon.
- **NFR-04 (Isolation):** The Command Center must never modify files outside its own workspace or the explicitly assigned project directory of a task.
- **NFR-05 (Latency):** API response times for worker status and heartbeats must stay under 20ms on local loopback.

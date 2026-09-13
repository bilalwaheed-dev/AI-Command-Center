# AI Command Center — System Architecture

**Version:** 1.0.0-draft  
**System Role:** Central Supervisor & Heterogeneous Worker Orchestration Platform  
**Target Environment:** Local-First (Windows Native, WSL2 Ubuntu, macOS Darwin, Linux VPS)

---

## 1. Executive Overview

The **AI Command Center** is a local-first, provider-agnostic Central Supervisor designed to orchestrate autonomous AI workers operating across multiple machines and execution environments. 

Its primary objective is to eliminate manual copy-pasting of tasks and prompts across workers (such as Antigravity instances, local Ollama models, cloud APIs, and shell daemons), providing a centralized registry, automated task dispatch queue, persistent project tracker, and real-time operational dashboard.

```
+-----------------------------------------------------------------------------------+
|                              AI COMMAND CENTER                                    |
|                             (Central Supervisor)                                  |
|                                                                                   |
|  +------------------+  +-------------------+  +--------------------------------+  |
|  |  Web Dashboard   |  |     REST API      |  |     Event Stream / SSE         |  |
|  |  (HTML5/CSS3/JS) |  |   (Flask Engine)  |  |   (Real-time State Updates)    |  |
|  +--------+---------+  +---------+---------+  +---------------+----------------+  |
|           |                      |                            |                   |
|  +--------v----------------------v----------------------------v----------------+  |
|  |                         Supervisor Core Engine                              |  |
|  |   - Worker Registry & Heartbeat Monitor                                     |  |
|  |   - Project Registry & Progress Calculator                                  |  |
|  |   - Task Queue & Dispatch Manager                                           |  |
|  |   - Project Bootstrap & Import Engine                                       |  |
|  +-------------------------------+--------------------------------------------+  |
|                                  |                                                |
|  +-------------------------------v---------------------------------------------+  |
|  |                     Persistence Layer (SQLite WAL)                          |  |
|  |   workers | projects | phases | tasks | worker_activities | system_config   |  |
|  +-------------------------------+--------------------------------------------+  |
+----------------------------------|------------------------------------------------+
                                   |
                                   | HTTP / Webhook / Mailbox Protocol
                                   v
+-----------------------------------------------------------------------------------+
|                              WORKER FLEET                                         |
|                                                                                   |
|   +-------------------+  +-------------------+  +-------------------+             |
|   |      PC-W1        |  |      PC-W2        |  |      MAC-W1       |             |
|   | (Windows Native)  |  |  (WSL2 Ubuntu)    |  |  (macOS Darwin)   |             |
|   |  Antigravity /    |  |   Local CLI /     |  |   Antigravity /   |             |
|   |  Python Daemon    |  |   Python Daemon   |  |   Python Daemon   |             |
|   +-------------------+  +-------------------+  +-------------------+             |
|   +-------------------+  +-------------------+  +-------------------+             |
|   |      MAC-W2       |  |      MAC-W3       |  |      LAP-W1       |             |
|   |  (macOS Darwin)   |  |  (macOS Darwin)   |  | (Pending Setup)   |             |
|   +-------------------+  +-------------------+  +-------------------+             |
+-----------------------------------------------------------------------------------+
```

---

## 2. Architectural Pillars

1. **Provider Agnostic:** The supervisor treats workers uniformly regardless of whether the execution backend is Google Antigravity, Ollama, OpenAI, Claude, a shell script, or a human operator.
2. **Local-First & Resilient:** Operates completely offline or locally without cloud lock-in. Uses persistent SQLite with Write-Ahead Logging (WAL) to guarantee zero state loss across restarts or crashes.
3. **Cross-Platform Compatibility:** Runs identically on Windows (cmd/PowerShell), Linux/WSL2, and macOS with standard Python 3.10+.
4. **Non-Invasive Worker Boundary:** Project repositories remain isolated. Each worker operates within its assigned project directory and communicates through defined HTTP API endpoints or structured mailbox directories.
5. **Real Task-Based Progress Tracking:** Progress metrics are strictly calculated from completed vs. total tasks, eliminating arbitrary percentage guesses.

---

## 3. Component Architecture

### 3.1 Central Supervisor Service
- **HTTP Web Server:** Light, production-grade REST API server exposing CRUD endpoints for workers, projects, tasks, and activities.
- **Heartbeat & Liveness Reaper:** Background daemon thread checking worker heartbeats every 5 seconds. If a worker fails to ping within its configured timeout (default: 30s), its state transitions from `online`/`idle`/`busy` to `offline`, triggering an activity log event.
- **Task Dispatcher:** Evaluates queued tasks against available idle workers. Dispatches tasks according to priority, worker tags, and capabilities.
- **Progress Calculator Engine:** Dynamically aggregates project completion percentages, remaining work, overdue tasks, and estimated times of completion (ETA).

### 3.2 Persistence Layer (SQLite + WAL)
- **Engine:** SQLite 3 with `PRAGMA journal_mode = WAL;` and `PRAGMA synchronous = NORMAL;` to allow high concurrency between HTTP workers and background threads.
- **Schema Entities:**
  - `workers`: ID, name, machine, environment, provider_type, status (`online`, `offline`, `idle`, `busy`, `blocked`), current_task_id, last_heartbeat_at, timeout_seconds, capabilities, metadata.
  - `projects`: ID, name, description, file_path, status (`planning`, `active`, `paused`, `completed`, `archived`), current_phase, eta_target, created_at, updated_at.
  - `phases`: ID, project_id, name, order_index, status (`pending`, `in_progress`, `completed`).
  - `tasks`: ID, project_id, phase_id, title, description, prompt_payload, status (`pending`, `queued`, `assigned`, `in_progress`, `completed`, `failed`, `blocked`), assigned_worker_id, priority (`low`, `normal`, `high`, `urgent`), est_minutes, result_summary, error_message, created_at, started_at, completed_at, updated_at.
  - `worker_activities`: ID, worker_id, task_id, project_id, event_type, message, payload_json, timestamp.

### 3.3 Worker Adapter Subsystem
The Supervisor interfaces with workers through a modular adapter design:
```
+-------------------------------------------------------------+
|                      BaseWorkerAdapter                      |
|  - dispatch_task(worker, task) -> bool                      |
|  - poll_status(worker) -> dict                              |
|  - cancel_task(worker, task) -> bool                        |
+------------------------------+------------------------------+
                               ^
         +---------------------+---------------------+
         |                     |                     |
+--------+---------+  +--------+---------+  +--------+---------+
| AntigravityAdapter| |  HttpDaemonAdapter| |   OllamaAdapter   |
| (Mailbox/Webhook)|  | (REST Long-Poll) |  | (Local Inference)|
+------------------+  +------------------+  +------------------+
```
- **Antigravity Worker Adapter:** Designed to deliver task prompts to Antigravity sessions via:
  1. *Direct Mailbox / Dropfile Protocol:* Writes `.task.json` prompts into worker task drop directories.
  2. *API Polling Protocol:* The Antigravity worker or its companion sidecar polls `/api/v1/workers/{worker_id}/tasks/next`.
  3. *Webhook Callback:* Receives completion reports from workers via `/api/v1/tasks/{task_id}/complete`.
- **HttpDaemonAdapter:** A lightweight standard daemon (`worker_daemon.py`) that can run on any machine (PC-W2, MAC-W1, etc.) to report hardware metrics, accept prompts, execute tasks, and pipe back logs.
- **Ollama / LLM Adapter:** For direct inference dispatch to local models.

### 3.4 Browser Dashboard
- Single-page responsive web console served directly by the Supervisor.
- Visual Fleet Monitor (grid of 6 worker nodes with live status indicators).
- Active Projects Tracker with real-time percentage progress bars and phase milestones.
- Interactive Task Queue with drag-and-drop or one-click assignment.
- Live Real-time Activity Feed logging every heartbeat, assignment, completion, and error.

---

## 4. Multi-Worker Network Topology

```
+--------------------------------------------------------------------------+
| BIG PC (Host)                                                            |
|                                                                          |
|   +------------------------------------------------------------------+   |
|   | AI-Command-Center Supervisor (Port 5050)                         |   |
|   | http://127.0.0.1:5050 (or LAN IP e.g. 192.168.1.100:5050)       |   |
|   +---------------------------------+--------------------------------+   |
|                                     |                                    |
|   +--------------------------+      |      +-------------------------+   |
|   | PC-W1 (Windows Native)   |<-----+----->| PC-W2 (WSL2 Ubuntu)     |   |
|   | localhost:5050           |             | host.docker.internal    |   |
|   +--------------------------+             +-------------------------+   |
+--------------------------------------------------------------------------+
                                      |
                     LAN / WireGuard / SSH Tunnel
                                      |
       +------------------------------+------------------------------+
       |                              |                              |
+------v---------------+      +-------v--------------+      +--------v-------------+
| MAC-W1 (macOS)       |      | MAC-W2 (macOS)       |      | MAC-W3 / LAP-W1      |
| connects to:         |      | connects to:         |      | connects to:         |
| http://<BIG_PC>:5050 |      | http://<BIG_PC>:5050 |      | http://<BIG_PC>:5050 |
+----------------------+      +----------------------+      +----------------------+
```

---

## 5. Security & Isolation Model
1. **Local-Only by Default:** Binds to `127.0.0.1` by default; configurable to `0.0.0.0` with optional Bearer token authentication for LAN/tailscale/wireguard worker access.
2. **Project Directory Sandboxing:** Worker tasks specify an absolute project path. Workers are prohibited from mutating files outside their assigned project root.
3. **Audit Logging:** Every worker state change, prompt dispatch, and task outcome is immutably appended to the `worker_activities` audit table.

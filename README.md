# AI Command Center

**Central Supervisor and Heterogeneous Worker Orchestrator for Multi-Machine Autonomous Agents.**

---

## Overview

The **AI Command Center** is a local-first, provider-agnostic central coordinator. It solves the multi-agent scaling problem by replacing manual prompt copy-pasting with a persistent task queue, automated prompt dispatch protocol, worker registry, real-time status monitoring, and an interactive browser dashboard.

### Designated Fleet
- **PC-W1**: Big PC / Windows Native (Architect & Supervisor Host)
- **PC-W2**: Big PC / WSL2 Ubuntu
- **MAC-W1**: macOS Darwin Worker 1
- **MAC-W2**: macOS Darwin Worker 2
- **MAC-W3**: macOS Darwin Worker 3
- **LAP-W1**: Portable Field Laptop (Pending Setup)

---

## Quick Start

### 1. Requirements
- Python 3.10+
- Dependencies installed:
  ```bash
  pip install -r requirements.txt
  ```

### 2. Start the Central Supervisor
On Windows:
```cmd
python supervisor.py --host 127.0.0.1 --port 5050
# or double-click start_supervisor.bat
```

On WSL2 / Linux / macOS:
```bash
python3 supervisor.py --host 0.0.0.0 --port 5050
# or ./start_supervisor.sh
```

### 3. Open the Dashboard
Open your browser and navigate to:
```
http://127.0.0.1:5050
```

---

## Connecting Workers

### Running the Headless Daemon
Any machine (PC-W2 in WSL2, MAC-W1, etc.) can connect to the supervisor using `worker_daemon.py`:

```bash
# Example connecting PC-W2 from WSL2:
python worker_daemon.py \
  --server http://127.0.0.1:5050 \
  --worker-id PC-W2 \
  --machine BIG-PC \
  --env WSL2-UBUNTU

# Example connecting MAC-W1 across LAN:
python3 worker_daemon.py \
  --server http://<BIG_PC_LAN_IP>:5050 \
  --worker-id MAC-W1 \
  --machine MACBOOK-1 \
  --env DARWIN-NATIVE
```

---

## API Reference (`/api/v1`)

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/v1/health` | Supervisor service health check |
| `GET` | `/api/v1/workers` | List all registered workers and liveness states |
| `POST` | `/api/v1/workers` | Register or update a worker node |
| `GET` | `/api/v1/workers/<id>` | Worker node details |
| `POST` | `/api/v1/workers/<id>/heartbeat` | Send heartbeat ping with status |
| `PUT` | `/api/v1/workers/<id>/status` | Update worker operational status |
| `GET` | `/api/v1/workers/<id>/tasks/next` | Poll next assigned or queued task |
| `GET` | `/api/v1/projects` | List projects with real calculated progress % |
| `POST` | `/api/v1/projects` | Scaffold and register a new project |
| `POST` | `/api/v1/projects/import` | Ingest existing directory into project registry |
| `GET` | `/api/v1/projects/<id>` | Project details, phases, tasks, and metrics |
| `GET` | `/api/v1/tasks` | Query task queue (supports `?project_id=`, `?worker_id=`, `?status=`) |
| `POST` | `/api/v1/tasks` | Enqueue a new task |
| `GET` | `/api/v1/tasks/<id>` | Task detail |
| `POST` | `/api/v1/tasks/<id>/assign` | Assign task to designated worker |
| `PUT` | `/api/v1/tasks/<id>/start` | Mark task in progress |
| `POST` | `/api/v1/tasks/<id>/complete` | Report task outcome and free worker |
| `GET` | `/api/v1/activity` | Retrieve recent audit log stream |
| `GET` | `/api/v1/stats` | Aggregated system telemetry |

---

## Running Tests

To run the automated verification suite:
```bash
python -m unittest discover -s tests -p "test_*.py"
```

---

## Project Structure
```
AI-Command-Center/
├── ARCHITECTURE.md          # System architecture specification
├── REQUIREMENTS.md          # Functional & non-functional requirements
├── ROADMAP.md               # 5-phase project roadmap
├── PROJECT.yaml             # System configuration and worker seeds
├── TASKS.md                 # WBS and task progress tracker
├── README.md                # Quickstart and usage manual
├── requirements.txt         # Python package dependencies
├── config.py                # Environment & directory configurations
├── database.py              # SQLite WAL persistence layer
├── models.py                # Domain business logic & calculations
├── supervisor.py            # Central REST API & background reaper
├── bootstrap_engine.py      # Project generator & import engine
├── worker_daemon.py         # Standalone worker agent client
├── adapters/
│   ├── base.py              # Abstract worker adapter interface
│   ├── antigravity.py       # Mailbox/file drop & prompt envelope adapter
│   ├── http_daemon.py       # REST callback adapter
│   └── mock.py              # Mock adapter for test suites
├── static/
│   ├── css/dashboard.css    # Responsive dark UI styling
│   └── js/dashboard.js      # Real-time state controller
├── templates/
│   └── dashboard.html       # Browser dashboard view
├── tests/
│   ├── test_supervisor.py   # E2E supervisor & persistence tests
│   └── test_adapters.py     # Worker adapter tests
├── start_supervisor.bat     # Windows launcher
└── start_supervisor.sh      # POSIX/WSL launcher
```

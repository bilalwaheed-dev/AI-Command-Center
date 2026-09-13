# AI Command Center — Strategic Roadmap

**Project:** AI Command Center  
**Lead Architect:** PC-W1 (Big PC / Windows Native)  
**Lifecycle Stage:** Phase 2 Complete (Fleet Onboarded & Secured)

---

## Roadmap Overview

```
+--------------------------------------------------------------------------+
|  Phase 1: Supervisor Core & Local Fleet Foundation (COMPLETED)           |
+-------------------------------------+------------------------------------+
                                      |
                                      v
+--------------------------------------------------------------------------+
|  Phase 2: Cross-Machine Network Fleet Connection (COMPLETED)             |
|  - Host bound to 0.0.0.0 & LAN IP (192.168.2.2:5050)                     |
|  - Bearer Token Auth Engine & Secret Generation                          |
|  - PC-W2 (Big PC / WSL2 Ubuntu) connected & verified                     |
|  - MAC-W1..3 and LAP-W1 onboarding protocols & scripts configured        |
|  - Multi-platform worker daemon with idle/busy/blocked states            |
+-------------------------------------+------------------------------------+
                                      |
                                      v
+--------------------------------------------------------------------------+
|  Phase 3: Deep Antigravity & Provider Dispatch Bridges (UPCOMING)        |
|  - Antigravity Mailbox File-Drop Adapter (`.antigravity/inbox/`)        |
|  - Clipboard / Auto-Prompt injection companion helper                    |
|  - Automatic task result parser & status callback bridge                 |
|  - Local Ollama / vLLM API worker integration                            |
+-------------------------------------+------------------------------------+
                                      |
                                      v
+--------------------------------------------------------------------------+
|  Phase 4: Multi-Worker Directed Acyclic Graph (DAG) Pipelines            |
|  - Complex multi-worker dependencies (e.g. Plan -> Implement -> Test)   |
|  - Cross-environment test pipelines (Windows Native + WSL2 Linux)        |
|  - Automatic task retry & failover reassignment upon worker failure      |
+-------------------------------------+------------------------------------+
                                      |
                                      v
+--------------------------------------------------------------------------+
|  Phase 5: Cloud VPS & Distributed Orchestration                          |
|  - External VPS worker agents                                            |
|  - Central artifact registry (binaries, test reports, logs)              |
|  - Advanced analytics & worker productivity metrics                      |
+--------------------------------------------------------------------------+
```

---

## Phase Details & Milestone Criteria

### Phase 1: Foundation & Core Supervisor Engine (Target: Immediate)
- [x] Create project documentation: `ARCHITECTURE.md`, `REQUIREMENTS.md`, `ROADMAP.md`, `PROJECT.yaml`, `TASKS.md`
- [x] Design and initialize SQLite WAL persistent database schema
- [x] Implement Supervisor Core Engine (`supervisor.py`)
- [x] Implement REST API endpoints (`/api/v1/*`)
- [x] Implement Background Heartbeat Liveness Reaper (auto-detect dead workers)
- [x] Implement Project Bootstrap Engine (creates standardized project folder structure)
- [x] Implement Existing Project Import Engine (scans and registers existing projects)
- [x] Implement Dynamic Progress Calculator (completed / total tasks %, remaining work, ETA)
- [x] Implement Responsive Browser Dashboard (`index.html`, CSS, Vanilla JS)
- [x] Implement Worker Daemon Client (`worker_daemon.py`)
- [x] Implement Worker Adapter Interface (`adapters/base.py`, `adapters/antigravity.py`, etc.)
- [x] Seed standard worker fleet: `PC-W1`, `PC-W2`, `MAC-W1`, `MAC-W2`, `MAC-W3`, `LAP-W1`
- [x] Write and run comprehensive automated test suite (`tests/test_supervisor.py`)

### Phase 2: Remote Fleet Connectivity & Hardening (COMPLETED)
- [x] Configure IP binding (`0.0.0.0:5050`) and auto-detect primary LAN IP (`192.168.2.2`)
- [x] Implement Bearer token authentication engine (`auth.py`) with uncommitted secret generation
- [x] Deploy and verify `worker_daemon.py` on PC-W2 inside WSL2 Ubuntu
- [x] Verify cross-boundary bidirectional communication between Windows Host and WSL2
- [x] Dispatch and complete real test task (`TASK-8D30BC4C`) across Windows-WSL2 boundary
- [x] Create automated onboarding scripts for Windows (`onboard_pc_w1.bat`), WSL2 (`onboard_pc_w2.sh`), and macOS (`onboard_mac.sh`)
- [x] Verify 14/14 automated test suite passing in CI/CD format

### Phase 3: Antigravity Automated Task Dispatch
- Implement file-system drop watcher for Antigravity sessions
- Standardize task prompt format with pre-built context injection
- Build Antigravity prompt receiver sidecar to ingest supervisor task prompts without manual copy-paste
- Ingest execution logs and status reports directly into supervisor activity feed

### Phase 4: Multi-Worker Pipelines
- Support composite workflows: Task B triggers automatically once Task A finishes on another worker
- Allow tagging tasks by environment requirements (`requires: windows`, `requires: wsl2`, `requires: gpu`)
- Dynamic worker load-balancing based on queue depth and hardware capability

### Phase 5: Production Scale & VPS Cluster
- Docker containerization for Supervisor deployment on VPS
- PostgreSQL backend support (configurable via DB URI, fallback to SQLite)
- Distributed log aggregation and dashboard telemetry graphs

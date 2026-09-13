"""Project bootstrap and import engine for AI Command Center.
Provides standardized project structure scaffolding and existing project ingestion.
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional
import uuid
import yaml

from database import db_session, log_activity, utc_now_iso
from models import complete_task, create_project, create_task, get_project_by_id


def slugify(text: str) -> str:
    """Generate a clean URL/ID friendly slug."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    return text.strip("-")


def bootstrap_new_project(
    name: str,
    target_path: str,
    description: str = "",
    architect: str = "PC-W1",
    db_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Scaffold a brand new project directory with standard documents and register it."""
    proj_path = Path(target_path).resolve()
    proj_path.mkdir(parents=True, exist_ok=True)
    proj_id = slugify(name) or f"proj-{uuid.uuid4().hex[:6]}"
    now = utc_now_iso()

    # 1. Scaffolding standard files
    # PROJECT.yaml
    project_yaml_content = {
        "name": name,
        "id": proj_id,
        "version": "0.1.0",
        "description": description or f"Project {name}",
        "architect": architect,
        "created_at": now,
        "current_phase": "Phase 1 - Initialization",
    }
    with open(proj_path / "PROJECT.yaml", "w", encoding="utf-8") as f:
        yaml.dump(project_yaml_content, f, sort_keys=False)

    # ARCHITECTURE.md
    arch_md = f"""# {name} — Architecture Specification

**Project:** {name}  
**Architect:** {architect}  
**Status:** Inception  

## 1. System Overview
{description or 'Architecture overview pending definition.'}

## 2. Architecture Principles
- Local-first & Modular
- Cross-platform reliability
- Clean component boundaries
"""
    with open(proj_path / "ARCHITECTURE.md", "w", encoding="utf-8") as f:
        f.write(arch_md)

    # REQUIREMENTS.md
    req_md = f"""# {name} — Requirements Specification

**Project:** {name}  
**Version:** 0.1.0  

## 1. Scope
{description or 'Project scope to be detailed.'}

## 2. Initial Requirements
- [ ] FR-01: Foundation setup
- [ ] FR-02: Core implementation
- [ ] FR-03: Verification and testing
"""
    with open(proj_path / "REQUIREMENTS.md", "w", encoding="utf-8") as f:
        f.write(req_md)

    # ROADMAP.md
    roadmap_md = f"""# {name} — Project Roadmap

## Phase 1: Inception & Foundation
- Setup repository structure
- Define core models and interfaces
- Implement Phase 1 prototype

## Phase 2: Feature Development
- Full functional implementation
"""
    with open(proj_path / "ROADMAP.md", "w", encoding="utf-8") as f:
        f.write(roadmap_md)

    # TASKS.md
    tasks_md = f"""# {name} — Task Backlog

| Task ID | Title | Priority | Status | Est (m) |
|---------|-------|----------|--------|---------|
| T-001 | Project Inception & Setup | High | COMPLETED | 15 |
| T-002 | Core Logic Prototype | High | PENDING | 60 |
| T-003 | Test Suite Implementation | Normal | PENDING | 45 |
"""
    with open(proj_path / "TASKS.md", "w", encoding="utf-8") as f:
        f.write(tasks_md)

    # 2. Register into SQLite
    project = create_project(
        project_id=proj_id,
        name=name,
        path=str(proj_path),
        description=description,
        status="active",
        current_phase="Phase 1 - Inception",
        db_path=db_path,
    )

    # 3. Create initial starter tasks
    create_task(
        project_id=proj_id,
        title="Project Inception & Setup",
        description=f"Initial directory scaffolding for {name}",
        priority="high",
        est_minutes=15,
        task_id=f"{proj_id}-T01",
        db_path=db_path,
    )
    create_task(
        project_id=proj_id,
        title="Core Logic Prototype",
        description=f"Implement core functional features for {name}",
        priority="high",
        est_minutes=60,
        task_id=f"{proj_id}-T02",
        db_path=db_path,
    )

    return get_project_by_id(proj_id, db_path)  # type: ignore


def import_existing_project(
    project_path_str: str,
    name: Optional[str] = None,
    description: Optional[str] = None,
    db_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Import an existing project folder into the Command Center."""
    proj_path = Path(project_path_str).resolve()
    if not proj_path.exists() or not proj_path.is_dir():
        raise ValueError(f"Target directory does not exist: {project_path_str}")

    proj_id = slugify(name or proj_path.name)
    proj_name = name or proj_path.name
    proj_desc = description or ""
    current_phase = "Phase 1 - Ingested"

    # Inspect for PROJECT.yaml
    yaml_file = proj_path / "PROJECT.yaml"
    if yaml_file.exists():
        try:
            with open(yaml_file, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
                if isinstance(data, dict):
                    proj_name = data.get("name", proj_name)
                    proj_id = slugify(data.get("id", proj_id))
                    proj_desc = data.get("description", proj_desc)
                    current_phase = data.get("current_phase", current_phase)
        except Exception:
            pass

    # Check if project already registered
    existing = get_project_by_id(proj_id, db_path)
    if existing:
        return existing

    # Create project record
    project = create_project(
        project_id=proj_id,
        name=proj_name,
        path=str(proj_path),
        description=proj_desc,
        status="active",
        current_phase=current_phase,
        db_path=db_path,
    )

    # Ingest tasks from TASKS.md if present
    tasks_file = proj_path / "TASKS.md"
    tasks_imported = 0
    if tasks_file.exists():
        try:
            with open(tasks_file, "r", encoding="utf-8") as f:
                content = f.read()
                # Parse markdown table lines: | T-101 | Title | Priority | Status | ...
                lines = content.splitlines()
                for line in lines:
                    trimmed = line.strip()
                    if "|" in trimmed and not trimmed.startswith("|-"):
                        parts = [p.strip() for p in trimmed.split("|") if p.strip()]
                        if len(parts) >= 2:
                            t_id = parts[0]
                            if t_id.lower() in ("id", "task id", "task", "task_id") or set(t_id) <= {"-", ":"}:
                                continue
                            t_title = parts[1]
                            t_prio = parts[2].lower() if len(parts) > 2 and parts[2].lower() in ("low", "normal", "high", "urgent") else "normal"
                            t_status = "completed" if (len(parts) > 3 and "complete" in parts[3].lower()) else "pending"
                            task_rec = create_task(
                                project_id=proj_id,
                                title=t_title,
                                description=f"Imported from {tasks_file.name}",
                                priority=t_prio,
                                est_minutes=30,
                                task_id=f"{proj_id}-{slugify(t_id)}",
                                db_path=db_path,
                            )
                            if t_status == "completed":
                                complete_task(task_rec["id"], result_summary="Imported as completed", db_path=db_path)
                            tasks_imported += 1
        except Exception:
            pass

    # If no tasks parsed, add a default task
    if tasks_imported == 0:
        create_task(
            project_id=proj_id,
            title="Ingest and review existing repository",
            description=f"Review files and structure in {str(proj_path)}",
            priority="normal",
            est_minutes=30,
            db_path=db_path,
        )

    log_activity(
        "project_imported",
        f"Project imported: {proj_name} from {str(proj_path)}",
        project_id=proj_id,
        db_path=db_path,
    )
    return get_project_by_id(proj_id, db_path)  # type: ignore

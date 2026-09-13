// AI Command Center — Dashboard Controller
let allWorkers = [];
let allProjects = [];
let allTasks = [];

document.addEventListener("DOMContentLoaded", () => {
  initClock();
  fetchAllData();
  setInterval(fetchAllData, 3000); // 3-second live refresh
});

function initClock() {
  const clockEl = document.getElementById("live-clock");
  const update = () => {
    const now = new Date();
    clockEl.textContent = now.toUTCString().replace("GMT", "UTC");
  };
  update();
  setInterval(update, 1000);
}

async function fetchAllData() {
  try {
    await Promise.all([
      fetchStats(),
      fetchWorkers(),
      fetchProjects(),
      fetchTasks(),
      fetchActivity(),
    ]);
  } catch (err) {
    console.error("Error fetching dashboard updates:", err);
  }
}

// --- Fetch & Render Stats ---
async function fetchStats() {
  try {
    const res = await fetch("/api/v1/stats");
    if (!res.ok) return;
    const data = await res.json();

    const w = data.workers;
    const t = data.tasks;

    document.getElementById("metric-workers-online").textContent = `${w.online + w.idle + w.busy} / ${w.total}`;
    document.getElementById("metric-workers-sub").textContent = `${w.idle} Idle, ${w.busy} Busy, ${w.offline} Offline`;

    document.getElementById("metric-tasks-active").textContent = `${t.in_progress + t.pending}`;
    document.getElementById("metric-tasks-sub").textContent = `${t.pending} Queued / ${t.in_progress} In Progress`;

    document.getElementById("metric-progress-pct").textContent = `${data.overall_progress_pct}%`;
    document.getElementById("metric-progress-sub").textContent = `${t.completed} Completed / ${t.total} Total`;

    document.getElementById("metric-projects-count").textContent = `${data.projects_count}`;
    document.getElementById("metric-projects-sub").textContent = `${data.projects_count} Tracked Pipelines`;
  } catch (e) {
    console.error("Failed to load stats:", e);
  }
}

// --- Fetch & Render Workers ---
async function fetchWorkers() {
  try {
    const res = await fetch("/api/v1/workers");
    if (!res.ok) return;
    const data = await res.json();
    allWorkers = data.workers || [];

    document.getElementById("workers-count-badge").textContent = `${allWorkers.length} Nodes`;

    const grid = document.getElementById("worker-grid");
    if (allWorkers.length === 0) {
      grid.innerHTML = `<div class="loading-state">No workers registered yet.</div>`;
      return;
    }

    grid.innerHTML = allWorkers.map(w => {
      let statusClass = `status-${w.status.toLowerCase()}`;
      let badgeClass = `badge-${w.status.toLowerCase()}`;
      let heartbeatDisplay = "Never";
      if (w.heartbeat_age_seconds !== null && w.heartbeat_age_seconds !== undefined) {
        if (w.heartbeat_age_seconds < 60) {
          heartbeatDisplay = `${w.heartbeat_age_seconds}s ago`;
        } else {
          heartbeatDisplay = `${Math.floor(w.heartbeat_age_seconds / 60)}m ago`;
        }
      }

      let taskDisplay = w.current_task_title ? `Task: ${w.current_task_title}` : "Idle / No Active Task";

      return `
        <div class="worker-card ${statusClass}">
          <div class="worker-card-header">
            <div>
              <div class="worker-id">${escapeHtml(w.id)}</div>
              <div style="font-size:0.75rem; color:#94a3b8;">${escapeHtml(w.name)}</div>
            </div>
            <span class="worker-status-badge ${badgeClass}">${escapeHtml(w.status)}</span>
          </div>
          <div class="worker-meta">
            <div><strong>Host:</strong> ${escapeHtml(w.machine)}</div>
            <div class="worker-env">${escapeHtml(w.environment)} [${escapeHtml(w.provider_type)}]</div>
            <div><strong>Heartbeat:</strong> ${heartbeatDisplay}</div>
          </div>
          <div class="worker-task-info">
            ${escapeHtml(taskDisplay)}
          </div>
        </div>
      `;
    }).join("");

    updateWorkerDropdowns();
  } catch (e) {
    console.error("Failed to load workers:", e);
  }
}

function updateWorkerDropdowns() {
  const taskWorkerSelect = document.getElementById("task-worker-select");
  const assignWorkerSelect = document.getElementById("assign-worker-select");

  if (taskWorkerSelect) {
    const currentVal = taskWorkerSelect.value;
    taskWorkerSelect.innerHTML = `<option value="">-- Leave in Queue (Unassigned) --</option>` +
      allWorkers.map(w => `<option value="${w.id}">${w.id} (${w.name} - ${w.status})</option>`).join("");
    taskWorkerSelect.value = currentVal;
  }

  if (assignWorkerSelect) {
    const currentVal = assignWorkerSelect.value;
    assignWorkerSelect.innerHTML = allWorkers.map(w => `<option value="${w.id}">${w.id} (${w.name} - ${w.status})</option>`).join("");
    assignWorkerSelect.value = currentVal;
  }
}

// --- Fetch & Render Projects ---
async function fetchProjects() {
  try {
    const res = await fetch("/api/v1/projects");
    if (!res.ok) return;
    const data = await res.json();
    allProjects = data.projects || [];

    document.getElementById("projects-count-badge").textContent = `${allProjects.length} Projects`;

    const container = document.getElementById("projects-list");
    if (allProjects.length === 0) {
      container.innerHTML = `<div class="loading-state">No projects registered. Create or import one to begin.</div>`;
      return;
    }

    container.innerHTML = allProjects.map(p => {
      const pct = p.progress_pct || 0;
      return `
        <div class="project-item">
          <div class="project-item-header">
            <div>
              <span class="project-name">${escapeHtml(p.name)}</span>
              <span class="badge" style="margin-left:8px;">${escapeHtml(p.current_phase || 'Active')}</span>
            </div>
            <span class="badge">${p.completed_tasks} / ${p.total_tasks} Tasks</span>
          </div>
          <div class="project-path">${escapeHtml(p.path)}</div>
          <div class="project-progress-container">
            <div class="progress-bar-bg">
              <div class="progress-bar-fill" style="width: ${pct}%;"></div>
            </div>
            <span class="progress-pct-label ${pct === 100 ? 'text-success' : 'text-accent'}">${pct}%</span>
          </div>
          <div class="project-stats-row">
            <span>Remaining Work: ${p.remaining_tasks} tasks (~${p.remaining_est_minutes} min)</span>
            <span>ETA Target: ${p.eta_target || 'None specified'}</span>
          </div>
        </div>
      `;
    }).join("");

    updateProjectDropdowns();
  } catch (e) {
    console.error("Failed to load projects:", e);
  }
}

function updateProjectDropdowns() {
  const taskProjectSelect = document.getElementById("task-project-select");
  if (taskProjectSelect) {
    const currentVal = taskProjectSelect.value;
    taskProjectSelect.innerHTML = allProjects.map(p => `<option value="${p.id}">${escapeHtml(p.name)} (${p.id})</option>`).join("");
    if (currentVal) taskProjectSelect.value = currentVal;
  }
}

// --- Fetch & Render Tasks ---
async function fetchTasks() {
  try {
    const res = await fetch("/api/v1/tasks");
    if (!res.ok) return;
    const data = await res.json();
    allTasks = data.tasks || [];
    document.getElementById("tasks-count-badge").textContent = `${allTasks.length} Tasks`;
    renderTasks();
  } catch (e) {
    console.error("Failed to load tasks:", e);
  }
}

function renderTasks() {
  const filter = document.getElementById("filter-task-status")?.value || "all";
  const tbody = document.getElementById("tasks-table-body");

  let filtered = allTasks;
  if (filter !== "all") {
    filtered = allTasks.filter(t => t.status === filter);
  }

  if (filtered.length === 0) {
    tbody.innerHTML = `<tr><td colspan="7" class="text-center">No tasks match filter.</td></tr>`;
    return;
  }

  tbody.innerHTML = filtered.map(t => {
    const pClass = `priority-${(t.priority || 'normal').toLowerCase()}`;
    const statusClass = `badge-${(t.status || 'pending').toLowerCase()}`;
    const assigned = t.assigned_worker_id ? `<span class="badge" style="color:var(--accent-cyan)">${escapeHtml(t.assigned_worker_id)}</span>` : `<span style="color:var(--text-muted)">Unassigned</span>`;

    let actions = "";
    if (t.status === "queued" || t.status === "pending") {
      actions = `<button class="btn btn-sm btn-secondary" onclick="promptAssignTask('${t.id}', '${escapeHtml(t.title)}')">Assign</button>`;
    } else if (t.status === "assigned") {
      actions = `
        <button class="btn btn-sm btn-primary" onclick="quickStartTask('${t.id}')">Start</button>
        <button class="btn btn-sm btn-ghost" onclick="promptAssignTask('${t.id}', '${escapeHtml(t.title)}')">Reassign</button>
      `;
    } else if (t.status === "in_progress") {
      actions = `<button class="btn btn-sm btn-primary" style="background:#10b981; border-color:#34d399;" onclick="quickCompleteTask('${t.id}')">Complete</button>`;
    } else if (t.status === "completed") {
      actions = `<span class="text-success" style="font-family:var(--font-mono); font-size:0.7rem;">DONE</span>`;
    }

    return `
      <tr>
        <td style="font-family:var(--font-mono); font-weight:600;">${escapeHtml(t.id)}</td>
        <td>${escapeHtml(t.project_name || t.project_id)}</td>
        <td>
          <div style="font-weight:600; color:#fff;">${escapeHtml(t.title)}</div>
          ${t.description ? `<div style="font-size:0.7rem; color:var(--text-muted);">${escapeHtml(t.description)}</div>` : ''}
        </td>
        <td class="${pClass}">${escapeHtml((t.priority || 'NORMAL').toUpperCase())}</td>
        <td><span class="worker-status-badge ${statusClass}">${escapeHtml(t.status)}</span></td>
        <td>${assigned}</td>
        <td>${actions}</td>
      </tr>
    `;
  }).join("");
}

// --- Fetch & Render Activity ---
async function fetchActivity() {
  try {
    const res = await fetch("/api/v1/activity?limit=40");
    if (!res.ok) return;
    const data = await res.json();
    const activities = data.activities || [];

    const stream = document.getElementById("activity-stream");
    if (activities.length === 0) {
      stream.innerHTML = `<div class="loading-state">No activity logged yet.</div>`;
      return;
    }

    stream.innerHTML = activities.map(a => {
      const typeClass = `type-${escapeHtml(a.event_type)}`;
      const timeDisplay = a.created_at ? new Date(a.created_at).toLocaleTimeString() : "";
      return `
        <div class="activity-item ${typeClass}">
          <div class="activity-header">
            <span class="activity-worker">${a.worker_id ? escapeHtml(a.worker_id) : 'SYSTEM'}</span>
            <span>${timeDisplay}</span>
          </div>
          <div class="activity-message">${escapeHtml(a.message)}</div>
        </div>
      `;
    }).join("");
  } catch (e) {
    console.error("Failed to load activity:", e);
  }
}

// --- Modal Operations ---
function openModal(id) {
  const el = document.getElementById(id);
  if (el) el.classList.add("open");
}

function closeModal(id) {
  const el = document.getElementById(id);
  if (el) el.classList.remove("open");
}

function promptAssignTask(taskId, taskTitle) {
  document.getElementById("assign-task-id").value = taskId;
  document.getElementById("assign-task-title").textContent = `${taskId} — ${taskTitle}`;
  openModal("modal-assign-task");
}

// --- Form Handlers ---
async function handleCreateTask(e) {
  e.preventDefault();
  const payload = {
    project_id: document.getElementById("task-project-select").value,
    title: document.getElementById("task-title-input").value.trim(),
    priority: document.getElementById("task-priority-select").value,
    est_minutes: parseInt(document.getElementById("task-est-input").value, 10) || 30,
    assigned_worker_id: document.getElementById("task-worker-select").value || null,
    description: document.getElementById("task-desc-input").value.trim(),
    prompt_payload: document.getElementById("task-prompt-input").value.trim(),
  };

  try {
    const res = await fetch("/api/v1/tasks", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (res.ok) {
      closeModal("modal-new-task");
      document.getElementById("form-new-task").reset();
      fetchAllData();
    } else {
      const err = await res.json();
      alert("Error: " + (err.error || "Failed to create task"));
    }
  } catch (err) {
    alert("Network error: " + err);
  }
}

async function handleAssignTask(e) {
  e.preventDefault();
  const taskId = document.getElementById("assign-task-id").value;
  const workerId = document.getElementById("assign-worker-select").value;

  try {
    const res = await fetch(`/api/v1/tasks/${taskId}/assign`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ worker_id: workerId }),
    });
    if (res.ok) {
      closeModal("modal-assign-task");
      fetchAllData();
    } else {
      const err = await res.json();
      alert("Error: " + (err.error || "Failed to assign task"));
    }
  } catch (err) {
    alert("Network error: " + err);
  }
}

async function quickStartTask(taskId) {
  try {
    const res = await fetch(`/api/v1/tasks/${taskId}/start`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({}),
    });
    if (res.ok) fetchAllData();
  } catch (err) {
    console.error(err);
  }
}

async function quickCompleteTask(taskId) {
  const summary = prompt("Enter completion summary:", "Completed successfully");
  if (summary === null) return;

  try {
    const res = await fetch(`/api/v1/tasks/${taskId}/complete`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ result_summary: summary, status: "completed" }),
    });
    if (res.ok) fetchAllData();
  } catch (err) {
    console.error(err);
  }
}

async function handleCreateProject(e) {
  e.preventDefault();
  const payload = {
    name: document.getElementById("project-name-input").value.trim(),
    path: document.getElementById("project-path-input").value.trim(),
    description: document.getElementById("project-desc-input").value.trim(),
  };

  try {
    const res = await fetch("/api/v1/projects", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (res.ok) {
      closeModal("modal-new-project");
      document.getElementById("form-new-project").reset();
      fetchAllData();
    } else {
      const err = await res.json();
      alert("Error: " + (err.error || "Failed to bootstrap project"));
    }
  } catch (err) {
    alert("Network error: " + err);
  }
}

async function handleImportProject(e) {
  e.preventDefault();
  const payload = {
    path: document.getElementById("import-path-input").value.trim(),
    name: document.getElementById("import-name-input").value.trim() || undefined,
  };

  try {
    const res = await fetch("/api/v1/projects/import", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (res.ok) {
      closeModal("modal-import-project");
      document.getElementById("form-import-project").reset();
      fetchAllData();
    } else {
      const err = await res.json();
      alert("Error: " + (err.error || "Failed to import project"));
    }
  } catch (err) {
    alert("Network error: " + err);
  }
}

function escapeHtml(str) {
  if (!str) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

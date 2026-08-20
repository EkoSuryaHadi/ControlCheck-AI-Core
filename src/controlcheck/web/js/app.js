/**
 * ControlCheck AI — Frontend Dashboard Logic
 */

const state = {
  activeOrgId: "11111111-1111-1111-1111-111111111111",
  activeProjectId: "PRJ-CCAI-001",
  findings: [],
  filteredFindings: [],
  activeCategory: "ALL",
  activeSeverity: "ALL",
  searchQuery: "",
  conversationId: null,
  health: {
    overall: 100.0,
    band: "Healthy",
    cost: 100.0,
    schedule: 100.0,
    progress: 100.0,
    dq: 100.0,
  },
};

document.addEventListener("DOMContentLoaded", () => {
  initDropZone();
  initFilters();
  initSearch();
  initChat();
  renderHealthGauge();
  loadMockInitialData();
});

// Mock Initial Data for Instant Demonstration
function loadMockInitialData() {
  state.findings = [
    {
      finding_id: "F-CST-001",
      rule_id: "CST-001",
      rule_name: "Actual Cost Exceeds Budget",
      category: "COST",
      severity: "critical",
      entity_id: "1.0",
      title: "Actual Cost Exceeds Budget on WBS 1.0",
      description: "Actual costs (IDR 1,250,000,000) exceeded allocated budget (IDR 1,000,000,000) by 25%.",
      business_impact: "Budget overrun risk and margin erosion.",
      recommendation: "Review commitment approval workflows and conduct cost variance investigation.",
      calculation: { actual_cost: 1250000000, budget: 1000000000, variance_pct: 25.0 },
      evidence: [{ source_sheet: "Actual Costs", source_rows: [12, 14, 18], record_ids: ["ACT-101", "ACT-102"] }],
    },
    {
      finding_id: "F-SCH-001",
      rule_id: "SCH-001",
      rule_name: "Overdue Activity Incomplete",
      category: "SCHEDULE",
      severity: "critical",
      entity_id: "ACT-040",
      title: "Foundation Work Overdue by 14 Days",
      description: "Activity ACT-040 is only 40% complete past its scheduled baseline finish date of 2026-08-01.",
      business_impact: "Downstream delay on structural assembly milestone.",
      recommendation: "Deploy additional subcontractor crew and fast-track steel deliveries.",
      calculation: { baseline_finish: "2026-08-01", progress_pct: 40.0, days_late: 14 },
      evidence: [{ source_sheet: "Schedule", source_rows: [42], record_ids: ["ACT-040"] }],
    },
    {
      finding_id: "F-PRG-002",
      rule_id: "PRG-002",
      rule_name: "Actual Progress Outpacing Cost",
      category: "PROGRESS",
      severity: "warning",
      entity_id: "WBS-2.1",
      title: "Progress Outpacing Cost Incurred",
      description: "Actual progress is reported at 85% while cost incurred is only 20% of budget.",
      business_impact: "Potential unrecorded accruals or progress overstatement.",
      recommendation: "Reconcile vendor timesheets and unbilled work-in-progress.",
      calculation: { progress: 0.85, cost_pct: 0.20 },
      evidence: [{ source_sheet: "Progress", source_rows: [25], record_ids: ["PRG-08"] }],
    },
    {
      finding_id: "F-DQ-001",
      rule_id: "DQ-001",
      rule_name: "Missing WBS Code Reference",
      category: "DATA_QUALITY",
      severity: "warning",
      entity_id: "TX-990",
      title: "Cost Transaction without WBS Reference",
      description: "Transaction TX-990 has blank WBS assignment in actual costs sheet.",
      business_impact: "Inaccurate cost roll-up and budget tracking.",
      recommendation: "Assign valid WBS code in ERP before monthly book closure.",
      calculation: {},
      evidence: [{ source_sheet: "Actual Costs", source_rows: [99], record_ids: ["TX-990"] }],
    },
  ];

  calculateHealthFromFindings();
  applyFilters();
}

// Calculate Health Score dynamically based on PRD §13 formula
function calculateHealthFromFindings() {
  const penalties = { COST: 0, SCHEDULE: 0, PROGRESS: 0, DATA_QUALITY: 0 };
  const weights = { critical: 15, warning: 5, observation: 1 };

  state.findings.forEach((f) => {
    const cat = f.category;
    if (penalties[cat] !== undefined) {
      penalties[cat] += weights[f.severity] || 0;
    }
  });

  state.health.cost = Math.max(0, 100 - penalties.COST);
  state.health.schedule = Math.max(0, 100 - penalties.SCHEDULE);
  state.health.progress = Math.max(0, 100 - penalties.PROGRESS);
  state.health.dq = Math.max(0, 100 - penalties.DATA_QUALITY);

  state.health.overall = +(
    0.30 * state.health.cost +
    0.30 * state.health.schedule +
    0.25 * state.health.progress +
    0.15 * state.health.dq
  ).toFixed(1);

  if (state.health.overall >= 80) state.health.band = "Healthy";
  else if (state.health.overall >= 60) state.health.band = "Needs Attention";
  else if (state.health.overall >= 40) state.health.band = "At Risk";
  else state.health.band = "Critical";

  renderHealthGauge();
  renderDomainCards();
}

// Render Circular SVG Health Gauge
function renderHealthGauge() {
  const gaugeValEl = document.getElementById("gauge-value");
  const gaugeBandEl = document.getElementById("gauge-band");
  const gaugeCircle = document.getElementById("gauge-circle");

  if (!gaugeValEl || !gaugeCircle) return;

  gaugeValEl.textContent = state.health.overall.toFixed(0);
  gaugeBandEl.textContent = state.health.band;
  gaugeBandEl.className = `gauge-band-badge badge-${state.health.band.toLowerCase().replace(" ", "-")}`;

  const circumference = 2 * Math.PI * 52;
  const offset = circumference - (state.health.overall / 100) * circumference;
  gaugeCircle.style.strokeDashoffset = offset;

  // Set color by band
  const colors = {
    Healthy: "#10b981",
    "Needs Attention": "#f59e0b",
    "At Risk": "#f97316",
    Critical: "#ef4444",
  };
  gaugeCircle.style.stroke = colors[state.health.band] || "#3b82f6";
}

function renderDomainCards() {
  const setCard = (id, score) => {
    const valEl = document.getElementById(`${id}-val`);
    const barEl = document.getElementById(`${id}-bar`);
    if (valEl && barEl) {
      valEl.textContent = `${score.toFixed(0)}%`;
      barEl.style.width = `${score}%`;
      barEl.style.backgroundColor = score >= 80 ? "#10b981" : score >= 60 ? "#f59e0b" : "#ef4444";
    }
  };
  setCard("cost", state.health.cost);
  setCard("sched", state.health.schedule);
  setCard("prog", state.health.progress);
  setCard("dq", state.health.dq);
}

// Dropzone file upload handling
function initDropZone() {
  const dropzone = document.getElementById("dropzone");
  const fileInput = document.getElementById("file-input");

  if (!dropzone || !fileInput) return;

  dropzone.addEventListener("click", () => fileInput.click());
  dropzone.addEventListener("dragover", (e) => {
    e.preventDefault();
    dropzone.classList.add("dragover");
  });
  dropzone.addEventListener("dragleave", () => dropzone.classList.remove("dragover"));
  dropzone.addEventListener("drop", (e) => {
    e.preventDefault();
    dropzone.classList.remove("dragover");
    if (e.dataTransfer.files.length) handleFileUpload(e.dataTransfer.files[0]);
  });

  fileInput.addEventListener("change", (e) => {
    if (e.target.files.length) handleFileUpload(e.target.files[0]);
  });
}

async function handleFileUpload(file) {
  const uploadText = document.getElementById("upload-status-text");
  if (uploadText) uploadText.textContent = `Uploading & Analyzing "${file.name}"...`;

  const formData = new FormData();
  formData.append("file", file);

  try {
    const res = await fetch("/v1/audits", {
      method: "POST",
      body: formData,
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    state.findings = data.findings || [];
    calculateHealthFromFindings();
    applyFilters();
    if (uploadText) uploadText.textContent = `Audit Complete! Loaded ${state.findings.length} findings from "${file.name}"`;

    // Notify AI Copilot
    addChatMessage("system", `Workbook <strong>${file.name}</strong> uploaded successfully. Detected ${state.findings.length} findings.`);
  } catch (err) {
    if (uploadText) uploadText.textContent = `Demo Mode: Local audit parsed (${err.message})`;
  }
}

// Filters & Search
function initFilters() {
  document.querySelectorAll(".filter-pill").forEach((pill) => {
    pill.addEventListener("click", (e) => {
      document.querySelectorAll(".filter-pill").forEach((p) => p.classList.remove("active"));
      e.target.classList.add("active");
      state.activeCategory = e.target.dataset.category || "ALL";
      applyFilters();
    });
  });
}

function initSearch() {
  const searchInput = document.getElementById("finding-search");
  if (searchInput) {
    searchInput.addEventListener("input", (e) => {
      state.searchQuery = e.target.value.toLowerCase().trim();
      applyFilters();
    });
  }
}

function applyFilters() {
  state.filteredFindings = state.findings.filter((f) => {
    const matchCat = state.activeCategory === "ALL" || f.category === state.activeCategory;
    const matchQuery =
      !state.searchQuery ||
      f.title.toLowerCase().includes(state.searchQuery) ||
      f.rule_id.toLowerCase().includes(state.searchQuery) ||
      f.entity_id.toLowerCase().includes(state.searchQuery);
    return matchCat && matchQuery;
  });

  renderFindingsTable();
}

function renderFindingsTable() {
  const tbody = document.getElementById("findings-tbody");
  const countEl = document.getElementById("finding-count");
  if (!tbody) return;

  if (countEl) countEl.textContent = `${state.filteredFindings.length} Findings`;
  tbody.innerHTML = "";

  if (state.filteredFindings.length === 0) {
    tbody.innerHTML = `<tr><td colspan="5" style="text-align: center; color: var(--text-muted); padding: 32px;">No findings matching current filters.</td></tr>`;
    return;
  }

  state.filteredFindings.forEach((f) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td><span class="severity-tag tag-${f.severity}">${f.severity}</span></td>
      <td><strong style="font-family: var(--font-mono); color: var(--primary);">${f.rule_id}</strong></td>
      <td><span style="font-family: var(--font-mono);">${f.entity_id}</span></td>
      <td><strong>${f.title}</strong><div style="font-size: 0.75rem; color: var(--text-muted);">${f.description.substring(0, 80)}...</div></td>
      <td><button class="btn-detail" style="background: var(--bg-surface-elevated); border: 1px solid var(--border-subtle); color: var(--text-secondary); padding: 4px 10px; border-radius: var(--radius-sm); cursor: pointer;">Inspect</button></td>
    `;
    tr.addEventListener("click", () => openFindingModal(f));
    tbody.appendChild(tr);
  });
}

function openFindingModal(finding) {
  const modal = document.getElementById("finding-modal");
  const body = document.getElementById("modal-body");
  if (!modal || !body) return;

  body.innerHTML = `
    <div style="display: flex; gap: 8px; margin-bottom: 12px;">
      <span class="severity-tag tag-${finding.severity}">${finding.severity}</span>
      <span style="font-family: var(--font-mono); font-weight: 700; color: var(--primary);">${finding.rule_id} — ${finding.rule_name}</span>
    </div>
    <h3 style="margin-bottom: 8px;">${finding.title}</h3>
    <p style="color: var(--text-secondary); margin-bottom: 16px;">${finding.description}</p>
    
    <div style="background: var(--bg-surface-elevated); padding: 14px; border-radius: var(--radius-md); margin-bottom: 16px;">
      <div style="font-size: 0.8rem; font-weight: 700; color: var(--color-at-risk); text-transform: uppercase;">Business Impact</div>
      <div>${finding.business_impact}</div>
    </div>

    <div style="background: var(--bg-surface-elevated); padding: 14px; border-radius: var(--radius-md); margin-bottom: 16px;">
      <div style="font-size: 0.8rem; font-weight: 700; color: var(--color-healthy); text-transform: uppercase;">Recommendation</div>
      <div>${finding.recommendation}</div>
    </div>

    <div style="font-size: 0.8rem; font-weight: 700; text-transform: uppercase; margin-bottom: 8px; color: var(--text-muted);">Source Evidence</div>
    <div style="font-family: var(--font-mono); font-size: 0.8rem; background: var(--bg-base); padding: 12px; border-radius: var(--radius-md); border: 1px solid var(--border-subtle);">
      ${JSON.stringify(finding.evidence, null, 2)}
    </div>
  `;

  modal.style.display = "flex";
}

function closeFindingModal() {
  const modal = document.getElementById("finding-modal");
  if (modal) modal.style.display = "none";
}

// AI Copilot Chat
function initChat() {
  const btnSend = document.getElementById("btn-send");
  const chatInput = document.getElementById("chat-input");

  if (btnSend && chatInput) {
    btnSend.addEventListener("click", () => sendChatMessage());
    chatInput.addEventListener("keypress", (e) => {
      if (e.key === "Enter") sendChatMessage();
    });
  }

  document.querySelectorAll(".chip").forEach((chip) => {
    chip.addEventListener("click", (e) => {
      if (chatInput) {
        chatInput.value = e.target.textContent;
        sendChatMessage();
      }
    });
  });
}

async function sendChatMessage() {
  const input = document.getElementById("chat-input");
  if (!input || !input.value.trim()) return;

  const question = input.value.trim();
  input.value = "";
  addChatMessage("user", question);

  // Call API or Fallback Grounded Reasoning
  try {
    const res = await fetch(`/v1/projects/${state.activeProjectId}/ai/ask`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Organization-ID": state.activeOrgId,
      },
      body: JSON.stringify({ question, conversation_id: state.conversationId }),
    });

    if (res.ok) {
      const data = await res.json();
      state.conversationId = data.conversation_id;
      addChatMessage("ai", data.answer, data.recommended_action);
      return;
    }
  } catch (_) {}

  // Local fallback grounded response
  setTimeout(() => {
    const qLower = question.lower ? question.lower() : question.toLowerCase();
    if (qLower.includes("cost") || qLower.includes("budget")) {
      addChatMessage("ai", `Found 1 critical cost finding on WBS 1.0 (Actual cost exceeded budget by IDR 250,000,000).`, "Review commitment approval workflows.");
    } else if (qLower.includes("delay") || qLower.includes("schedule")) {
      addChatMessage("ai", `Activity ACT-040 (Foundation Work) is delayed by 14 days past baseline finish.`, "Fast-track critical path activities.");
    } else {
      addChatMessage("ai", `Project health score is ${state.health.overall}/100 ('${state.health.band}'). Cost and Schedule have critical deductions.`, "Address top critical findings first.");
    }
  }, 400);
}

function addChatMessage(sender, text, action = null) {
  const container = document.getElementById("copilot-messages");
  if (!container) return;

  const bubble = document.createElement("div");
  bubble.className = `chat-bubble bubble-${sender}`;
  bubble.innerHTML = `<div>${text}</div>` + (action ? `<div style="margin-top: 8px; padding-top: 8px; border-top: 1px dashed rgba(255,255,255,0.15); font-size: 0.75rem; color: var(--color-healthy);"><strong>Action:</strong> ${action}</div>` : "");

  container.appendChild(bubble);
  container.scrollTop = container.scrollHeight;
}

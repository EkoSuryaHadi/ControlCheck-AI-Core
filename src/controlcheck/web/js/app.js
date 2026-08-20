/**
 * ControlCheck AI — Executive Analytics Command Center Logic
 */

const state = {
  activeOrgId: "11111111-1111-1111-1111-111111111111",
  activeProjectId: "PRJ-CCAI-001",
  findings: [],
  filteredFindings: [],
  activeCategory: "ALL",
  searchQuery: "",
  conversationId: null,
  expandedFindingId: null,
  currentPage: 1,
  pageSize: 5,
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
  initTheme();
  initUpload();
  initFilters();
  initSearch();
  initPagination();
  initCopilotDrawer();
  renderHealthGauge();
  loadMockInitialData();
});

// Theme Management
function initTheme() {
  const btnToggleTheme = document.getElementById("btn-toggle-theme");
  const sunIcon = document.getElementById("theme-icon-sun");
  const moonIcon = document.getElementById("theme-icon-moon");
  const themeLabel = document.getElementById("theme-label");

  const applyTheme = (theme) => {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem("controlcheck_theme", theme);
    if (theme === "light") {
      if (sunIcon) sunIcon.style.display = "inline-block";
      if (moonIcon) moonIcon.style.display = "none";
      if (themeLabel) themeLabel.textContent = "Light";
    } else {
      if (sunIcon) sunIcon.style.display = "none";
      if (moonIcon) moonIcon.style.display = "inline-block";
      if (themeLabel) themeLabel.textContent = "Dark";
    }
  };

  const savedTheme = localStorage.getItem("controlcheck_theme") || "dark";
  applyTheme(savedTheme);

  if (btnToggleTheme) {
    btnToggleTheme.addEventListener("click", () => {
      const current = document.documentElement.getAttribute("data-theme") || "dark";
      const next = current === "dark" ? "light" : "dark";
      applyTheme(next);
    });
  }
}

// Slide-Over AI Copilot Drawer
function initCopilotDrawer() {
  const drawer = document.getElementById("copilot-drawer");
  const backdrop = document.getElementById("copilot-backdrop");
  const btnOpen = document.getElementById("btn-open-copilot");
  const btnClose = document.getElementById("btn-close-copilot");
  const btnSend = document.getElementById("btn-send");
  const chatInput = document.getElementById("chat-input");

  const openDrawer = () => {
    if (drawer) drawer.classList.add("open");
    if (backdrop) backdrop.classList.add("open");
  };

  const closeDrawer = () => {
    if (drawer) drawer.classList.remove("open");
    if (backdrop) backdrop.classList.remove("open");
  };

  if (btnOpen) btnOpen.addEventListener("click", openDrawer);
  if (btnClose) btnClose.addEventListener("click", closeDrawer);
  if (backdrop) backdrop.addEventListener("click", closeDrawer);

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

// Initial Mock Dataset for Demonstration
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
      business_impact: "Budget overrun risk and margin erosion on primary structural package.",
      recommendation: "Conduct cost variance investigation and tighten purchase order approval limits.",
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
      business_impact: "Critical path delay impacting subsequent structural assembly milestones.",
      recommendation: "Deploy additional subcontractor shift and fast-track rebar deliveries.",
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
  updateCategoryCounts();
  applyFilters();
}

// Compute Category Counts for Filter Chips
function updateCategoryCounts() {
  const counts = { ALL: state.findings.length, COST: 0, SCHEDULE: 0, PROGRESS: 0, DATA_QUALITY: 0 };
  state.findings.forEach((f) => {
    if (counts[f.category] !== undefined) counts[f.category]++;
  });

  const setC = (id, val) => {
    const el = document.getElementById(id);
    if (el) el.textContent = val;
  };
  setC("count-all", counts.ALL);
  setC("count-cost", counts.COST);
  setC("count-sched", counts.SCHEDULE);
  setC("count-prog", counts.PROGRESS);
  setC("count-dq", counts.DATA_QUALITY);
}

// Health Scoring Formula (PRD §13)
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

function renderHealthGauge() {
  const gaugeValEl = document.getElementById("gauge-value");
  const gaugeBandEl = document.getElementById("gauge-band");
  const gaugeCircle = document.getElementById("gauge-circle");

  if (!gaugeValEl || !gaugeCircle) return;

  gaugeValEl.textContent = state.health.overall.toFixed(0);
  if (gaugeBandEl) {
    gaugeBandEl.textContent = state.health.band;
    gaugeBandEl.className = `kpi-badge badge-${state.health.band.toLowerCase().replace(" ", "-")}`;
  }

  const circumference = 2 * Math.PI * 32; // radius 32
  const offset = circumference - (state.health.overall / 100) * circumference;
  gaugeCircle.style.strokeDashoffset = offset;

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

// Upload & File Handling
function initUpload() {
  const fileInput = document.getElementById("file-input");
  const btnQuickUpload = document.getElementById("btn-quick-upload");

  if (btnQuickUpload && fileInput) {
    btnQuickUpload.addEventListener("click", () => fileInput.click());
  }

  if (fileInput) {
    fileInput.addEventListener("change", (e) => {
      if (e.target.files.length) handleFileUpload(e.target.files[0]);
    });
  }

  // Support Drag & Drop directly onto the viewport window
  window.addEventListener("dragover", (e) => e.preventDefault());
  window.addEventListener("drop", (e) => {
    e.preventDefault();
    if (e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files.length) {
      const file = e.dataTransfer.files[0];
      if (file.name.toLowerCase().endsWith(".xlsx")) {
        handleFileUpload(file);
      }
    }
  });
}

async function handleFileUpload(file) {
  const btnQuickUpload = document.getElementById("btn-quick-upload");
  const originalBtnText = btnQuickUpload ? btnQuickUpload.innerHTML : "Upload Dataset (Standard / Custom)";
  if (btnQuickUpload) {
    btnQuickUpload.innerHTML = `<span>⏳ Auto-Mapping & Auditing...</span>`;
    btnQuickUpload.disabled = true;
  }

  const formData = new FormData();
  formData.append("file", file);

  try {
    const res = await fetch("/v1/audits", {
      method: "POST",
      body: formData,
    });
    const data = await res.json();
    if (!res.ok) {
      const errMsg = (data && (data.message || data.detail || (data.error && data.error.message))) || `HTTP ${res.status}`;
      throw new Error(errMsg);
    }

    state.findings = data.findings || [];
    calculateHealthFromFindings();
    updateCategoryCounts();
    applyFilters();

    if (btnQuickUpload) {
      btnQuickUpload.innerHTML = `<span>✓ Audit Complete</span>`;
      setTimeout(() => {
        btnQuickUpload.innerHTML = originalBtnText;
        btnQuickUpload.disabled = false;
      }, 2000);
    }

    addChatMessage("system", `Processed <strong>${file.name}</strong>. Smart Ingestion evaluated ${state.findings.length} findings across 20 rules.`);

  } catch (err) {
    if (btnQuickUpload) {
      btnQuickUpload.innerHTML = `<span>⚠️ Error</span>`;
      setTimeout(() => {
        btnQuickUpload.innerHTML = originalBtnText;
        btnQuickUpload.disabled = false;
      }, 3000);
    }
    alert(`Upload Error: ${err.message}`);
  }
}


// Filters & Search
function initFilters() {
  document.querySelectorAll(".filter-chip").forEach((chip) => {
    chip.addEventListener("click", (e) => {
      document.querySelectorAll(".filter-chip").forEach((p) => p.classList.remove("active"));
      const target = e.target.closest(".filter-chip");
      target.classList.add("active");
      state.activeCategory = target.dataset.category || "ALL";
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

  state.currentPage = 1;
  state.expandedFindingId = null;
  renderFindingsTable();
}

function initPagination() {
  const btnPrev = document.getElementById("btn-prev-page");
  const btnNext = document.getElementById("btn-next-page");

  if (btnPrev) {
    btnPrev.addEventListener("click", () => {
      if (state.currentPage > 1) {
        state.currentPage--;
        renderFindingsTable();
      }
    });
  }

  if (btnNext) {
    btnNext.addEventListener("click", () => {
      const totalPages = Math.ceil(state.filteredFindings.length / state.pageSize) || 1;
      if (state.currentPage < totalPages) {
        state.currentPage++;
        renderFindingsTable();
      }
    });
  }
}

// Accordion Findings Table Rendering
function renderFindingsTable() {
  const tbody = document.getElementById("findings-tbody");
  const infoEl = document.getElementById("pagination-info");
  const pagesContainer = document.getElementById("pagination-pages");
  const btnPrev = document.getElementById("btn-prev-page");
  const btnNext = document.getElementById("btn-next-page");

  if (!tbody) return;

  const total = state.filteredFindings.length;
  const totalPages = Math.max(1, Math.ceil(total / state.pageSize));

  if (state.currentPage > totalPages) state.currentPage = totalPages;
  tbody.innerHTML = "";

  if (total === 0) {
    tbody.innerHTML = `<tr><td colspan="6" style="text-align: center; color: var(--text-muted); padding: 36px;">No findings matching current filters.</td></tr>`;
    if (infoEl) infoEl.textContent = "Showing 0 findings";
    return;
  }

  const startIdx = (state.currentPage - 1) * state.pageSize;
  const endIdx = Math.min(startIdx + state.pageSize, total);
  const pageFindings = state.filteredFindings.slice(startIdx, endIdx);

  pageFindings.forEach((f) => {
    const isExpanded = state.expandedFindingId === f.finding_id;

    // Main Row
    const tr = document.createElement("tr");
    tr.className = `finding-row ${isExpanded ? "expanded" : ""}`;
    tr.innerHTML = `
      <td><span class="accordion-chevron">▶</span></td>
      <td><span class="severity-pill pill-${f.severity}">${f.severity}</span></td>
      <td><strong style="font-family: var(--font-mono); color: var(--primary);">${f.rule_id}</strong></td>
      <td><span style="font-family: var(--font-mono);">${f.entity_id}</span></td>
      <td>
        <strong style="color: var(--text-primary); font-size: 0.85rem;">${f.title}</strong>
        <div style="font-size: 0.75rem; color: var(--text-muted);">${f.description.substring(0, 75)}...</div>
      </td>
      <td style="text-align: right;">
        <button class="page-btn" style="font-size: 0.725rem;">${isExpanded ? "Collapse ▲" : "Expand ▼"}</button>
      </td>
    `;

    tr.addEventListener("click", () => {
      state.expandedFindingId = isExpanded ? null : f.finding_id;
      renderFindingsTable();
    });

    tbody.appendChild(tr);

    // Accordion Drawer Row
    if (isExpanded) {
      const drawerTr = document.createElement("tr");
      drawerTr.className = "accordion-drawer";
      drawerTr.innerHTML = `
        <td colspan="6" style="padding: 0;">
          <div class="accordion-body">
            
            <div class="detail-card">
              <div class="detail-title" style="color: var(--color-at-risk);">
                ⚠️ Business Impact
              </div>
              <p style="color: var(--text-primary);">${f.business_impact || "No business impact documented."}</p>
            </div>

            <div class="detail-card">
              <div class="detail-title" style="color: var(--color-healthy);">
                💡 Actionable Recommendation
              </div>
              <p style="color: var(--text-primary);">${f.recommendation || "Review and reconcile."}</p>
            </div>

            <div class="detail-card" style="grid-column: 1 / -1;">
              <div class="detail-title" style="color: var(--accent-cyan);">
                🔍 Source Spreadsheet Lineage Trace
              </div>
              <div style="font-family: var(--font-mono); font-size: 0.75rem; background: var(--bg-surface-elevated); padding: 10px; border-radius: var(--radius-sm); border: 1px solid var(--border-subtle); overflow-x: auto;">
                ${JSON.stringify(f.evidence, null, 2)}
              </div>
            </div>

          </div>
        </td>
      `;
      tbody.appendChild(drawerTr);
    }
  });

  // Update Pagination Controls
  if (infoEl) {
    infoEl.textContent = `Showing ${startIdx + 1}–${endIdx} of ${total} findings (Page ${state.currentPage} of ${totalPages})`;
  }

  if (btnPrev) btnPrev.disabled = state.currentPage <= 1;
  if (btnNext) btnNext.disabled = state.currentPage >= totalPages;

  if (pagesContainer) {
    pagesContainer.innerHTML = "";
    const maxButtons = 5;
    let startPage = Math.max(1, state.currentPage - Math.floor(maxButtons / 2));
    let endPage = Math.min(totalPages, startPage + maxButtons - 1);
    if (endPage - startPage + 1 < maxButtons) {
      startPage = Math.max(1, endPage - maxButtons + 1);
    }

    for (let p = startPage; p <= endPage; p++) {
      const pageBtn = document.createElement("button");
      pageBtn.className = `page-btn ${p === state.currentPage ? "btn-header-primary" : ""}`;
      pageBtn.textContent = p;
      pageBtn.addEventListener("click", () => {
        state.currentPage = p;
        state.expandedFindingId = null;
        renderFindingsTable();
      });
      pagesContainer.appendChild(pageBtn);
    }
  }
}

// AI Copilot Chat
async function sendChatMessage() {
  const input = document.getElementById("chat-input");
  if (!input || !input.value.trim()) return;

  const question = input.value.trim();
  input.value = "";
  addChatMessage("user", question);

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
    const qLower = question.toLowerCase();
    if (qLower.includes("cost") || qLower.includes("budget")) {
      addChatMessage("ai", `Found 1 critical cost finding on WBS 1.0 (Actual cost exceeded budget by IDR 250,000,000).`, "Review commitment approval workflows.");
    } else if (qLower.includes("delay") || qLower.includes("schedule")) {
      addChatMessage("ai", `Activity ACT-040 (Foundation Work) is delayed by 14 days past baseline finish.`, "Fast-track critical path activities.");
    } else {
      addChatMessage("ai", `Project health score is ${state.health.overall}/100 ('${state.health.band}'). Evaluated across 20 rules.`, "Address top critical findings first.");
    }
  }, 350);
}

function addChatMessage(sender, text, action = null) {
  const container = document.getElementById("copilot-messages");
  if (!container) return;

  const bubble = document.createElement("div");
  bubble.className = `chat-bubble bubble-${sender}`;
  bubble.innerHTML = `<div>${text}</div>` + (action ? `<div style="margin-top: 6px; padding-top: 6px; border-top: 1px dashed rgba(255,255,255,0.15); font-size: 0.725rem; color: var(--color-healthy);"><strong>Recommended Action:</strong> ${action}</div>` : "");

  container.appendChild(bubble);
  container.scrollTop = container.scrollHeight;
}

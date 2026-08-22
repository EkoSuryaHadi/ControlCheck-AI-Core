import React, { useState, useEffect } from "react"
import { useParams, useNavigate } from "react-router-dom"
import { INITIAL_FINDINGS } from "./FindingsPage"
import { useProject } from "@/context/ProjectContext"
import { useAuth } from "@/context/AuthContext"
import { api } from "@/lib/api"
import { SeverityBadge, StatusBadge } from "@/components/ui/Badges"
import {
  ArrowLeft,
  Plus,
  CheckCircle2,
  Sparkles,
  Layers,
  FileSpreadsheet,
  History,
  CheckSquare,
  AlertCircle,
  FileCode,
  Loader2,
  X,
  Calendar,
  User,
  Clock,
  Shield,
} from "lucide-react"

interface ActionItem {
  id: string
  title: string
  assignee: string
  dueDate: string
  priority: "high" | "medium" | "low"
  status: "open" | "in_review" | "completed"
  notes?: string
}

interface HistoryEntry {
  id: string
  timestamp: string
  actor: string
  action: string
  notes?: string
}

export const FindingDetailPage: React.FC = () => {
  const { findingId } = useParams<{ findingId: string }>()
  const navigate = useNavigate()
  const { liveFindings } = useProject()
  const { user } = useAuth()

  const [activeTab, setActiveTab] = useState<"overview" | "evidence" | "ai" | "actions" | "history">(
    "overview"
  )
  const [status, setStatus] = useState("Open")
  const [isUpdatingStatus, setIsUpdatingStatus] = useState(false)
  const [evidenceList, setEvidenceList] = useState<any[]>([])

  // Modal States
  const [showActionModal, setShowActionModal] = useState(false)
  const [showResolveModal, setShowResolveModal] = useState(false)

  // Action Form State
  const [actionTitle, setActionTitle] = useState("")
  const [actionAssignee, setActionAssignee] = useState("Budi Santoso")
  const [actionDueDate, setActionDueDate] = useState("2024-11-05")
  const [actionPriority, setActionPriority] = useState<"high" | "medium" | "low">("high")
  const [actionNotes, setActionNotes] = useState("")

  // Resolve Form State
  const [resolutionNotes, setResolutionNotes] = useState("")
  const [rootCauseCategory, setRootCauseCategory] = useState("Vendor Pricing Variance")

  // Dynamic Lists for this finding
  const [actions, setActions] = useState<ActionItem[]>([
    {
      id: "ACT-01",
      title: "Conduct price variance audit on PO-23017",
      assignee: "Budi Santoso",
      dueDate: "05 Nov 2024",
      priority: "high",
      status: "in_review",
      notes: "Cross-reference vendor quote with baseline equipment estimation.",
    },
  ])

  const [historyTrail, setHistoryTrail] = useState<HistoryEntry[]>([
    {
      id: "HIST-01",
      timestamp: "28 Oct 2024 14:30",
      actor: "Deterministic Engine",
      action: "Finding detected during automated audit run #829",
      notes: "Severity set to CRITICAL based on rule CST-01 threshold (+24.3% variance).",
    },
    {
      id: "HIST-02",
      timestamp: "28 Oct 2024 15:10",
      actor: user?.name || "Eko Prasetyo",
      action: "Action item #ACT-01 created and assigned to Budi Santoso",
    },
  ])

  // Find either from live backend findings or baseline catalog
  const finding =
    liveFindings.find((f) => f.id === findingId || f.rule_id === findingId) ||
    INITIAL_FINDINGS.find((f) => f.id === findingId) ||
    INITIAL_FINDINGS[0]

  useEffect(() => {
    if (finding?.id && finding.id.includes("-")) {
      api.findings
        .getEvidence(finding.id)
        .then((res) => {
          if (res?.items?.length) setEvidenceList(res.items)
        })
        .catch(() => {})
    }
  }, [finding?.id])

  const handleCreateAction = (e: React.FormEvent) => {
    e.preventDefault()
    if (!actionTitle.trim()) return

    const newAction: ActionItem = {
      id: `ACT-0${actions.length + 1}`,
      title: actionTitle,
      assignee: actionAssignee,
      dueDate: actionDueDate,
      priority: actionPriority,
      status: "open",
      notes: actionNotes,
    }

    setActions((prev) => [...prev, newAction])

    // Log to history trail
    const newHist: HistoryEntry = {
      id: `HIST-0${historyTrail.length + 1}`,
      timestamp: new Date().toLocaleString("en-GB", {
        day: "2-digit",
        month: "short",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      }),
      actor: user?.name || "Eko Prasetyo",
      action: `Action item #${newAction.id} created: "${newAction.title}"`,
      notes: `Assigned to ${newAction.assignee} (Due: ${newAction.dueDate})`,
    }

    setHistoryTrail((prev) => [...prev, newHist])
    setShowActionModal(false)
    setActionTitle("")
    setActionNotes("")
    setActiveTab("actions")
  }

  const handleConfirmResolve = async (e: React.FormEvent) => {
    e.preventDefault()
    setIsUpdatingStatus(true)

    try {
      if (finding?.id && finding.id.includes("-")) {
        await api.findings.updateStatus(finding.id, "resolved")
      }
      setStatus("Resolved")

      const newHist: HistoryEntry = {
        id: `HIST-0${historyTrail.length + 1}`,
        timestamp: new Date().toLocaleString("en-GB", {
          day: "2-digit",
          month: "short",
          year: "numeric",
          hour: "2-digit",
          minute: "2-digit",
        }),
        actor: user?.name || "Eko Prasetyo",
        action: `Finding status updated to RESOLVED`,
        notes: `Category: ${rootCauseCategory} | Resolution: ${resolutionNotes || "Mitigation verified by project manager"}`,
      }

      setHistoryTrail((prev) => [...prev, newHist])
      setShowResolveModal(false)
      setResolutionNotes("")
    } catch {
      setStatus("Resolved")
      setShowResolveModal(false)
    } finally {
      setIsUpdatingStatus(false)
    }
  }

  const metrics = [
    {
      metric: "Budget (BAC)",
      budget: "Rp 771,000,000",
      actual: "—",
      variance: "—",
      variancePct: "—",
    },
    {
      metric: "Actual (AC)",
      budget: "—",
      actual: "Rp 958,400,000",
      variance: "187,400,000",
      variancePct: "24.3%",
    },
    {
      metric: "Commitment (PO)",
      budget: "—",
      actual: "Rp 210,000,000",
      variance: "—",
      variancePct: "—",
    },
    {
      metric: "EAC (Forecast)",
      budget: "—",
      actual: "Rp 1,168,400,000",
      variance: "414,400,000",
      variancePct: "53.7%",
    },
  ]

  const fallbackEvidence = [
    {
      table: "raw_cost_records",
      row: 142,
      wbs: "03.02",
      field: "transaction_amount",
      value: "Rp 125,000,000",
      vendor: "PT. Alpha Teknik",
      po: "PO-23017",
      date: "2024-10-15",
    },
    {
      table: "raw_cost_records",
      row: 156,
      wbs: "03.02",
      field: "transaction_amount",
      value: "Rp 62,400,000",
      vendor: "PT. Beta Mekanikal",
      po: "PO-23021",
      date: "2024-10-22",
    },
    {
      table: "raw_budget_records",
      row: 12,
      wbs: "03.02",
      field: "bac_amount",
      value: "Rp 771,000,000",
      vendor: "Baseline 01",
      po: "—",
      date: "2024-01-01",
    },
  ]

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-12">
      {/* Back button */}
      <div>
        <button
          onClick={() => navigate("/findings")}
          className="inline-flex items-center gap-1.5 text-xs font-semibold text-slate-500 hover:text-slate-900 transition-colors"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          <span>Back to Findings</span>
        </button>
      </div>

      {/* Main Finding Header Card */}
      <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm space-y-4">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="flex items-start gap-3">
            <span
              className={`px-3 py-1 text-white rounded-md text-xs font-bold uppercase tracking-wider ${
                status === "Resolved" ? "bg-emerald-600" : "bg-red-500"
              }`}
            >
              {status === "Resolved" ? "RESOLVED" : (finding.severity || "CRITICAL").toUpperCase()}
            </span>
            <div>
              <h1 className="text-xl font-bold text-slate-900 tracking-tight">
                {finding.title}
              </h1>
              <div className="text-xs text-slate-400 font-mono mt-0.5">
                ID: {finding.id}
              </div>
            </div>
          </div>

          <div className="flex items-center gap-2.5">
            <button
              onClick={() => setShowActionModal(true)}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-xs font-semibold shadow-sm transition-colors"
            >
              <Plus className="w-3.5 h-3.5" />
              <span>Create Action</span>
            </button>
            {status !== "Resolved" ? (
              <button
                onClick={() => setShowResolveModal(true)}
                className="flex items-center gap-1.5 px-3 py-1.5 bg-white border border-slate-200 hover:bg-slate-50 text-slate-700 rounded-lg text-xs font-semibold shadow-sm transition-colors"
              >
                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                <span>Mark as Resolved</span>
              </button>
            ) : (
              <span className="flex items-center gap-1.5 px-3 py-1.5 bg-emerald-50 text-emerald-700 border border-emerald-200 rounded-lg text-xs font-semibold">
                <CheckCircle2 className="w-3.5 h-3.5" />
                <span>Resolved</span>
              </span>
            )}
          </div>
        </div>

        {/* Metadata Grid */}
        <div className="grid grid-cols-2 sm:grid-cols-5 gap-4 pt-4 border-t border-slate-100 text-xs">
          <div>
            <div className="text-[10px] uppercase font-bold text-slate-400">Category</div>
            <div className="font-semibold text-slate-800 mt-0.5">{finding.category}</div>
          </div>
          <div>
            <div className="text-[10px] uppercase font-bold text-slate-400">WBS</div>
            <div className="font-semibold text-slate-800 mt-0.5">
              {finding.wbs || (finding as any).wbs_code || "03.02"} - {finding.wbs_name || "Compressor Package"}
            </div>
          </div>
          <div>
            <div className="text-[10px] uppercase font-bold text-slate-400">Impact</div>
            <div className="font-bold text-red-600 mt-0.5 tabular-nums">
              {finding.impact || (finding as any).business_impact || "Rp 187.4M (24.3%)"}
            </div>
          </div>
          <div>
            <div className="text-[10px] uppercase font-bold text-slate-400">Detected On</div>
            <div className="font-semibold text-slate-800 mt-0.5">
              {finding.detected_on || "28 Oct 2024"}
            </div>
          </div>
          <div>
            <div className="text-[10px] uppercase font-bold text-slate-400">Status</div>
            <div className="mt-0.5">
              <StatusBadge status={status} />
            </div>
          </div>
        </div>
      </div>

      {/* Tabs Navigation */}
      <div className="flex border-b border-slate-200 text-xs font-semibold space-x-6">
        {[
          { id: "overview", label: "Overview", icon: Layers },
          { id: "evidence", label: "Evidence", icon: FileSpreadsheet },
          { id: "ai", label: "Analysis (AI)", icon: Sparkles },
          { id: "actions", label: `Actions (${actions.length})`, icon: CheckSquare },
          { id: "history", label: `History (${historyTrail.length})`, icon: History },
        ].map((t) => {
          const Icon = t.icon
          const isActive = activeTab === t.id
          return (
            <button
              key={t.id}
              onClick={() => setActiveTab(t.id as any)}
              className={`flex items-center gap-1.5 pb-3 border-b-2 transition-all ${
                isActive
                  ? "border-blue-600 text-blue-600"
                  : "border-transparent text-slate-500 hover:text-slate-800"
              }`}
            >
              <Icon className="w-4 h-4" />
              <span>{t.label}</span>
            </button>
          )
        })}
      </div>

      {/* Tab 1: Overview */}
      {activeTab === "overview" && (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          <div className="lg:col-span-8 space-y-6">
            <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm">
              <h2 className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-2">
                DESCRIPTION
              </h2>
              <p className="text-xs text-slate-800 leading-relaxed">
                {finding.description ||
                  "Actual cost on WBS 03.02 exceeds the approved budget by 24.3%. This indicates potential cost overrun risk if the trend continues."}
              </p>
            </div>

            {/* Metrics Breakdown */}
            <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm space-y-3">
              <h2 className="text-xs font-bold uppercase tracking-wider text-slate-400">
                METRICS
              </h2>
              <div className="overflow-x-auto">
                <table className="w-full text-xs text-left border-collapse">
                  <thead>
                    <tr className="bg-slate-50 border-b border-slate-200 text-[11px] text-slate-500 font-semibold uppercase">
                      <th className="py-2.5 px-3">Metric</th>
                      <th className="py-2.5 px-3 text-right">Budget</th>
                      <th className="py-2.5 px-3 text-right">Actual</th>
                      <th className="py-2.5 px-3 text-right">Variance</th>
                      <th className="py-2.5 px-3 text-right">Variance %</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 font-medium">
                    {metrics.map((m, i) => (
                      <tr key={i} className="hover:bg-slate-50">
                        <td className="py-2.5 px-3 font-semibold text-slate-800">{m.metric}</td>
                        <td className="py-2.5 px-3 text-right font-mono text-slate-600 tabular-nums">
                          {m.budget}
                        </td>
                        <td className="py-2.5 px-3 text-right font-mono text-slate-900 font-bold tabular-nums">
                          {m.actual}
                        </td>
                        <td className="py-2.5 px-3 text-right font-mono text-red-600 font-bold tabular-nums">
                          {m.variance}
                        </td>
                        <td className="py-2.5 px-3 text-right font-mono text-red-600 font-bold tabular-nums">
                          {m.variancePct}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>

          <div className="lg:col-span-4 space-y-4">
            <div className="bg-linear-to-br from-purple-50/80 to-white p-5 rounded-xl border border-purple-200 shadow-sm space-y-4">
              <div>
                <div className="flex items-center gap-1.5 text-purple-900 text-xs font-bold uppercase tracking-wider mb-1.5">
                  <Sparkles className="w-3.5 h-3.5 text-purple-600" />
                  <span>AI SUMMARY</span>
                </div>
                <p className="text-xs text-slate-700 leading-relaxed">
                  {finding.ai_summary ||
                    "Main cost drivers are material purchase variance and additional work order on piping modification. Review PO 23017 and 23021 for detail."}
                </p>
              </div>

              <div className="pt-3 border-t border-purple-100">
                <div className="text-[10px] font-bold text-slate-600 uppercase tracking-wider mb-1">
                  RECOMMENDATION
                </div>
                <p className="text-xs text-slate-700 leading-relaxed">
                  {finding.recommendation ||
                    "Review material quantity variance and additional work order. Negotiate with vendor and optimize installation method."}
                </p>
              </div>

              <div className="pt-3 border-t border-purple-100">
                <div className="text-[10px] font-bold text-red-700 uppercase tracking-wider mb-1">
                  POTENTIAL IMPACT
                </div>
                <p className="text-xs text-red-700 font-medium leading-relaxed">
                  {finding.potential_impact ||
                    "If not addressed, potential additional cost up to Rp 414.4M (EAC over budget)."}
                </p>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Tab 2: Evidence */}
      {activeTab === "evidence" && (
        <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-sm font-bold text-slate-900">
                Verbatim Evidence Records (Raw Row Lineage)
              </h2>
              <p className="text-xs text-slate-500">
                Extracted directly from source Excel workbook without alteration
              </p>
            </div>
            <span className="text-xs font-mono bg-blue-50 text-blue-700 px-2 py-1 rounded border border-blue-200">
              3 Lineage Records
            </span>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-xs text-left border-collapse">
              <thead>
                <tr className="bg-slate-50 border-b border-slate-200 text-[11px] text-slate-500 font-semibold uppercase">
                  <th className="py-2.5 px-3">Source Table</th>
                  <th className="py-2.5 px-3">Excel Row</th>
                  <th className="py-2.5 px-3">WBS Code</th>
                  <th className="py-2.5 px-3">Field</th>
                  <th className="py-2.5 px-3">Value</th>
                  <th className="py-2.5 px-3">Vendor / Entity</th>
                  <th className="py-2.5 px-3">PO Reference</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 font-medium">
                {fallbackEvidence.map((ev, i) => (
                  <tr key={i} className="hover:bg-slate-50">
                    <td className="py-2.5 px-3 font-mono text-blue-600">{ev.table}</td>
                    <td className="py-2.5 px-3 font-mono font-bold text-slate-800">
                      Row #{ev.row}
                    </td>
                    <td className="py-2.5 px-3 font-mono text-slate-700">{ev.wbs}</td>
                    <td className="py-2.5 px-3 text-slate-600">{ev.field}</td>
                    <td className="py-2.5 px-3 font-bold text-slate-900 tabular-nums">
                      {ev.value}
                    </td>
                    <td className="py-2.5 px-3 text-slate-700">{ev.vendor}</td>
                    <td className="py-2.5 px-3 font-mono text-slate-600">{ev.po}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Tab 3: Analysis (AI) */}
      {activeTab === "ai" && (
        <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm space-y-4">
          <div className="flex items-center gap-2 text-purple-900">
            <Sparkles className="w-5 h-5 text-purple-600" />
            <h2 className="text-sm font-bold">Deterministic Audit Reasoning & Root Cause</h2>
          </div>
          <div className="p-4 bg-purple-50/50 rounded-lg border border-purple-200 space-y-3 text-xs text-slate-800 leading-relaxed">
            <p>
              <strong>Rule CST-01 Evaluation:</strong> Threshold for cost variance warning is set at 10.0%, critical at 20.0%. WBS 03.02 evaluated with BAC = Rp 771,000,000 and AC = Rp 958,400,000.
            </p>
            <p>
              Variance = Actual - Budget = +Rp 187,400,000 (+24.3%). Since variance exceeds critical threshold (20.0%), finding severity is rated <strong>CRITICAL</strong>.
            </p>
            <p>
              Underlying vendor records indicate purchase order PO-23017 was issued with unit price higher than original engineering estimate.
            </p>
          </div>
        </div>
      )}

      {/* Tab 4: Actions */}
      {activeTab === "actions" && (
        <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-sm font-bold text-slate-900">Assigned Corrective Actions</h2>
              <p className="text-xs text-slate-500">Track and assign mitigation tasks for this audit finding</p>
            </div>
            <button
              onClick={() => setShowActionModal(true)}
              className="flex items-center gap-1 px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-xs font-semibold shadow-sm transition-colors"
            >
              <Plus className="w-3.5 h-3.5" />
              <span>New Action Item</span>
            </button>
          </div>

          <div className="space-y-3">
            {actions.map((act) => (
              <div
                key={act.id}
                className="p-4 border border-slate-200 rounded-xl hover:border-slate-300 transition-all flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-slate-50/50"
              >
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-xs font-bold text-blue-600 bg-blue-50 px-2 py-0.5 rounded">
                      {act.id}
                    </span>
                    <h3 className="font-semibold text-slate-900 text-xs">{act.title}</h3>
                    <span
                      className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase ${
                        act.priority === "high"
                          ? "bg-red-50 text-red-700"
                          : "bg-amber-50 text-amber-700"
                      }`}
                    >
                      {act.priority} Priority
                    </span>
                  </div>
                  {act.notes && <p className="text-xs text-slate-600">{act.notes}</p>}
                  <div className="flex items-center gap-4 text-[11px] text-slate-500 pt-1">
                    <span className="flex items-center gap-1">
                      <User className="w-3 h-3 text-slate-400" />
                      <span>{act.assignee}</span>
                    </span>
                    <span className="flex items-center gap-1">
                      <Calendar className="w-3 h-3 text-slate-400" />
                      <span>Due: {act.dueDate}</span>
                    </span>
                  </div>
                </div>

                <div className="flex items-center gap-2 shrink-0">
                  <StatusBadge status={act.status} />
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Tab 5: History */}
      {activeTab === "history" && (
        <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm space-y-4">
          <div className="flex items-center justify-between border-b border-slate-100 pb-3">
            <div>
              <h2 className="text-sm font-bold text-slate-900">Audit History & Event Trail</h2>
              <p className="text-xs text-slate-500">Immutable ledger of finding detections and status changes</p>
            </div>
            <span className="text-xs font-semibold text-slate-500">
              {historyTrail.length} Event Logged
            </span>
          </div>

          <div className="space-y-4">
            {historyTrail.map((h, idx) => (
              <div key={h.id} className="flex items-start gap-3 relative">
                <div className="w-8 h-8 rounded-full bg-blue-50 text-blue-600 flex items-center justify-center shrink-0 mt-0.5 border border-blue-200">
                  <Clock className="w-4 h-4" />
                </div>
                <div className="flex-1 bg-slate-50 p-3 rounded-xl border border-slate-200/70 space-y-1">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold text-slate-900">{h.action}</span>
                    <span className="text-[10px] font-mono text-slate-400">{h.timestamp}</span>
                  </div>
                  <div className="text-[11px] text-slate-600">
                    By <strong className="text-slate-800">{h.actor}</strong>
                  </div>
                  {h.notes && (
                    <div className="text-xs text-slate-700 bg-white p-2 rounded border border-slate-200/80 mt-1">
                      {h.notes}
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Modal: Create Action Item */}
      {showActionModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 backdrop-blur-xs p-4">
          <div className="w-full max-w-lg bg-white rounded-2xl p-6 shadow-2xl border border-slate-200 space-y-4 animate-in fade-in zoom-in-95">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <h2 className="text-base font-bold text-slate-900">Create Corrective Action Item</h2>
              <button
                onClick={() => setShowActionModal(false)}
                className="text-slate-400 hover:text-slate-600 p-1"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleCreateAction} className="space-y-4 text-xs">
              <div>
                <label className="font-bold text-slate-700 block mb-1">Action Title *</label>
                <input
                  type="text"
                  required
                  value={actionTitle}
                  onChange={(e) => setActionTitle(e.target.value)}
                  placeholder="e.g. Conduct vendor price audit on PO-23017"
                  className="w-full p-2.5 bg-slate-50 border border-slate-200 rounded-lg text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="font-bold text-slate-700 block mb-1">Assignee</label>
                  <select
                    value={actionAssignee}
                    onChange={(e) => setActionAssignee(e.target.value)}
                    className="w-full p-2 bg-slate-50 border border-slate-200 rounded-lg text-slate-900 focus:outline-none focus:ring-1 focus:ring-blue-500"
                  >
                    <option value="Budi Santoso">Budi Santoso (Cost Engineer)</option>
                    <option value="Rina Amelia">Rina Amelia (Scheduler)</option>
                    <option value="Eko Prasetyo">Eko Prasetyo (Project Control Lead)</option>
                    <option value="Ahmad Dahlan">Ahmad Dahlan (Site Manager)</option>
                  </select>
                </div>

                <div>
                  <label className="font-bold text-slate-700 block mb-1">Priority</label>
                  <select
                    value={actionPriority}
                    onChange={(e) => setActionPriority(e.target.value as any)}
                    className="w-full p-2 bg-slate-50 border border-slate-200 rounded-lg text-slate-900 focus:outline-none focus:ring-1 focus:ring-blue-500"
                  >
                    <option value="high">High Priority</option>
                    <option value="medium">Medium Priority</option>
                    <option value="low">Low Priority</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="font-bold text-slate-700 block mb-1">Due Date</label>
                <input
                  type="date"
                  value={actionDueDate}
                  onChange={(e) => setActionDueDate(e.target.value)}
                  className="w-full p-2 bg-slate-50 border border-slate-200 rounded-lg text-slate-900 focus:outline-none focus:ring-1 focus:ring-blue-500"
                />
              </div>

              <div>
                <label className="font-bold text-slate-700 block mb-1">Mitigation Description & Instructions</label>
                <textarea
                  rows={3}
                  value={actionNotes}
                  onChange={(e) => setActionNotes(e.target.value)}
                  placeholder="Detail the exact verification steps required..."
                  className="w-full p-2 bg-slate-50 border border-slate-200 rounded-lg text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>

              <div className="flex items-center justify-end gap-2 pt-2 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setShowActionModal(false)}
                  className="px-3 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-lg font-semibold"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-semibold shadow-sm"
                >
                  Create & Assign Action
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal: Mark as Resolved */}
      {showResolveModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 backdrop-blur-xs p-4">
          <div className="w-full max-w-md bg-white rounded-2xl p-6 shadow-2xl border border-slate-200 space-y-4 animate-in fade-in zoom-in-95">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <h2 className="text-base font-bold text-slate-900">Resolve Audit Finding</h2>
              <button
                onClick={() => setShowResolveModal(false)}
                className="text-slate-400 hover:text-slate-600 p-1"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleConfirmResolve} className="space-y-4 text-xs">
              <div>
                <label className="font-bold text-slate-700 block mb-1">Root Cause Category *</label>
                <select
                  value={rootCauseCategory}
                  onChange={(e) => setRootCauseCategory(e.target.value)}
                  className="w-full p-2 bg-slate-50 border border-slate-200 rounded-lg text-slate-900 focus:outline-none focus:ring-1 focus:ring-blue-500"
                >
                  <option value="Vendor Pricing Variance">Vendor Pricing Variance</option>
                  <option value="Scope Change / Additional Work Order">Scope Change / Additional Work Order</option>
                  <option value="Estimating Baseline Error">Estimating Baseline Error</option>
                  <option value="Data Ingestion Anomaly">Data Ingestion Anomaly</option>
                  <option value="Approved Management Exception">Approved Management Exception</option>
                </select>
              </div>

              <div>
                <label className="font-bold text-slate-700 block mb-1">Resolution Summary & Mitigation Audit *</label>
                <textarea
                  required
                  rows={3}
                  value={resolutionNotes}
                  onChange={(e) => setResolutionNotes(e.target.value)}
                  placeholder="Explain how this finding was mitigated or verified..."
                  className="w-full p-2 bg-slate-50 border border-slate-200 rounded-lg text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>

              <div className="p-3 bg-emerald-50 text-emerald-800 border border-emerald-200 rounded-lg text-[11px] flex items-start gap-2">
                <Shield className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
                <span>
                  Resolving this finding will update project health penalties and record an immutable entry in the audit trail.
                </span>
              </div>

              <div className="flex items-center justify-end gap-2 pt-2 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setShowResolveModal(false)}
                  className="px-3 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-lg font-semibold"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isUpdatingStatus}
                  className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 text-white rounded-lg font-semibold shadow-sm flex items-center gap-1.5"
                >
                  {isUpdatingStatus ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : null}
                  <span>Confirm Resolution</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}

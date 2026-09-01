import React, { useEffect, useState } from "react"
import { useNavigate } from "react-router-dom"
import { useProject } from "@/context/ProjectContext"
import { HealthGauge } from "@/components/ui/HealthGauge"
import { DomainHealthBar, MetricCard } from "@/components/ui/DomainHealthBar"
import { SeverityBadge } from "@/components/ui/Badges"
import { api, AnalysisSummary } from "@/lib/api"
import {
  DollarSign,
  TrendingUp,
  AlertTriangle,
  ChevronRight,
  Sparkles,
  Bot,
  ArrowUpRight,
  FileCheck,
  CheckCircle2,
  FileText,
} from "lucide-react"
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  BarChart,
  Bar,
  Legend,
} from "recharts"

export const DashboardPage: React.FC = () => {
  const { currentProject, currentRun, healthData, liveFindings } = useProject()
  const [summary, setSummary] = useState<AnalysisSummary | null>(null)
  const navigate = useNavigate()

  useEffect(() => {
    if (!currentProject?.id || !currentRun?.id) {
      setSummary(null)
      return
    }
    void api.runs.getSummary(currentProject.id, currentRun.id).then(setSummary).catch(() => setSummary(null))
  }, [currentProject?.id, currentRun?.id])

  const severityRank: Record<string, number> = { critical: 0, warning: 1, observation: 2 }
  const criticalFindings = [...liveFindings]
    .filter((finding) => ["critical", "warning"].includes(String(finding.severity).toLowerCase()))
    .sort((a, b) => (severityRank[a.severity] ?? 9) - (severityRank[b.severity] ?? 9))
    .slice(0, 5)
    .map((finding) => ({ ...finding, impact: finding.impact || finding.potential_impact || "—" }))

  const recentActivities = currentRun ? [{ type: "analysis", title: `Analysis completed: ${currentProject?.name || "Current project"}`, author: "Server analysis", time: currentRun.completed_at ? new Date(currentRun.completed_at).toLocaleString() : "ล่าสุด", icon: FileCheck, iconColor: "text-blue-600 bg-blue-50" }] : []
  const riskTrendData = [{ month: currentRun?.completed_at ? new Date(currentRun.completed_at).toLocaleDateString(undefined, { month: "short" }) : "Current", warning: liveFindings.filter((f) => f.severity === "warning").length, observation: liveFindings.filter((f) => f.severity === "observation").length, critical: liveFindings.filter((f) => f.severity === "critical").length }]
  const costTrendData: Array<{ month: string; bac?: number; ac?: number; eac?: number }> = summary?.cost.available ? [{ month: "Current", bac: summary.cost.budget_total, ac: summary.cost.actual_total, eac: summary.cost.actual_total }] : []

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-12">
      {/* Top Section: Health & KPI Summary */}
      <div className="space-y-3">
        <div className="grid grid-cols-1 md:grid-cols-12 gap-4">
          {/* Health Gauge Box */}
          <div className="md:col-span-3">
            <HealthGauge
              score={healthData?.overall_score ?? null}
              label={healthData?.status_label ?? "NOT COMPUTED"}
              lastUpdated={currentRun ? "Latest completed analysis" : "No completed analysis"}
              size={150}
              className="h-full"
            />
          </div>

          {/* Metric Summary Cards */}
          <div className="md:col-span-9 grid grid-cols-2 lg:grid-cols-4 gap-4">
            <MetricCard
              title="CRITICAL"
              value={healthData?.critical_findings_count ?? liveFindings.filter((f) => f.severity === "critical").length}
              delta={{ label: "current run", value: 0, isPositive: true }}
              variant="critical"
            />
            <MetricCard
              title="WARNING"
              value={healthData?.warning_findings_count ?? liveFindings.filter((f) => f.severity === "warning").length}
              delta={{ label: "current run", value: 0, isPositive: true }}
              variant="warning"
            />
            <MetricCard
              title="OBSERVATION"
              value={healthData?.observation_findings_count ?? liveFindings.filter((f) => f.severity === "observation").length}
              delta={{ label: "current run", value: 0, isPositive: true }}
              variant="observation"
            />
            <MetricCard
              title="DATA QUALITY"
              value={healthData?.data_quality_score == null ? "—" : `${healthData.data_quality_score}`}
              delta={{ label: "vs last month", value: 3, isPositive: true }}
              variant="success"
            />
          </div>
        </div>

        {/* Domain Health Score Strip */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          <DomainHealthBar
            title="COST HEALTH"
              score={healthData?.cost_score ?? null}
            weight="30%"
            icon="cost"
            onClick={() => navigate("/cost")}
          />
          <DomainHealthBar
            title="SCHEDULE HEALTH"
              score={healthData?.schedule_score ?? null}
            weight="30%"
            icon="schedule"
            onClick={() => navigate("/schedule")}
          />
          <DomainHealthBar
            title="PROGRESS HEALTH"
              score={healthData?.progress_score ?? null}
            weight="25%"
            icon="progress"
            onClick={() => navigate("/progress")}
          />
          <DomainHealthBar
            title="DATA QUALITY"
              score={healthData?.data_quality_score ?? null}
            weight="15%"
            icon="quality"
            onClick={() => navigate("/data")}
          />
        </div>
      </div>

      {/* Middle Analytical Row */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Cost Performance Card */}
        <div className="lg:col-span-4 bg-white p-5 rounded-xl border border-slate-200 shadow-sm flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-xs font-bold uppercase tracking-wider text-slate-700">
                COST PERFORMANCE
              </h2>
              <span className="text-xs text-slate-400 font-medium">Billion IDR</span>
            </div>

            <div className="space-y-3">
              <div className="flex items-center justify-between py-1.5 border-b border-slate-100">
                <span className="text-xs font-medium text-slate-600 flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-blue-500" />
                  Budget (BAC)
                </span>
                <span className="text-xs font-bold text-slate-900 tabular-nums">
                  —
                </span>
              </div>
              <div className="flex items-center justify-between py-1.5 border-b border-slate-100">
                <span className="text-xs font-medium text-slate-600 flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-purple-600" />
                  Actual (AC)
                </span>
                <span className="text-xs font-bold text-slate-900 tabular-nums">
                  —
                </span>
              </div>
              <div className="flex items-center justify-between py-1.5 border-b border-slate-100">
                <span className="text-xs font-medium text-slate-600 flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-amber-500" />
                  Commitment (PO)
                </span>
                <span className="text-xs font-bold text-slate-900 tabular-nums">
                  —
                </span>
              </div>
              <div className="flex items-center justify-between py-1.5">
                <span className="text-xs font-medium text-slate-600 flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-red-500" />
                  Estimate at Completion (EAC)
                </span>
                <span className="text-xs font-bold text-slate-900 tabular-nums">
                  —
                </span>
              </div>
            </div>
          </div>

          <div className="mt-4 rounded-lg bg-blue-50 p-3 text-xs text-blue-900">
            <div className="font-semibold">Schedule coverage</div>
            <div className="mt-1">{summary ? `${summary.schedule.activity_count.toLocaleString()} activities imported` : "Run summary is loading"}</div>
            {summary && <button onClick={() => navigate("/schedule")} className="mt-2 font-semibold text-blue-700 hover:underline">View schedule details →</button>}
          </div>

          {/* Bottom KPI Triad */}
          <div className="grid grid-cols-3 gap-2 pt-4 mt-4 border-t border-slate-100 text-center">
            <div className="p-2 bg-slate-50 rounded-lg">
              <div className="text-[10px] uppercase font-bold text-slate-500">CPI</div>
              <div className="text-sm font-bold text-slate-900 tabular-nums mt-0.5">—</div>
            </div>
            <div className="p-2 bg-red-50/50 rounded-lg">
              <div className="text-[10px] uppercase font-bold text-red-600">CV</div>
              <div className="text-xs font-bold text-red-600 tabular-nums mt-0.5">—</div>
            </div>
            <div className="p-2 bg-amber-50/50 rounded-lg">
              <div className="text-[10px] uppercase font-bold text-amber-700">EAC VAR</div>
              <div className="text-xs font-bold text-amber-700 tabular-nums mt-0.5">—</div>
            </div>
          </div>
        </div>

        {/* Cost Trend Chart */}
        <div className="lg:col-span-4 bg-white p-5 rounded-xl border border-slate-200 shadow-sm flex flex-col justify-between">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-purple-600" />
              <h2 className="text-xs font-bold uppercase tracking-wider text-slate-700">
                COST TREND (AC Cumulative)
              </h2>
            </div>
            <span className="text-[10px] text-slate-400">Billion IDR</span>
          </div>

          <div className="h-56 w-full">
            {costTrendData.length === 0 ? <div className="flex h-full items-center justify-center text-center text-xs text-slate-400">Cost data is not available in this analysis run.</div> : <ResponsiveContainer width="100%" height="100%">
              <LineChart data={costTrendData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#F1F5F9" />
                <XAxis dataKey="month" tick={{ fontSize: 10, fill: "#94A3B8" }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fontSize: 10, fill: "#94A3B8" }} axisLine={false} tickLine={false} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: "#07192D",
                    borderRadius: "8px",
                    color: "#fff",
                    fontSize: "11px",
                    border: "none",
                  }}
                />
                <Line
                  type="monotone"
                  dataKey="bac"
                  name="Budget (BAC)"
                  stroke="#94A3B8"
                  strokeDasharray="4 4"
                  dot={false}
                  strokeWidth={1.5}
                />
                <Line
                  type="monotone"
                  dataKey="ac"
                  name="Actual (AC)"
                  stroke="#1769E8"
                  strokeWidth={2.5}
                  dot={{ r: 3, fill: "#1769E8" }}
                />
                <Line
                  type="monotone"
                  dataKey="eac"
                  name="Forecast (EAC)"
                  stroke="#EF4444"
                  strokeDasharray="3 3"
                  dot={false}
                  strokeWidth={1.5}
                />
              </LineChart>
            </ResponsiveContainer>}
          </div>

          <div className="flex items-center justify-center gap-4 text-[10px] text-slate-500 pt-2 border-t border-slate-100">
            <span className="flex items-center gap-1">
              <span className="w-3 h-0.5 bg-slate-400 inline-block border-dashed" /> Budget (BAC)
            </span>
            <span className="flex items-center gap-1">
              <span className="w-3 h-0.5 bg-blue-600 inline-block" /> Actual (AC)
            </span>
            <span className="flex items-center gap-1">
              <span className="w-3 h-0.5 bg-red-500 inline-block" /> Forecast (EAC)
            </span>
          </div>
        </div>

        {/* Top Critical Findings */}
        <div className="lg:col-span-4 bg-white p-5 rounded-xl border border-slate-200 shadow-sm flex flex-col justify-between">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-xs font-bold uppercase tracking-wider text-slate-700">
              TOP CRITICAL FINDINGS
            </h2>
            <button
              onClick={() => navigate("/findings")}
              className="text-xs font-semibold text-blue-600 hover:text-blue-700 hover:underline"
            >
              View all
            </button>
          </div>

          <div className="space-y-2 flex-1">
            {criticalFindings.map((f) => (
              <div
                key={f.id}
                onClick={() => navigate(`/findings/${f.id}`)}
                className="p-2.5 rounded-lg border border-slate-100 hover:border-slate-300 hover:bg-slate-50/70 transition-all cursor-pointer flex items-center justify-between group"
              >
                <div className="flex items-center gap-2.5 overflow-hidden pr-2">
                  <span
                    className={`w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold text-white shrink-0 ${
                      f.severity === "critical" ? "bg-red-500" : "bg-amber-500"
                    }`}
                  >
                    {f.severity === "critical" ? "A" : "B"}
                  </span>
                  <span className="text-xs font-semibold text-slate-800 truncate group-hover:text-blue-600 transition-colors">
                    {f.title}
                  </span>
                </div>
                <div className="text-right shrink-0 flex items-center gap-1.5">
                  <span className="text-xs font-bold text-slate-900 tabular-nums">
                    {f.impact}
                  </span>
                  <ChevronRight className="w-3.5 h-3.5 text-slate-400 group-hover:text-slate-700 group-hover:translate-x-0.5 transition-all" />
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Bottom Operational Row */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Risk Trend by Severity Stacked Chart */}
        <div className="lg:col-span-4 bg-white p-5 rounded-xl border border-slate-200 shadow-sm flex flex-col justify-between">
          <div className="flex items-center justify-between mb-2">
            <h2 className="text-xs font-bold uppercase tracking-wider text-slate-700">
              RISK TREND (by Severity)
            </h2>
            <div className="flex items-center gap-3 text-[10px]">
              <span className="flex items-center gap-1 text-amber-600">
                <span className="w-2 h-2 rounded-sm bg-amber-500" /> Warning
              </span>
              <span className="flex items-center gap-1 text-yellow-600">
                <span className="w-2 h-2 rounded-sm bg-yellow-400" /> Observation
              </span>
              <span className="flex items-center gap-1 text-red-600">
                <span className="w-2 h-2 rounded-sm bg-red-500" /> Critical
              </span>
            </div>
          </div>

          <div className="h-48 w-full">
            <ResponsiveContainer width="100%" height="100%">
                <BarChart data={riskTrendData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#F1F5F9" />
                <XAxis dataKey="month" tick={{ fontSize: 10, fill: "#94A3B8" }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fontSize: 10, fill: "#94A3B8" }} axisLine={false} tickLine={false} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: "#07192D",
                    borderRadius: "8px",
                    color: "#fff",
                    fontSize: "11px",
                    border: "none",
                  }}
                />
                <Bar dataKey="critical" stackId="a" fill="#EF4444" radius={[0, 0, 0, 0]} />
                <Bar dataKey="warning" stackId="a" fill="#F59E0B" radius={[0, 0, 0, 0]} />
                <Bar dataKey="observation" stackId="a" fill="#EAB308" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Recent Activities List */}
        <div className="lg:col-span-4 bg-white p-5 rounded-xl border border-slate-200 shadow-sm flex flex-col justify-between">
          <h2 className="text-xs font-bold uppercase tracking-wider text-slate-700 mb-3">
            RECENT ACTIVITIES
          </h2>

          <div className="space-y-3 flex-1">
            {recentActivities.map((act, i) => {
              const Icon = act.icon
              return (
                <div key={i} className="flex items-start gap-3 p-2 rounded-lg hover:bg-slate-50 transition-colors">
                  <div className={`p-2 rounded-lg ${act.iconColor} shrink-0 mt-0.5`}>
                    <Icon className="w-3.5 h-3.5" />
                  </div>
                  <div className="overflow-hidden flex-1">
                    <div className="text-xs font-semibold text-slate-800 line-clamp-2">
                      {act.title}
                    </div>
                    <div className="flex items-center gap-2 text-[10px] text-slate-400 mt-1">
                      <span>{act.time}</span>
                      <span>•</span>
                      <span>{act.author}</span>
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        </div>

        {/* AI Insight & Assistant Trigger */}
        <div className="lg:col-span-4 bg-linear-to-br from-purple-50/80 via-white to-purple-50/40 p-5 rounded-xl border border-purple-200/80 shadow-sm flex flex-col justify-between">
          <div>
            <div className="flex items-center gap-2 mb-3">
              <div className="p-1.5 rounded-lg bg-purple-600 text-white">
                <Sparkles className="w-4 h-4" />
              </div>
              <h2 className="text-xs font-bold uppercase tracking-wider text-purple-900">
                AI INSIGHT
              </h2>
            </div>

            <p className="text-xs leading-relaxed text-slate-700">Server returned <strong className="text-slate-900 font-semibold">{liveFindings.length}</strong> findings for this project. Cost KPI cards will populate when a cost dataset is available.</p>
          </div>

          <div className="pt-4">
            <button
              onClick={() => navigate("/assistant")}
              className="w-full flex items-center justify-center gap-2 py-2.5 px-4 bg-purple-600 hover:bg-purple-700 text-white rounded-lg text-xs font-semibold shadow-sm transition-all hover:shadow-md"
            >
              <Bot className="w-4 h-4" />
              <span>Ask AI Assistant</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

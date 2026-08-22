import React, { useState } from "react"
import { useNavigate } from "react-router-dom"
import { useProject } from "@/context/ProjectContext"
import { HealthGauge } from "@/components/ui/HealthGauge"
import { DomainHealthBar, MetricCard } from "@/components/ui/DomainHealthBar"
import { SeverityBadge } from "@/components/ui/Badges"
import { formatCurrency, formatNumber } from "@/lib/utils"
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

// Mock trend data matching mockup
const COST_TREND_DATA = [
  { month: "Jan", bac: 20, ac: 18, eac: 20 },
  { month: "Feb", bac: 40, ac: 38, eac: 40 },
  { month: "Mar", bac: 65, ac: 60, eac: 65 },
  { month: "Apr", bac: 95, ac: 92, eac: 95 },
  { month: "May", bac: 125, ac: 120, eac: 128 },
  { month: "Jun", bac: 155, ac: 152, eac: 162 },
  { month: "Jul", bac: 185, ac: 187, eac: 198 },
  { month: "Aug", bac: 215, ac: null, eac: 232 },
  { month: "Sep", bac: 235, ac: null, eac: 254 },
  { month: "Oct", bac: 245, ac: null, eac: 268 },
  { month: "Nov", bac: 245, ac: null, eac: 268 },
  { month: "Dec", bac: 245, ac: null, eac: 268 },
]

const RISK_TREND_DATA = [
  { month: "Feb", warning: 30, observation: 15, critical: 10 },
  { month: "Apr", warning: 32, observation: 14, critical: 12 },
  { month: "May", warning: 35, observation: 16, critical: 14 },
  { month: "Jul", warning: 38, observation: 18, critical: 16 },
  { month: "Aug", warning: 40, observation: 20, critical: 18 },
  { month: "Sep", warning: 45, observation: 22, critical: 20 },
]

export const DashboardPage: React.FC = () => {
  const { currentProject, healthData } = useProject()
  const navigate = useNavigate()

  const criticalFindings = [
    {
      id: "FND-2024-001",
      title: "Cost Overrun Risk - WBS 03.02",
      impact: "Rp 187.4M",
      severity: "critical",
      wbs: "03.02",
    },
    {
      id: "FND-2024-002",
      title: "PO Exposure exceeds Budget - WBS 11",
      impact: "Rp 28.7M",
      severity: "critical",
      wbs: "11",
    },
    {
      id: "FND-2024-003",
      title: "Activity Delay - Compressor Installation",
      impact: "18 days",
      severity: "critical",
      wbs: "03.02.01",
    },
    {
      id: "FND-2024-004",
      title: "Negative Total Float - 5 Activities",
      impact: "-12 days",
      severity: "critical",
      wbs: "Various",
    },
    {
      id: "FND-2024-005",
      title: "Cost Spike Detected - WBS 04.01",
      impact: "+132%",
      severity: "warning",
      wbs: "04.01",
    },
  ]

  const recentActivities = [
    {
      type: "import",
      title: "Data imported: Actual_Cost_Oct_2024.xlsx",
      author: "by Budi Santoso",
      time: "2 minutes ago",
      icon: FileCheck,
      iconColor: "text-blue-600 bg-blue-50",
    },
    {
      type: "resolved",
      title: "Finding resolved: PO Exposure exceeds Budget - WBS 15",
      author: "by Rina Amelia",
      time: "1 hour ago",
      icon: CheckCircle2,
      iconColor: "text-emerald-600 bg-emerald-50",
    },
    {
      type: "report",
      title: "Report generated: Monthly_Project_Control_Oct_2024.pdf",
      author: "by Eko Prasetyo",
      time: "3 hours ago",
      icon: FileText,
      iconColor: "text-purple-600 bg-purple-50",
    },
  ]

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-12">
      {/* Top Section: Health & KPI Summary */}
      <div className="space-y-3">
        <div className="grid grid-cols-1 md:grid-cols-12 gap-4">
          {/* Health Gauge Box */}
          <div className="md:col-span-3">
            <HealthGauge
              score={healthData?.overall_score ?? 68}
              label={healthData?.status_label ?? "MODERATE"}
              lastUpdated="Last update: 2 minutes ago"
              size={150}
              className="h-full"
            />
          </div>

          {/* Metric Summary Cards */}
          <div className="md:col-span-9 grid grid-cols-2 lg:grid-cols-4 gap-4">
            <MetricCard
              title="CRITICAL"
              value={healthData?.critical_findings_count ?? 17}
              delta={{ label: "vs last month", value: 4, isPositive: false }}
              variant="critical"
            />
            <MetricCard
              title="WARNING"
              value={healthData?.warning_findings_count ?? 23}
              delta={{ label: "vs last month", value: 5, isPositive: false }}
              variant="warning"
            />
            <MetricCard
              title="OBSERVATION"
              value={healthData?.observation_findings_count ?? 12}
              delta={{ label: "vs last month", value: 2, isPositive: true }}
              variant="observation"
            />
            <MetricCard
              title="DATA QUALITY"
              value={`${healthData?.data_quality_score ?? 92}`}
              delta={{ label: "vs last month", value: 3, isPositive: true }}
              variant="success"
            />
          </div>
        </div>

        {/* Domain Health Score Strip */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          <DomainHealthBar
            title="COST HEALTH"
            score={healthData?.cost_score ?? 58}
            weight="30%"
            icon="cost"
            onClick={() => navigate("/cost")}
          />
          <DomainHealthBar
            title="SCHEDULE HEALTH"
            score={healthData?.schedule_score ?? 71}
            weight="30%"
            icon="schedule"
            onClick={() => navigate("/schedule")}
          />
          <DomainHealthBar
            title="PROGRESS HEALTH"
            score={healthData?.progress_score ?? 67}
            weight="25%"
            icon="progress"
            onClick={() => navigate("/progress")}
          />
          <DomainHealthBar
            title="DATA QUALITY"
            score={healthData?.data_quality_score ?? 92}
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
                  Rp 245.00 B
                </span>
              </div>
              <div className="flex items-center justify-between py-1.5 border-b border-slate-100">
                <span className="text-xs font-medium text-slate-600 flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-purple-600" />
                  Actual (AC)
                </span>
                <span className="text-xs font-bold text-slate-900 tabular-nums">
                  Rp 187.40 B
                </span>
              </div>
              <div className="flex items-center justify-between py-1.5 border-b border-slate-100">
                <span className="text-xs font-medium text-slate-600 flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-amber-500" />
                  Commitment (PO)
                </span>
                <span className="text-xs font-bold text-slate-900 tabular-nums">
                  Rp 72.30 B
                </span>
              </div>
              <div className="flex items-center justify-between py-1.5">
                <span className="text-xs font-medium text-slate-600 flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-red-500" />
                  Estimate at Completion (EAC)
                </span>
                <span className="text-xs font-bold text-slate-900 tabular-nums">
                  Rp 268.60 B
                </span>
              </div>
            </div>
          </div>

          {/* Bottom KPI Triad */}
          <div className="grid grid-cols-3 gap-2 pt-4 mt-4 border-t border-slate-100 text-center">
            <div className="p-2 bg-slate-50 rounded-lg">
              <div className="text-[10px] uppercase font-bold text-slate-500">CPI</div>
              <div className="text-sm font-bold text-slate-900 tabular-nums mt-0.5">0.92</div>
            </div>
            <div className="p-2 bg-red-50/50 rounded-lg">
              <div className="text-[10px] uppercase font-bold text-red-600">CV</div>
              <div className="text-xs font-bold text-red-600 tabular-nums mt-0.5">-Rp 20.9 B</div>
            </div>
            <div className="p-2 bg-amber-50/50 rounded-lg">
              <div className="text-[10px] uppercase font-bold text-amber-700">EAC VAR</div>
              <div className="text-xs font-bold text-amber-700 tabular-nums mt-0.5">+ Rp 23.6 B</div>
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
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={COST_TREND_DATA} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
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
            </ResponsiveContainer>
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
              <BarChart data={RISK_TREND_DATA} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
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

            <p className="text-xs leading-relaxed text-slate-700">
              Project cost performance is trending worse than last month due to cost spike in{" "}
              <strong className="text-slate-900 font-semibold">WBS 03.02</strong> and high PO exposure in{" "}
              <strong className="text-slate-900 font-semibold">WBS 11</strong>. Schedule delay on critical activities may impact final completion by{" "}
              <strong className="text-red-600 font-semibold">18 days</strong>.
            </p>
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

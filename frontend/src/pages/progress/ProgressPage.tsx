import React, { useState } from "react"
import {
  TrendingUp,
  TrendingDown,
  Calendar,
  Layers,
  AlertTriangle,
  CheckCircle2,
  Milestone,
  ArrowUpRight,
  ArrowDownRight,
  Sparkles,
} from "lucide-react"
import {
  ResponsiveContainer,
  LineChart,
  Line,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  Legend,
} from "recharts"

const SCURVE_DATA = [
  { month: "Jan 24", planned: 4.2, actual: 4.0, forecast: 4.0 },
  { month: "Feb 24", planned: 11.5, actual: 10.8, forecast: 10.8 },
  { month: "Mar 24", planned: 21.0, actual: 19.5, forecast: 19.5 },
  { month: "Apr 24", planned: 33.2, actual: 30.5, forecast: 30.5 },
  { month: "May 24", planned: 47.0, actual: 42.0, forecast: 42.0 },
  { month: "Jun 24", planned: 60.5, actual: 53.0, forecast: 53.0 },
  { month: "Jul 24", planned: 72.4, actual: 61.8, forecast: 61.8 },
  { month: "Aug 24", planned: 82.0, actual: null, forecast: 69.5 },
  { month: "Sep 24", planned: 89.5, actual: null, forecast: 77.0 },
  { month: "Oct 24", planned: 94.8, actual: null, forecast: 84.5 },
  { month: "Nov 24", planned: 98.2, actual: null, forecast: 91.2 },
  { month: "Dec 24", planned: 100.0, actual: null, forecast: 96.5 },
  { month: "Jan 25", planned: 100.0, actual: null, forecast: 100.0 },
]

const MILESTONES = [
  { name: "Detailed Engineering Freeze", target: "Mar 2024", status: "completed", progress: "100%" },
  { name: "Compressor Long-Lead Procurement", target: "May 2024", status: "delayed", progress: "88%" },
  { name: "Piping Fabrication & Spooling", target: "Jul 2024", status: "in_progress", progress: "64%" },
  { name: "Mechanical Completion & Pressure Test", target: "Oct 2024", status: "pending", progress: "0%" },
  { name: "Commercial Operation Date (COD)", target: "Dec 2024", status: "at_risk", progress: "0%" },
]

export const ProgressPage: React.FC = () => {
  const [chartType, setChartType] = useState<"cumulative" | "monthly">("cumulative")

  const progressList = [
    { wbs: "01", name: "Project Management", plan: 85.0, actual: 82.0, variance: -3.0, weight: "6.0%" },
    { wbs: "02", name: "Detailed Engineering", plan: 98.0, actual: 95.0, variance: -3.0, weight: "14.0%" },
    { wbs: "03", name: "Procurement & Fabrication", plan: 78.0, actual: 64.0, variance: -14.0, weight: "48.0%" },
    { wbs: "04", name: "Civil & Construction", plan: 52.0, actual: 42.0, variance: -10.0, weight: "24.0%" },
    { wbs: "05", name: "Commissioning & Startup", plan: 15.0, actual: 8.0, variance: -7.0, weight: "8.0%" },
  ]

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-12">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-slate-900 tracking-tight">
            Physical Progress & Interactive S-Curve
          </h1>
          <p className="text-xs text-slate-500 mt-0.5">
            Planned Value (PV%) vs Earned Value (EV%) physical milestone verification and forecast slippage
          </p>
        </div>

        <div className="flex items-center gap-2 bg-white p-1 rounded-lg border border-slate-200 text-xs">
          <button
            onClick={() => setChartType("cumulative")}
            className={`px-3 py-1 rounded-md font-semibold transition-colors ${
              chartType === "cumulative"
                ? "bg-blue-600 text-white shadow-xs"
                : "text-slate-600 hover:text-slate-900"
            }`}
          >
            Cumulative S-Curve
          </button>
          <button
            onClick={() => setChartType("monthly")}
            className={`px-3 py-1 rounded-md font-semibold transition-colors ${
              chartType === "monthly"
                ? "bg-blue-600 text-white shadow-xs"
                : "text-slate-600 hover:text-slate-900"
            }`}
          >
            Monthly Increments
          </button>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
          <div className="text-[10px] font-bold text-slate-400 uppercase">Progress Health Score</div>
          <div className="text-2xl font-bold text-amber-600 mt-1">67 / 100</div>
          <div className="text-[11px] text-slate-500 mt-1">Weight 25% in Overall Health</div>
        </div>
        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
          <div className="text-[10px] font-bold text-slate-400 uppercase">Planned Physical Progress</div>
          <div className="text-2xl font-bold text-slate-900 mt-1">72.4%</div>
          <div className="text-[11px] text-slate-500 mt-1">Baseline Milestone Cut-off</div>
        </div>
        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
          <div className="text-[10px] font-bold text-blue-600 uppercase">Actual Earned Progress</div>
          <div className="text-2xl font-bold text-blue-600 mt-1">61.8%</div>
          <div className="text-[11px] text-slate-500 mt-1">Verified Field Measurements</div>
        </div>
        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
          <div className="text-[10px] font-bold text-red-600 uppercase">Overall Progress Lag</div>
          <div className="text-2xl font-bold text-red-600 mt-1">-10.6%</div>
          <div className="text-[11px] text-red-600 font-semibold mt-1">Critical Path Impact (+18d)</div>
        </div>
      </div>

      {/* Main S-Curve Chart Panel */}
      <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-slate-100 pb-3">
          <div>
            <h2 className="text-sm font-bold text-slate-900 flex items-center gap-2">
              <TrendingUp className="w-4 h-4 text-blue-600" />
              <span>Project Cumulative Physical S-Curve (% Progress)</span>
            </h2>
            <p className="text-xs text-slate-500">
              Tracking baseline schedule vs actual achievements and projected completion curve
            </p>
          </div>

          <div className="flex items-center gap-4 text-xs font-semibold">
            <span className="flex items-center gap-1.5 text-slate-600">
              <span className="w-3 h-0.5 bg-slate-400 inline-block border-dashed" /> Planned (PV%)
            </span>
            <span className="flex items-center gap-1.5 text-blue-600">
              <span className="w-3 h-1 bg-blue-600 inline-block rounded" /> Actual (EV%)
            </span>
            <span className="flex items-center gap-1.5 text-amber-600">
              <span className="w-3 h-0.5 bg-amber-500 inline-block border-dashed" /> Forecast (EAC%)
            </span>
          </div>
        </div>

        {/* Recharts S-Curve Visualizer */}
        <div className="h-80 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={SCURVE_DATA} margin={{ top: 10, right: 20, left: -10, bottom: 0 }}>
              <defs>
                <linearGradient id="actualGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#1769E8" stopOpacity={0.25} />
                  <stop offset="95%" stopColor="#1769E8" stopOpacity={0.0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#F1F5F9" />
              <XAxis dataKey="month" tick={{ fontSize: 11, fill: "#64748B" }} axisLine={false} tickLine={false} />
              <YAxis
                domain={[0, 100]}
                unit="%"
                tick={{ fontSize: 11, fill: "#64748B" }}
                axisLine={false}
                tickLine={false}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: "#07192D",
                  borderRadius: "8px",
                  color: "#fff",
                  fontSize: "11px",
                  border: "none",
                }}
                formatter={(value: any) => [`${value}%`]}
              />
              <Line
                type="monotone"
                dataKey="planned"
                name="Planned (PV%)"
                stroke="#94A3B8"
                strokeWidth={2}
                strokeDasharray="4 4"
                dot={false}
              />
              <Area
                type="monotone"
                dataKey="actual"
                name="Actual (EV%)"
                stroke="#1769E8"
                strokeWidth={3}
                fillOpacity={1}
                fill="url(#actualGradient)"
                dot={{ r: 4, fill: "#1769E8" }}
              />
              <Line
                type="monotone"
                dataKey="forecast"
                name="Forecast (EAC%)"
                stroke="#F59E0B"
                strokeWidth={2}
                strokeDasharray="3 3"
                dot={false}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>

        <div className="p-3 bg-amber-50 text-amber-900 border border-amber-200 rounded-lg text-xs flex items-center justify-between">
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0" />
            <span>
              <strong>Forecast Anomaly Alert:</strong> Actual progress curve diverges from planned baseline at Month 5 (May 2024) primarily due to Procurement lag in WBS 03. Projected COD slips from Dec 2024 to Jan 2025.
            </span>
          </div>
        </div>
      </div>

      {/* Bottom Grid: Milestones & WBS Breakdown */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Milestone Timeline */}
        <div className="lg:col-span-4 bg-white p-5 rounded-xl border border-slate-200 shadow-sm space-y-4">
          <div className="flex items-center gap-2">
            <Milestone className="w-4 h-4 text-blue-600" />
            <h2 className="text-xs font-bold uppercase tracking-wider text-slate-700">
              Key Project Milestones
            </h2>
          </div>

          <div className="space-y-3">
            {MILESTONES.map((m, idx) => (
              <div key={idx} className="p-3 rounded-lg border border-slate-100 bg-slate-50/60 space-y-1.5">
                <div className="flex items-center justify-between text-xs">
                  <span className="font-semibold text-slate-900">{m.name}</span>
                  <span
                    className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase ${
                      m.status === "completed"
                        ? "bg-emerald-50 text-emerald-700"
                        : m.status === "delayed"
                        ? "bg-red-50 text-red-700"
                        : m.status === "at_risk"
                        ? "bg-amber-50 text-amber-700"
                        : "bg-slate-100 text-slate-600"
                    }`}
                  >
                    {m.status.replace("_", " ")}
                  </span>
                </div>
                <div className="flex items-center justify-between text-[11px] text-slate-500">
                  <span>Target: {m.target}</span>
                  <span className="font-mono font-bold text-slate-700">{m.progress}</span>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* WBS Physical Progress Table */}
        <div className="lg:col-span-8 bg-white p-5 rounded-xl border border-slate-200 shadow-sm space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-xs font-bold uppercase tracking-wider text-slate-700">
              WBS Physical Progress Matrix
            </h2>
            <span className="text-xs text-slate-500">Weighted Progress Calculation</span>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-xs text-left border-collapse">
              <thead>
                <tr className="bg-slate-50 text-[11px] font-semibold text-slate-500 uppercase border-b border-slate-200">
                  <th className="py-3 px-4">WBS</th>
                  <th className="py-3 px-4">Package Name</th>
                  <th className="py-3 px-4 text-right">Weight</th>
                  <th className="py-3 px-4 text-right">Planned %</th>
                  <th className="py-3 px-4 text-right">Actual %</th>
                  <th className="py-3 px-4 text-right">Variance</th>
                  <th className="py-3 px-4">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 font-medium">
                {progressList.map((row) => (
                  <tr key={row.wbs} className="hover:bg-slate-50">
                    <td className="py-3 px-4 font-mono font-bold text-blue-600">{row.wbs}</td>
                    <td className="py-3 px-4 font-semibold text-slate-900">{row.name}</td>
                    <td className="py-3 px-4 text-right font-mono text-slate-600">{row.weight}</td>
                    <td className="py-3 px-4 text-right font-mono text-slate-600">{row.plan.toFixed(1)}%</td>
                    <td className="py-3 px-4 text-right font-mono font-bold text-slate-900">{row.actual.toFixed(1)}%</td>
                    <td className="py-3 px-4 text-right font-mono font-bold text-red-600">
                      {row.variance.toFixed(1)}%
                    </td>
                    <td className="py-3 px-4">
                      <span
                        className={`px-2 py-0.5 rounded text-[11px] font-bold ${
                          row.variance <= -10
                            ? "bg-red-50 text-red-700"
                            : row.variance < 0
                            ? "bg-amber-50 text-amber-700"
                            : "bg-emerald-50 text-emerald-700"
                        }`}
                      >
                        {row.variance <= -10 ? "Severe Lag" : row.variance < 0 ? "Minor Lag" : "On Track"}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  )
}

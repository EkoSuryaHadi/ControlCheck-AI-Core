import React from "react"
import { Calendar, Clock, AlertTriangle, CheckCircle2 } from "lucide-react"

export const SchedulePage: React.FC = () => {
  const delayedActivities = [
    { code: "ACT-1020", name: "Compressor Foundation Concrete Pour", wbs: "03.02.01", delay: "18 days", float: "-12 days", critical: true },
    { code: "ACT-1085", name: "Piping Spool Hydrotesting", wbs: "03.01.04", delay: "14 days", float: "-8 days", critical: true },
    { code: "ACT-2010", name: "Control Room Transformer Cable Pulling", wbs: "11.02.01", delay: "10 days", float: "2 days", critical: false },
    { code: "ACT-3040", name: "Flare Header Tie-In Welding", wbs: "04.02.03", delay: "7 days", float: "0 days", critical: true },
  ]

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-12">
      <div>
        <h1 className="text-xl font-bold text-slate-900 tracking-tight">Schedule Health & Critical Path Risk</h1>
        <p className="text-xs text-slate-500 mt-0.5">
          Activity delays, baseline slippage, negative total float, and critical path analysis
        </p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
          <div className="text-[10px] font-bold text-slate-400 uppercase">Schedule Health</div>
          <div className="text-2xl font-bold text-amber-600 mt-1">71 / 100</div>
        </div>
        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
          <div className="text-[10px] font-bold text-red-600 uppercase">Critical Delay</div>
          <div className="text-2xl font-bold text-red-600 mt-1">18 Days</div>
        </div>
        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
          <div className="text-[10px] font-bold text-red-600 uppercase">Negative Float Items</div>
          <div className="text-2xl font-bold text-red-600 mt-1">5 Activities</div>
        </div>
        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
          <div className="text-[10px] font-bold text-slate-400 uppercase">Target Completion</div>
          <div className="text-2xl font-bold text-slate-900 mt-1">15 Dec 2025</div>
        </div>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="p-4 border-b border-slate-200">
          <h2 className="text-xs font-bold uppercase tracking-wider text-slate-700">Delayed Critical Activities</h2>
        </div>
        <table className="w-full text-xs text-left border-collapse">
          <thead>
            <tr className="bg-slate-50 text-[11px] font-semibold text-slate-500 uppercase border-b border-slate-200">
              <th className="py-3 px-4">Activity ID</th>
              <th className="py-3 px-4">Activity Name</th>
              <th className="py-3 px-4">WBS</th>
              <th className="py-3 px-4 text-right">Delay</th>
              <th className="py-3 px-4 text-right">Total Float</th>
              <th className="py-3 px-4">Critical Path</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 font-medium">
            {delayedActivities.map((act) => (
              <tr key={act.code} className="hover:bg-slate-50">
                <td className="py-3 px-4 font-mono font-bold text-blue-600">{act.code}</td>
                <td className="py-3 px-4 font-semibold text-slate-900">{act.name}</td>
                <td className="py-3 px-4 font-mono text-slate-600">{act.wbs}</td>
                <td className="py-3 px-4 text-right font-bold text-red-600">{act.delay}</td>
                <td className="py-3 px-4 text-right font-mono font-bold text-red-600">{act.float}</td>
                <td className="py-3 px-4">
                  <span className={`px-2 py-0.5 rounded text-[11px] font-bold ${act.critical ? "bg-red-50 text-red-700" : "bg-slate-100 text-slate-600"}`}>
                    {act.critical ? "Critical" : "Near-Critical"}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

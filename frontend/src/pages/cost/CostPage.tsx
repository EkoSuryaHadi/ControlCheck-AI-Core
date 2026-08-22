import React from "react"
import { DollarSign, TrendingDown, ArrowUpRight, ArrowDownRight, Layers } from "lucide-react"
import { formatCurrency } from "@/lib/utils"

export const CostPage: React.FC = () => {
  const costBreakdown = [
    { wbs: "01", name: "Project Management", bac: "Rp 15.00 B", ac: "Rp 12.40 B", cv: "+Rp 2.60 B", cpi: 1.05 },
    { wbs: "02", name: "Detailed Engineering", bac: "Rp 35.00 B", ac: "Rp 34.20 B", cv: "+Rp 0.80 B", cpi: 1.02 },
    { wbs: "03", name: "Procurement & Fabrication", bac: "Rp 120.00 B", ac: "Rp 138.40 B", cv: "-Rp 18.40 B", cpi: 0.86 },
    { wbs: "04", name: "Civil & Construction", bac: "Rp 55.00 B", ac: "Rp 59.80 B", cv: "-Rp 4.80 B", cpi: 0.91 },
    { wbs: "05", name: "Commissioning & Startup", bac: "Rp 20.00 B", ac: "Rp 3.60 B", cv: "+Rp 0.00 B", cpi: 1.00 },
  ]

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-12">
      <div>
        <h1 className="text-xl font-bold text-slate-900 tracking-tight">Cost Performance Analysis</h1>
        <p className="text-xs text-slate-500 mt-0.5">
          Budget at Completion (BAC), Actual Cost (AC), Commitments and Cost Variance breakdown
        </p>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
          <div className="text-[10px] font-bold text-slate-400 uppercase">Budget (BAC)</div>
          <div className="text-2xl font-bold text-slate-900 mt-1">Rp 245.00 B</div>
        </div>
        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
          <div className="text-[10px] font-bold text-slate-400 uppercase">Actual Incurred (AC)</div>
          <div className="text-2xl font-bold text-slate-900 mt-1">Rp 187.40 B</div>
        </div>
        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
          <div className="text-[10px] font-bold text-red-600 uppercase">Cost Variance (CV)</div>
          <div className="text-2xl font-bold text-red-600 mt-1">-Rp 20.90 B</div>
        </div>
        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
          <div className="text-[10px] font-bold text-slate-400 uppercase">Cost Performance Index</div>
          <div className="text-2xl font-bold text-amber-600 mt-1">0.92 CPI</div>
        </div>
      </div>

      {/* WBS Cost Table */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="p-4 border-b border-slate-200 flex items-center justify-between">
          <h2 className="text-xs font-bold uppercase tracking-wider text-slate-700">
            WBS Cost Exposure Breakdown
          </h2>
          <span className="text-xs text-slate-500">5 Level-1 WBS Packages</span>
        </div>
        <table className="w-full text-xs text-left border-collapse">
          <thead>
            <tr className="bg-slate-50 text-[11px] font-semibold text-slate-500 uppercase border-b border-slate-200">
              <th className="py-3 px-4">WBS</th>
              <th className="py-3 px-4">Package Name</th>
              <th className="py-3 px-4 text-right">BAC</th>
              <th className="py-3 px-4 text-right">AC</th>
              <th className="py-3 px-4 text-right">Variance</th>
              <th className="py-3 px-4 text-right">CPI</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 font-medium">
            {costBreakdown.map((row) => (
              <tr key={row.wbs} className="hover:bg-slate-50">
                <td className="py-3 px-4 font-mono font-bold text-blue-600">{row.wbs}</td>
                <td className="py-3 px-4 font-semibold text-slate-900">{row.name}</td>
                <td className="py-3 px-4 text-right font-mono text-slate-700">{row.bac}</td>
                <td className="py-3 px-4 text-right font-mono font-bold text-slate-900">{row.ac}</td>
                <td className={`py-3 px-4 text-right font-mono font-bold ${row.cv.startsWith("-") ? "text-red-600" : "text-emerald-600"}`}>
                  {row.cv}
                </td>
                <td className="py-3 px-4 text-right font-bold tabular-nums">
                  <span className={`px-2 py-0.5 rounded ${row.cpi < 1.0 ? "bg-red-50 text-red-700" : "bg-emerald-50 text-emerald-700"}`}>
                    {row.cpi.toFixed(2)}
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

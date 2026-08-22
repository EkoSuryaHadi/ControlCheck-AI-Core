import React from "react"
import { Sliders, Shield, Users, Database, Key } from "lucide-react"

export const SettingsPage: React.FC = () => {
  return (
    <div className="space-y-6 max-w-5xl mx-auto pb-12">
      <div>
        <h1 className="text-xl font-bold text-slate-900 tracking-tight">Organization & System Settings</h1>
        <p className="text-xs text-slate-500 mt-0.5">
          Rule thresholds, severity tolerances, user access control, and integration configurations
        </p>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 shadow-sm divide-y divide-slate-100">
        <div className="p-5 flex items-start gap-4">
          <div className="p-2.5 rounded-lg bg-blue-50 text-blue-600">
            <Sliders className="w-5 h-5" />
          </div>
          <div className="flex-1">
            <h2 className="text-sm font-bold text-slate-900">Deterministic Control Rule Thresholds</h2>
            <p className="text-xs text-slate-500 mt-0.5">
              Configure cost variance tolerances (Warning: 10%, Critical: 20%) and negative float limits.
            </p>
          </div>
          <button className="px-3 py-1.5 border border-slate-200 rounded-lg text-xs font-semibold hover:bg-slate-50">
            Edit Thresholds
          </button>
        </div>

        <div className="p-5 flex items-start gap-4">
          <div className="p-2.5 rounded-lg bg-purple-50 text-purple-600">
            <Shield className="w-5 h-5" />
          </div>
          <div className="flex-1">
            <h2 className="text-sm font-bold text-slate-900">Health Scoring Weights (PRD §13 Formula)</h2>
            <p className="text-xs text-slate-500 mt-0.5">
              Cost: 30% | Schedule: 30% | Progress: 25% | Data Quality: 15%
            </p>
          </div>
          <button className="px-3 py-1.5 border border-slate-200 rounded-lg text-xs font-semibold hover:bg-slate-50">
            Configure Weights
          </button>
        </div>

        <div className="p-5 flex items-start gap-4">
          <div className="p-2.5 rounded-lg bg-emerald-50 text-emerald-600">
            <Users className="w-5 h-5" />
          </div>
          <div className="flex-1">
            <h2 className="text-sm font-bold text-slate-900">User Access & Role-Based Access Control (RBAC)</h2>
            <p className="text-xs text-slate-500 mt-0.5">
              Manage organization admins, project managers, and project viewers.
            </p>
          </div>
          <button className="px-3 py-1.5 border border-slate-200 rounded-lg text-xs font-semibold hover:bg-slate-50">
            Manage Users
          </button>
        </div>
      </div>
    </div>
  )
}

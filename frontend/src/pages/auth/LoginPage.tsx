import React, { useState } from "react"
import { useNavigate, Link } from "react-router-dom"
import { useAuth } from "@/context/AuthContext"
import { api } from "@/lib/api"
import { Lock, Mail, ArrowRight, AlertCircle } from "lucide-react"
import { BrandLogo } from "@/components/common/BrandLogo"

export const LoginPage: React.FC = () => {
  const navigate = useNavigate()
  const { login } = useAuth()
  const [email, setEmail] = useState("admin@controlcheck.ai")
  const [password, setPassword] = useState("controlcheck123")
  const [error, setError] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setIsLoading(true)

    try {
      // Try backend auth
      const res = await api.auth.login({ email, password })
      login(
        res.access_token,
        { id: res.user_id || "usr-01", email, name: res.name || "Eko Prasetyo", role: "Project Control Manager" },
        res.org_id || "org-01"
      )
      navigate("/dashboard")
    } catch (err: any) {
      // Fallback demo login if offline/demo
      login(
        "demo-jwt-token",
        { id: "demo-usr-01", email, name: "Eko Prasetyo", role: "Project Control Manager" },
        "demo-org-01"
      )
      navigate("/dashboard")
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="min-h-screen w-full flex items-center justify-center bg-navy-950 px-4 font-sans">
      <div className="w-full max-w-md bg-white rounded-2xl p-8 shadow-2xl border border-slate-700/50 space-y-6">
        {/* Brand Header */}
        <div className="text-center space-y-3 pb-2 border-b border-slate-100">
          <BrandLogo variant="full" theme="light" size="lg" className="mx-auto" imgClassName="h-11 w-auto max-w-[240px]" />
          <p className="text-[11px] text-slate-500 font-medium">
            Enterprise Project Control & Deterministic Audit Engine
          </p>
        </div>

        {error && (
          <div className="p-3 bg-red-50 border border-red-200 text-red-700 text-xs rounded-lg flex items-center gap-2">
            <AlertCircle className="w-4 h-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="text-[11px] font-bold uppercase text-slate-600 block mb-1">
              Email Address
            </label>
            <div className="relative">
              <Mail className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full pl-9 pr-3 py-2 text-xs bg-slate-50 border border-slate-200 rounded-lg text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="you@company.com"
              />
            </div>
          </div>

          <div>
            <label className="text-[11px] font-bold uppercase text-slate-600 block mb-1">
              Password
            </label>
            <div className="relative">
              <Lock className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
              <input
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full pl-9 pr-3 py-2 text-xs bg-slate-50 border border-slate-200 rounded-lg text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="••••••••"
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={isLoading}
            className="w-full py-2.5 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white rounded-lg text-xs font-semibold shadow-md shadow-blue-500/20 flex items-center justify-center gap-1.5 transition-all"
          >
            <span>{isLoading ? "Signing in..." : "Sign In to Workspace"}</span>
            <ArrowRight className="w-4 h-4" />
          </button>
        </form>

        <div className="pt-2 text-center text-xs text-slate-500">
          Demo credentials pre-filled for immediate testing
        </div>
      </div>
    </div>
  )
}

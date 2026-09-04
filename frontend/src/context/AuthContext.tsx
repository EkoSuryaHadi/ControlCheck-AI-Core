import React, { createContext, useContext, useEffect, useState } from "react"
import { apiClient, User } from "@/lib/api"
import { isJwtExpired } from "@/lib/authSession"

interface AuthContextType {
  user: User | null
  token: string | null
  orgId: string | null
  isAuthenticated: boolean
  isLoading: boolean
  login: (token: string, user: User, orgId: string) => void
  logout: () => void
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

const clearStoredSession = () => {
  localStorage.removeItem("controlcheck_token")
  localStorage.removeItem("controlcheck_user")
  localStorage.removeItem("controlcheck_org_id")
  localStorage.removeItem("controlcheck_current_project_id")
}

const loadStoredUser = (): User | null => {
  try {
    const saved = localStorage.getItem("controlcheck_user")
    return saved ? JSON.parse(saved) : null
  } catch {
    return null
  }
}

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [token, setToken] = useState<string | null>(null)
  const [orgId, setOrgId] = useState<string | null>(null)
  const [user, setUser] = useState<User | null>(null)
  // Starts true so protected routes show "Checking session…" while the stored
  // token is validated against the server instead of flashing the dashboard.
  const [isLoading, setIsLoading] = useState(true)

  const logout = () => {
    setToken(null)
    setUser(null)
    setOrgId(null)
    clearStoredSession()
  }

  const login = (newToken: string, newUser: User, newOrgId: string) => {
    if (isJwtExpired(newToken, 0)) throw new Error("Cannot start a session with an expired token.")
    setToken(newToken)
    setUser(newUser)
    setOrgId(newOrgId)
    // Demo workspaces have no server account behind them — keep them in
    // memory only so a reload returns to the login/register gate.
    if (newToken === "demo-jwt-token") {
      clearStoredSession()
      return
    }
    localStorage.setItem("controlcheck_token", newToken)
    localStorage.setItem("controlcheck_user", JSON.stringify(newUser))
    localStorage.setItem("controlcheck_org_id", newOrgId)
  }

  useEffect(() => {
    let cancelled = false

    async function validateStoredSession() {
      const storedToken = localStorage.getItem("controlcheck_token")
      const storedOrg = localStorage.getItem("controlcheck_org_id")
      if (!storedToken || isJwtExpired(storedToken)) {
        clearStoredSession()
        if (!cancelled) setIsLoading(false)
        return
      }
      try {
        // Lightweight authenticated call — 401/403 means the session is not
        // valid on the server (revoked, replaced, or demo leftovers).
        await apiClient.get(`/v1/organizations/${storedOrg}/projects`, {
          params: { limit: 1 },
        })
        if (cancelled) return
        setToken(storedToken)
        setOrgId(storedOrg || null)
        setUser(loadStoredUser())
      } catch (err: any) {
        if (cancelled) return
        const status = err?.response?.status
        if (status === 401 || status === 403) {
          clearStoredSession()
        } else {
          // Network/server hiccup: keep the local session (offline tolerant).
          setToken(storedToken)
          setOrgId(storedOrg || null)
          setUser(loadStoredUser())
        }
      } finally {
        if (!cancelled) setIsLoading(false)
      }
    }

    void validateStoredSession()
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    if (!token) return
    const checkExpiry = () => {
      if (isJwtExpired(token)) logout()
    }
    checkExpiry()
    const timer = window.setInterval(checkExpiry, 30_000)
    return () => window.clearInterval(timer)
  }, [token])

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        orgId,
        isAuthenticated: Boolean(token && user && orgId),
        isLoading,
        login,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}

// eslint-disable-next-line react-refresh/only-export-components
export const useAuth = () => {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider")
  return ctx
}

export default AuthProvider

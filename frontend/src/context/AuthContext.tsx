import React, { createContext, useContext, useState } from "react"
import { User } from "@/lib/api"
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

const loadStoredToken = () => {
  const saved = localStorage.getItem("controlcheck_token")
  if (!saved || isJwtExpired(saved)) {
    if (saved) clearStoredSession()
    return null
  }
  return saved
}

const loadStoredUser = (): User | null => {
  try {
    const saved = localStorage.getItem("controlcheck_user")
    return saved ? JSON.parse(saved) : null
  } catch {
    clearStoredSession()
    return null
  }
}

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [token, setToken] = useState<string | null>(() => loadStoredToken())
  const [orgId, setOrgId] = useState<string | null>(() => token ? localStorage.getItem("controlcheck_org_id") : null)
  const [user, setUser] = useState<User | null>(() => token ? loadStoredUser() : null)
  const isLoading = false

  const login = (newToken: string, newUser: User, newOrgId: string) => {
    if (isJwtExpired(newToken, 0)) throw new Error("Cannot start a session with an expired token.")
    setToken(newToken)
    setUser(newUser)
    setOrgId(newOrgId)
    localStorage.setItem("controlcheck_token", newToken)
    localStorage.setItem("controlcheck_user", JSON.stringify(newUser))
    localStorage.setItem("controlcheck_org_id", newOrgId)
  }

  const logout = () => {
    setToken(null)
    setUser(null)
    setOrgId(null)
    clearStoredSession()
  }

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

export const useAuth = () => {
  const context = useContext(AuthContext)
  if (!context) throw new Error("useAuth must be used within an AuthProvider")
  return context
}

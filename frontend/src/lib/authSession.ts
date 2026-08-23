export interface AuthIdentity {
  accessToken: string
  userId: string
  email: string
  fullName: string
  orgId: string
  role: string
}

const decodeJwtPayload = (token: string): Record<string, any> => {
  const parts = token.split(".")
  if (parts.length !== 3) return {}
  try {
    const base64 = parts[1].replace(/-/g, "+").replace(/_/g, "/")
    const padded = base64.padEnd(Math.ceil(base64.length / 4) * 4, "=")
    return JSON.parse(decodeURIComponent(Array.from(atob(padded)).map((char) => `%${char.charCodeAt(0).toString(16).padStart(2, "0")}`).join("")))
  } catch {
    return {}
  }
}

export const normalizeAuthResponse = (
  response: any,
  fallback: { email: string; fullName?: string }
): AuthIdentity => {
  const accessToken = response?.access_token
  if (!accessToken) throw new Error("Authentication response did not include an access token.")

  const claims = decodeJwtPayload(accessToken)
  const orgId = String(response?.org_id || claims.org_id || "")
  const userId = String(response?.user_id || claims.sub || "")
  const email = String(response?.email || claims.email || fallback.email || "")
  const fullName = String(response?.full_name || response?.name || fallback.fullName || email)
  const role = String(response?.role || claims.role || "org_member")

  if (!orgId) throw new Error("No workspace organization was returned for this account.")
  if (!userId) throw new Error("No user identity was returned for this account.")

  return { accessToken, userId, email, fullName, orgId, role }
}

export const DEMO_ACCESS_TOKEN = "demo-jwt-token"

export const isDemoAccessToken = (token) => token === DEMO_ACCESS_TOKEN

export const isPersistentWorkspaceSession = (token) =>
  Boolean(token) && !isDemoAccessToken(token)

export function resolveApiBaseUrl(viteApiBaseUrl) {
  // API paths in the codebase already start with /v1/..., so the base is
  // just the origin — empty string means same origin as the SPA.
  return viteApiBaseUrl || ""
}

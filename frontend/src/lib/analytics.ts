type AnalyticsParams = Record<string, string | number | boolean | undefined>

declare global {
  interface Window {
    gtag?: (...args: any[]) => void
  }
}

export const trackEvent = (eventName: string, params: AnalyticsParams = {}) => {
  if (typeof window === "undefined") return

  if (typeof window.gtag === "function") {
    window.gtag("event", eventName, params)
  }

  const existing = JSON.parse(localStorage.getItem("controlcheck_analytics_events") || "[]")
  existing.push({ event: eventName, params, at: new Date().toISOString() })
  localStorage.setItem("controlcheck_analytics_events", JSON.stringify(existing.slice(-100)))
}

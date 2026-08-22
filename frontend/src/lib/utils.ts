import { type ClassValue, clsx } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function formatCurrency(amount: number | null | undefined, currency: string = "IDR", compact: boolean = true): string {
  if (amount === null || amount === undefined || isNaN(amount)) return "—"
  
  if (compact) {
    const abs = Math.abs(amount)
    const sign = amount < 0 ? "-" : ""
    if (abs >= 1_000_000_000_000) {
      return `${sign}Rp ${(abs / 1_000_000_000_000).toFixed(2)} T`
    }
    if (abs >= 1_000_000_000) {
      return `${sign}Rp ${(abs / 1_000_000_000).toFixed(2)} B`
    }
    if (abs >= 1_000_000) {
      return `${sign}Rp ${(abs / 1_000_000).toFixed(2)} M`
    }
    if (abs >= 1_000) {
      return `${sign}Rp ${(abs / 1_000).toFixed(1)} K`
    }
    return `${sign}Rp ${abs.toLocaleString("id-ID")}`
  }

  return new Intl.NumberFormat("id-ID", {
    style: "currency",
    currency: currency,
    maximumFractionDigits: 0,
  }).format(amount)
}

export function formatNumber(num: number | null | undefined, decimals: number = 2): string {
  if (num === null || num === undefined || isNaN(num)) return "—"
  return num.toLocaleString("en-US", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  })
}

export function formatPercent(val: number | null | undefined, includeSign: boolean = false): string {
  if (val === null || val === undefined || isNaN(val)) return "—"
  const formatted = `${val.toFixed(1)}%`
  if (includeSign && val > 0) return `+${formatted}`
  return formatted
}

export function formatDate(dateStr: string | null | undefined): string {
  if (!dateStr) return "—"
  try {
    const d = new Date(dateStr)
    return d.toLocaleDateString("en-GB", {
      day: "2-digit",
      month: "short",
      year: "numeric",
    })
  } catch {
    return dateStr
  }
}

import type { Stance, Verdict } from '../types'

export function initials(name: string): string {
  const parts = name.trim().split(/\s+/)
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase()
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase()
}

export function pct(value: number): string {
  return `${Math.round(value * 100)}%`
}

export function money(value: number | null): string | null {
  if (value == null) return null
  return value.toLocaleString(undefined, { style: 'currency', currency: 'USD' })
}

interface StanceStyle {
  label: string
  text: string
  border: string
  soft: string
  dot: string
}

export function stanceStyle(stance: Stance): StanceStyle {
  switch (stance) {
    case 'bullish':
      return { label: 'Bullish', text: 'text-bull', border: 'border-bull/30', soft: 'bg-bull-soft', dot: 'bg-bull' }
    case 'bearish':
      return { label: 'Bearish', text: 'text-bear', border: 'border-bear/30', soft: 'bg-bear-soft', dot: 'bg-bear' }
    default:
      return { label: 'Neutral', text: 'text-flat', border: 'border-flat/30', soft: 'bg-flat-soft', dot: 'bg-flat' }
  }
}

export function verdictStyle(verdict: Verdict): { text: string; soft: string; border: string } {
  switch (verdict) {
    case 'BUY':
      return { text: 'text-bull', soft: 'bg-bull-soft', border: 'border-bull/40' }
    case 'SELL':
      return { text: 'text-bear', soft: 'bg-bear-soft', border: 'border-bear/40' }
    default:
      return { text: 'text-flat', soft: 'bg-flat-soft', border: 'border-flat/40' }
  }
}

// The indicators worth surfacing in the brief, with display labels.
export const FEATURED_INDICATORS: [string, string][] = [
  ['price', 'Price'],
  ['rsi14', 'RSI(14)'],
  ['adx14', 'ADX(14)'],
  ['hurst', 'Hurst'],
  ['zscore50', 'Z-score'],
  ['hist_vol21', 'Volatility'],
]

export function formatIndicator(key: string, value: number | null): string {
  if (value == null) return 'n/a'
  if (key === 'hist_vol21') return pct(value)
  if (key === 'price') return value.toLocaleString(undefined, { maximumFractionDigits: 2 })
  return value.toFixed(2)
}

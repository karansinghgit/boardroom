import type { ReactNode } from 'react'
import { stanceStyle } from '../../lib/ui'
import type { Stance } from '../../types'

export function StanceTag({ stance }: { stance: Stance }) {
  const s = stanceStyle(stance)
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border ${s.border} ${s.soft} px-2.5 py-0.5 text-xs font-medium tracking-wide ${s.text}`}
    >
      <span className={`h-1.5 w-1.5 rounded-full ${s.dot}`} />
      {s.label}
    </span>
  )
}

export function SectionLabel({ children }: { children: ReactNode }) {
  return (
    <div className="mb-4">
      <span className="text-[11px] font-semibold uppercase tracking-[0.18em] text-ink-faint">
        {children}
      </span>
      <div className="rule mt-2" />
    </div>
  )
}

export function Card({ children, className = '' }: { children: ReactNode; className?: string }) {
  return (
    <div
      className={`rounded-[var(--radius-card)] border border-line bg-paper-raised/80 backdrop-blur-sm shadow-[0_1px_2px_rgba(28,26,23,0.04),0_12px_30px_-18px_rgba(28,26,23,0.18)] ${className}`}
    >
      {children}
    </div>
  )
}

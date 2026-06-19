import { motion } from 'framer-motion'
import { initials, pct, stanceStyle } from '../lib/ui'
import type { InvestorVerdict } from '../types'
import { Card, StanceTag } from './primitives'

export function InvestorCard({ verdict, index }: { verdict: InvestorVerdict; index: number }) {
  const s = stanceStyle(verdict.stance)

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.45, ease: 'easeOut', delay: index * 0.08 }}
    >
      <Card className="flex h-full flex-col p-6">
        <div className="flex items-start gap-3.5">
          <div
            className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-full ${s.soft} ${s.text} font-display text-sm font-semibold ring-1 ring-inset ${s.border}`}
          >
            {initials(verdict.investor)}
          </div>
          <div className="min-w-0 flex-1">
            <h3 className="font-display text-[17px] font-medium leading-tight text-ink">
              {verdict.investor}
            </h3>
            <div className="mt-1.5 flex items-center gap-2">
              <StanceTag stance={verdict.stance} />
              <span className="text-xs text-ink-faint">conviction {pct(verdict.conviction)}</span>
            </div>
          </div>
        </div>

        <p className="mt-4 text-[14px] leading-relaxed text-ink-soft">{verdict.thesis}</p>

        {verdict.key_points.length > 0 && (
          <ul className="mt-3 space-y-1">
            {verdict.key_points.map((p) => (
              <li key={p} className="flex gap-2 text-[13px] leading-snug text-ink-soft">
                <span className={`mt-[3px] ${s.text}`}>&bull;</span>
                <span>{p}</span>
              </li>
            ))}
          </ul>
        )}

        {verdict.rebuttal && (
          <div className="mt-auto pt-4">
            <div className="border-t border-line pt-3 text-[13px] italic leading-relaxed text-ink-faint">
              {verdict.rebuttal}
            </div>
          </div>
        )}
      </Card>
    </motion.div>
  )
}

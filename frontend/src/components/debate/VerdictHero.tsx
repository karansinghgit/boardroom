import { motion } from 'framer-motion'
import { money, pct, verdictStyle } from '../../lib/ui'
import type { BoardroomResult } from '../../types'
import { Card } from '../ui/primitives'

export function VerdictHero({ result }: { result: BoardroomResult }) {
  const v = result.verdict
  const style = verdictStyle(v.verdict)
  const name = result.company_name || result.ticker
  const price = money(result.brief.price)

  return (
    <Card className="overflow-hidden">
      <div className="px-7 pt-7 pb-6 sm:px-9">
        <div className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-1">
          <h1 className="font-display text-3xl font-semibold leading-tight text-ink sm:text-4xl">
            {name}
          </h1>
          <div className="flex items-baseline gap-3 text-ink-soft">
            <span className="rounded-md bg-panel px-2 py-0.5 font-mono text-sm tracking-wide">
              {result.ticker}
            </span>
            {price && <span className="font-medium text-ink">{price}</span>}
          </div>
        </div>

        <div className="mt-6 flex items-center gap-5">
          <motion.div
            initial={{ scale: 0.9, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            transition={{ type: 'spring', stiffness: 240, damping: 20, delay: 0.1 }}
            className={`flex items-baseline gap-3 rounded-2xl border ${style.border} ${style.soft} px-5 py-3`}
          >
            <span className={`font-display text-4xl font-semibold ${style.text}`}>{v.verdict}</span>
          </motion.div>
          <div className="min-w-[120px] flex-1">
            <div className="flex items-center justify-between text-xs text-ink-faint">
              <span className="uppercase tracking-[0.15em]">Confidence</span>
              <span className="font-medium text-ink-soft">{pct(v.confidence)}</span>
            </div>
            <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-panel">
              <motion.div
                initial={{ width: 0 }}
                animate={{ width: pct(v.confidence) }}
                transition={{ duration: 0.7, ease: 'easeOut', delay: 0.25 }}
                className={`h-full rounded-full ${style.text.replace('text-', 'bg-')}`}
              />
            </div>
          </div>
        </div>

        <p className="mt-6 max-w-2xl text-[15px] leading-relaxed text-ink-soft">{v.rationale}</p>

        {v.decisive_factors.length > 0 && (
          <div className="mt-5 flex flex-wrap gap-2">
            {v.decisive_factors.map((f) => (
              <span
                key={f}
                className="rounded-full border border-line bg-paper px-3 py-1 text-xs text-ink-soft"
              >
                {f}
              </span>
            ))}
          </div>
        )}
      </div>

      <div className="border-t border-line bg-panel/50 px-7 py-4 sm:px-9">
        <p className="text-sm leading-relaxed text-ink-soft">
          <span className="font-medium text-ink">Strongest dissent.</span> {v.dissent}
        </p>
      </div>
    </Card>
  )
}

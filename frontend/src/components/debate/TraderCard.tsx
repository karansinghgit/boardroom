import { pct, verdictStyle } from '../../lib/ui'
import type { TraderPlan } from '../../types'
import { Card, SectionLabel } from '../ui/primitives'

export function TraderCard({ trader }: { trader: TraderPlan }) {
  const style = verdictStyle(trader.action)
  return (
    <section>
      <SectionLabel>The Trader&rsquo;s Proposal</SectionLabel>
      <Card className="p-7 sm:p-8">
        <div className="flex flex-wrap items-baseline gap-x-4 gap-y-1">
          <span className={`font-display text-2xl font-semibold ${style.text}`}>
            {trader.action}
          </span>
          <span className="text-sm text-ink-faint">conviction {pct(trader.conviction)}</span>
          <span className="text-sm text-ink-faint">&middot; {trader.time_horizon}</span>
        </div>
        <p className="mt-4 text-[15px] leading-relaxed text-ink-soft">{trader.thesis}</p>
      </Card>
    </section>
  )
}

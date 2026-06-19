import type { RiskReview } from '../../types'
import { Card, SectionLabel } from '../ui/primitives'

const SIZE_LABEL: Record<RiskReview['suggested_position_size'], string> = {
  none: 'No position',
  small: 'Small',
  medium: 'Medium',
  full: 'Full',
}

export function Risk({ risk }: { risk: RiskReview }) {
  return (
    <section>
      <SectionLabel>Risk Team</SectionLabel>
      <Card className="p-7 sm:p-8">
        <div className="flex flex-col gap-6 sm:flex-row sm:items-start sm:justify-between">
          <p className="max-w-xl text-[15px] leading-relaxed text-ink-soft">{risk.summary}</p>
          <div className="shrink-0 rounded-xl border border-line bg-panel/60 px-5 py-3 text-center">
            <div className="text-[11px] uppercase tracking-[0.14em] text-ink-faint">
              Suggested size
            </div>
            <div className="mt-1 font-display text-xl font-medium text-ink">
              {SIZE_LABEL[risk.suggested_position_size]}
            </div>
          </div>
        </div>

        {risk.key_risks.length > 0 && (
          <div className="mt-6 flex flex-wrap gap-2">
            {risk.key_risks.map((r) => (
              <span
                key={r}
                className="rounded-full border border-bear/20 bg-bear-soft px-3 py-1 text-[13px] text-bear"
              >
                {r}
              </span>
            ))}
          </div>
        )}

        {risk.perspectives.length > 0 && (
          <div className="mt-6 grid gap-3 sm:grid-cols-3">
            {risk.perspectives.map((p) => (
              <div key={p.stance} className="rounded-xl border border-line bg-paper p-4">
                <div className="flex items-center justify-between">
                  <span className="text-[11px] font-semibold uppercase tracking-[0.12em] text-ink-faint">
                    {p.stance}
                  </span>
                  <span className="text-xs text-ink-soft">
                    {SIZE_LABEL[p.suggested_position_size]}
                  </span>
                </div>
                <p className="mt-2 text-[13px] leading-snug text-ink-soft">{p.argument}</p>
              </div>
            ))}
          </div>
        )}

        <p className="mt-5 text-[13px] text-ink-faint">{risk.confidence_adjustment}</p>
      </Card>
    </section>
  )
}

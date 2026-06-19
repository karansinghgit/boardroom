import { FEATURED_INDICATORS, formatIndicator } from '../../lib/ui'
import type { ResearchBrief } from '../../types'
import { Card, SectionLabel, StanceTag } from '../ui/primitives'

function AnalystColumn({
  title,
  stance,
  summary,
  positives,
  negatives,
  posLabel,
  negLabel,
}: {
  title: string
  stance: ResearchBrief['fundamentals']['stance']
  summary: string
  positives: string[]
  negatives: string[]
  posLabel: string
  negLabel: string
}) {
  return (
    <div className="flex-1">
      <div className="flex items-center justify-between">
        <h3 className="font-display text-lg font-medium text-ink">{title}</h3>
        <StanceTag stance={stance} />
      </div>
      <p className="mt-3 text-sm leading-relaxed text-ink-soft">{summary}</p>
      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        <PointList label={posLabel} items={positives} tone="text-bull" />
        <PointList label={negLabel} items={negatives} tone="text-bear" />
      </div>
    </div>
  )
}

function PointList({ label, items, tone }: { label: string; items: string[]; tone: string }) {
  if (items.length === 0) return null
  return (
    <div>
      <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-ink-faint">
        {label}
      </div>
      <ul className="mt-1.5 space-y-1">
        {items.map((it) => (
          <li key={it} className="flex gap-2 text-[13px] leading-snug text-ink-soft">
            <span className={`mt-[3px] ${tone}`}>&bull;</span>
            <span>{it}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}

export function Brief({ brief }: { brief: ResearchBrief }) {
  return (
    <section>
      <SectionLabel>The Research Brief</SectionLabel>
      <Card className="p-7 sm:p-8">
        <div className="flex flex-col gap-8 lg:flex-row lg:gap-10">
          <AnalystColumn
            title="Fundamentals"
            stance={brief.fundamentals.stance}
            summary={brief.fundamentals.summary}
            positives={brief.fundamentals.strengths}
            negatives={brief.fundamentals.concerns}
            posLabel="Strengths"
            negLabel="Concerns"
          />
          <div className="hidden w-px self-stretch bg-line lg:block" />
          <AnalystColumn
            title="Quant"
            stance={brief.technicals.stance}
            summary={brief.technicals.summary}
            positives={brief.technicals.notable}
            negatives={[]}
            posLabel="Signals"
            negLabel=""
          />
        </div>

        <div className="mt-7 border-t border-line pt-5">
          <div className="grid grid-cols-3 gap-x-6 gap-y-4 sm:grid-cols-6">
            {FEATURED_INDICATORS.map(([key, label]) => (
              <div key={key}>
                <div className="text-[11px] uppercase tracking-[0.12em] text-ink-faint">{label}</div>
                <div className="mt-1 font-mono text-sm text-ink">
                  {formatIndicator(key, brief.indicator_snapshot[key] ?? null)}
                </div>
              </div>
            ))}
          </div>
        </div>
      </Card>
    </section>
  )
}

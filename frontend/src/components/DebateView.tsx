import { Brief } from './Brief'
import { InvestorCard } from './InvestorCard'
import { Risk } from './Risk'
import { VerdictHero } from './Verdict'
import { SectionLabel } from './primitives'
import type { BoardroomResult } from '../types'

export function DebateView({ result }: { result: BoardroomResult }) {
  return (
    <div className="space-y-12">
      <VerdictHero result={result} />
      <Brief brief={result.brief} />
      <section>
        <SectionLabel>The Debate</SectionLabel>
        <div className="grid gap-5 md:grid-cols-2">
          {result.debate.map((v, i) => (
            <InvestorCard key={v.investor} verdict={v} index={i} />
          ))}
        </div>
      </section>
      <Risk risk={result.risk} />
    </div>
  )
}

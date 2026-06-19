// Mirrors the BoardroomResult schema returned by the API.

export type Stance = 'bullish' | 'neutral' | 'bearish'
export type Verdict = 'BUY' | 'HOLD' | 'SELL'
export type PositionSize = 'none' | 'small' | 'medium' | 'full'

export interface FundamentalRead {
  stance: Stance
  summary: string
  strengths: string[]
  concerns: string[]
}

export interface TechnicalRead {
  stance: Stance
  score: number
  summary: string
  notable: string[]
}

export interface ResearchBrief {
  ticker: string
  company_name: string | null
  price: number | null
  fundamentals: FundamentalRead
  technicals: TechnicalRead
  indicator_snapshot: Record<string, number | null>
  fundamentals_data: Record<string, unknown>
}

export interface InvestorVerdict {
  investor: string
  stance: Stance
  conviction: number
  thesis: string
  key_points: string[]
  rebuttal: string | null
}

export interface RiskReview {
  key_risks: string[]
  suggested_position_size: PositionSize
  confidence_adjustment: string
  summary: string
}

export interface FinalVerdict {
  verdict: Verdict
  confidence: number
  rationale: string
  decisive_factors: string[]
  dissent: string
}

export interface BoardroomResult {
  ticker: string
  company_name: string | null
  as_of: string | null
  brief: ResearchBrief
  debate: InvestorVerdict[]
  risk: RiskReview
  verdict: FinalVerdict
  offline?: boolean
}

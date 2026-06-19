import type { BoardroomResult } from './types'

// A representative result so the page has something to show on first load and
// in Storybook-free local development, before any request is made.
export const sampleResult: BoardroomResult = {
  ticker: 'ACME',
  company_name: 'Acme Corporation',
  as_of: null,
  offline: true,
  brief: {
    ticker: 'ACME',
    company_name: 'Acme Corporation',
    price: 265.45,
    fundamentals: {
      stance: 'neutral',
      summary: 'On the numbers the business looks fairly valued, with a stable operating history and no obvious balance-sheet strain.',
      strengths: ['Stable operating history.', 'No signs of stretched leverage.'],
      concerns: ['Limited visibility on forward estimates.'],
    },
    technicals: {
      stance: 'neutral',
      score: 0.1,
      summary:
        'The blended technical score is 0.10 (neutral). Trend and momentum lean constructive while the volatility regime is unremarkable.',
      notable: ['RSI(14) at 58.7.', 'ADX(14) at 19.6 indicates a soft trend.', 'Hurst exponent 0.39.'],
    },
    indicator_snapshot: {
      price: 265.45,
      ema8: 265.33,
      ema21: 261.66,
      ema55: 252.18,
      adx14: 19.62,
      rsi14: 58.7,
      rsi28: 60.24,
      atr14: 4.96,
      bb_percent_b: 0.61,
      zscore50: 1.35,
      hist_vol21: 0.23,
      hurst: 0.39,
      skew63: 0.3,
      kurtosis63: 0.39,
    },
    fundamentals_data: {},
  },
  debate: [
    {
      investor: 'Warren Buffett',
      stance: 'neutral',
      conviction: 0.4,
      thesis:
        'A decent business at a fair price, but nothing here screams a wide, widening moat at a margin of safety. I would rather wait for a better entry.',
      key_points: ['Quality is adequate, not exceptional.', 'Price offers little margin of safety.'],
      rebuttal: 'Peter Lynch sees growth; I see a fair business fully priced. I hold neutral.',
    },
    {
      investor: 'Peter Lynch',
      stance: 'bullish',
      conviction: 0.65,
      thesis:
        'The story is understandable and the growth looks reasonably priced. This is the kind of steady compounder retail investors overlook.',
      key_points: ['Reasonable growth for the multiple.', 'An understandable, ownable story.'],
      rebuttal: 'Buffett wants a fatter discount; I think the growth pays for the price.',
    },
    {
      investor: 'Michael Burry',
      stance: 'bearish',
      conviction: 0.8,
      thesis:
        'Positioning looks crowded and the tape is masking softening internals. The risk-reward favours the short side here.',
      key_points: ['Crowded positioning.', 'Internals weaker than price implies.'],
      rebuttal: 'The bulls are extrapolating a soft trend; ADX at 19.6 is not conviction.',
    },
    {
      investor: 'Stanley Druckenmiller',
      stance: 'bullish',
      conviction: 0.7,
      thesis:
        'The liquidity backdrop is supportive and momentum is positive. I want to be long asymmetric setups while the regime cooperates.',
      key_points: ['Supportive liquidity regime.', 'Positive momentum tilt.'],
      rebuttal: 'Burry is fighting the tape and the macro at the same time.',
    },
    {
      investor: 'Howard Marks',
      stance: 'neutral',
      conviction: 0.5,
      thesis:
        'Price sits mid-cycle with sentiment neither euphoric nor fearful. There is no obvious margin for error to lean on either way.',
      key_points: ['Mid-cycle pricing.', 'No sentiment edge.'],
      rebuttal: 'Both the bull and bear cases overstate their edge at this price.',
    },
  ],
  trader: {
    action: 'HOLD',
    conviction: 0.5,
    thesis:
      'The bull and bear cases roughly offset. I would wait for either a cheaper entry or a cleaner trend before committing capital.',
    time_horizon: 'watch and revisit',
  },
  risk: {
    perspectives: [
      {
        stance: 'aggressive',
        suggested_position_size: 'medium',
        argument: 'If the trend confirms, the asymmetry justifies sizing up.',
      },
      {
        stance: 'neutral',
        suggested_position_size: 'small',
        argument: 'A measured starter position respects the split in views.',
      },
      {
        stance: 'conservative',
        suggested_position_size: 'none',
        argument: 'With no edge and elevated volatility, patience costs nothing.',
      },
    ],
    key_risks: ['Single-name concentration risk.', 'Annualised volatility around 22.8%.'],
    suggested_position_size: 'small',
    confidence_adjustment: 'Trim conviction where the investors disagree.',
    summary: 'Sizing should respect the dispersion of views and the current volatility.',
  },
  verdict: {
    verdict: 'HOLD',
    confidence: 0.55,
    rationale:
      'The panel is split: growth and macro voices lean long, value and contrarian voices counsel patience. With no decisive edge, the firm holds.',
    decisive_factors: ['Split debate', 'Neutral technical score', 'Elevated volatility'],
    dissent: 'Michael Burry dissented (bearish): crowded positioning and softening internals argue for the short side.',
  },
}

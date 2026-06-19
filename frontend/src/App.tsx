import { useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { ApiError, fetchDebate } from './api'
import { sampleResult } from './sampleResult'
import type { BoardroomResult } from './types'
import { SearchBar } from './components/SearchBar'
import { DebateView } from './components/DebateView'
import { Loading } from './components/Loading'

type Status = 'idle' | 'loading' | 'error'

export default function App() {
  const [result, setResult] = useState<BoardroomResult>(sampleResult)
  const [isSample, setIsSample] = useState(true)
  const [status, setStatus] = useState<Status>('idle')
  const [error, setError] = useState<string | null>(null)

  async function run(ticker: string, rounds: number) {
    setStatus('loading')
    setError(null)
    try {
      const data = await fetchDebate(ticker, rounds)
      setResult(data)
      setIsSample(false)
      setStatus('idle')
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Something went wrong.')
      setStatus('idle')
    }
  }

  return (
    <div className="relative z-10 mx-auto max-w-4xl px-5 pb-28 pt-14 sm:px-8">
      <header className="text-center">
        <h1 className="font-display text-[34px] font-semibold tracking-tight text-ink sm:text-[40px]">
          BoardRoom
        </h1>
        <p className="mx-auto mt-3 max-w-md text-[15px] leading-relaxed text-ink-soft">
          A panel of legendary investors debates a stock, grounded in a deterministic quant
          engine, and the firm reaches a verdict.
        </p>
      </header>

      <div className="mt-9">
        <SearchBar onSubmit={run} loading={status === 'loading'} />
        <div className="mt-3 flex min-h-[20px] items-center justify-center gap-3 text-xs">
          {error && <span className="text-bear">{error}</span>}
          {!error && isSample && (
            <span className="text-ink-faint">
              Showing a sample debate. Enter a ticker for a live run.
            </span>
          )}
          {!error && !isSample && result.offline && (
            <span className="text-ink-faint">
              Offline engine (no API key on the server). Reasoning is heuristic.
            </span>
          )}
        </div>
      </div>

      <main className="mt-8">
        <AnimatePresence mode="wait">
          {status === 'loading' ? (
            <motion.div key="loading" exit={{ opacity: 0 }}>
              <Loading />
            </motion.div>
          ) : (
            <motion.div
              key={`${result.ticker}-${isSample}`}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.4 }}
            >
              <DebateView result={result} />
            </motion.div>
          )}
        </AnimatePresence>
      </main>

      <footer className="mt-20 text-center text-xs text-ink-faint">
        Personas are stylized for debate and do not represent the named investors. Not investment
        advice.
      </footer>
    </div>
  )
}

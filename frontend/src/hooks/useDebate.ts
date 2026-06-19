import { useState } from 'react'
import { ApiError, fetchDebate } from '../api'
import { sampleResult } from '../sampleResult'
import type { BoardroomResult } from '../types'

export type DebateStatus = 'idle' | 'loading' | 'error'

export interface UseDebate {
  /** The debate currently shown (starts as the bundled sample). */
  result: BoardroomResult
  /** True until the first live request resolves. */
  isSample: boolean
  status: DebateStatus
  error: string | null
  run: (ticker: string, rounds: number) => Promise<void>
}

/** Owns the request lifecycle for a debate: idle, loading, result, or error. */
export function useDebate(): UseDebate {
  const [result, setResult] = useState<BoardroomResult>(sampleResult)
  const [isSample, setIsSample] = useState(true)
  const [status, setStatus] = useState<DebateStatus>('idle')
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

  return { result, isSample, status, error, run }
}

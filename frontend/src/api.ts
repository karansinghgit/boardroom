import type { BoardroomResult } from './types'

export class ApiError extends Error {}

/**
 * Request a debate from the backend. The dev server proxies /api to Django.
 */
export async function fetchDebate(ticker: string, rounds = 1): Promise<BoardroomResult> {
  const symbol = ticker.trim().toUpperCase()
  if (!symbol) throw new ApiError('Enter a ticker symbol.')

  const params = new URLSearchParams({ rounds: String(rounds) })
  let response: Response
  try {
    response = await fetch(`/api/debate/${encodeURIComponent(symbol)}?${params}`)
  } catch {
    throw new ApiError('Could not reach the server. Is the backend running on port 8000?')
  }

  const data = await response.json().catch(() => null)
  if (!response.ok) {
    const message = (data && (data.error as string)) || `Request failed (${response.status}).`
    throw new ApiError(message)
  }
  return data as BoardroomResult
}

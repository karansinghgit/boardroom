import { useState, type FormEvent } from 'react'

export function SearchBar({
  onSubmit,
  loading,
}: {
  onSubmit: (ticker: string, rounds: number) => void
  loading: boolean
}) {
  const [ticker, setTicker] = useState('')
  const [rounds, setRounds] = useState(1)

  function handle(e: FormEvent) {
    e.preventDefault()
    if (!loading) onSubmit(ticker, rounds)
  }

  return (
    <form
      onSubmit={handle}
      className="flex flex-col gap-3 rounded-2xl border border-line bg-paper-raised/80 p-2 shadow-[0_1px_2px_rgba(28,26,23,0.04)] backdrop-blur-sm sm:flex-row sm:items-center"
    >
      <input
        value={ticker}
        onChange={(e) => setTicker(e.target.value)}
        placeholder="Enter a ticker, e.g. AAPL"
        autoCapitalize="characters"
        spellCheck={false}
        className="flex-1 rounded-xl bg-transparent px-4 py-2.5 font-mono text-[15px] uppercase tracking-wide text-ink placeholder:font-sans placeholder:normal-case placeholder:tracking-normal placeholder:text-ink-faint focus:outline-none"
      />
      <div className="flex items-center gap-2 px-2 sm:px-0">
        <label className="flex items-center gap-2 text-xs text-ink-faint">
          Rounds
          <select
            value={rounds}
            onChange={(e) => setRounds(Number(e.target.value))}
            className="rounded-lg border border-line bg-paper px-2 py-1.5 text-sm text-ink focus:outline-none"
          >
            {[0, 1, 2, 3].map((r) => (
              <option key={r} value={r}>
                {r}
              </option>
            ))}
          </select>
        </label>
        <button
          type="submit"
          disabled={loading}
          className="rounded-xl bg-ink px-5 py-2.5 text-sm font-medium text-paper transition hover:bg-ink/90 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {loading ? 'Convening…' : 'Convene the board'}
        </button>
      </div>
    </form>
  )
}

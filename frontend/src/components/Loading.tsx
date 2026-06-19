import { motion } from 'framer-motion'

const NAMES = ['Warren Buffett', 'Peter Lynch', 'Michael Burry', 'Stanley Druckenmiller', 'Howard Marks']

export function Loading() {
  return (
    <div className="flex flex-col items-center gap-7 py-24 text-center">
      <div className="font-display text-xl text-ink-soft">The board is convening</div>
      <div className="flex max-w-md flex-wrap justify-center gap-2">
        {NAMES.map((n, i) => (
          <motion.span
            key={n}
            initial={{ opacity: 0.25 }}
            animate={{ opacity: [0.25, 1, 0.25] }}
            transition={{ duration: 1.5, repeat: Infinity, delay: i * 0.18 }}
            className="rounded-full border border-line bg-paper-raised px-3 py-1 text-xs text-ink-soft"
          >
            {n}
          </motion.span>
        ))}
      </div>
    </div>
  )
}

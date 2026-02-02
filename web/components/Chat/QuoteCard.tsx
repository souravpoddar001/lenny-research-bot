'use client'

import { KeyQuote } from '@/lib/types'

type QuoteCardProps = {
  quote: KeyQuote
  color: string
}

export function QuoteCard({ quote, color }: QuoteCardProps) {
  return (
    <div
      className="flex-1 min-w-[250px] max-w-[350px] p-4 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)]"
      style={{ borderLeftWidth: '4px', borderLeftColor: color }}
    >
      <p className="text-sm text-[var(--color-text-primary)] line-clamp-3 mb-3">
        "{quote.text}"
      </p>
      <div className="flex items-center justify-between">
        <span className="text-xs text-[var(--color-text-secondary)] font-medium">
          {quote.speaker}
        </span>
        <a
          href={quote.youtube_link}
          target="_blank"
          rel="noopener noreferrer"
          className="text-xs px-2 py-1 rounded bg-[var(--color-violet-subtle)] text-[var(--color-violet)] hover:bg-[var(--color-violet)] hover:text-white transition-colors"
        >
          {quote.timestamp}
        </a>
      </div>
    </div>
  )
}

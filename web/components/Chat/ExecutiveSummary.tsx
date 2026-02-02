'use client'

import { ExecutiveSummary as ExecutiveSummaryType } from '@/lib/types'
import { ConceptMap } from './ConceptMap'
import { QuoteCard } from './QuoteCard'

type ExecutiveSummaryProps = {
  summary: ExecutiveSummaryType
}

export function ExecutiveSummary({ summary }: ExecutiveSummaryProps) {
  // Create a map of supporting point id to color
  const colorMap = new Map(
    summary.supporting_points.map((sp) => [sp.id, sp.color])
  )

  return (
    <div className="mb-6 p-4 rounded-xl bg-[var(--color-surface-elevated)] border border-[var(--color-border)]">
      {/* Header */}
      <div className="flex items-center gap-2 mb-4">
        <div className="w-2 h-2 rounded-full bg-[var(--color-amber)]" />
        <span className="text-xs font-medium text-[var(--color-text-muted)] uppercase tracking-wide">
          Executive Summary
        </span>
      </div>

      {/* Concept Map */}
      <ConceptMap
        mainInsight={summary.main_insight}
        supportingPoints={summary.supporting_points}
      />

      {/* Quote Cards */}
      {summary.key_quotes.length > 0 && (
        <div className="mt-4 pt-4 border-t border-[var(--color-border-subtle)]">
          <div className="flex flex-wrap gap-3 justify-center">
            {summary.key_quotes.map((quote, index) => (
              <QuoteCard
                key={index}
                quote={quote}
                color={colorMap.get(quote.supports) || 'var(--color-border)'}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

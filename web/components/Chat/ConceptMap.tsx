'use client'

import { SupportingPoint } from '@/lib/types'

type ConceptMapProps = {
  mainInsight: string
  supportingPoints: SupportingPoint[]
}

export function ConceptMap({ mainInsight, supportingPoints }: ConceptMapProps) {
  return (
    <div className="w-full">
      {/* Main Insight - displayed prominently as text */}
      <div className="mb-6 text-center">
        <p className="text-base font-semibold text-[var(--color-text-primary)] leading-relaxed max-w-xl mx-auto">
          {mainInsight}
        </p>
      </div>

      {/* Supporting points as cards with descriptions */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        {supportingPoints.map((point) => (
          <div
            key={point.id}
            className="p-3 rounded-lg bg-[var(--color-surface)] border border-[var(--color-border)]"
            style={{ borderLeftWidth: '3px', borderLeftColor: point.color }}
          >
            <div className="flex items-center gap-2 mb-1">
              <span
                className="w-2 h-2 rounded-full flex-shrink-0"
                style={{ backgroundColor: point.color }}
              />
              <span className="text-sm font-medium text-[var(--color-text-primary)]">
                {point.label}
              </span>
            </div>
            {point.description && (
              <p className="text-xs text-[var(--color-text-secondary)] ml-4">
                {point.description}
              </p>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}

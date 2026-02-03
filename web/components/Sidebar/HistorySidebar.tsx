'use client'

import { useState } from 'react'
import { HistoryEntry, PopularEntry } from '@/lib/types'

type HistorySidebarProps = {
  history: HistoryEntry[]
  popular: PopularEntry[]
  isLoading: boolean
  onSelectQuery: (cacheKey: string, query: string) => void
}

export function HistorySidebar({
  history,
  popular,
  isLoading,
  onSelectQuery,
}: HistorySidebarProps) {
  const [isCollapsed, setIsCollapsed] = useState(false)

  if (isCollapsed) {
    return (
      <div className="w-12 border-r border-[var(--color-border)] bg-[var(--color-surface)] flex flex-col items-center py-4">
        <button
          onClick={() => setIsCollapsed(false)}
          className="p-2 rounded-lg hover:bg-[var(--color-border-subtle)] transition-colors"
          title="Expand sidebar"
        >
          <ChevronRightIcon />
        </button>
        <div className="mt-4 space-y-2">
          <div className="p-2 rounded-lg hover:bg-[var(--color-border-subtle)]" title="My History">
            <HistoryIcon />
          </div>
          <div className="p-2 rounded-lg hover:bg-[var(--color-border-subtle)]" title="Popular">
            <FireIcon />
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="w-64 border-r border-[var(--color-border)] bg-[var(--color-surface)] flex flex-col h-full">
      {/* Header */}
      <div className="p-3 border-b border-[var(--color-border)] flex items-center justify-between">
        <span className="text-sm font-medium text-[var(--color-text-primary)]">Research</span>
        <button
          onClick={() => setIsCollapsed(true)}
          className="p-1 rounded hover:bg-[var(--color-border-subtle)] transition-colors"
          title="Collapse sidebar"
        >
          <ChevronLeftIcon />
        </button>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-3 space-y-6">
        {isLoading ? (
          <div className="text-sm text-[var(--color-text-muted)] text-center py-4">
            Loading...
          </div>
        ) : (
          <>
            {/* My History */}
            <section>
              <h3 className="text-xs font-semibold text-[var(--color-text-muted)] uppercase tracking-wider mb-2 flex items-center gap-2">
                <HistoryIcon className="w-3 h-3" />
                My History
              </h3>
              {history.length === 0 ? (
                <p className="text-xs text-[var(--color-text-muted)] italic">
                  No queries yet
                </p>
              ) : (
                <ul className="space-y-1">
                  {history.slice(0, 20).map((entry, i) => (
                    <li key={`${entry.cache_key}-${i}`}>
                      <button
                        onClick={() => onSelectQuery(entry.cache_key, entry.query)}
                        className="w-full text-left px-2 py-1.5 text-sm text-[var(--color-text-secondary)] hover:bg-[var(--color-border-subtle)] rounded transition-colors truncate"
                        title={entry.query}
                      >
                        {entry.query}
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </section>

            {/* Popular */}
            <section>
              <h3 className="text-xs font-semibold text-[var(--color-text-muted)] uppercase tracking-wider mb-2 flex items-center gap-2">
                <FireIcon className="w-3 h-3" />
                Popular
              </h3>
              {popular.length === 0 ? (
                <p className="text-xs text-[var(--color-text-muted)] italic">
                  No popular queries yet
                </p>
              ) : (
                <ul className="space-y-1">
                  {popular.map((entry, i) => (
                    <li key={`${entry.cache_key}-${i}`}>
                      <button
                        onClick={() => onSelectQuery(entry.cache_key, entry.query)}
                        className="w-full text-left px-2 py-1.5 text-sm text-[var(--color-text-secondary)] hover:bg-[var(--color-border-subtle)] rounded transition-colors truncate"
                        title={`${entry.query} (${entry.access_count} searches)`}
                      >
                        {entry.query}
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </section>
          </>
        )}
      </div>
    </div>
  )
}

function ChevronLeftIcon() {
  return (
    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
    </svg>
  )
}

function ChevronRightIcon() {
  return (
    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
    </svg>
  )
}

function HistoryIcon({ className = 'w-4 h-4' }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
    </svg>
  )
}

function FireIcon({ className = 'w-4 h-4' }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M17.657 18.657A8 8 0 016.343 7.343S7 9 9 10c0-2 .5-5 2.986-7C14 5 16.09 5.777 17.656 7.343A7.975 7.975 0 0120 13a7.975 7.975 0 01-2.343 5.657z" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M9.879 16.121A3 3 0 1012.015 11L11 14H9c0 .768.293 1.536.879 2.121z" />
    </svg>
  )
}

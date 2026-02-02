'use client'

import { useState, useRef, KeyboardEvent } from 'react'

type SearchBarProps = {
  value: string
  onChange: (value: string) => void
  onSearch: (query: string) => void
  loading: boolean
  mode: 'quick' | 'deep'
  onModeChange: (mode: 'quick' | 'deep') => void
}

export function SearchBar({
  value,
  onChange,
  onSearch,
  loading,
  mode,
  onModeChange,
}: SearchBarProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      if (value.trim() && !loading) {
        onSearch(value)
      }
    }
  }

  const handleSubmit = () => {
    if (value.trim() && !loading) {
      onSearch(value)
    }
  }

  return (
    <div className="bg-white dark:bg-gray-800 rounded-xl shadow-lg border border-gray-200 dark:border-gray-700">
      {/* Mode Toggle */}
      <div className="flex border-b border-gray-200 dark:border-gray-700">
        <button
          onClick={() => onModeChange('deep')}
          className={`flex-1 px-4 py-2 text-sm font-medium transition-colors
            ${mode === 'deep'
              ? 'text-primary-600 border-b-2 border-primary-600 bg-primary-50 dark:bg-primary-900/20'
              : 'text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200'
            }`}
        >
          Deep Research
          <span className="ml-1 text-xs text-gray-400">(30-60s)</span>
        </button>
        <button
          onClick={() => onModeChange('quick')}
          className={`flex-1 px-4 py-2 text-sm font-medium transition-colors
            ${mode === 'quick'
              ? 'text-primary-600 border-b-2 border-primary-600 bg-primary-50 dark:bg-primary-900/20'
              : 'text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200'
            }`}
        >
          Quick Q&A
          <span className="ml-1 text-xs text-gray-400">(&lt;10s)</span>
        </button>
      </div>

      {/* Search Input */}
      <div className="p-4">
        <div className="flex gap-3">
          <div className="flex-1 relative">
            <textarea
              ref={textareaRef}
              value={value}
              onChange={(e) => onChange(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={
                mode === 'deep'
                  ? 'Ask a research question... (e.g., "How do top PMs think about product-market fit?")'
                  : 'Ask a quick question...'
              }
              className="w-full px-4 py-3 rounded-lg border border-gray-300 dark:border-gray-600
                       bg-gray-50 dark:bg-gray-700 text-gray-900 dark:text-white
                       placeholder-gray-500 dark:placeholder-gray-400
                       focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent
                       resize-none"
              rows={2}
              disabled={loading}
            />
          </div>
          <button
            onClick={handleSubmit}
            disabled={!value.trim() || loading}
            className="px-6 py-3 bg-primary-600 text-white rounded-lg font-medium
                     hover:bg-primary-700 disabled:opacity-50 disabled:cursor-not-allowed
                     transition-colors flex items-center gap-2 self-end"
          >
            {loading ? (
              <>
                <span className="animate-spin h-4 w-4 border-2 border-white border-t-transparent rounded-full"></span>
                <span>Researching</span>
              </>
            ) : (
              <>
                <SearchIcon />
                <span>{mode === 'deep' ? 'Research' : 'Search'}</span>
              </>
            )}
          </button>
        </div>

        {/* Mode Description */}
        <p className="mt-2 text-xs text-gray-500 dark:text-gray-400">
          {mode === 'deep' ? (
            <>
              <strong>Deep Research:</strong> Comprehensive analysis with multiple retrieval stages.
              Best for complex questions requiring synthesis across sources.
            </>
          ) : (
            <>
              <strong>Quick Q&A:</strong> Fast, direct answers. Best for simple factual questions.
            </>
          )}
        </p>
      </div>
    </div>
  )
}

function SearchIcon() {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      fill="none"
      viewBox="0 0 24 24"
      strokeWidth={2}
      stroke="currentColor"
      className="w-5 h-5"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z"
      />
    </svg>
  )
}

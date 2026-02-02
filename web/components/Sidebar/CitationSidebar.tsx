'use client'

import { useEffect, useCallback } from 'react'
import { Citation } from '@/lib/types'

type CitationSidebarProps = {
  isOpen: boolean
  citation: Citation | undefined
  allCitations: Citation[]
  onClose: () => void
  onNavigate: (citationId: string) => void
}

export function CitationSidebar({
  isOpen,
  citation,
  allCitations,
  onClose,
  onNavigate,
}: CitationSidebarProps) {
  // Close on escape
  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) {
        onClose()
      }
    }
    document.addEventListener('keydown', handleEscape)
    return () => document.removeEventListener('keydown', handleEscape)
  }, [isOpen, onClose])

  // Prevent body scroll when open
  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = 'hidden'
    } else {
      document.body.style.overflow = ''
    }
    return () => {
      document.body.style.overflow = ''
    }
  }, [isOpen])

  const currentIndex = citation
    ? allCitations.findIndex((c) => c.id === citation.id)
    : -1

  const canGoPrev = currentIndex > 0
  const canGoNext = currentIndex < allCitations.length - 1

  const handlePrev = useCallback(() => {
    if (canGoPrev) {
      onNavigate(allCitations[currentIndex - 1].id)
    }
  }, [canGoPrev, currentIndex, allCitations, onNavigate])

  const handleNext = useCallback(() => {
    if (canGoNext) {
      onNavigate(allCitations[currentIndex + 1].id)
    }
  }, [canGoNext, currentIndex, allCitations, onNavigate])

  // Extract video ID from YouTube URL for thumbnail
  const getVideoId = (url: string) => {
    const match = url.match(/(?:v=|\/)([\w-]{11})/)
    return match ? match[1] : null
  }

  const videoId = citation ? getVideoId(citation.youtube_url) : null

  return (
    <>
      {/* Overlay */}
      <div
        className={`sidebar-overlay ${isOpen ? 'open' : ''}`}
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Sidebar */}
      <aside
        className={`fixed top-0 right-0 h-full w-full max-w-md bg-[var(--color-surface)] border-l border-[var(--color-border)] shadow-sidebar z-50 transform transition-transform duration-300 ease-out ${
          isOpen ? 'translate-x-0' : 'translate-x-full'
        }`}
        role="dialog"
        aria-modal="true"
        aria-label="Citation details"
      >
        {citation && (
          <div className="h-full flex flex-col">
            {/* Header */}
            <div className="flex items-center justify-between p-4 border-b border-[var(--color-border)]">
              <div className="flex items-center gap-2">
                <span className="citation-marker pointer-events-none">
                  {currentIndex + 1}
                </span>
                <span className="text-sm text-[var(--color-text-muted)]">
                  of {allCitations.length} sources
                </span>
              </div>

              <div className="flex items-center gap-1">
                {/* Navigation */}
                <button
                  onClick={handlePrev}
                  disabled={!canGoPrev}
                  className="p-2 rounded-lg hover:bg-[var(--color-border-subtle)] disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
                  aria-label="Previous citation"
                >
                  <ChevronLeftIcon />
                </button>
                <button
                  onClick={handleNext}
                  disabled={!canGoNext}
                  className="p-2 rounded-lg hover:bg-[var(--color-border-subtle)] disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
                  aria-label="Next citation"
                >
                  <ChevronRightIcon />
                </button>

                {/* Close */}
                <button
                  onClick={onClose}
                  className="p-2 rounded-lg hover:bg-[var(--color-border-subtle)] transition-colors ml-2"
                  aria-label="Close sidebar"
                >
                  <CloseIcon />
                </button>
              </div>
            </div>

            {/* Content */}
            <div className="flex-1 overflow-y-auto custom-scrollbar p-6 space-y-6">
              {/* YouTube Thumbnail */}
              {videoId && (
                <a
                  href={citation.youtube_link || citation.youtube_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="youtube-thumb block aspect-video bg-[var(--color-border)]"
                >
                  <img
                    src={`https://img.youtube.com/vi/${videoId}/maxresdefault.jpg`}
                    alt={citation.title}
                    className="w-full h-full object-cover"
                    onError={(e) => {
                      // Fallback to hqdefault if maxres doesn't exist
                      e.currentTarget.src = `https://img.youtube.com/vi/${videoId}/hqdefault.jpg`
                    }}
                  />
                  <div className="youtube-play-icon">
                    <div className="w-16 h-16 rounded-full bg-red-600 flex items-center justify-center">
                      <svg className="w-6 h-6 text-white ml-1" fill="currentColor" viewBox="0 0 24 24">
                        <path d="M8 5v14l11-7z" />
                      </svg>
                    </div>
                  </div>
                </a>
              )}

              {/* Episode Info */}
              <div>
                <h3 className="font-display font-semibold text-lg text-[var(--color-text-primary)] mb-1">
                  {citation.title}
                </h3>
                <p className="text-sm text-[var(--color-text-secondary)]">
                  with {citation.guest}
                </p>
              </div>

              {/* Quote */}
              <div className="p-4 rounded-xl bg-[var(--color-amber-subtle)] border-l-4 border-[var(--color-amber)]">
                <blockquote className="text-[var(--color-text-primary)] italic">
                  "{citation.quote}"
                </blockquote>
                <p className="mt-3 text-sm font-medium text-[var(--color-text-secondary)]">
                  — {citation.speaker}
                  {citation.timestamp && (
                    <span className="text-[var(--color-text-muted)]">
                      {' '}at {citation.timestamp}
                    </span>
                  )}
                </p>
              </div>

              {/* Watch Button */}
              <a
                href={citation.youtube_link || citation.youtube_url}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center justify-center gap-2 w-full py-3 px-4 rounded-xl font-medium transition-all duration-200"
                style={{
                  background: 'var(--color-amber)',
                  color: 'white',
                }}
                onMouseOver={(e) => {
                  e.currentTarget.style.background = 'var(--color-amber-hover)'
                }}
                onMouseOut={(e) => {
                  e.currentTarget.style.background = 'var(--color-amber)'
                }}
              >
                <YoutubeIcon />
                Watch at {citation.timestamp || 'start'}
              </a>
            </div>
          </div>
        )}
      </aside>
    </>
  )
}

function ChevronLeftIcon() {
  return (
    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
    </svg>
  )
}

function ChevronRightIcon() {
  return (
    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
    </svg>
  )
}

function CloseIcon() {
  return (
    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
    </svg>
  )
}

function YoutubeIcon() {
  return (
    <svg className="w-5 h-5" viewBox="0 0 24 24" fill="currentColor">
      <path d="M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z" />
    </svg>
  )
}

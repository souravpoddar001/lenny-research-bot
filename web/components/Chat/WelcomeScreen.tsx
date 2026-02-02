'use client'

type WelcomeScreenProps = {
  onSuggestionClick: (suggestion: string) => void
}

const STARTER_SUGGESTIONS = [
  {
    label: 'Product-Market Fit',
    query: 'How do top PMs think about product-market fit?',
  },
  {
    label: 'Hiring PMs',
    query: 'What makes a great PM hire according to leaders?',
  },
  {
    label: 'Growth Strategy',
    query: 'What growth strategies worked for successful startups?',
  },
  {
    label: 'Pricing',
    query: 'How should startups approach pricing their product?',
  },
  {
    label: 'Career Growth',
    query: "What's the path to becoming a VP of Product?",
  },
]

export function WelcomeScreen({ onSuggestionClick }: WelcomeScreenProps) {
  return (
    <div className="flex-1 flex items-center justify-center p-8">
      <div className="max-w-2xl w-full text-center">
        {/* Hero */}
        <div className="mb-12 stagger-children">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-[var(--color-amber-subtle)] mb-6">
            <svg
              className="w-8 h-8 text-[var(--color-amber)]"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={1.5}
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M12 18.75a6 6 0 006-6v-1.5m-6 7.5a6 6 0 01-6-6v-1.5m6 7.5v3.75m-3.75 0h7.5M12 15.75a3 3 0 01-3-3V4.5a3 3 0 116 0v8.25a3 3 0 01-3 3z"
              />
            </svg>
          </div>

          <h1 className="font-display text-3xl md:text-4xl font-semibold text-[var(--color-text-primary)] mb-4 text-balance">
            Research Lenny's Podcast
          </h1>

          <p className="text-lg text-[var(--color-text-secondary)] max-w-lg mx-auto text-balance">
            Ask questions and get comprehensive, citation-backed answers from
            300+ conversations with top product leaders.
          </p>
        </div>

        {/* Suggestions */}
        <div className="space-y-4">
          <p className="text-sm text-[var(--color-text-muted)]">
            Try asking about:
          </p>

          <div className="flex flex-wrap justify-center gap-2 stagger-children">
            {STARTER_SUGGESTIONS.map((suggestion) => (
              <button
                key={suggestion.label}
                onClick={() => onSuggestionClick(suggestion.query)}
                className="chip"
              >
                {suggestion.label}
              </button>
            ))}
          </div>
        </div>

        {/* Subtle footer note */}
        <p className="mt-12 text-xs text-[var(--color-text-muted)]">
          Powered by AI · Responses include verified citations with timestamps
        </p>
      </div>
    </div>
  )
}

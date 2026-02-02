// Core data types for Lenny's Research Bot

export type SupportingPoint = {
  id: string
  label: string
  description: string
  color: string
}

export type KeyQuote = {
  text: string
  speaker: string
  timestamp: string
  youtube_link: string
  supports: string  // References SupportingPoint.id
}

export type ExecutiveSummary = {
  main_insight: string
  supporting_points: SupportingPoint[]
  key_quotes: KeyQuote[]
}

export type Citation = {
  id: string
  quote: string
  speaker: string
  title: string
  guest: string
  timestamp: string
  youtube_url: string
  youtube_link: string
}

export type Source = {
  transcript_id: string
  title: string
  guest: string
  youtube_url: string
}

export type Message = {
  id: string
  role: 'user' | 'assistant'
  content: string
  citations?: Citation[]
  sources?: Source[]
  suggestedFollowups?: string[]
  executiveSummary?: ExecutiveSummary
  timestamp: Date
}

export type LoadingStep = 'analyzing' | 'searching' | 'finding' | 'synthesizing'

export type ResearchResponse = {
  content: string
  citations: Omit<Citation, 'id'>[]
  sources: Source[]
  unverified_quotes?: string[]
  suggested_followups?: string[]
  executive_summary?: ExecutiveSummary
}

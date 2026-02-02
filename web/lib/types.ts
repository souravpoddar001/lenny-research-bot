// Core data types for Lenny's Research Bot

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
  timestamp: Date
}

export type LoadingStep = 'analyzing' | 'searching' | 'finding' | 'synthesizing'

export type ResearchResponse = {
  content: string
  citations: Omit<Citation, 'id'>[]
  sources: Source[]
  unverified_quotes?: string[]
  suggested_followups?: string[]
}

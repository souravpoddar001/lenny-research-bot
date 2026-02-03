import { ResearchResponse, HistoryEntry, PopularEntry } from './types'
import { ensureSessionId } from './session'

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || ''

function getHeaders(): HeadersInit {
  const headers: HeadersInit = {
    'Content-Type': 'application/json',
  }

  const sessionId = ensureSessionId()
  if (sessionId) {
    headers['X-Session-ID'] = sessionId
  }

  return headers
}

export async function sendResearchQuery(
  query: string,
  context?: string
): Promise<ResearchResponse> {
  const response = await fetch(`${API_BASE_URL}/api/research`, {
    method: 'POST',
    headers: getHeaders(),
    body: JSON.stringify({ query, context }),
  })

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}))
    throw new Error(errorData.error || `Research request failed: ${response.status}`)
  }

  return response.json()
}

export async function sendQuickQuery(
  query: string,
  context?: string
): Promise<ResearchResponse> {
  const response = await fetch(`${API_BASE_URL}/api/query`, {
    method: 'POST',
    headers: getHeaders(),
    body: JSON.stringify({ query, context }),
  })

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}))
    throw new Error(errorData.error || `Query request failed: ${response.status}`)
  }

  return response.json()
}

export async function getHistory(): Promise<HistoryEntry[]> {
  const response = await fetch(`${API_BASE_URL}/api/history`, {
    method: 'GET',
    headers: getHeaders(),
  })

  if (!response.ok) {
    console.error('Failed to fetch history')
    return []
  }

  const data = await response.json()
  return data.queries || []
}

export async function getPopular(limit: number = 10): Promise<PopularEntry[]> {
  const response = await fetch(`${API_BASE_URL}/api/popular?limit=${limit}`, {
    method: 'GET',
    headers: { 'Content-Type': 'application/json' },
  })

  if (!response.ok) {
    console.error('Failed to fetch popular queries')
    return []
  }

  const data = await response.json()
  return data.queries || []
}

export async function getCachedResult(cacheKey: string): Promise<ResearchResponse | null> {
  const response = await fetch(`${API_BASE_URL}/api/cached?key=${cacheKey}`, {
    method: 'GET',
    headers: { 'Content-Type': 'application/json' },
  })

  if (!response.ok) {
    return null
  }

  return response.json()
}

export function generateFollowups(
  query: string,
  response: ResearchResponse
): string[] {
  const followups: string[] = []

  const guests = new Set(response.citations.map((c) => c.guest))
  if (guests.size > 1) {
    const guestArray = Array.from(guests)
    followups.push(`What else did ${guestArray[0]} say about this?`)
  }

  const topics = extractTopics(response.content)
  if (topics.length > 0) {
    followups.push(`Tell me more about ${topics[0]}`)
  }

  if (query.toLowerCase().includes('how')) {
    followups.push('What are the common mistakes to avoid?')
  } else if (query.toLowerCase().includes('what')) {
    followups.push('Can you give specific examples?')
  }

  if (guests.size >= 1) {
    followups.push('What do other guests say about this?')
  }

  return followups.slice(0, 4)
}

function extractTopics(content: string): string[] {
  const topics: string[] = []

  const quotedMatch = content.match(/"([^"]+)"/g)
  if (quotedMatch) {
    topics.push(...quotedMatch.slice(0, 2).map((q) => q.replace(/"/g, '')))
  }

  const exampleMatch = content.match(/(?:such as|like|including)\s+([^,.]+)/gi)
  if (exampleMatch) {
    topics.push(...exampleMatch.slice(0, 2).map((m) => m.replace(/^(such as|like|including)\s+/i, '')))
  }

  return topics
}

export function isFollowUpQuery(query: string): boolean {
  const normalized = query.toLowerCase().trim()

  if (normalized.split(' ').length <= 5) {
    return true
  }

  const referentialWords = ['that', 'this', 'these', 'those', 'it', 'they', 'more', 'else', 'other']
  if (referentialWords.some((word) => normalized.includes(word))) {
    return true
  }

  const followUpPatterns = [
    /^(what|how|why|can you|tell me|explain|elaborate)/i,
    /^(and|but|also|what about)/i,
  ]
  if (followUpPatterns.some((pattern) => pattern.test(normalized))) {
    return true
  }

  return false
}

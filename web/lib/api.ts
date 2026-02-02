import { ResearchResponse } from './types'

// Use Next.js API routes (which proxy to the backend)
// This avoids CORS issues

export async function sendResearchQuery(
  query: string,
  context?: string
): Promise<ResearchResponse> {
  const response = await fetch('/api/research', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      query,
      context,
    }),
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
  const response = await fetch('/api/query', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      query,
      context,
    }),
  })

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}))
    throw new Error(errorData.error || `Query request failed: ${response.status}`)
  }

  return response.json()
}

// Generate suggested follow-up questions based on the response
export function generateFollowups(
  query: string,
  response: ResearchResponse
): string[] {
  const followups: string[] = []

  // If there are multiple guests mentioned, suggest asking about others
  const guests = new Set(response.citations.map((c) => c.guest))
  if (guests.size > 1) {
    const guestArray = Array.from(guests)
    followups.push(`What else did ${guestArray[0]} say about this?`)
  }

  // Suggest diving deeper based on common patterns
  const topics = extractTopics(response.content)
  if (topics.length > 0) {
    followups.push(`Tell me more about ${topics[0]}`)
  }

  // Generic follow-ups based on query type
  if (query.toLowerCase().includes('how')) {
    followups.push('What are the common mistakes to avoid?')
  } else if (query.toLowerCase().includes('what')) {
    followups.push('Can you give specific examples?')
  }

  // Always offer to hear from other perspectives
  if (guests.size >= 1) {
    followups.push('What do other guests say about this?')
  }

  return followups.slice(0, 4) // Max 4 suggestions
}

// Simple topic extraction from response content
function extractTopics(content: string): string[] {
  const topics: string[] = []

  // Look for quoted terms or emphasized phrases
  const quotedMatch = content.match(/"([^"]+)"/g)
  if (quotedMatch) {
    topics.push(...quotedMatch.slice(0, 2).map((q) => q.replace(/"/g, '')))
  }

  // Look for phrases after "such as" or "like"
  const exampleMatch = content.match(/(?:such as|like|including)\s+([^,.]+)/gi)
  if (exampleMatch) {
    topics.push(...exampleMatch.slice(0, 2).map((m) => m.replace(/^(such as|like|including)\s+/i, '')))
  }

  return topics
}

// Check if a query looks like a follow-up (short, references previous context)
export function isFollowUpQuery(query: string): boolean {
  const normalized = query.toLowerCase().trim()

  // Short queries are likely follow-ups
  if (normalized.split(' ').length <= 5) {
    return true
  }

  // Contains referential words
  const referentialWords = ['that', 'this', 'these', 'those', 'it', 'they', 'more', 'else', 'other']
  if (referentialWords.some((word) => normalized.includes(word))) {
    return true
  }

  // Starts with follow-up patterns
  const followUpPatterns = [
    /^(what|how|why|can you|tell me|explain|elaborate)/i,
    /^(and|but|also|what about)/i,
  ]
  if (followUpPatterns.some((pattern) => pattern.test(normalized))) {
    return true
  }

  return false
}

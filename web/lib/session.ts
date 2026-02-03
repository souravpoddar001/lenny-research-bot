/**
 * Session management for anonymous user tracking.
 *
 * Generates a random UUID on first visit and stores it in localStorage.
 * This ID is used to track personal query history without requiring login.
 */

const SESSION_KEY = 'lenny-session-id'

/**
 * Get the current session ID, or null if none exists.
 */
export function getSessionId(): string | null {
  if (typeof window === 'undefined') return null
  return localStorage.getItem(SESSION_KEY)
}

/**
 * Get existing session ID or create a new one.
 */
export function ensureSessionId(): string {
  if (typeof window === 'undefined') return ''

  let sessionId = localStorage.getItem(SESSION_KEY)

  if (!sessionId) {
    sessionId = crypto.randomUUID()
    localStorage.setItem(SESSION_KEY, sessionId)
  }

  return sessionId
}

/**
 * Clear the session ID (for testing/debugging).
 */
export function clearSessionId(): void {
  if (typeof window === 'undefined') return
  localStorage.removeItem(SESSION_KEY)
}

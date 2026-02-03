# Query History Sidebar Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a collapsible sidebar showing personal query history and popular research topics.

**Architecture:** Anonymous session IDs in localStorage link to server-side history in Azure Blob Storage. Popular queries derived from access counts in the existing cache. Frontend sidebar fetches both on load.

**Tech Stack:** Python Azure Functions, Azure Blob Storage, Next.js, React hooks, Tailwind CSS

---

## Task 1: Add access_count to cache entries

**Files:**
- Modify: `functions/shared/cache.py`

**Step 1: Update store_result to include access_count**

In `functions/shared/cache.py`, modify the `store_result` function to initialize `access_count`:

```python
def store_result(query: str, result: dict) -> None:
    """
    Store a research result in the cache.

    Args:
        query: The original query string.
        result: The result dict to cache.

    Note:
        Silently skips storage if Azure Storage is not configured.
    """
    container = _get_container_client()
    if container is None:
        return

    cache_key = get_cache_key(query)
    blob_name = f"{cache_key}.json"

    cache_entry = {
        "query": query,
        "cached_at": datetime.now(timezone.utc).isoformat(),
        "access_count": 1,  # NEW: Initialize access count
        "result": result,
    }

    try:
        blob_client = container.get_blob_client(blob_name)
        blob_client.upload_blob(
            json.dumps(cache_entry, ensure_ascii=False, indent=2),
            overwrite=True,
        )
        logger.info(f"Cached result for query: {query[:50]}...")

    except (AzureError, TypeError, ValueError) as e:
        logger.warning(f"Cache write error: {type(e).__name__}: {e}")
```

**Step 2: Add increment_access_count function**

Add this new function after `store_result`:

```python
def increment_access_count(query: str) -> None:
    """
    Increment the access count for a cached query.

    Args:
        query: The query string to increment count for.
    """
    container = _get_container_client()
    if container is None:
        return

    cache_key = get_cache_key(query)
    blob_name = f"{cache_key}.json"

    try:
        blob_client = container.get_blob_client(blob_name)
        data = blob_client.download_blob().readall()
        cache_entry = json.loads(data.decode("utf-8"))

        # Increment access count (handle legacy entries without count)
        cache_entry["access_count"] = cache_entry.get("access_count", 0) + 1

        blob_client.upload_blob(
            json.dumps(cache_entry, ensure_ascii=False, indent=2),
            overwrite=True,
        )
        logger.debug(f"Incremented access count for: {query[:50]}...")

    except (ResourceNotFoundError, AzureError, json.JSONDecodeError) as e:
        logger.warning(f"Failed to increment access count: {e}")
```

**Step 3: Add get_popular_queries function**

Add this function to retrieve popular queries:

```python
def get_popular_queries(limit: int = 10) -> list[dict]:
    """
    Get the most popular cached queries by access count.

    Args:
        limit: Maximum number of queries to return.

    Returns:
        List of dicts with query, cache_key, and access_count.
    """
    container = _get_container_client()
    if container is None:
        return []

    queries = []

    try:
        for blob in container.list_blobs():
            if not blob.name.endswith(".json"):
                continue

            try:
                blob_client = container.get_blob_client(blob.name)
                data = blob_client.download_blob().readall()
                entry = json.loads(data.decode("utf-8"))

                queries.append({
                    "query": entry.get("query", ""),
                    "cache_key": blob.name.replace(".json", ""),
                    "access_count": entry.get("access_count", 1),
                })
            except (AzureError, json.JSONDecodeError):
                continue

        # Sort by access_count descending
        queries.sort(key=lambda x: x["access_count"], reverse=True)
        return queries[:limit]

    except AzureError as e:
        logger.warning(f"Failed to get popular queries: {e}")
        return []
```

**Step 4: Update get_cached_result to increment count**

Modify `get_cached_result` to increment access count on hit:

```python
def get_cached_result(query: str) -> Optional[dict]:
    """
    Check cache for existing result.

    Args:
        query: The query string to look up.

    Returns:
        Cached result dict if found, None otherwise.
        Logs cache HIT or MISS for monitoring.
        Increments access_count on HIT.
    """
    container = _get_container_client()
    if container is None:
        return None

    cache_key = get_cache_key(query)
    blob_name = f"{cache_key}.json"

    try:
        blob_client = container.get_blob_client(blob_name)
        data = blob_client.download_blob().readall()
        cached_entry = json.loads(data.decode("utf-8"))

        logger.info(f"Cache HIT for query: {query[:50]}...")

        # Increment access count asynchronously (fire and forget)
        increment_access_count(query)

        return cached_entry.get("result")

    except ResourceNotFoundError:
        logger.info(f"Cache MISS for query: {query[:50]}...")
        return None

    except AzureError as e:
        logger.warning(f"Cache read error: {e}")
        return None

    except json.JSONDecodeError as e:
        logger.warning(f"Cache JSON decode error: {e}")
        return None
```

**Step 5: Commit**

```bash
git add functions/shared/cache.py
git commit -m "feat(cache): add access_count tracking and popular queries"
```

---

## Task 2: Create history module

**Files:**
- Create: `functions/shared/history.py`

**Step 1: Create the history module**

Create `functions/shared/history.py`:

```python
"""
Session history module using Azure Blob Storage.

Tracks query history per anonymous session for the sidebar feature.
"""

import os
import json
import logging
from datetime import datetime, timezone
from typing import Optional

from azure.storage.blob import ContainerClient
from azure.core.exceptions import ResourceNotFoundError, AzureError

from .cache import get_cache_key

logger = logging.getLogger(__name__)

DEFAULT_HISTORY_CONTAINER = "research-history"


def _get_history_container() -> Optional[ContainerClient]:
    """Get Azure Blob Storage container for history, creating if needed."""
    connection_string = os.environ.get("AZURE_STORAGE_CONNECTION_STRING")

    if not connection_string:
        logger.warning("AZURE_STORAGE_CONNECTION_STRING not configured. History disabled.")
        return None

    container_name = os.environ.get("HISTORY_CONTAINER_NAME", DEFAULT_HISTORY_CONTAINER)

    try:
        client = ContainerClient.from_connection_string(
            conn_str=connection_string,
            container_name=container_name,
        )

        if not client.exists():
            client.create_container()
            logger.info(f"Created history container: {container_name}")

        return client
    except AzureError as e:
        logger.warning(f"Failed to connect to history storage: {e}")
        return None


def get_session_history(session_id: str) -> list[dict]:
    """
    Get query history for a session.

    Args:
        session_id: The anonymous session ID.

    Returns:
        List of query entries with query, cache_key, and timestamp.
    """
    if not session_id:
        return []

    container = _get_history_container()
    if container is None:
        return []

    blob_name = f"{session_id}.json"

    try:
        blob_client = container.get_blob_client(blob_name)
        data = blob_client.download_blob().readall()
        session_data = json.loads(data.decode("utf-8"))
        return session_data.get("queries", [])

    except ResourceNotFoundError:
        return []

    except (AzureError, json.JSONDecodeError) as e:
        logger.warning(f"Failed to get session history: {e}")
        return []


def add_to_history(session_id: str, query: str) -> None:
    """
    Add a query to session history.

    Args:
        session_id: The anonymous session ID.
        query: The query string to add.
    """
    if not session_id or not query:
        return

    container = _get_history_container()
    if container is None:
        return

    blob_name = f"{session_id}.json"
    cache_key = get_cache_key(query)

    new_entry = {
        "query": query,
        "cache_key": cache_key,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    try:
        blob_client = container.get_blob_client(blob_name)

        # Try to get existing history
        try:
            data = blob_client.download_blob().readall()
            session_data = json.loads(data.decode("utf-8"))
        except ResourceNotFoundError:
            session_data = {
                "session_id": session_id,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "queries": [],
            }

        # Check if query already exists (by cache_key)
        existing_keys = {q["cache_key"] for q in session_data["queries"]}
        if cache_key not in existing_keys:
            # Add to front (most recent first)
            session_data["queries"].insert(0, new_entry)

            # Limit to 50 entries
            session_data["queries"] = session_data["queries"][:50]

            blob_client.upload_blob(
                json.dumps(session_data, ensure_ascii=False, indent=2),
                overwrite=True,
            )
            logger.debug(f"Added to history for session {session_id[:8]}...")

    except (AzureError, json.JSONDecodeError) as e:
        logger.warning(f"Failed to add to history: {e}")
```

**Step 2: Commit**

```bash
git add functions/shared/history.py
git commit -m "feat: add session history module"
```

---

## Task 3: Add API endpoints

**Files:**
- Modify: `functions/function_app.py`

**Step 1: Add imports**

At the top of `function_app.py`, add:

```python
from shared.history import get_session_history, add_to_history
from shared.cache import get_popular_queries
```

**Step 2: Add /api/history endpoint**

Add after the `health_check` function:

```python
@app.route(route="history", methods=["GET"])
def get_history(req: func.HttpRequest) -> func.HttpResponse:
    """
    Get query history for the current session.

    Headers:
        X-Session-ID: Anonymous session identifier

    Response:
    {
        "queries": [
            {"query": "...", "cache_key": "...", "timestamp": "..."}
        ]
    }
    """
    session_id = req.headers.get("X-Session-ID", "")

    if not session_id:
        return func.HttpResponse(
            json.dumps({"queries": []}),
            mimetype="application/json",
        )

    queries = get_session_history(session_id)

    return func.HttpResponse(
        json.dumps({"queries": queries}),
        mimetype="application/json",
    )
```

**Step 3: Add /api/popular endpoint**

Add after the `get_history` function:

```python
@app.route(route="popular", methods=["GET"])
def get_popular(req: func.HttpRequest) -> func.HttpResponse:
    """
    Get popular queries by access count.

    Query params:
        limit: Number of results (default 10, max 50)

    Response:
    {
        "queries": [
            {"query": "...", "cache_key": "...", "access_count": 47}
        ]
    }
    """
    try:
        limit = min(int(req.params.get("limit", "10")), 50)
    except ValueError:
        limit = 10

    queries = get_popular_queries(limit)

    return func.HttpResponse(
        json.dumps({"queries": queries}),
        mimetype="application/json",
    )
```

**Step 4: Modify deep_research to track history**

Update the `deep_research` function to add queries to session history:

```python
@app.route(route="research", methods=["POST"])
def deep_research(req: func.HttpRequest) -> func.HttpResponse:
    """
    Deep research endpoint for comprehensive analysis.

    Headers:
        X-Session-ID: Optional anonymous session identifier for history tracking

    Request body:
    {
        "query": "How do top PMs think about product-market fit?",
        "output_type": "article",  // optional: article, report, qa_response
        "mode": "pageindex"  // optional: "vector" (default) or "pageindex"
    }

    Response:
    {
        "content": "...",
        "citations": [...],
        "sources": [...],
        "unverified_quotes": [...]
    }
    """
    try:
        body = req.get_json()
        query = body.get("query")
        mode = body.get("mode")  # Optional: "vector" or "pageindex"
        session_id = req.headers.get("X-Session-ID", "")

        if not query:
            return func.HttpResponse(
                json.dumps({"error": "Missing 'query' in request body"}),
                status_code=400,
                mimetype="application/json",
            )

        pipeline = get_pipeline(mode=mode)
        result = pipeline.research(query)

        # Add to session history if session ID provided
        if session_id:
            add_to_history(session_id, query)

        return func.HttpResponse(
            json.dumps(result.to_dict()),
            mimetype="application/json",
        )

    except Exception as e:
        tb = traceback.format_exc()
        logging.error(f"Error in deep_research: {e}\n{tb}")
        return func.HttpResponse(
            json.dumps({"error": str(e), "traceback": tb}),
            status_code=500,
            mimetype="application/json",
        )
```

**Step 5: Commit**

```bash
git add functions/function_app.py
git commit -m "feat(api): add history and popular endpoints"
```

---

## Task 4: Add /api/cached endpoint for direct cache retrieval

**Files:**
- Modify: `functions/function_app.py`
- Modify: `functions/shared/cache.py`

**Step 1: Add get_by_cache_key function to cache.py**

Add this function to `functions/shared/cache.py`:

```python
def get_by_cache_key(cache_key: str) -> Optional[dict]:
    """
    Get cached result directly by cache key.

    Args:
        cache_key: The SHA256 hash cache key.

    Returns:
        Cached result dict if found, None otherwise.
    """
    container = _get_container_client()
    if container is None:
        return None

    blob_name = f"{cache_key}.json"

    try:
        blob_client = container.get_blob_client(blob_name)
        data = blob_client.download_blob().readall()
        cached_entry = json.loads(data.decode("utf-8"))
        return cached_entry.get("result")

    except (ResourceNotFoundError, AzureError, json.JSONDecodeError):
        return None
```

**Step 2: Add /api/cached endpoint**

Add to `function_app.py` after the popular endpoint, and add import:

```python
from shared.cache import get_popular_queries, get_by_cache_key
```

```python
@app.route(route="cached", methods=["GET"])
def get_cached(req: func.HttpRequest) -> func.HttpResponse:
    """
    Get a cached result by cache key (for sidebar click).

    Query params:
        key: The cache key (SHA256 hash)

    Response:
        The cached research result, or 404 if not found.
    """
    cache_key = req.params.get("key", "")

    if not cache_key:
        return func.HttpResponse(
            json.dumps({"error": "Missing 'key' parameter"}),
            status_code=400,
            mimetype="application/json",
        )

    result = get_by_cache_key(cache_key)

    if result is None:
        return func.HttpResponse(
            json.dumps({"error": "Cache entry not found"}),
            status_code=404,
            mimetype="application/json",
        )

    return func.HttpResponse(
        json.dumps(result),
        mimetype="application/json",
    )
```

**Step 3: Commit**

```bash
git add functions/shared/cache.py functions/function_app.py
git commit -m "feat(api): add /api/cached endpoint for direct cache retrieval"
```

---

## Task 5: Create frontend session management

**Files:**
- Create: `web/lib/session.ts`

**Step 1: Create the session module**

Create `web/lib/session.ts`:

```typescript
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
```

**Step 2: Commit**

```bash
git add web/lib/session.ts
git commit -m "feat(web): add session management module"
```

---

## Task 6: Update frontend API to include session ID

**Files:**
- Modify: `web/lib/api.ts`
- Modify: `web/lib/types.ts`

**Step 1: Add new types to types.ts**

Add to the end of `web/lib/types.ts`:

```typescript
export type HistoryEntry = {
  query: string
  cache_key: string
  timestamp: string
}

export type PopularEntry = {
  query: string
  cache_key: string
  access_count: number
}
```

**Step 2: Update api.ts with session header and new functions**

Replace `web/lib/api.ts` with:

```typescript
import { ResearchResponse, HistoryEntry, PopularEntry } from './types'
import { ensureSessionId } from './session'

// API base URL - uses environment variable in production, local proxy in development
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || ''

/**
 * Get headers including session ID for all requests.
 */
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
  const response = await fetch(`${API_BASE_URL}/api/query`, {
    method: 'POST',
    headers: getHeaders(),
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
```

**Step 3: Commit**

```bash
git add web/lib/types.ts web/lib/api.ts
git commit -m "feat(web): add session header and history/popular API functions"
```

---

## Task 7: Add Next.js API routes for history/popular/cached

**Files:**
- Create: `web/app/api/history/route.ts`
- Create: `web/app/api/popular/route.ts`
- Create: `web/app/api/cached/route.ts`

**Step 1: Create history route**

Create `web/app/api/history/route.ts`:

```typescript
import { NextRequest, NextResponse } from 'next/server'

const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:7071'

export async function GET(request: NextRequest) {
  try {
    const sessionId = request.headers.get('X-Session-ID') || ''

    const response = await fetch(`${BACKEND_URL}/api/history`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
        'X-Session-ID': sessionId,
      },
    })

    if (!response.ok) {
      return NextResponse.json({ queries: [] })
    }

    const data = await response.json()
    return NextResponse.json(data)
  } catch (error) {
    console.error('History API error:', error)
    return NextResponse.json({ queries: [] })
  }
}
```

**Step 2: Create popular route**

Create `web/app/api/popular/route.ts`:

```typescript
import { NextRequest, NextResponse } from 'next/server'

const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:7071'

export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url)
    const limit = searchParams.get('limit') || '10'

    const response = await fetch(`${BACKEND_URL}/api/popular?limit=${limit}`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
    })

    if (!response.ok) {
      return NextResponse.json({ queries: [] })
    }

    const data = await response.json()
    return NextResponse.json(data)
  } catch (error) {
    console.error('Popular API error:', error)
    return NextResponse.json({ queries: [] })
  }
}
```

**Step 3: Create cached route**

Create `web/app/api/cached/route.ts`:

```typescript
import { NextRequest, NextResponse } from 'next/server'

const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:7071'

export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url)
    const key = searchParams.get('key')

    if (!key) {
      return NextResponse.json(
        { error: 'Missing key parameter' },
        { status: 400 }
      )
    }

    const response = await fetch(`${BACKEND_URL}/api/cached?key=${key}`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
    })

    if (!response.ok) {
      return NextResponse.json(
        { error: 'Cache entry not found' },
        { status: 404 }
      )
    }

    const data = await response.json()
    return NextResponse.json(data)
  } catch (error) {
    console.error('Cached API error:', error)
    return NextResponse.json(
      { error: 'Failed to fetch cached result' },
      { status: 500 }
    )
  }
}
```

**Step 4: Commit**

```bash
git add web/app/api/history/route.ts web/app/api/popular/route.ts web/app/api/cached/route.ts
git commit -m "feat(web): add Next.js API routes for history, popular, cached"
```

---

## Task 8: Create useHistory hook

**Files:**
- Create: `web/hooks/useHistory.ts`

**Step 1: Create the hook**

Create `web/hooks/useHistory.ts`:

```typescript
'use client'

import { useState, useEffect, useCallback } from 'react'
import { HistoryEntry, PopularEntry } from '@/lib/types'
import { getHistory, getPopular } from '@/lib/api'

type UseHistoryResult = {
  history: HistoryEntry[]
  popular: PopularEntry[]
  isLoading: boolean
  refresh: () => Promise<void>
}

export function useHistory(): UseHistoryResult {
  const [history, setHistory] = useState<HistoryEntry[]>([])
  const [popular, setPopular] = useState<PopularEntry[]>([])
  const [isLoading, setIsLoading] = useState(true)

  const fetchData = useCallback(async () => {
    setIsLoading(true)
    try {
      const [historyData, popularData] = await Promise.all([
        getHistory(),
        getPopular(10),
      ])
      setHistory(historyData)
      setPopular(popularData)
    } catch (error) {
      console.error('Failed to fetch history/popular:', error)
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchData()
  }, [fetchData])

  return {
    history,
    popular,
    isLoading,
    refresh: fetchData,
  }
}
```

**Step 2: Commit**

```bash
git add web/hooks/useHistory.ts
git commit -m "feat(web): add useHistory hook"
```

---

## Task 9: Create HistorySidebar component

**Files:**
- Create: `web/components/Sidebar/HistorySidebar.tsx`
- Modify: `web/components/Sidebar/index.ts`

**Step 1: Create the sidebar component**

Create `web/components/Sidebar/HistorySidebar.tsx`:

```typescript
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
```

**Step 2: Update index.ts**

Modify `web/components/Sidebar/index.ts`:

```typescript
export { CitationSidebar } from './CitationSidebar'
export { HistorySidebar } from './HistorySidebar'
```

**Step 3: Commit**

```bash
git add web/components/Sidebar/HistorySidebar.tsx web/components/Sidebar/index.ts
git commit -m "feat(web): add HistorySidebar component"
```

---

## Task 10: Integrate sidebar into page.tsx

**Files:**
- Modify: `web/app/page.tsx`
- Modify: `web/hooks/useChat.ts`

**Step 1: Update useChat hook to support loading cached results**

Add a new function to `web/hooks/useChat.ts`. After the existing imports:

```typescript
import { sendResearchQuery, generateFollowups, isFollowUpQuery, getCachedResult } from '@/lib/api'
```

Add this new function inside the `useChat` hook, after `sendMessage`:

```typescript
  const loadCachedQuery = useCallback(
    async (cacheKey: string, query: string) => {
      if (state.isLoading) return

      // Create user message
      const userMessage: Message = {
        id: `user-${Date.now()}`,
        role: 'user',
        content: query,
        timestamp: new Date(),
      }

      setState((prev) => ({
        ...prev,
        messages: [...prev.messages, userMessage],
        isLoading: true,
        error: null,
      }))

      startLoadingSteps()

      try {
        const response = await getCachedResult(cacheKey)

        if (!response) {
          throw new Error('Cached result not found')
        }

        // Add IDs to citations
        const citationsWithIds: Citation[] = response.citations.map((c, i) => ({
          ...c,
          id: `citation-${Date.now()}-${i}`,
        }))

        // Generate follow-up suggestions
        const suggestedFollowups = generateFollowups(query, response)

        const assistantMessage: Message = {
          id: `assistant-${Date.now()}`,
          role: 'assistant',
          content: response.content,
          citations: citationsWithIds,
          sources: response.sources,
          suggestedFollowups,
          executiveSummary: response.executive_summary,
          timestamp: new Date(),
        }

        setState((prev) => ({
          ...prev,
          messages: [...prev.messages, assistantMessage],
          isLoading: false,
        }))
      } catch (err) {
        setState((prev) => ({
          ...prev,
          isLoading: false,
          error: err instanceof Error ? err.message : 'An error occurred',
        }))
      } finally {
        stopLoadingSteps()
      }
    },
    [state.isLoading, startLoadingSteps, stopLoadingSteps]
  )
```

Add `loadCachedQuery` to the return object:

```typescript
  return {
    messages: state.messages,
    isLoading: state.isLoading,
    loadingStep: state.loadingStep,
    error: state.error,
    sidebarOpen: state.sidebarOpen,
    activeCitation,
    allCitations,
    sendMessage,
    loadCachedQuery,  // NEW
    openCitation,
    closeSidebar,
    clearError,
    clearConversation,
  }
```

**Step 2: Update page.tsx to include history sidebar**

Replace `web/app/page.tsx`:

```typescript
'use client'

import { useCallback } from 'react'
import { useChat } from '@/hooks/useChat'
import { useHistory } from '@/hooks/useHistory'
import { Header } from '@/components/Header'
import { ChatContainer } from '@/components/Chat'
import { ChatInput } from '@/components/Input'
import { CitationSidebar, HistorySidebar } from '@/components/Sidebar'

export default function Home() {
  const {
    messages,
    isLoading,
    loadingStep,
    error,
    sidebarOpen,
    activeCitation,
    allCitations,
    sendMessage,
    loadCachedQuery,
    openCitation,
    closeSidebar,
    clearError,
    clearConversation,
  } = useChat()

  const { history, popular, isLoading: historyLoading, refresh: refreshHistory } = useHistory()

  const handleSuggestionClick = useCallback(
    (suggestion: string) => {
      sendMessage(suggestion)
    },
    [sendMessage]
  )

  const handleSelectQuery = useCallback(
    async (cacheKey: string, query: string) => {
      await loadCachedQuery(cacheKey, query)
      // Refresh history after loading a query
      refreshHistory()
    },
    [loadCachedQuery, refreshHistory]
  )

  // Refresh history when a new message is sent
  const handleSendMessage = useCallback(
    async (query: string) => {
      await sendMessage(query)
      refreshHistory()
    },
    [sendMessage, refreshHistory]
  )

  return (
    <div className="h-screen flex flex-col bg-[var(--color-bg)]">
      {/* Header */}
      <Header
        onClearConversation={clearConversation}
        hasMessages={messages.length > 0}
      />

      {/* Main Content with Sidebar */}
      <div className="flex-1 flex min-h-0">
        {/* History Sidebar */}
        <HistorySidebar
          history={history}
          popular={popular}
          isLoading={historyLoading}
          onSelectQuery={handleSelectQuery}
        />

        {/* Main Area */}
        <main className="flex-1 flex flex-col min-h-0">
          {/* Error Banner */}
          {error && (
            <div className="px-4 py-3 bg-red-50 dark:bg-red-900/20 border-b border-red-200 dark:border-red-800">
              <div className="max-w-3xl mx-auto flex items-center justify-between">
                <p className="text-sm text-red-800 dark:text-red-200">{error}</p>
                <button
                  onClick={clearError}
                  className="text-red-600 hover:text-red-800 dark:text-red-400 dark:hover:text-red-200"
                >
                  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>
            </div>
          )}

          {/* Chat Area */}
          <ChatContainer
            messages={messages}
            isLoading={isLoading}
            loadingStep={loadingStep}
            onCitationClick={openCitation}
            onSuggestionClick={handleSuggestionClick}
          />

          {/* Input */}
          <ChatInput
            onSend={handleSendMessage}
            disabled={isLoading}
          />
        </main>
      </div>

      {/* Citation Sidebar */}
      <CitationSidebar
        isOpen={sidebarOpen}
        citation={activeCitation}
        allCitations={allCitations}
        onClose={closeSidebar}
        onNavigate={openCitation}
      />
    </div>
  )
}
```

**Step 3: Commit**

```bash
git add web/hooks/useChat.ts web/app/page.tsx
git commit -m "feat(web): integrate history sidebar into main page"
```

---

## Task 11: Final verification

**Step 1: Test backend endpoints**

```bash
cd functions
func start
```

In another terminal:
```bash
# Test popular endpoint
curl http://localhost:7071/api/popular

# Test history endpoint (will be empty without session)
curl -H "X-Session-ID: test-123" http://localhost:7071/api/history

# Test cached endpoint (use a real cache key from popular)
curl "http://localhost:7071/api/cached?key=YOUR_CACHE_KEY"
```

**Step 2: Test frontend**

```bash
cd web
npm run dev
```

Open http://localhost:3000 and verify:
1. Sidebar appears on the left
2. Popular queries section shows cached queries
3. Clicking a query loads the cached result instantly
4. My History section updates after running queries
5. Sidebar collapses and expands correctly

**Step 3: Final commit**

```bash
git add -A
git commit -m "feat: complete query history sidebar implementation"
```

---

## Summary

| Task | Description | Files |
|------|-------------|-------|
| 1 | Add access_count to cache | `functions/shared/cache.py` |
| 2 | Create history module | `functions/shared/history.py` |
| 3 | Add API endpoints | `functions/function_app.py` |
| 4 | Add /api/cached endpoint | `functions/shared/cache.py`, `functions/function_app.py` |
| 5 | Create session management | `web/lib/session.ts` |
| 6 | Update frontend API | `web/lib/api.ts`, `web/lib/types.ts` |
| 7 | Add Next.js API routes | `web/app/api/history/route.ts`, etc. |
| 8 | Create useHistory hook | `web/hooks/useHistory.ts` |
| 9 | Create HistorySidebar | `web/components/Sidebar/HistorySidebar.tsx` |
| 10 | Integrate into page | `web/app/page.tsx`, `web/hooks/useChat.ts` |
| 11 | Final verification | Testing |

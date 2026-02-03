# Query History Sidebar Design

**Date**: 2026-02-03
**Status**: Approved
**Goal**: Allow users to revisit previous queries without re-running them, and discover popular research topics.

---

## Problem Statement

Users currently have no way to:
1. Go back to a query they tried earlier without re-running it
2. Discover what topics have already been researched (and are cached)
3. Remember the exact phrasing of previous queries

## Solution Overview

Add a collapsible sidebar with two sections:
- **My History**: Personal query history tied to an anonymous session ID
- **Popular Research**: Top queries by access count from the shared cache

## Data Architecture

### Session History Storage

New blob container `research-history` stores per-session history:

```
research-history/
  └── {session_id}.json    # One file per anonymous user
```

Session file schema:
```json
{
  "session_id": "abc123-def456-...",
  "created_at": "2026-02-03T10:00:00Z",
  "queries": [
    {
      "query": "what is product market fit",
      "cache_key": "3b77052677b255e9ba3bad8144c53e5497f92a3ab57afefb920bd995154cd967",
      "timestamp": "2026-02-03T10:30:00Z"
    }
  ]
}
```

### Cache Entry Enhancement

Add `access_count` to existing cache entries in `research-cache/`:

```json
{
  "query": "what is product market fit",
  "cached_at": "2026-02-03T10:30:00Z",
  "access_count": 47,
  "result": { ... }
}
```

### Session ID

- Generated client-side using `crypto.randomUUID()`
- Stored in `localStorage` as `lenny-session-id`
- Sent via `X-Session-ID` header on all API calls

## API Design

### New Endpoints

#### GET /api/history

Returns the current session's query history.

**Request:**
```
Headers:
  X-Session-ID: abc123-def456-...
```

**Response:**
```json
{
  "queries": [
    {
      "query": "what is product market fit",
      "cache_key": "3b77052...",
      "timestamp": "2026-02-03T10:30:00Z"
    }
  ]
}
```

#### GET /api/popular

Returns top queries by access count.

**Request:**
```
Query params: ?limit=10 (optional, defaults to 10)
```

**Response:**
```json
{
  "queries": [
    {
      "query": "what is product market fit",
      "cache_key": "3b77052...",
      "access_count": 47
    }
  ]
}
```

### Modified Endpoint

#### POST /api/research

Changes:
- Accept optional `X-Session-ID` header
- On cache HIT: increment `access_count` in cache entry
- On cache MISS: after storing result, add query to session history
- On any request with session ID: add to session history if not already present

## Frontend UI

### Sidebar Layout

```
┌─────────────────────────────────────────────────────┐
│ [≡]  Lenny's Research Bot              [☀] [+New]  │
├──────────────┬──────────────────────────────────────┤
│              │                                      │
│ MY HISTORY   │                                      │
│ ─────────────│         (Chat area)                  │
│ ● what is PMF│                                      │
│ ● hiring PMs │                                      │
│              │                                      │
│ POPULAR      │                                      │
│ ─────────────│                                      │
│ 🔥 product   │                                      │
│    market fit│                                      │
│ 🔥 growth    │                                      │
│    metrics   │                                      │
│              │                                      │
│ [Collapse ‹] │                                      │
└──────────────┴──────────────────────────────────────┘
```

### Behavior

- **Collapsed state**: Only icons visible, expands on hover or click
- **Click a query**: Loads cached result instantly (no API call to research endpoint)
- **My History**: Chronological (most recent first), max 20 items displayed
- **Popular**: Top 10 by access count, fetched on page load
- **Truncation**: Long queries show tooltip on hover with full text

## Implementation Plan

### Backend (Python Azure Functions)

| File | Changes |
|------|---------|
| `functions/shared/cache.py` | Add `access_count` field, add `increment_access_count()` function |
| `functions/shared/history.py` | **NEW** — `get_session_history()`, `add_to_history()`, `get_popular_queries()` |
| `functions/function_app.py` | Add `/api/history` and `/api/popular` endpoints, modify `/api/research` |
| `functions/local.settings.json` | Add `HISTORY_CONTAINER_NAME` (defaults to `research-history`) |

### Frontend (Next.js)

| File | Changes |
|------|---------|
| `web/lib/session.ts` | **NEW** — `getSessionId()`, `ensureSessionId()` |
| `web/lib/api.ts` | Add `X-Session-ID` header, add `getHistory()`, `getPopular()`, `getCachedResult()` |
| `web/components/Sidebar/HistorySidebar.tsx` | **NEW** — Collapsible sidebar component |
| `web/hooks/useHistory.ts` | **NEW** — Hook for history/popular state management |
| `web/app/page.tsx` | Integrate sidebar, adjust layout grid |

### Estimated Scope

- Backend: ~300 lines
- Frontend: ~400 lines

## Future Considerations

- **Search within history**: Filter/search past queries
- **Delete from history**: Allow users to remove items
- **Sync across devices**: Would require authentication
- **Analytics**: Track popular topics, usage patterns

---

## Appendix: Cache Key Generation

For reference, cache keys are SHA256 hashes of normalized queries:

```python
def get_cache_key(query: str) -> str:
    normalized = query.lower().strip()
    return hashlib.sha256(normalized.encode()).hexdigest()
```

This ensures "What is PMF" and "what is pmf" map to the same cache entry.

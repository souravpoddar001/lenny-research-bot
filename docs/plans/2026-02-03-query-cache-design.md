# Query Cache Design

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Reduce cost waste by caching research query results, avoiding repeated LLM pipeline runs for identical queries.

**Architecture:** Exact-match cache using Azure Blob Storage. Cache key is SHA256 hash of normalized query. Cache lives forever until manually cleared during transcript ingestion.

**Tech Stack:** Azure Blob Storage, Python (azure-storage-blob SDK)

---

## Architecture

```
┌─────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   Frontend  │────▶│  /api/research   │────▶│  Azure Blob     │
│   (Next.js) │     │  (Azure Func)    │     │  Storage Cache  │
└─────────────┘     └──────────────────┘     └─────────────────┘
                            │                        │
                            │  Cache miss?           │ Cache hit?
                            ▼                        ▼
                    ┌──────────────────┐      Return cached
                    │  Research        │      response
                    │  Pipeline (LLM)  │
                    └──────────────────┘
                            │
                            │ Store result
                            ▼
                    ┌─────────────────┐
                    │  Azure Blob     │
                    └─────────────────┘
```

## Cache Strategy

- **Key format**: `sha256(query.lower().strip())` → e.g., `a1b2c3d4e5f6.json`
- **Storage**: Azure Blob container `research-cache`
- **TTL**: None (cache forever)
- **Invalidation**: Manual - clear all cache when new transcripts are ingested

## Expected Hit Rate

Low hit rate expected (exact match only). Primary value:
- Suggested follow-up question clicks (deterministic)
- Same user retrying exact query
- Zero risk of returning wrong cached result

---

## Implementation Tasks

### Task 1: Create cache module

**Files:**
- Create: `functions/shared/cache.py`

**Implementation:**

```python
import hashlib
import json
import logging
import os
from datetime import datetime, timezone
from typing import Optional

from azure.storage.blob import BlobServiceClient, ContainerClient
from azure.core.exceptions import ResourceNotFoundError

logger = logging.getLogger(__name__)

CONTAINER_NAME = os.environ.get("CACHE_CONTAINER_NAME", "research-cache")


def _get_container_client() -> Optional[ContainerClient]:
    """Get blob container client, return None if not configured."""
    connection_string = os.environ.get("AZURE_STORAGE_CONNECTION_STRING")
    if not connection_string:
        logger.warning("AZURE_STORAGE_CONNECTION_STRING not set, caching disabled")
        return None

    blob_service = BlobServiceClient.from_connection_string(connection_string)
    container = blob_service.get_container_client(CONTAINER_NAME)

    # Create container if it doesn't exist
    if not container.exists():
        container.create_container()
        logger.info(f"Created cache container: {CONTAINER_NAME}")

    return container


def normalize_query(query: str) -> str:
    """Normalize query for consistent cache keys."""
    return query.lower().strip()


def get_cache_key(query: str) -> str:
    """Generate cache key from query."""
    normalized = normalize_query(query)
    return hashlib.sha256(normalized.encode()).hexdigest()


def get_cached_result(query: str) -> Optional[dict]:
    """
    Check cache for query result.

    Returns:
        Cached result dict if found, None otherwise.
    """
    container = _get_container_client()
    if not container:
        return None

    cache_key = get_cache_key(query)
    blob_name = f"{cache_key}.json"

    try:
        blob_client = container.get_blob_client(blob_name)
        data = blob_client.download_blob().readall()
        cached = json.loads(data)
        logger.info(f"Cache HIT for query: {query[:50]}...")
        return cached.get("result")
    except ResourceNotFoundError:
        logger.info(f"Cache MISS for query: {query[:50]}...")
        return None
    except Exception as e:
        logger.error(f"Cache read error: {e}")
        return None


def store_result(query: str, result: dict) -> None:
    """Store query result in cache."""
    container = _get_container_client()
    if not container:
        return

    cache_key = get_cache_key(query)
    blob_name = f"{cache_key}.json"

    cache_entry = {
        "query": query,
        "cached_at": datetime.now(timezone.utc).isoformat(),
        "result": result,
    }

    try:
        blob_client = container.get_blob_client(blob_name)
        blob_client.upload_blob(
            json.dumps(cache_entry),
            overwrite=True,
            content_settings={"content_type": "application/json"}
        )
        logger.info(f"Cached result for query: {query[:50]}...")
    except Exception as e:
        logger.error(f"Cache write error: {e}")


def clear_cache() -> int:
    """
    Clear all cached results.

    Returns:
        Number of cache entries deleted.
    """
    container = _get_container_client()
    if not container:
        return 0

    count = 0
    try:
        blobs = container.list_blobs()
        for blob in blobs:
            container.delete_blob(blob.name)
            count += 1
        logger.info(f"Cleared {count} cache entries")
    except Exception as e:
        logger.error(f"Cache clear error: {e}")

    return count
```

---

### Task 2: Integrate cache into research pipeline

**Files:**
- Modify: `functions/shared/research.py`

**Changes:**

1. Add import at top:
```python
from .cache import get_cached_result, store_result
```

2. Modify `research()` method to check cache before running pipeline and store after:

```python
async def research(self, query: str, output_type: str = "article") -> ResearchOutput:
    # Check cache first
    cached = get_cached_result(query)
    if cached:
        return ResearchOutput(
            content=cached["content"],
            citations=[Citation(**c) for c in cached["citations"]],
            sources=cached["sources"],
            unverified_quotes=cached.get("unverified_quotes", []),
            executive_summary=cached.get("executive_summary"),
        )

    # Run expensive pipeline (existing code)
    result = await self._run_full_pipeline(query, output_type)

    # Store in cache
    store_result(query, result.to_dict())

    return result
```

---

### Task 3: Add cache clear to transcript ingestion

**Files:**
- Modify: `scripts/ingest_transcripts.py`

**Changes:**

Add at end of successful ingestion:

```python
# Clear query cache since transcript data has changed
from functions.shared.cache import clear_cache

cleared = clear_cache()
print(f"Cleared {cleared} cached query results")
```

---

### Task 4: Add environment configuration

**Files:**
- Modify: `functions/local.settings.json`

**Changes:**

Add to `Values`:
```json
"AZURE_STORAGE_CONNECTION_STRING": "DefaultEndpointsProtocol=https;AccountName=...;AccountKey=...;EndpointSuffix=core.windows.net",
"CACHE_CONTAINER_NAME": "research-cache"
```

Note: Use same storage account as search index, or create new one.

---

### Task 5: Add azure-storage-blob to dependencies

**Files:**
- Modify: `functions/requirements.txt`

**Changes:**

Add:
```
azure-storage-blob>=12.19.0
```

---

## Error Handling

- **Blob storage unavailable**: Skip cache, run pipeline (graceful degradation)
- **Corrupted cache entry**: Log error, return None, run pipeline
- **No silent failures**: All cache operations logged for monitoring

## Testing

1. Run query → should see "Cache MISS" in logs
2. Run same query → should see "Cache HIT", instant response
3. Run slightly different query → should see "Cache MISS"
4. Run transcript ingestion → should see "Cleared X cache entries"
5. Run original query → should see "Cache MISS" again

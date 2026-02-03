"""
Query result caching module using Azure Blob Storage.

Caches research results to avoid re-running expensive LLM pipelines for
repeated queries. Uses SHA256 hashing for cache keys.
"""

import os
import re
import json
import hashlib
import logging
from datetime import datetime, timezone
from typing import Optional

from azure.storage.blob import ContainerClient
from azure.core.exceptions import ResourceNotFoundError, AzureError

logger = logging.getLogger(__name__)

# Default container name for cache blobs
DEFAULT_CONTAINER_NAME = "research-cache"


def _get_container_client() -> Optional[ContainerClient]:
    """
    Get Azure Blob Storage container client, creating container if needed.

    Returns:
        ContainerClient if storage is configured, None otherwise.
        Returns None and logs warning if connection string is not set.
    """
    connection_string = os.environ.get("AZURE_STORAGE_CONNECTION_STRING")

    if not connection_string:
        logger.warning(
            "AZURE_STORAGE_CONNECTION_STRING not configured. "
            "Caching is disabled."
        )
        return None

    container_name = os.environ.get("CACHE_CONTAINER_NAME", DEFAULT_CONTAINER_NAME)

    try:
        client = ContainerClient.from_connection_string(
            conn_str=connection_string,
            container_name=container_name,
        )

        # Create container if it doesn't exist
        if not client.exists():
            client.create_container()
            logger.info(f"Created cache container: {container_name}")

        return client
    except AzureError as e:
        logger.warning(f"Failed to connect to Azure Blob Storage: {type(e).__name__}: {str(e)}")
        return None


def normalize_query(query: str) -> str:
    """
    Normalize a query string for consistent cache key generation.

    Args:
        query: The raw query string.

    Returns:
        Normalized query (lowercase, stripped of whitespace and trailing punctuation,
        with multiple spaces collapsed to single space).
    """
    normalized = query.lower().strip()
    # Remove trailing punctuation (?, !, .)
    normalized = normalized.rstrip("?!.")
    # Collapse multiple spaces to single space
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized


def get_cache_key(query: str) -> str:
    """
    Generate a cache key from a query using SHA256 hash.

    Args:
        query: The query string (will be normalized first).

    Returns:
        SHA256 hash of the normalized query.
    """
    normalized = normalize_query(query)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def get_cached_result(query: str) -> Optional[dict]:
    """
    Check cache for existing result.

    Args:
        query: The query string to look up.

    Returns:
        Cached result dict if found, None otherwise.
        Logs cache HIT or MISS for monitoring.
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
        "result": result,
        "access_count": 1,
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


def increment_access_count(query: str) -> None:
    """
    Increment the access count for a cached query.

    Args:
        query: The query string whose access count should be incremented.

    Note:
        Handles legacy cache entries that don't have access_count by defaulting to 0.
        Silently handles errors to avoid disrupting cache reads.
    """
    container = _get_container_client()
    if container is None:
        return

    cache_key = get_cache_key(query)
    blob_name = f"{cache_key}.json"

    try:
        blob_client = container.get_blob_client(blob_name)
        data = blob_client.download_blob().readall()
        cached_entry = json.loads(data.decode("utf-8"))

        # Handle legacy entries that don't have access_count
        current_count = cached_entry.get("access_count", 0)
        cached_entry["access_count"] = current_count + 1

        blob_client.upload_blob(
            json.dumps(cached_entry, ensure_ascii=False, indent=2),
            overwrite=True,
        )
        logger.debug(f"Incremented access count to {cached_entry['access_count']} for query: {query[:50]}...")

    except ResourceNotFoundError:
        logger.debug(f"Cannot increment access count - blob not found: {blob_name}")

    except AzureError as e:
        logger.warning(f"Failed to increment access count: {type(e).__name__}: {e}")

    except json.JSONDecodeError as e:
        logger.warning(f"Failed to parse cache entry for access count update: {e}")


def get_popular_queries(limit: int = 10) -> list[dict]:
    """
    Get the most popular queries based on access count.

    Args:
        limit: Maximum number of queries to return (default 10).

    Returns:
        List of dicts with 'query', 'cache_key', and 'access_count' fields,
        sorted by access_count descending. Filters out test queries and
        deduplicates queries that differ only in case/punctuation.
        Returns empty list on failure.
    """
    container = _get_container_client()
    if container is None:
        return []

    # Blacklist patterns for test queries
    TEST_PATTERNS = ["test cache", "test query", "hello", "asdf"]
    MIN_QUERY_LENGTH = 10  # Filter very short queries

    results = []

    try:
        blobs = container.list_blobs()
        for blob in blobs:
            if not blob.name.endswith(".json"):
                continue

            try:
                blob_client = container.get_blob_client(blob.name)
                data = blob_client.download_blob().readall()
                cached_entry = json.loads(data.decode("utf-8"))

                query = cached_entry.get("query", "")
                cache_key = blob.name[:-5]  # Remove .json extension
                access_count = cached_entry.get("access_count", 0)

                # Filter out test queries and very short queries
                query_lower = query.lower().strip()
                if len(query_lower) < MIN_QUERY_LENGTH:
                    continue
                if any(pattern in query_lower for pattern in TEST_PATTERNS):
                    continue

                results.append({
                    "query": query,
                    "cache_key": cache_key,
                    "access_count": access_count,
                    "_normalized": normalize_query(query),  # For deduplication
                })

            except (AzureError, json.JSONDecodeError) as e:
                logger.debug(f"Skipping blob {blob.name} due to error: {e}")
                continue

        # Deduplicate by normalized query, keeping highest access_count
        seen_normalized = {}
        for entry in results:
            normalized = entry["_normalized"]
            if normalized not in seen_normalized:
                seen_normalized[normalized] = entry
            elif entry["access_count"] > seen_normalized[normalized]["access_count"]:
                seen_normalized[normalized] = entry

        # Remove internal field and sort
        deduped = list(seen_normalized.values())
        for entry in deduped:
            del entry["_normalized"]

        deduped.sort(key=lambda x: x["access_count"], reverse=True)
        return deduped[:limit]

    except AzureError as e:
        logger.warning(f"Failed to get popular queries: {type(e).__name__}: {e}")
        return []


def clear_cache() -> int:
    """
    Delete all cached results.

    Returns:
        Number of cache entries deleted.
        Returns 0 if storage is not configured.
    """
    container = _get_container_client()
    if container is None:
        return 0

    deleted_count = 0

    try:
        blobs = container.list_blobs()
        for blob in blobs:
            if blob.name.endswith(".json"):
                container.delete_blob(blob.name)
                deleted_count += 1

        logger.info(f"Cleared {deleted_count} cache entries")
        return deleted_count

    except AzureError as e:
        logger.warning(f"Cache clear error: {e}")
        return deleted_count

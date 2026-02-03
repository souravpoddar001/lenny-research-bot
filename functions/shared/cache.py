"""
Query result caching module using Azure Blob Storage.

Caches research results to avoid re-running expensive LLM pipelines for
repeated queries. Uses SHA256 hashing for cache keys.
"""

import os
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
        logger.warning(f"Failed to connect to Azure Blob Storage: {e}")
        return None


def normalize_query(query: str) -> str:
    """
    Normalize a query string for consistent cache key generation.

    Args:
        query: The raw query string.

    Returns:
        Normalized query (lowercase, stripped of whitespace).
    """
    return query.lower().strip()


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
    }

    try:
        blob_client = container.get_blob_client(blob_name)
        blob_client.upload_blob(
            json.dumps(cache_entry, ensure_ascii=False, indent=2),
            overwrite=True,
        )
        logger.info(f"Cached result for query: {query[:50]}...")

    except AzureError as e:
        logger.warning(f"Cache write error: {e}")


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

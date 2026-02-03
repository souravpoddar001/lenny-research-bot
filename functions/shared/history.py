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
    """
    Get Azure Blob Storage container client for history, creating container if needed.

    Returns:
        ContainerClient if storage is configured, None otherwise.
        Returns None and logs warning if connection string is not set.
    """
    connection_string = os.environ.get("AZURE_STORAGE_CONNECTION_STRING")

    if not connection_string:
        logger.warning(
            "AZURE_STORAGE_CONNECTION_STRING not configured. "
            "Session history is disabled."
        )
        return None

    container_name = os.environ.get("HISTORY_CONTAINER_NAME", DEFAULT_HISTORY_CONTAINER)

    try:
        client = ContainerClient.from_connection_string(
            conn_str=connection_string,
            container_name=container_name,
        )

        # Create container if it doesn't exist
        if not client.exists():
            client.create_container()
            logger.info(f"Created history container: {container_name}")

        return client
    except AzureError as e:
        logger.warning(f"Failed to connect to Azure Blob Storage for history: {type(e).__name__}: {str(e)}")
        return None


def get_session_history(session_id: str) -> list[dict]:
    """
    Get query history for a session.

    Args:
        session_id: The session identifier.

    Returns:
        List of query history entries (most recent first).
        Returns empty list if session_id is empty, container unavailable,
        or session file doesn't exist.
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

    except AzureError as e:
        logger.warning(f"Failed to get session history: {type(e).__name__}: {e}")
        return []

    except json.JSONDecodeError as e:
        logger.warning(f"Failed to parse session history JSON: {e}")
        return []


def add_to_history(session_id: str, query: str) -> None:
    """
    Add a query to the session history.

    Args:
        session_id: The session identifier.
        query: The query string to add.

    Note:
        - Duplicates (by cache_key) are not added.
        - New entries are inserted at the front (most recent first).
        - History is limited to 50 entries per session.
        - Silently skips if session_id or query is empty, or storage unavailable.
    """
    if not session_id or not query:
        return

    container = _get_history_container()
    if container is None:
        return

    cache_key = get_cache_key(query)
    blob_name = f"{session_id}.json"

    new_entry = {
        "query": query,
        "cache_key": cache_key,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    try:
        blob_client = container.get_blob_client(blob_name)

        # Try to get existing session data
        try:
            data = blob_client.download_blob().readall()
            session_data = json.loads(data.decode("utf-8"))
        except ResourceNotFoundError:
            session_data = {
                "session_id": session_id,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "queries": [],
            }

        queries = session_data.get("queries", [])

        # Check for duplicate by cache_key
        existing_keys = {q.get("cache_key") for q in queries}
        if cache_key in existing_keys:
            logger.debug(f"Query already in history for session {session_id[:8]}...")
            return

        # Insert at front (most recent first)
        queries.insert(0, new_entry)

        # Limit to 50 entries
        queries = queries[:50]
        session_data["queries"] = queries

        # Upload updated session data
        blob_client.upload_blob(
            json.dumps(session_data, ensure_ascii=False, indent=2),
            overwrite=True,
        )
        logger.debug(f"Added query to history for session {session_id[:8]}...")

    except AzureError as e:
        logger.warning(f"Failed to add to session history: {type(e).__name__}: {e}")

    except json.JSONDecodeError as e:
        logger.warning(f"Failed to parse existing session history: {e}")

"""
Index loader for PageIndex with caching support.

Supports loading from:
- Local JSON files (default)
- Azure Blob Storage (for production deployments)
"""

import os
import json
from pathlib import Path
from typing import Optional


class IndexLoader:
    """
    Loads PageIndex data from storage with caching.

    The index is split into multiple files for efficiency:
    - episode_index.json: Level 1 (all episodes)
    - themes/_index.json: Theme list
    - themes/{theme_id}.json: Individual theme details
    - topics/{episode_id}.json: Topics for each episode
    - quotes/{episode_id}.json: Quotes for each episode

    Usage:
        loader = IndexLoader("./index")
        episodes = loader.load_episode_index()
        theme = loader.load_theme("product-market-fit")
        topics = loader.load_topics("sean-ellis")
        quotes = loader.load_quotes("sean-ellis")
    """

    def __init__(
        self,
        index_path: Optional[str] = None,
        use_blob_storage: bool = False,
        blob_connection_string: Optional[str] = None,
        blob_container: str = "pageindex",
    ):
        """
        Initialize the index loader.

        Args:
            index_path: Path to local index directory (default: ./index or env var)
            use_blob_storage: If True, load from Azure Blob Storage
            blob_connection_string: Azure Storage connection string
            blob_container: Blob container name
        """
        self.use_blob_storage = use_blob_storage

        if use_blob_storage:
            self._init_blob_client(blob_connection_string, blob_container)
        else:
            self.index_path = Path(
                index_path
                or os.environ.get("PAGEINDEX_LOCAL_PATH", "./index")
            )

        # In-memory cache
        self._cache: dict = {}

    def _init_blob_client(
        self,
        connection_string: Optional[str],
        container: str,
    ):
        """Initialize Azure Blob Storage client."""
        try:
            from azure.storage.blob import BlobServiceClient
        except ImportError:
            raise ImportError(
                "azure-storage-blob is required for blob storage support. "
                "Install with: pip install azure-storage-blob"
            )

        conn_str = connection_string or os.environ.get(
            "AZURE_STORAGE_CONNECTION_STRING"
        )
        if not conn_str:
            raise ValueError(
                "Blob connection string required. Set AZURE_STORAGE_CONNECTION_STRING "
                "environment variable or pass blob_connection_string parameter."
            )

        self.blob_client = BlobServiceClient.from_connection_string(conn_str)
        self.container = self.blob_client.get_container_client(container)

    def _load_json(self, path: str) -> dict:
        """Load JSON from storage (local or blob)."""
        if self.use_blob_storage:
            blob = self.container.get_blob_client(path)
            content = blob.download_blob().readall()
            return json.loads(content)
        else:
            file_path = self.index_path / path
            if not file_path.exists():
                raise FileNotFoundError(f"Index file not found: {file_path}")
            with open(file_path, "r") as f:
                return json.load(f)

    def _get_cached(self, cache_key: str, path: str) -> dict:
        """Get data from cache or load from storage."""
        if cache_key not in self._cache:
            self._cache[cache_key] = self._load_json(path)
        return self._cache[cache_key]

    def load_episode_index(self) -> dict:
        """
        Load Level 1: Episode index.

        Returns:
            Dict with episode metadata keyed by episode_id
        """
        data = self._get_cached("episode_index", "episode_index.json")
        return data.get("episodes", {})

    def load_theme_list(self) -> list[str]:
        """
        Load list of all theme IDs.

        Returns:
            List of theme ID strings
        """
        data = self._get_cached("theme_list", "themes/_index.json")
        return data.get("themes", [])

    def load_theme(self, theme_id: str) -> dict:
        """
        Load Level 2: Specific theme details.

        Args:
            theme_id: Theme identifier (e.g., "product-market-fit")

        Returns:
            Theme dict with description, episodes, subtopics, etc.
        """
        cache_key = f"theme_{theme_id}"
        return self._get_cached(cache_key, f"themes/{theme_id}.json")

    def load_all_themes(self) -> dict[str, dict]:
        """
        Load all themes into a dict.

        Returns:
            Dict of theme_id -> theme_data
        """
        themes = {}
        for theme_id in self.load_theme_list():
            try:
                themes[theme_id] = self.load_theme(theme_id)
            except FileNotFoundError:
                continue
        return themes

    def load_topics(self, episode_id: str) -> list[dict]:
        """
        Load Level 3: Topics for an episode.

        Args:
            episode_id: Episode identifier

        Returns:
            List of topic dicts with title, summary, timestamps, etc.
        """
        cache_key = f"topics_{episode_id}"
        try:
            data = self._get_cached(cache_key, f"topics/{episode_id}.json")
            return data.get("topics", [])
        except FileNotFoundError:
            return []

    def load_quotes(self, episode_id: str) -> list[dict]:
        """
        Load Level 4: Quotes for an episode.

        Args:
            episode_id: Episode identifier

        Returns:
            List of quote dicts with text, speaker, timestamp, etc.
        """
        cache_key = f"quotes_{episode_id}"
        try:
            data = self._get_cached(cache_key, f"quotes/{episode_id}.json")
            return data.get("quotes", [])
        except FileNotFoundError:
            return []

    def load_quotes_for_topic(self, topic_id: str) -> list[dict]:
        """
        Load quotes for a specific topic.

        Args:
            topic_id: Topic identifier (format: {episode_id}_t{n})

        Returns:
            List of quotes belonging to that topic
        """
        # Extract episode_id from topic_id
        parts = topic_id.rsplit("_t", 1)
        if len(parts) != 2:
            return []

        episode_id = parts[0]
        all_quotes = self.load_quotes(episode_id)

        return [q for q in all_quotes if q.get("topic_id") == topic_id]

    def get_episode_summary(self, episode_id: str) -> str:
        """Get formatted summary for an episode."""
        episodes = self.load_episode_index()
        ep = episodes.get(episode_id, {})
        return (
            f"**{ep.get('guest', 'Unknown')}** - {ep.get('title', 'Unknown')}\n"
            f"{ep.get('summary', 'No summary available.')}"
        )

    def get_theme_summary(self, theme_id: str) -> str:
        """Get formatted summary for a theme."""
        theme = self.load_theme(theme_id)
        return (
            f"**{theme.get('name', theme_id)}** ({theme.get('episode_count', 0)} episodes)\n"
            f"{theme.get('description', 'No description available.')}"
        )

    def clear_cache(self):
        """Clear the in-memory cache."""
        self._cache.clear()

    def get_stats(self) -> dict:
        """Get index statistics."""
        episodes = self.load_episode_index()
        themes = self.load_theme_list()

        total_topics = 0
        total_quotes = 0

        for ep_id in episodes.keys():
            topics = self.load_topics(ep_id)
            quotes = self.load_quotes(ep_id)
            total_topics += len(topics)
            total_quotes += len(quotes)

        return {
            "total_episodes": len(episodes),
            "total_themes": len(themes),
            "total_topics": total_topics,
            "total_quotes": total_quotes,
            "cache_size": len(self._cache),
        }

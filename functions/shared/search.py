"""
Azure AI Search client for hybrid search (vector + keyword + semantic).
"""

import os
from typing import Optional
from azure.search.documents import SearchClient as AzureSearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.models import VectorizedQuery
from azure.core.credentials import AzureKeyCredential

from .embeddings import EmbeddingClient
from .chunking import Chunk


class SearchClient:
    """
    Azure AI Search client with hybrid search capabilities.

    Supports:
    - Vector similarity search
    - Keyword (BM25) search
    - Semantic ranking
    - Metadata filtering

    Usage:
        client = SearchClient()
        results = client.hybrid_search("product-market fit", top_k=20)
    """

    def __init__(
        self,
        endpoint: Optional[str] = None,
        api_key: Optional[str] = None,
        index_name: str = "lenny-transcripts-index",
        embedding_client: Optional[EmbeddingClient] = None,
    ):
        self.endpoint = endpoint or os.environ.get("AZURE_SEARCH_ENDPOINT")
        self.api_key = api_key or os.environ.get("AZURE_SEARCH_API_KEY")
        self.index_name = index_name
        self.credential = AzureKeyCredential(self.api_key)

        self.client = AzureSearchClient(
            endpoint=self.endpoint,
            index_name=self.index_name,
            credential=self.credential,
        )

        self.index_client = SearchIndexClient(
            endpoint=self.endpoint,
            credential=self.credential,
        )

        self.embedding_client = embedding_client or EmbeddingClient()

    def hybrid_search(
        self,
        query: str,
        top_k: int = 20,
        filters: Optional[str] = None,
        chunk_type: Optional[str] = None,
        guest: Optional[str] = None,
        keywords: Optional[list[str]] = None,
        use_semantic: bool = True,
    ) -> list[dict]:
        """
        Perform hybrid search combining vector, keyword, and semantic ranking.

        Args:
            query: Search query text
            top_k: Number of results to return
            filters: OData filter expression
            chunk_type: Filter by chunk type (topic_segment, speaker_turn, sentence_group)
            guest: Filter by guest name
            keywords: Filter by keywords (any match)
            use_semantic: Enable semantic ranking

        Returns:
            List of search results with scores
        """
        # Build filter expression
        filter_parts = []
        if filters:
            filter_parts.append(filters)
        if chunk_type:
            filter_parts.append(f"chunk_type eq '{chunk_type}'")
        if guest:
            filter_parts.append(f"guest eq '{guest}'")
        if keywords:
            keyword_filters = " or ".join(
                f"keywords/any(k: k eq '{kw}')" for kw in keywords
            )
            filter_parts.append(f"({keyword_filters})")

        filter_expr = " and ".join(filter_parts) if filter_parts else None

        # Get query embedding
        query_vector = self.embedding_client.get_embedding(query)

        # Build vector query
        vector_query = VectorizedQuery(
            vector=query_vector,
            k_nearest_neighbors=top_k,
            fields="content_vector",
        )

        # Execute search
        search_kwargs = {
            "search_text": query,
            "vector_queries": [vector_query],
            "top": top_k,
            "select": [
                "id", "chunk_id", "transcript_id", "guest", "title",
                "youtube_url", "video_id", "publish_date", "keywords",
                "speaker", "timestamp_start", "timestamp_end",
                "content", "chunk_sequence", "chunk_type"
            ],
        }

        if filter_expr:
            search_kwargs["filter"] = filter_expr

        if use_semantic:
            search_kwargs["query_type"] = "semantic"
            search_kwargs["semantic_configuration_name"] = "semantic-config"

        results = self.client.search(**search_kwargs)

        return [
            {
                **dict(result),
                "@search.score": result["@search.score"],
                "@search.reranker_score": result.get("@search.reranker_score"),
            }
            for result in results
        ]

    def vector_search(
        self,
        query: str,
        top_k: int = 50,
        filters: Optional[str] = None,
    ) -> list[dict]:
        """
        Pure vector similarity search.

        Args:
            query: Search query text
            top_k: Number of results
            filters: OData filter expression

        Returns:
            List of search results
        """
        query_vector = self.embedding_client.get_embedding(query)

        vector_query = VectorizedQuery(
            vector=query_vector,
            k_nearest_neighbors=top_k,
            fields="content_vector",
        )

        search_kwargs = {
            "vector_queries": [vector_query],
            "top": top_k,
            "select": [
                "id", "chunk_id", "transcript_id", "guest", "title",
                "youtube_url", "speaker", "timestamp_start",
                "content", "chunk_type"
            ],
        }

        if filters:
            search_kwargs["filter"] = filters

        results = self.client.search(**search_kwargs)

        return [dict(result) for result in results]

    def keyword_search(
        self,
        query: str,
        top_k: int = 20,
        filters: Optional[str] = None,
    ) -> list[dict]:
        """
        Traditional keyword (BM25) search.

        Args:
            query: Search query text
            top_k: Number of results
            filters: OData filter expression

        Returns:
            List of search results
        """
        search_kwargs = {
            "search_text": query,
            "top": top_k,
            "select": [
                "id", "chunk_id", "transcript_id", "guest", "title",
                "youtube_url", "speaker", "timestamp_start",
                "content", "chunk_type"
            ],
        }

        if filters:
            search_kwargs["filter"] = filters

        results = self.client.search(**search_kwargs)

        return [dict(result) for result in results]

    def upload_chunks(self, chunks: list[Chunk]) -> dict:
        """
        Upload chunks to the search index.

        Args:
            chunks: List of Chunk objects to upload

        Returns:
            Upload result summary
        """
        documents = []
        for chunk in chunks:
            doc = chunk.to_dict()
            # Add embedding
            doc["content_vector"] = self.embedding_client.get_embedding(chunk.content)
            documents.append(doc)

        result = self.client.upload_documents(documents)

        return {
            "total": len(documents),
            "succeeded": sum(1 for r in result if r.succeeded),
            "failed": sum(1 for r in result if not r.succeeded),
        }

    def upload_chunks_batch(
        self,
        chunks: list[Chunk],
        batch_size: int = 100,
    ) -> dict:
        """
        Upload chunks with batched embedding generation.

        More efficient for large numbers of chunks.

        Args:
            chunks: List of Chunk objects
            batch_size: Batch size for embedding generation

        Returns:
            Upload result summary
        """
        total_succeeded = 0
        total_failed = 0

        for i in range(0, len(chunks), batch_size):
            batch = chunks[i:i + batch_size]

            # Batch generate embeddings
            texts = [c.content for c in batch]
            embeddings = self.embedding_client.get_embeddings_batch(texts, batch_size)

            # Prepare documents
            documents = []
            for chunk, embedding in zip(batch, embeddings):
                doc = chunk.to_dict()
                doc["content_vector"] = embedding
                documents.append(doc)

            # Upload batch
            result = self.client.upload_documents(documents)
            total_succeeded += sum(1 for r in result if r.succeeded)
            total_failed += sum(1 for r in result if not r.succeeded)

        return {
            "total": len(chunks),
            "succeeded": total_succeeded,
            "failed": total_failed,
        }

    def delete_transcript(self, transcript_id: str) -> int:
        """
        Delete all chunks for a transcript.

        Args:
            transcript_id: Transcript ID to delete

        Returns:
            Number of deleted documents
        """
        # Find all chunks for this transcript
        results = self.client.search(
            search_text="*",
            filter=f"transcript_id eq '{transcript_id}'",
            select=["id"],
            top=10000,
        )

        doc_ids = [{"id": r["id"]} for r in results]

        if doc_ids:
            self.client.delete_documents(doc_ids)

        return len(doc_ids)

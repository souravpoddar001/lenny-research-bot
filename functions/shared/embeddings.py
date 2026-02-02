"""
Embedding generation module using Azure OpenAI.

Uses text-embedding-3-small for cost-effective embeddings.
"""

import os
from typing import Optional
from openai import AzureOpenAI


class EmbeddingClient:
    """
    Azure OpenAI embedding client with batch processing support.

    Usage:
        client = EmbeddingClient()
        embedding = await client.get_embedding("text to embed")
        embeddings = await client.get_embeddings_batch(["text1", "text2", ...])
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        endpoint: Optional[str] = None,
        deployment_name: str = "text-embedding-3-small",
        api_version: str = "2024-02-01",
    ):
        self.client = AzureOpenAI(
            api_key=api_key or os.environ.get("AZURE_OPENAI_API_KEY"),
            azure_endpoint=endpoint or os.environ.get("AZURE_OPENAI_ENDPOINT"),
            api_version=api_version,
        )
        self.deployment_name = deployment_name
        self.dimensions = 1536  # text-embedding-3-small default

    def get_embedding(self, text: str) -> list[float]:
        """
        Get embedding for a single text.

        Args:
            text: Text to embed

        Returns:
            List of floats representing the embedding vector
        """
        # Truncate if too long (8191 token limit for embedding models)
        if len(text) > 30000:
            text = text[:30000]

        response = self.client.embeddings.create(
            model=self.deployment_name,
            input=text,
        )
        return response.data[0].embedding

    def get_embeddings_batch(
        self,
        texts: list[str],
        batch_size: int = 100,
    ) -> list[list[float]]:
        """
        Get embeddings for multiple texts with batching.

        Args:
            texts: List of texts to embed
            batch_size: Number of texts per API call (max 2048)

        Returns:
            List of embedding vectors
        """
        all_embeddings = []

        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]

            # Truncate long texts
            batch = [t[:30000] if len(t) > 30000 else t for t in batch]

            response = self.client.embeddings.create(
                model=self.deployment_name,
                input=batch,
            )

            # Sort by index to maintain order
            sorted_data = sorted(response.data, key=lambda x: x.index)
            batch_embeddings = [item.embedding for item in sorted_data]
            all_embeddings.extend(batch_embeddings)

        return all_embeddings

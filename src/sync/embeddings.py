"""OpenAI embedding client with batching and token counting."""

from __future__ import annotations

import logging

import tiktoken
from openai import OpenAI

from repo_sync.config import Settings
from repo_sync.models import ContentChunk

logger = logging.getLogger(__name__)

_encoder = tiktoken.get_encoding("cl100k_base")

# OpenAI embedding API limit per batch request
MAX_BATCH_SIZE = 2048
MAX_TOKENS_PER_TEXT = 8191


def _truncate_text(text: str, max_tokens: int = MAX_TOKENS_PER_TEXT) -> str:
    """Truncate text to fit within token limit."""
    tokens = _encoder.encode(text)
    if len(tokens) <= max_tokens:
        return text
    return _encoder.decode(tokens[:max_tokens])


class EmbeddingClient:
    def __init__(self, settings: Settings) -> None:
        self._client = OpenAI(api_key=settings.openai_api_key)
        self._model = settings.openai_embedding_model

    def embed_chunks(self, chunks: list[ContentChunk]) -> list[list[float]]:
        """Embed a list of chunks, batching as needed.

        Returns a list of embedding vectors in the same order as the input chunks.
        """
        texts = [_truncate_text(chunk.text_for_embedding) for chunk in chunks]
        all_embeddings: list[list[float]] = []

        for i in range(0, len(texts), MAX_BATCH_SIZE):
            batch = texts[i : i + MAX_BATCH_SIZE]
            logger.info(
                "Embedding batch %d-%d of %d",
                i,
                i + len(batch),
                len(texts),
            )
            response = self._client.embeddings.create(
                model=self._model,
                input=batch,
            )
            # Response data is sorted by index
            batch_embeddings = [item.embedding for item in response.data]
            all_embeddings.extend(batch_embeddings)

        return all_embeddings

    def embed_query(self, query: str) -> list[float]:
        """Embed a single query string for search."""
        text = _truncate_text(query)
        response = self._client.embeddings.create(
            model=self._model,
            input=[text],
        )
        return response.data[0].embedding

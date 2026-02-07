"""Qdrant collection management and point upsert/delete."""

from __future__ import annotations

import logging

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PayloadSchemaType,
    PointStruct,
    VectorParams,
)

from config import Settings
from models import CollectionName, ContentChunk

logger = logging.getLogger(__name__)

PAYLOAD_INDEXES: dict[CollectionName, list[tuple[str, PayloadSchemaType]]] = {
    CollectionName.CODE: [
        ("repo_name", PayloadSchemaType.KEYWORD),
        ("module_name", PayloadSchemaType.KEYWORD),
        ("chunk_type", PayloadSchemaType.KEYWORD),
        ("file_path", PayloadSchemaType.KEYWORD),
    ],
    CollectionName.MANIFESTS: [
        ("repo_name", PayloadSchemaType.KEYWORD),
        ("module_name", PayloadSchemaType.KEYWORD),
        ("module_category", PayloadSchemaType.KEYWORD),
    ],
    CollectionName.VIEWS: [
        ("repo_name", PayloadSchemaType.KEYWORD),
        ("module_name", PayloadSchemaType.KEYWORD),
        ("xml_id", PayloadSchemaType.KEYWORD),
        ("view_type", PayloadSchemaType.KEYWORD),
        ("view_model", PayloadSchemaType.KEYWORD),
    ],
}


class QdrantLoader:
    def __init__(self, settings: Settings) -> None:
        self._client = QdrantClient(
            url=settings.qdrant_url,
            api_key=settings.qdrant_api_key,
        )
        self._dimensions = settings.embedding_dimensions

    def ensure_collections(self) -> None:
        """Create all collections if they don't exist, and set up payload indexes."""
        existing = {c.name for c in self._client.get_collections().collections}

        for collection in CollectionName:
            if collection.value not in existing:
                logger.info("Creating collection: %s", collection.value)
                self._client.create_collection(
                    collection_name=collection.value,
                    vectors_config=VectorParams(
                        size=self._dimensions,
                        distance=Distance.COSINE,
                    ),
                )

            # Create payload indexes
            for field_name, field_type in PAYLOAD_INDEXES.get(collection, []):
                try:
                    self._client.create_payload_index(
                        collection_name=collection.value,
                        field_name=field_name,
                        field_schema=field_type,
                    )
                except Exception:
                    pass  # Index already exists

    def delete_module_points(
        self,
        repo_name: str,
        module_name: str,
    ) -> None:
        """Delete all points for a specific module across all collections."""
        for collection in CollectionName:
            try:
                self._client.delete(
                    collection_name=collection.value,
                    points_selector=Filter(
                        must=[
                            FieldCondition(
                                key="repo_name",
                                match=MatchValue(value=repo_name),
                            ),
                            FieldCondition(
                                key="module_name",
                                match=MatchValue(value=module_name),
                            ),
                        ]
                    ),
                )
            except Exception:
                logger.warning(
                    "Failed to delete points for %s/%s in %s",
                    repo_name,
                    module_name,
                    collection.value,
                )

    def upsert_chunks(
        self,
        chunks: list[ContentChunk],
        embeddings: list[list[float]],
    ) -> None:
        """Upsert chunks with their embeddings into the appropriate collections."""
        # Group by collection
        by_collection: dict[CollectionName, list[PointStruct]] = {}

        for chunk, vector in zip(chunks, embeddings):
            point = PointStruct(
                id=chunk.point_id,
                vector=vector,
                payload=chunk.payload(),
            )
            by_collection.setdefault(chunk.collection, []).append(point)

        for collection, points in by_collection.items():
            # Qdrant accepts up to ~100 points per upsert for efficiency
            batch_size = 100
            for i in range(0, len(points), batch_size):
                batch = points[i : i + batch_size]
                self._client.upsert(
                    collection_name=collection.value,
                    points=batch,
                )
            logger.info(
                "Upserted %d points into %s", len(points), collection.value
            )

    def collection_stats(self) -> dict[str, int]:
        """Return point counts per collection."""
        stats = {}
        for collection in CollectionName:
            try:
                info = self._client.get_collection(collection.value)
                stats[collection.value] = info.points_count or 0
            except Exception:
                stats[collection.value] = 0
        return stats

    @property
    def client(self) -> QdrantClient:
        return self._client

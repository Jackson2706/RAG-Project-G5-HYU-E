"""Qdrant repository: versioned collections, the active alias, upserts and vector search.

Server mode (Docker Compose) is the default. Local mode (``QDRANT_PATH``) is an
embedded, single-process fallback that always performs exact search.
"""

from __future__ import annotations

from typing import Any

from qdrant_client import QdrantClient, models

# Payload fields copied to every point; indexed for filtering in server mode.
PAYLOAD_KEYWORD_FIELDS = ("doc_id", "version_id", "campus", "language", "audience", "document_type", "topics", "academic_year")
DISTANCES = {"Cosine": models.Distance.COSINE, "Dot": models.Distance.DOT, "Euclid": models.Distance.EUCLID}


class QdrantRepository:
    def __init__(self, client: QdrantClient, alias: str, local_mode: bool) -> None:
        self.client = client
        self.alias = alias
        self.local_mode = local_mode

    @classmethod
    def connect(cls, url: str, path: str | None, alias: str, api_key: str | None = None) -> QdrantRepository:
        if path:
            return cls(QdrantClient(path=path), alias, local_mode=True)
        return cls(QdrantClient(url=url, api_key=api_key, timeout=10), alias, local_mode=False)

    def ping(self) -> bool:
        self.client.get_collections()
        return True

    def collection_exists(self, name: str) -> bool:
        return self.client.collection_exists(name)

    def create_collection(self, name: str, dimension: int, distance: str, hnsw_m: int, hnsw_ef_construct: int) -> None:
        self.client.create_collection(
            collection_name=name,
            vectors_config=models.VectorParams(size=dimension, distance=DISTANCES[distance]),
            hnsw_config=models.HnswConfigDiff(m=hnsw_m, ef_construct=hnsw_ef_construct),
        )
        if not self.local_mode:  # payload indexes have no effect in local mode
            for field in PAYLOAD_KEYWORD_FIELDS:
                self.client.create_payload_index(name, field, models.PayloadSchemaType.KEYWORD)

    def delete_collection(self, name: str) -> None:
        if self.client.collection_exists(name):
            self.client.delete_collection(name)

    def upsert(self, name: str, ids: list[str], vectors: list[list[float]], payloads: list[dict[str, Any]], batch: int = 256) -> None:
        for i in range(0, len(ids), batch):
            self.client.upsert(
                collection_name=name,
                points=models.Batch(ids=ids[i : i + batch], vectors=vectors[i : i + batch], payloads=payloads[i : i + batch]),
                wait=True,
            )

    def retrieve_vectors(self, name: str, ids: list[str]) -> dict[str, list[float]]:
        if not ids or not self.client.collection_exists(name):
            return {}
        out: dict[str, list[float]] = {}
        for i in range(0, len(ids), 256):
            for p in self.client.retrieve(name, ids=ids[i : i + 256], with_vectors=True, with_payload=False):
                out[str(p.id)] = list(p.vector)  # type: ignore[arg-type]
        return out

    def count(self, name: str) -> int:
        return self.client.count(name, exact=True).count

    def all_point_ids(self, name: str) -> list[str]:
        ids, offset = [], None
        while True:
            points, offset = self.client.scroll(name, limit=512, offset=offset, with_payload=False, with_vectors=False)
            ids += [str(p.id) for p in points]
            if offset is None:
                return ids

    def vector_params(self, name: str) -> tuple[int, str]:
        params = self.client.get_collection(name).config.params.vectors
        return params.size, params.distance.value  # type: ignore[union-attr]

    def active_collection(self) -> str | None:
        for a in self.client.get_aliases().aliases:
            if a.alias_name == self.alias:
                return a.collection_name
        return None

    def point_alias_to(self, collection: str) -> None:
        """Atomically move the active alias to `collection` (delete + create in one request)."""
        ops: list[Any] = []
        if self.active_collection():
            ops.append(models.DeleteAliasOperation(delete_alias=models.DeleteAlias(alias_name=self.alias)))
        ops.append(models.CreateAliasOperation(create_alias=models.CreateAlias(collection_name=collection, alias_name=self.alias)))
        self.client.update_collection_aliases(change_aliases_operations=ops)

    def search(self, vector: list[float], limit: int, query_filter: models.Filter | None, exact: bool,
               hnsw_ef: int | None, score_threshold: float | None, collection: str | None = None) -> list[models.ScoredPoint]:  # fmt: skip
        params = None if self.local_mode else models.SearchParams(exact=exact, hnsw_ef=None if exact else hnsw_ef)
        return self.client.query_points(
            collection_name=collection or self.alias, query=vector, query_filter=query_filter, limit=limit,
            search_params=params, score_threshold=score_threshold, with_payload=True,
        ).points  # fmt: skip

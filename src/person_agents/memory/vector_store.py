import uuid
from pathlib import Path
from typing import Any

import structlog

from person_agents.config.settings import settings

logger = structlog.get_logger()


class VectorStore:
    def __init__(self, persist_dir: Path | None = None):
        self.persist_dir = persist_dir or settings.chroma_path
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        self._client: Any = None
        self._collection: Any = None

    def _ensure_client(self) -> None:
        if self._client is None:
            import chromadb
            self._client = chromadb.PersistentClient(path=str(self.persist_dir))
            self._collection = self._client.get_or_create_collection("memories")

    def add(self, text: str, metadata: dict[str, Any] | None = None) -> str:
        self._ensure_client()
        doc_id = str(uuid.uuid4())
        self._collection.add(documents=[text], ids=[doc_id], metadatas=[metadata or {}])
        return doc_id

    def query(self, text: str, n_results: int = 5) -> list[dict[str, Any]]:
        self._ensure_client()
        results = self._collection.query(query_texts=[text], n_results=n_results)
        docs = results.get("documents", [[]])[0]
        metas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]
        return [{"text": d, "metadata": m, "distance": dist} for d, m, dist in zip(docs, metas, distances)]

    def count(self) -> int:
        self._ensure_client()
        return self._collection.count()

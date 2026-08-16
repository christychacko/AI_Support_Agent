from __future__ import annotations

import chromadb
from chromadb.utils import embedding_functions

from app.config import get_settings

COLLECTION_NAME = "support_kb"

# all-MiniLM-L6-v2 runs locally on CPU -- no API key, no per-call cost.
_embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
    model_name="all-MiniLM-L6-v2"
)


def get_collection():
    settings = get_settings()
    client = chromadb.PersistentClient(path=settings.chroma_persist_dir)
    return client.get_or_create_collection(
        name=COLLECTION_NAME, embedding_function=_embedding_fn
    )


def retrieve(query: str, k: int = 4) -> list[dict]:
    collection = get_collection()
    if collection.count() == 0:
        return []
    results = collection.query(query_texts=[query], n_results=min(k, collection.count()))
    docs = results.get("documents", [[]])[0]
    metas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]
    return [
        {"text": doc, "source": meta.get("source", "unknown"), "distance": dist}
        for doc, meta, dist in zip(docs, metas, distances)
    ]

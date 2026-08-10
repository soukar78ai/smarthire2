"""
vector_store.py
Local, free semantic search over resumes using ChromaDB (embedded, on-disk)
and a local sentence-transformers embedding model. No API calls, no cost,
no rate limits - this is what makes semantic search free at 50-500 resumes.
"""
import os
from typing import Optional

import chromadb
from sentence_transformers import SentenceTransformer

CHROMA_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "chroma_db")
COLLECTION_NAME = "resumes"
EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"

_model: Optional[SentenceTransformer] = None
_client = None
_collection = None


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer(EMBEDDING_MODEL_NAME)
    return _model


def _get_collection():
    global _client, _collection
    if _collection is None:
        _client = chromadb.PersistentClient(path=CHROMA_DIR)
        _collection = _client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
    return _collection


def add_resume(resume_id: str, resume_text: str, metadata: dict) -> None:
    """
    Embed a resume's full text and store it in Chroma, keyed by resume_id.
    metadata should include at least: candidate_name, file_name, file_type.
    Re-adding the same resume_id overwrites the previous entry (upsert).
    """
    model = _get_model()
    collection = _get_collection()
    embedding = model.encode(resume_text).tolist()

    collection.upsert(
        ids=[resume_id],
        embeddings=[embedding],
        documents=[resume_text],
        metadatas=[metadata],
    )


def search(jd_text: str, top_k: int = 5) -> list[dict]:
    """
    Return the top_k resumes most semantically similar to the JD text.
    Each result: {resume_id, similarity (0-1, higher=better), resume_text, metadata}
    """
    model = _get_model()
    collection = _get_collection()

    if collection.count() == 0:
        return []

    top_k = min(top_k, collection.count())
    query_embedding = model.encode(jd_text).tolist()

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k,
    )

    output = []
    for i in range(len(results["ids"][0])):
        distance = results["distances"][0][i]  # cosine distance, 0 = identical
        similarity = max(0.0, 1.0 - distance)
        output.append(
            {
                "resume_id": results["ids"][0][i],
                "similarity": round(similarity, 4),
                "resume_text": results["documents"][0][i],
                "metadata": results["metadatas"][0][i],
            }
        )
    return output


def count_resumes() -> int:
    return _get_collection().count()


def delete_resume(resume_id: str) -> None:
    _get_collection().delete(ids=[resume_id])

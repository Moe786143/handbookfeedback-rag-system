"""
Retrieval: turns a question into an embedding, searches ChromaDB for the
most similar handbook chunks, and returns them ranked by relevance.

This is Part 2 of the assignment, steps 1-3 (embed question -> search ->
retrieve top chunks). Step 4 (generate the answer) lives in generator.py —
kept separate so retrieval can be tested and reasoned about on its own,
without needing a Groq API key at all.
"""
import chromadb
from sentence_transformers import SentenceTransformer

from app.config import CHROMA_PATH, COLLECTION_NAME, EMBEDDING_MODEL, TOP_K

# Loaded once at import time rather than per-request — loading the model
# and opening the DB connection on every API call would make each request
# noticeably slower for no benefit, since neither one changes between calls.
_model = SentenceTransformer(EMBEDDING_MODEL)
_client = chromadb.PersistentClient(path=CHROMA_PATH)


def _get_collection():
    """
    Fetches the Chroma collection, with a clear error if ingestion hasn't
    been run yet — better than a cryptic ChromaDB exception.
    """
    try:
        return _client.get_collection(COLLECTION_NAME)
    except Exception as exc:
        raise RuntimeError(
            "Handbook collection not found. Run `python run_ingest.py` first "
            "to process the handbook before asking questions."
        ) from exc


def retrieve_chunks(question: str, top_k: int = TOP_K) -> list[dict]:
    """
    Embeds the question and returns the top_k most relevant handbook chunks.

    Returns a list of {"text": str, "page": int, "distance": float},
    ordered from most to least relevant (lowest distance first).
    """
    collection = _get_collection()

    question_embedding = _model.encode([question]).tolist()

    results = collection.query(
        query_embeddings=question_embedding,
        n_results=top_k,
    )

    chunks = []
    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]

    for doc, meta, dist in zip(documents, metadatas, distances):
        chunks.append(
            {
                "text": doc,
                "page": meta.get("page"),
                "distance": dist,
            }
        )

    return chunks

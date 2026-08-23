"""
Handbook ingestion pipeline.

Run this once (or whenever the handbook changes) via run_ingest.py.
It does the four things Part 1 of the assignment asks for, in order:

    1. Load the handbook PDF
    2. Extract the text (page by page, so we can cite a page number later)
    3. Split the text into overlapping chunks
    4. Generate embeddings for each chunk and store them in ChromaDB

Kept deliberately dependency-light and readable — no LangChain — so every
step here is something you can point at and explain in one sentence.
"""
from pathlib import Path

import chromadb
from pypdf import PdfReader
from sentence_transformers import SentenceTransformer

import re

from app.config import (
    CHROMA_PATH,
    CHUNK_OVERLAP,
    CHUNK_SIZE,
    COLLECTION_NAME,
    EMBEDDING_MODEL,
    HANDBOOK_PATH,
)


def fix_letter_spaced_text(text: str) -> str:
    """
    Some pypdf versions extract this particular PDF with every letter
    separated by a single space and a double space marking real word
    boundaries, e.g. "W e  a r e" instead of "We are". Other pypdf
    versions extract the exact same PDF perfectly normally.

    Rather than assuming which situation we're in, this checks first:
    in genuinely letter-spaced text, most whitespace-separated tokens are
    a single character long. In normally-extracted text, most tokens are
    real multi-character words. Only text matching the broken pattern
    gets the aggressive fix — anything else is left alone (beyond basic
    whitespace cleanup), so this never corrupts correctly-extracted text.
    """
    tokens = text.split()
    if not tokens:
        return text.strip()

    single_char_tokens = sum(1 for t in tokens if len(t) == 1 and t.isalnum())
    single_char_ratio = single_char_tokens / len(tokens)

    if single_char_ratio < 0.4:
        # Text is already normal — just collapse newlines/extra whitespace
        # into single spaces, without touching genuine word-separating spaces.
        return re.sub(r"\s+", " ", text).strip()

    # Text matches the letter-spaced pattern — apply the boundary-marking fix.
    WORD_BOUNDARY = "\x00"
    marked = text.replace("  ", WORD_BOUNDARY).replace("\n", WORD_BOUNDARY)
    no_letter_gaps = marked.replace(" ", "")
    restored = no_letter_gaps.replace(WORD_BOUNDARY, " ")
    restored = re.sub(r" {2,}", " ", restored)
    return restored.strip()


def load_pdf_pages(pdf_path: str) -> list[dict]:
    """
    Step 1 + 2: Load the PDF and extract text, one entry per page.

    Returns a list of {"page": <1-based page number>, "text": <page text>}.
    Blank pages (e.g. section dividers with only an image) are skipped —
    there's nothing to search on an empty page.

    Text is passed through fix_letter_spaced_text() to repair the
    letter-by-letter spacing this particular PDF export produces — see
    that function's docstring for why this is necessary.
    """
    reader = PdfReader(pdf_path)
    pages = []

    for i, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        text = fix_letter_spaced_text(text)
        if text:
            pages.append({"page": i, "text": text})

    return pages


def chunk_text(pages: list[dict], chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[dict]:
    """
    Step 3: Split each page's text into overlapping word-based chunks.

    Chunking per page (rather than concatenating the whole book first) means
    every chunk already knows which page it came from — that's what lets the
    API return a "source: Page 12" instead of just an answer with no citation.

    Overlap means a sentence that gets cut in half by the chunk boundary
    still appears in full in at least one of the two chunks.

    Returns a list of {"page": int, "chunk_id": str, "text": str}.
    """
    chunks = []

    for page in pages:
        words = page["text"].split()
        step = chunk_size - overlap

        if not words:
            continue

        for start in range(0, len(words), step):
            chunk_words = words[start : start + chunk_size]
            if not chunk_words:
                continue

            chunk_text_value = " ".join(chunk_words)
            chunk_id = f"page{page['page']}_chunk{start // step}"

            chunks.append(
                {
                    "chunk_id": chunk_id,
                    "page": page["page"],
                    "text": chunk_text_value,
                }
            )

            # Stop once this chunk reaches the end of the page's words.
            if start + chunk_size >= len(words):
                break

    return chunks


def build_vector_store(
    chunks: list[dict],
    chroma_path: str = CHROMA_PATH,
    collection_name: str = COLLECTION_NAME,
    embedding_model_name: str = EMBEDDING_MODEL,
) -> None:
    """
    Step 4: Generate an embedding for every chunk and store it in ChromaDB.

    ChromaDB persists to disk at `chroma_path`, so ingestion only needs to
    run once — the API reads from this same folder on every request rather
    than re-embedding the handbook each time it starts.
    """
    print(f"Loading embedding model '{embedding_model_name}'...")
    model = SentenceTransformer(embedding_model_name)

    print(f"Embedding {len(chunks)} chunks...")
    texts = [c["text"] for c in chunks]
    embeddings = model.encode(texts, show_progress_bar=True).tolist()

    print(f"Writing to ChromaDB at '{chroma_path}'...")
    client = chromadb.PersistentClient(path=chroma_path)

    # Start clean each time ingestion runs, so re-running it after editing
    # the handbook doesn't leave stale chunks from the old version behind.
    try:
        client.delete_collection(collection_name)
    except Exception:
        pass

    collection = client.create_collection(collection_name)

    collection.add(
        ids=[c["chunk_id"] for c in chunks],
        embeddings=embeddings,
        documents=texts,
        metadatas=[{"page": c["page"]} for c in chunks],
    )

    print(f"Done. {collection.count()} chunks stored in collection '{collection_name}'.")


def run_ingestion(pdf_path: str = HANDBOOK_PATH) -> None:
    """Runs the full pipeline: load -> chunk -> embed -> store."""
    if not Path(pdf_path).exists():
        raise FileNotFoundError(
            f"Handbook not found at '{pdf_path}'. Check HANDBOOK_PATH in your .env file."
        )

    pages = load_pdf_pages(pdf_path)
    print(f"Extracted text from {len(pages)} pages.")

    chunks = chunk_text(pages)
    print(f"Split into {len(chunks)} chunks (size={CHUNK_SIZE} words, overlap={CHUNK_OVERLAP}).")

    build_vector_store(chunks)


if __name__ == "__main__":
    run_ingestion()
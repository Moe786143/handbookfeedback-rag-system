"""
Multi-source ingestion pipeline: Student Handbook (PDF) + ZAIO website.

Run this once (or whenever either source changes) via run_ingest.py.
It does what Part 1 of this assignment asks for, in order:

    1. Load the Student Handbook (PDF)
    2. Crawl and extract text from the ZAIO website
    3. Clean the website content (strip nav/header/footer — see web_scraper.py)
    4. Split both sources into chunks
    5. Generate embeddings for every chunk
    6. Store everything in the same vector database, with metadata recording
       which source each chunk came from (Handbook + page number, or
       Website + URL)

Both sources are normalised into the same shape early on — a list of
{"source", "page", "url", "text"} dicts — so chunking, embedding, and
storage don't need to know or care which source a piece of text came from.
Only the final metadata written to ChromaDB (and the API's source citation
built from it later) treats the two sources differently.
"""
import re
from pathlib import Path

import chromadb
from pypdf import PdfReader
from sentence_transformers import SentenceTransformer

from app.config import (
    CHROMA_PATH,
    CHUNK_OVERLAP,
    CHUNK_SIZE,
    COLLECTION_NAME,
    EMBEDDING_MODEL,
    HANDBOOK_PATH,
    WEBSITE_MAX_PAGES,
    WEBSITE_URL,
)
from app.web_scraper import crawl_website


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
        return re.sub(r"\s+", " ", text).strip()

    WORD_BOUNDARY = "\x00"
    marked = text.replace("  ", WORD_BOUNDARY).replace("\n", WORD_BOUNDARY)
    no_letter_gaps = marked.replace(" ", "")
    restored = no_letter_gaps.replace(WORD_BOUNDARY, " ")
    restored = re.sub(r" {2,}", " ", restored)
    return restored.strip()


def load_handbook_documents(pdf_path: str) -> list[dict]:
    """
    Loads the Student Handbook and returns one document per page, in the
    unified {"source", "page", "url", "text"} shape used by chunk_text().

    "url" is None here since a PDF page has no URL — chunk_text() and the
    metadata builder both know to only use whichever of page/url applies
    for a given source type.
    """
    reader = PdfReader(pdf_path)
    documents = []

    for i, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        text = fix_letter_spaced_text(text)
        if text:
            documents.append({"source": "Handbook", "page": i, "url": None, "text": text})

    return documents


def load_website_documents(start_url: str = WEBSITE_URL, max_pages: int = WEBSITE_MAX_PAGES) -> list[dict]:
    """
    Crawls the ZAIO website and returns one document per page, in the same
    unified shape as load_handbook_documents() — "page" is None here since
    website content is cited by URL, not a page number.
    """
    print(f"Crawling {start_url} (up to {max_pages} pages)...")
    crawled = crawl_website(start_url, max_pages=max_pages)

    return [
        {"source": "Website", "page": None, "url": page["url"], "text": page["text"]}
        for page in crawled
    ]


def chunk_text(
    documents: list[dict], chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP
) -> list[dict]:
    """
    Splits each document's text into overlapping word-based chunks.

    Chunking per document (rather than concatenating everything into one
    giant blob first) means every chunk already knows exactly which page
    or URL it came from — that's what lets the API cite "Student Handbook -
    Page 12" or a real URL instead of just returning an answer with no
    traceable source.

    Overlap means a sentence cut in half by a chunk boundary still appears
    in full in at least one of the two resulting chunks.
    """
    chunks = []

    for doc_index, doc in enumerate(documents):
        words = doc["text"].split()
        step = chunk_size - overlap

        if not words:
            continue

        for start in range(0, len(words), step):
            chunk_words = words[start : start + chunk_size]
            if not chunk_words:
                continue

            chunk_id = f"{doc['source'].lower()}_{doc_index}_chunk{start // step}"

            chunks.append(
                {
                    "chunk_id": chunk_id,
                    "source": doc["source"],
                    "page": doc["page"],
                    "url": doc["url"],
                    "text": " ".join(chunk_words),
                }
            )

            if start + chunk_size >= len(words):
                break

    return chunks


def _build_metadata(chunk: dict) -> dict:
    """
    Builds the metadata dict stored alongside each chunk's embedding.

    ChromaDB metadata values must be strings, numbers, or booleans — not
    None — so this only includes the page number for Handbook chunks and
    only the URL for Website chunks, rather than storing null placeholders
    for whichever field doesn't apply.
    """
    metadata = {"source": chunk["source"]}
    if chunk["source"] == "Handbook":
        metadata["page"] = chunk["page"]
    elif chunk["source"] == "Website":
        metadata["url"] = chunk["url"]
    return metadata


def build_vector_store(
    chunks: list[dict],
    chroma_path: str = CHROMA_PATH,
    collection_name: str = COLLECTION_NAME,
    embedding_model_name: str = EMBEDDING_MODEL,
) -> None:
    """
    Generates an embedding for every chunk (regardless of source) and
    stores them all in the same ChromaDB collection, each tagged with
    metadata identifying which source it came from.

    Storing both sources in one collection (rather than two separate
    databases) is what lets a single similarity search return the best
    matching chunk across both the handbook and the website at once —
    Part 2 asks the assistant to "search across knowledge sources", which
    is naturally satisfied by there being only one place to search.
    """
    print(f"Loading embedding model '{embedding_model_name}'...")
    model = SentenceTransformer(embedding_model_name)

    print(f"Embedding {len(chunks)} chunks...")
    texts = [c["text"] for c in chunks]
    embeddings = model.encode(texts, show_progress_bar=True).tolist()

    print(f"Writing to ChromaDB at '{chroma_path}'...")
    client = chromadb.PersistentClient(path=chroma_path)

    try:
        client.delete_collection(collection_name)
    except Exception:
        pass

    collection = client.create_collection(collection_name)

    collection.add(
        ids=[c["chunk_id"] for c in chunks],
        embeddings=embeddings,
        documents=texts,
        metadatas=[_build_metadata(c) for c in chunks],
    )

    print(f"Done. {collection.count()} chunks stored in collection '{collection_name}'.")


def run_ingestion(
    pdf_path: str = HANDBOOK_PATH,
    website_url: str = WEBSITE_URL,
    website_max_pages: int = WEBSITE_MAX_PAGES,
) -> None:
    """Runs the full pipeline across both sources: load -> chunk -> embed -> store."""
    if not Path(pdf_path).exists():
        raise FileNotFoundError(
            f"Handbook not found at '{pdf_path}'. Check HANDBOOK_PATH in your .env file."
        )

    handbook_docs = load_handbook_documents(pdf_path)
    print(f"Extracted text from {len(handbook_docs)} handbook pages.")

    website_docs = load_website_documents(website_url, website_max_pages)
    print(f"Crawled and extracted text from {len(website_docs)} website pages.")

    all_documents = handbook_docs + website_docs

    chunks = chunk_text(all_documents)
    handbook_chunk_count = sum(1 for c in chunks if c["source"] == "Handbook")
    website_chunk_count = sum(1 for c in chunks if c["source"] == "Website")
    print(
        f"Split into {len(chunks)} chunks total "
        f"({handbook_chunk_count} from handbook, {website_chunk_count} from website)."
    )

    build_vector_store(chunks)


if __name__ == "__main__":
    run_ingestion()

"""
Unit tests for the RAG system.

Split into three groups matching the assignment's own parts:
  - Ingestion (chunking logic — doesn't need the vector DB or an API key)
  - API contract (request validation, error handling — mocks out the
    actual retrieval/generation so tests run fast and don't need a live
    Groq key or a populated ChromaDB)
  - A note on end-to-end testing, which belongs in test_end_to_end.py
    once the handbook has actually been ingested.

Run with:  pytest
"""
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.ingest import chunk_text
from app.main import app

client = TestClient(app)


# --------------------------------------------------------------------------
# Ingestion tests — pure logic, no external dependencies
# --------------------------------------------------------------------------


def test_chunk_text_splits_long_page_into_multiple_chunks():
    """A page with more words than chunk_size should produce >1 chunk."""
    long_text = " ".join(f"word{i}" for i in range(500))
    pages = [{"page": 1, "text": long_text}]

    chunks = chunk_text(pages, chunk_size=100, overlap=20)

    assert len(chunks) > 1
    assert all(c["page"] == 1 for c in chunks)


def test_chunk_text_keeps_short_page_as_one_chunk():
    """A page shorter than chunk_size should stay as a single chunk."""
    short_text = "This is a short page with only a few words."
    pages = [{"page": 5, "text": short_text}]

    chunks = chunk_text(pages, chunk_size=100, overlap=20)

    assert len(chunks) == 1
    assert chunks[0]["page"] == 5
    assert chunks[0]["text"] == short_text


def test_chunk_text_preserves_page_numbers_across_multiple_pages():
    """Chunks must remember which page they came from — this is what
    lets the API cite a source page in its response."""
    pages = [
        {"page": 1, "text": "Content from page one."},
        {"page": 2, "text": "Content from page two."},
    ]

    chunks = chunk_text(pages, chunk_size=50, overlap=5)
    pages_seen = {c["page"] for c in chunks}

    assert pages_seen == {1, 2}


def test_chunk_text_handles_empty_pages_list():
    """Ingesting a document with no pages shouldn't raise an exception."""
    assert chunk_text([]) == []


# --------------------------------------------------------------------------
# API contract tests — mock retrieval/generation so these run without a
# live Groq key or a populated ChromaDB collection.
# --------------------------------------------------------------------------


def test_root_endpoint_reports_healthy():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_ask_rejects_missing_question_field():
    """Part 5: the API must handle invalid requests gracefully — a request
    body with no 'question' key should return 422, not crash."""
    response = client.post("/ask", json={})
    assert response.status_code == 422


def test_ask_rejects_empty_question_string():
    response = client.post("/ask", json={"question": ""})
    assert response.status_code == 422


def test_ask_rejects_whitespace_only_question():
    response = client.post("/ask", json={"question": "   "})
    assert response.status_code == 422


def test_ask_rejects_malformed_json():
    """Sending a body that isn't valid JSON at all should not crash the
    server — FastAPI/Starlette returns 422 for this automatically."""
    response = client.post(
        "/ask",
        content=b"{not valid json",
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 422


@patch("app.main.generate_answer")
@patch("app.main.retrieve_chunks")
def test_ask_returns_answer_and_source_on_success(mock_retrieve, mock_generate):
    """With retrieval and generation mocked, confirm the endpoint wires
    everything together correctly and returns the expected JSON shape."""
    mock_retrieve.return_value = [
        {"text": "Fees must be paid before orientation day.", "page": 16, "distance": 0.1}
    ]
    mock_generate.return_value = "Fees must be paid in full before orientation day."

    response = client.post("/ask", json={"question": "When must fees be paid?"})

    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == "Fees must be paid in full before orientation day."
    assert body["source"] == "Page 16"


@patch("app.main.generate_answer")
@patch("app.main.retrieve_chunks")
def test_ask_returns_not_available_source_when_llm_cannot_answer(
    mock_retrieve, mock_generate
):
    """When the handbook doesn't cover a question, the source should be
    N/A rather than pointing at an irrelevant page."""
    from app.config import NOT_FOUND_MESSAGE

    mock_retrieve.return_value = [
        {"text": "Unrelated handbook content.", "page": 3, "distance": 0.9}
    ]
    mock_generate.return_value = NOT_FOUND_MESSAGE

    response = client.post(
        "/ask", json={"question": "What is the capital of France?"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == NOT_FOUND_MESSAGE
    assert body["source"] == "N/A"


@patch("app.main.retrieve_chunks")
def test_ask_returns_503_when_handbook_not_ingested(mock_retrieve):
    """If run_ingest.py hasn't been run yet, the API should fail clearly
    rather than with an obscure ChromaDB error."""
    mock_retrieve.side_effect = RuntimeError(
        "Handbook collection not found. Run `python run_ingest.py` first."
    )

    response = client.post("/ask", json={"question": "What are the fees?"})

    assert response.status_code == 503

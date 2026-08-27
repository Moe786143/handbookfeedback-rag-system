"""
Unit tests for the multi-source RAG system (Student Handbook + ZAIO website).

Split into groups:
  - Ingestion (chunking + metadata logic — pure functions, no external deps)
  - Web scraper (HTML cleaning + domain filtering — pure functions, no
    actual network calls, so these run offline)
  - Generator (source citation formatting for each source type)
  - API contract (request validation, error handling — mocks out actual
    retrieval/generation so tests run fast without a live Groq key or a
    populated ChromaDB collection)

Run with:  pytest
"""
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.generator import build_context, pick_source
from app.ingest import _build_metadata, chunk_text
from app.main import app
from app.web_scraper import _is_crawlable, _same_domain, clean_page_text

client = TestClient(app)


# --------------------------------------------------------------------------
# Ingestion tests — multi-source chunking and metadata
# --------------------------------------------------------------------------


def test_chunk_text_preserves_source_type():
    """Chunks must remember whether they came from the Handbook or Website —
    this is what makes correctly-formatted citations possible downstream."""
    documents = [
        {"source": "Handbook", "page": 16, "url": None, "text": "Fees information here."},
        {"source": "Website", "page": None, "url": "https://www.zaio.io/bootcamps", "text": "Bootcamp information here."},
    ]

    chunks = chunk_text(documents, chunk_size=50, overlap=5)
    sources_seen = {c["source"] for c in chunks}

    assert sources_seen == {"Handbook", "Website"}


def test_chunk_text_preserves_page_for_handbook_chunks():
    documents = [{"source": "Handbook", "page": 16, "url": None, "text": "Fee content here."}]
    chunks = chunk_text(documents, chunk_size=50, overlap=5)

    assert all(c["page"] == 16 for c in chunks)
    assert all(c["url"] is None for c in chunks)


def test_chunk_text_preserves_url_for_website_chunks():
    documents = [
        {"source": "Website", "page": None, "url": "https://www.zaio.io/bootcamps", "text": "Bootcamp content here."}
    ]
    chunks = chunk_text(documents, chunk_size=50, overlap=5)

    assert all(c["url"] == "https://www.zaio.io/bootcamps" for c in chunks)
    assert all(c["page"] is None for c in chunks)


def test_build_metadata_excludes_none_values():
    """ChromaDB rejects None as a metadata value — the metadata builder
    must only include the field that actually applies to each source."""
    handbook_chunk = {"source": "Handbook", "page": 16, "url": None}
    website_chunk = {"source": "Website", "page": None, "url": "https://www.zaio.io/bootcamps"}

    handbook_meta = _build_metadata(handbook_chunk)
    website_meta = _build_metadata(website_chunk)

    assert None not in handbook_meta.values()
    assert None not in website_meta.values()
    assert handbook_meta == {"source": "Handbook", "page": 16}
    assert website_meta == {"source": "Website", "url": "https://www.zaio.io/bootcamps"}


# --------------------------------------------------------------------------
# Web scraper tests — pure logic, no actual network calls
# --------------------------------------------------------------------------


def test_clean_page_text_removes_navigation():
    html = "<html><body><nav><a href='/x'>Menu</a></nav><main><p>Real content</p></main></body></html>"
    cleaned = clean_page_text(html)

    assert "Real content" in cleaned
    assert "Menu" not in cleaned


def test_clean_page_text_removes_footer():
    html = "<html><body><main><p>Real content</p></main><footer><p>Copyright 2026</p></footer></body></html>"
    cleaned = clean_page_text(html)

    assert "Real content" in cleaned
    assert "Copyright" not in cleaned


def test_clean_page_text_removes_scripts_and_styles():
    html = "<html><head><script>track()</script><style>.a{color:red}</style></head><body><p>Content</p></body></html>"
    cleaned = clean_page_text(html)

    assert "Content" in cleaned
    assert "track()" not in cleaned
    assert "color:red" not in cleaned


def test_same_domain_accepts_matching_host():
    assert _same_domain("https://www.zaio.io/bootcamps", "www.zaio.io") is True


def test_same_domain_rejects_subdomain():
    """A different subdomain (applications.zaio.io) should not be treated
    as the same site as www.zaio.io — the crawler must not wander onto it."""
    assert _same_domain("https://applications.zaio.io/apply", "www.zaio.io") is False


def test_same_domain_rejects_external_site():
    assert _same_domain("https://discord.gg/invite", "www.zaio.io") is False


def test_is_crawlable_rejects_mailto():
    assert _is_crawlable("mailto:hello@zaio.io") is False


def test_is_crawlable_rejects_tel():
    assert _is_crawlable("tel:+27213006808") is False


def test_is_crawlable_rejects_binary_files():
    assert _is_crawlable("https://www.zaio.io/logo.png") is False
    assert _is_crawlable("https://www.zaio.io/handbook.pdf") is False


def test_is_crawlable_accepts_normal_page():
    assert _is_crawlable("https://www.zaio.io/bootcamps") is True


# --------------------------------------------------------------------------
# Generator tests — source citation formatting
# --------------------------------------------------------------------------


def test_pick_source_formats_handbook_citation():
    chunk = {"source": "Handbook", "page": 16, "url": None, "text": "..."}
    assert pick_source([chunk], "Some answer") == "Student Handbook - Page 16"


def test_pick_source_formats_website_citation():
    chunk = {"source": "Website", "page": None, "url": "https://www.zaio.io/bootcamps", "text": "..."}
    assert pick_source([chunk], "Some answer") == "https://www.zaio.io/bootcamps"


def test_pick_source_returns_na_when_not_found():
    from app.config import NOT_FOUND_MESSAGE

    chunk = {"source": "Handbook", "page": 16, "url": None, "text": "..."}
    assert pick_source([chunk], NOT_FOUND_MESSAGE) == "N/A"


def test_pick_source_returns_na_for_empty_chunks():
    assert pick_source([], "anything") == "N/A"


def test_build_context_labels_each_chunk_by_source():
    handbook_chunk = {"source": "Handbook", "page": 16, "url": None, "text": "Fee info"}
    website_chunk = {"source": "Website", "page": None, "url": "https://www.zaio.io/bootcamps", "text": "Bootcamp info"}

    context = build_context([handbook_chunk, website_chunk])

    assert "Student Handbook - Page 16" in context
    assert "ZAIO Website - https://www.zaio.io/bootcamps" in context


# --------------------------------------------------------------------------
# API contract tests — mock retrieval/generation so these run without a
# live Groq key or a populated ChromaDB collection.
# --------------------------------------------------------------------------


def test_root_endpoint_reports_healthy():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_ask_rejects_missing_question_field():
    response = client.post("/ask", json={})
    assert response.status_code == 422


def test_ask_rejects_empty_question_string():
    response = client.post("/ask", json={"question": ""})
    assert response.status_code == 422


def test_ask_rejects_whitespace_only_question():
    response = client.post("/ask", json={"question": "   "})
    assert response.status_code == 422


def test_ask_rejects_malformed_json():
    response = client.post(
        "/ask",
        content=b"{not valid json",
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 422


@patch("app.main.generate_answer")
@patch("app.main.retrieve_chunks")
def test_ask_returns_handbook_citation_on_success(mock_retrieve, mock_generate):
    mock_retrieve.return_value = [
        {"text": "Fees are R38,950.", "source": "Handbook", "page": 16, "url": None, "distance": 0.1}
    ]
    mock_generate.return_value = "The total fees are R38,950."

    response = client.post("/ask", json={"question": "What are the fees?"})

    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == "The total fees are R38,950."
    assert body["source"] == "Student Handbook - Page 16"


@patch("app.main.generate_answer")
@patch("app.main.retrieve_chunks")
def test_ask_returns_website_url_on_success(mock_retrieve, mock_generate):
    mock_retrieve.return_value = [
        {
            "text": "Full Stack AI Engineer bootcamp.",
            "source": "Website",
            "page": None,
            "url": "https://www.zaio.io/fullstack-ai-engineer-bootcamp",
            "distance": 0.1,
        }
    ]
    mock_generate.return_value = "ZAIO offers a Full Stack AI Engineer bootcamp."

    response = client.post("/ask", json={"question": "What courses does ZAIO offer?"})

    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "https://www.zaio.io/fullstack-ai-engineer-bootcamp"


@patch("app.main.generate_answer")
@patch("app.main.retrieve_chunks")
def test_ask_returns_not_available_source_when_llm_cannot_answer(
    mock_retrieve, mock_generate
):
    from app.config import NOT_FOUND_MESSAGE

    mock_retrieve.return_value = [
        {"text": "Unrelated content.", "source": "Handbook", "page": 3, "url": None, "distance": 0.9}
    ]
    mock_generate.return_value = NOT_FOUND_MESSAGE

    response = client.post("/ask", json={"question": "What is the capital of France?"})

    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == NOT_FOUND_MESSAGE
    assert body["source"] == "N/A"


@patch("app.main.retrieve_chunks")
def test_ask_returns_503_when_knowledge_base_not_ingested(mock_retrieve):
    mock_retrieve.side_effect = RuntimeError(
        "Knowledge base not found. Run `python run_ingest.py` first."
    )

    response = client.post("/ask", json={"question": "What are the fees?"})

    assert response.status_code == 503

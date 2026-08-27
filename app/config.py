"""
Central configuration for the RAG system.
Reads settings from environment variables (via a .env file in development),
so nothing sensitive — like the Groq API key — is hard-coded into the source.
"""
import os
from dotenv import load_dotenv

load_dotenv()

# --- Groq (LLM) ---
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")

# --- Embeddings ---
# all-MiniLM-L6-v2 is small, fast, and free — runs locally, no API needed.
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")

# --- Vector store ---
CHROMA_PATH = os.getenv("CHROMA_PATH", "./chroma_db")
COLLECTION_NAME = os.getenv("COLLECTION_NAME", "handbook")

# --- Chunking ---
# Word-based chunking with overlap so an answer that spans a chunk boundary
# isn't lost entirely from either chunk.
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "220"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "40"))

# --- Retrieval ---
TOP_K = int(os.getenv("TOP_K", "4"))

# --- Source document (PDF) ---
HANDBOOK_PATH = os.getenv("HANDBOOK_PATH", "./data/handbook.pdf")

# --- Source document (Website) ---
WEBSITE_URL = os.getenv("WEBSITE_URL", "https://www.zaio.io")
WEBSITE_MAX_PAGES = int(os.getenv("WEBSITE_MAX_PAGES", "12"))

# Message returned when neither knowledge source covers the question.
# This exact wording is what the assignment specifies.
NOT_FOUND_MESSAGE = (
    "I could not find that information in the available knowledge base."
)

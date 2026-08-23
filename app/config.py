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
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")

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

# --- Source document ---
HANDBOOK_PATH = os.getenv("HANDBOOK_PATH", "./data/handbook.pdf")

# Message returned when the handbook genuinely doesn't cover the question.
NOT_FOUND_MESSAGE = (
    "I don't know — that information isn't available in the student handbook."
)

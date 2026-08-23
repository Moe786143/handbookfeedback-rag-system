"""
Run this once to process the handbook and build the vector database.

    python run_ingest.py

Re-run it any time the handbook PDF changes — it rebuilds the collection
from scratch each time rather than appending to the old one.
"""
from app.ingest import run_ingestion

if __name__ == "__main__":
    run_ingestion()

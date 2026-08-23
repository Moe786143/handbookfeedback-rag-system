"""
API layer — Part 3 and Part 5 of the assignment.

Exposes a single endpoint:

    POST /ask
    {"question": "What is the attendance requirement?"}

    -> {"answer": "...", "source": "Page 12"}

Part 5 asks for the API to accept JSON, return JSON, and handle invalid
requests gracefully — that's handled below with explicit validation and a
custom exception handler, rather than letting FastAPI's default 500 errors
leak through with a stack trace.
"""
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator

from app.generator import generate_answer, pick_source
from app.retriever import retrieve_chunks

app = FastAPI(
    title="Student Handbook Assistant",
    description="RAG-based API that answers student questions from the bootcamp handbook.",
    version="1.0.0",
)


class AskRequest(BaseModel):
    """Request body for POST /ask."""

    question: str = Field(..., min_length=1, description="The student's question.")

    @field_validator("question")
    @classmethod
    def question_not_blank(cls, value: str) -> str:
        # min_length=1 catches an empty string, but not one that's just
        # whitespace — so blank submissions are rejected either way.
        if not value.strip():
            raise ValueError("question must not be empty or only whitespace")
        return value


class AskResponse(BaseModel):
    """Response body for POST /ask."""

    answer: str
    source: str


@app.get("/")
def root():
    """Basic liveness check — confirms the API is up."""
    return {"status": "ok", "message": "Student Handbook Assistant is running."}


@app.post("/ask", response_model=AskResponse)
def ask(request: AskRequest):
    """
    Answers a student's question using the handbook.

    Pipeline: embed the question -> retrieve the most relevant chunks ->
    ask the LLM to answer using only those chunks -> return the answer
    with a page citation.
    """
    try:
        chunks = retrieve_chunks(request.question)
    except RuntimeError as exc:
        # Raised by retriever.py if ingestion hasn't been run yet.
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    try:
        answer = generate_answer(request.question, chunks)
    except RuntimeError as exc:
        # Raised by generator.py if GROQ_API_KEY is missing.
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        # Anything else from the Groq call (rate limit, network issue, etc.)
        # — surfaced as a clean 502 rather than a raw traceback.
        raise HTTPException(
            status_code=502, detail=f"The language model request failed: {exc}"
        ) from exc

    source = pick_source(chunks, answer)

    return AskResponse(answer=answer, source=source)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request, exc):
    """
    Last-resort safety net — Part 5 asks for invalid requests to be handled
    gracefully. Anything not already caught above still returns clean JSON
    with a 500 status instead of an unhandled server crash.
    """
    return JSONResponse(
        status_code=500,
        content={"detail": "An unexpected error occurred. Please try again."},
    )

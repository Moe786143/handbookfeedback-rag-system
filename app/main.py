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
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator

from app.generator import generate_answer, pick_source, split_answer_and_citation
from app.retriever import retrieve_chunks

app = FastAPI(
    title="Student Handbook Assistant",
    description="RAG-based API that answers student questions from the bootcamp handbook.",
    version="1.0.0",
)

# Allows the React frontend (running on a different port during development)
# to call this API from the browser. Browsers block cross-origin requests
# by default unless the server explicitly opts in via these headers.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class AskRequest(BaseModel):
    """Request body for POST /ask."""

    question: str = Field(..., min_length=1, description="The student's question.")

    @field_validator("question")
    @classmethod
    def question_not_blank(cls, value: str) -> str:
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
    Answers a student's question using both knowledge sources.

    Pipeline: embed the question -> retrieve the most relevant chunks ->
    ask the LLM to answer using only those chunks -> return the answer
    with the correct citation.
    """
    try:
        chunks = retrieve_chunks(request.question)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    try:
        raw_response = generate_answer(request.question, chunks)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=502, detail=f"The language model request failed: {exc}"
        ) from exc

    answer, claimed_label = split_answer_and_citation(raw_response)
    source = pick_source(chunks, answer, claimed_label)

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

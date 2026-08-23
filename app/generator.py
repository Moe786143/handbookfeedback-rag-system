"""
Answer generation: takes the retrieved handbook chunks and the student's
question, and asks an LLM (via Groq) to answer using only that context.

This is Part 2, step 4 of the assignment — "use the retrieved context to
generate the answer." The system prompt is what enforces the assignment's
groundedness requirement: if the handbook doesn't cover it, say so instead
of guessing.
"""
from groq import Groq

from app.config import GROQ_API_KEY, GROQ_MODEL, NOT_FOUND_MESSAGE

SYSTEM_PROMPT = """You are a helpful assistant that answers student questions \
using ONLY the provided handbook excerpts as your source of truth.

Rules:
- Answer using only the information in the excerpts below. Do not use \
outside knowledge, even if you know the general answer.
- If the excerpts do not contain enough information to answer the \
question, respond with exactly: "{not_found}"
- Keep answers concise and direct — a sentence or two is usually enough.
- Do not mention "the excerpts" or "the context" in your answer; just \
answer as if you know the handbook.
""".format(not_found=NOT_FOUND_MESSAGE)


def build_context(chunks: list[dict]) -> str:
    """
    Formats retrieved chunks into a labelled block the model can cite from.
    Each chunk is tagged with its page number so the model's answer stays
    traceable back to a specific part of the handbook.
    """
    if not chunks:
        return "(No relevant excerpts were found in the handbook.)"

    parts = []
    for chunk in chunks:
        parts.append(f"[Page {chunk['page']}]\n{chunk['text']}")

    return "\n\n---\n\n".join(parts)


def generate_answer(question: str, chunks: list[dict]) -> str:
    """
    Sends the question and retrieved context to Groq and returns the
    generated answer as a plain string.
    """
    if not GROQ_API_KEY:
        raise RuntimeError(
            "GROQ_API_KEY is not set. Add it to your .env file — "
            "get a free key at https://console.groq.com/keys"
        )

    context = build_context(chunks)

    user_message = (
        f"Handbook excerpts:\n\n{context}\n\n"
        f"Question: {question}"
    )

    client = Groq(api_key=GROQ_API_KEY)

    response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        temperature=0.1,  # Low temperature — we want faithful answers, not creative ones.
        max_tokens=300,
    )

    return response.choices[0].message.content.strip()


def pick_source(chunks: list[dict], answer: str) -> str:
    """
    Chooses which page to cite as the source for the response.

    If the model said it doesn't know, there's no real source to cite.
    Otherwise, the top retrieved chunk (chunks are already ranked by
    relevance) is the best single citation to show alongside the answer.
    """
    if not chunks or answer.strip() == NOT_FOUND_MESSAGE:
        return "N/A"

    return f"Page {chunks[0]['page']}"

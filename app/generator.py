"""
Answer generation: takes the retrieved chunks (from either the Handbook or
the Website, or both) and the student's question, and asks an LLM (via
Groq) to answer using only that context.

This is Part 2, step 4 of the assignment — "generate an answer using the
retrieved context only." The system prompt is what enforces the
assignment's groundedness requirement: if neither source covers the
question, say so instead of guessing.

A note on source citation: with two knowledge sources feeding the same
question, the single nearest chunk by embedding distance isn't always the
one the model actually drew its answer from — a handbook fact and a
similar-sounding website fact can both be in the retrieved set, and the
model may reasonably use whichever states things more directly, not
necessarily the top-ranked one. To keep the citation accurate rather than
just "the closest match," the model is asked to state which specific
excerpt it used, and that claim is checked against the real retrieved
chunks before being trusted — a wrong or hallucinated citation falls back
to the top-ranked chunk instead of being taken at face value.
"""
from groq import Groq

from app.config import GROQ_API_KEY, GROQ_MODEL, NOT_FOUND_MESSAGE

SOURCE_MARKER = "SOURCE:"

SYSTEM_PROMPT = """You are a helpful assistant that answers student questions \
using ONLY the provided excerpts as your source of truth. The excerpts may \
come from the Student Handbook or the ZAIO website — treat both as equally \
valid sources of truth.

Rules:
- Answer using only the information in the excerpts below. Do not use \
outside knowledge, even if you know the general answer.
- If the excerpts do not contain enough information to answer the \
question, respond with exactly: "{not_found}"
- Keep answers concise and direct — a sentence or two is usually enough.
- Do not mention "the excerpts" or "the context" in your answer; just \
answer as if you already know this information.
- After your answer, on its own new line, write "{marker}" followed by \
the exact label (copied character-for-character, including the square \
brackets) of the ONE excerpt you actually used to answer. If you \
responded with the not-found message, write "{marker} NONE" instead.
""".format(not_found=NOT_FOUND_MESSAGE, marker=SOURCE_MARKER)


def _label_chunk(chunk: dict) -> str:
    """
    Builds a human-readable label for a chunk so the LLM's context block
    shows which source and location each excerpt came from — this is what
    lets the model point back to a specific excerpt by name.
    """
    if chunk["source"] == "Handbook":
        return f"Student Handbook - Page {chunk['page']}"
    if chunk["source"] == "Website":
        return f"ZAIO Website - {chunk['url']}"
    return "Unknown source"


def build_context(chunks: list[dict]) -> str:
    """
    Formats retrieved chunks into a labelled block the model can cite from,
    regardless of which source each one came from.
    """
    if not chunks:
        return "(No relevant excerpts were found in either knowledge source.)"

    parts = [f"[{_label_chunk(chunk)}]\n{chunk['text']}" for chunk in chunks]
    return "\n\n---\n\n".join(parts)


def generate_answer(question: str, chunks: list[dict]) -> str:
    """
    Sends the question and retrieved context to Groq and returns the raw
    response text, including the trailing "SOURCE: ..." line the model
    was asked to add. Callers should pass this through split_answer_and_citation()
    before showing the answer to a user.
    """
    if not GROQ_API_KEY:
        raise RuntimeError(
            "GROQ_API_KEY is not set. Add it to your .env file — "
            "get a free key at https://console.groq.com/keys"
        )

    context = build_context(chunks)

    user_message = f"Excerpts:\n\n{context}\n\nQuestion: {question}"

    client = Groq(api_key=GROQ_API_KEY)

    response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        temperature=0.1,
        max_tokens=2048,
    )

    return response.choices[0].message.content.strip()


def split_answer_and_citation(raw_response: str) -> tuple[str, str | None]:
    """
    Separates the model's visible answer from the trailing "SOURCE: ..."
    line it was asked to add.
    """
    if SOURCE_MARKER not in raw_response:
        return raw_response.strip(), None

    answer_part, _, claim_part = raw_response.rpartition(SOURCE_MARKER)
    claimed_label = claim_part.strip()

    if claimed_label.upper() == "NONE":
        claimed_label = None

    return answer_part.strip(), claimed_label


def _format_final_source(chunk: dict) -> str:
    """
    Formats a chunk's citation the way it should actually appear in the
    API response: "Student Handbook - Page 18" for Handbook chunks, or
    just the bare URL for Website chunks.
    """
    if chunk["source"] == "Handbook":
        return f"Student Handbook - Page {chunk['page']}"
    if chunk["source"] == "Website":
        return chunk["url"]
    return "N/A"


def pick_source(chunks: list[dict], answer: str, claimed_label: str | None = None) -> str:
    """
    Chooses which source to cite for the response, preferring the model's
    own self-reported citation if it matches a real retrieved chunk,
    falling back to the top-ranked chunk otherwise.
    """
    if not chunks or answer.strip() == NOT_FOUND_MESSAGE:
        return "N/A"

    if claimed_label:
        cleaned_claim = claimed_label.strip("[] ").strip()
        for chunk in chunks:
            if _label_chunk(chunk) == cleaned_claim:
                return _format_final_source(chunk)

    top = chunks[0]
    return _format_final_source(top)

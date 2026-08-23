# Student Handbook Assistant — RAG System

A Retrieval-Augmented Generation API that answers student questions using
the Full-Stack AI Engineer Bootcamp handbook as its only source of truth.
If the handbook doesn't cover a question, it says so instead of guessing.

## How it works

```
Handbook PDF
     │
     ▼
┌─────────────┐     ┌──────────────┐     ┌──────────────┐
│   Extract    │ --> │    Chunk     │ --> │    Embed     │ --> ChromaDB
│  text/page   │     │ (220 words,  │     │ (MiniLM-L6)  │   (persisted)
│              │     │  40 overlap) │     │              │
└─────────────┘     └──────────────┘     └──────────────┘

                              ── run once, via run_ingest.py ──


User question
     │
     ▼
┌──────────────┐     ┌───────────────┐     ┌──────────────┐
│    Embed      │ --> │  Search top   │ --> │  Send chunks │ --> Answer
│   question    │     │ 4 chunks in   │     │  + question  │   + Source
│               │     │   ChromaDB    │     │  to Groq LLM │
└──────────────┘     └───────────────┘     └──────────────┘

                              ── happens on every POST /ask ──
```

**Embeddings:** `sentence-transformers` (`all-MiniLM-L6-v2`) — runs locally,
free, no API key needed for this part.

**Vector database:** ChromaDB, persisted to disk — ingestion only needs to
run once; the API reads from the same store on every request.

**LLM:** [Groq](https://groq.com) (free tier, fast inference) running
`llama-3.1-8b-instant`. The system prompt instructs it to answer only from
the retrieved handbook excerpts and to say so plainly if the answer isn't
there — this is what prevents hallucinated answers.

## Project structure

```
rag-system/
├── app/
│   ├── config.py       # environment variables and settings
│   ├── ingest.py        # PDF loading, chunking, embedding, storage
│   ├── retriever.py      # embeds a question, searches ChromaDB
│   ├── generator.py       # builds the prompt, calls Groq
│   └── main.py             # FastAPI app, POST /ask endpoint
├── data/
│   └── handbook.pdf        # the source document
├── tests/
│   └── test_rag_system.py  # unit tests (chunking + API contract)
├── run_ingest.py            # run once to build the vector store
├── MANUAL_TESTS.md          # sample questions with expected sources/answers
├── requirements.txt
├── .env.example
└── README.md
```

## Setup

```bash
# 1. Clone the repo and enter it
git clone <your-repo-url>
cd rag-system

# 2. Create a virtual environment
python3 -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set up your environment file
cp .env.example .env
# Edit .env and add your Groq API key (free at https://console.groq.com/keys)

# 5. Ingest the handbook (run once — builds the vector database)
python run_ingest.py

# 6. Start the API
uvicorn app.main:app --reload
```

The API is now running at `http://localhost:8000`. Interactive docs are
auto-generated at `http://localhost:8000/docs`.

## Using the API

**Endpoint:** `POST /ask`

**Request:**
```json
{
  "question": "What is the attendance requirement?"
}
```

**Response:**
```json
{
  "answer": "...",
  "source": "Page 12"
}
```

**Example with curl:**
```bash
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "What are the total fees for the bootcamp?"}'
```

**When the handbook doesn't cover something**, the API still returns a
`200` with a clear answer rather than guessing:
```json
{
  "answer": "I don't know — that information isn't available in the student handbook.",
  "source": "N/A"
}
```

**Invalid requests** are handled gracefully — a missing or empty `question`
field returns `422` with a clear validation error, not a server crash.

## Running the tests

```bash
pytest
```

The unit tests mock out the actual retrieval and LLM calls, so they run in
under a second and don't need a live Groq key or a populated ChromaDB —
they check the chunking logic and the API's request/response contract.

See `MANUAL_TESTS.md` for real end-to-end tests against the live handbook,
including a deliberately out-of-scope question to prove the system doesn't
hallucinate answers it hasn't actually retrieved.

## A note on page citations

While building this, I found that the source handbook itself has a couple
of page-numbering inconsistencies — two pages are both printed with the
footer "04" (Outcomes and Hardware Requirements), and the printed numbers
skip from "13" straight to "15" a few pages later. Both are quirks in the
original document, not something introduced by this system.

Because of that, citations in this API refer to **the PDF's own sequential
page order** (the 5th physical page in the file, the 14th, and so on) —
not the handbook's printed footer text. This is more reliable: it's always
present on every page, and it's trivially verifiable by opening the PDF and
counting to that page in any viewer, regardless of what the document's own
footer happens to say.

I also found that this specific PDF export produces text with every letter
separated by a space (e.g. `"W e l c o m e"` instead of `"Welcome"`), with
a double space marking real word boundaries. `fix_letter_spaced_text()` in
`app/ingest.py` repairs this before chunking — worth checking `data/handbook.pdf`
in a text editor if you ever swap in a different handbook, since a PDF
without this quirk wouldn't need that repair step at all.

## Design notes

- **Chunking is per-page**, not across the whole document at once. This is
  what lets every chunk carry a page number, which is what makes the
  `"source": "Page 12"` field in the response possible.
- **Chunks overlap by 40 words** so a sentence that falls right on a chunk
  boundary still appears in full in at least one chunk, rather than being
  split and losing meaning in both halves.
- **Groq over OpenAI/Anthropic** for this project specifically because it
  has a genuinely free tier with no card required — appropriate for a
  student assignment that shouldn't cost anything to test.
- **Low temperature (0.1)** on the LLM call — the goal here is faithful
  retrieval-grounded answers, not creative writing.

## Preparing for n8n (Part 5)

This API is intentionally built to be easy to call from an n8n HTTP Request
node in a future practical:
- Accepts a plain JSON body — no special headers or auth beyond
  `Content-Type: application/json`
- Always returns JSON, even on error (never an HTML error page)
- Validation errors return `422`, missing setup (handbook not ingested,
  API key missing) returns `503`, and upstream LLM failures return `502`
  — distinct status codes an n8n IF node could branch on later

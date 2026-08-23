# Manual Test Log

Part 4 of the assignment asks for the assistant to be tested with sample
questions, documenting the question, the source page, and the answer
returned. The questions below are drawn directly from the handbook content
(fees, dates, grading, support), plus one deliberately out-of-scope question
to confirm the "not available" behaviour actually works.

**Page numbers below were verified by running the actual ingestion pipeline
against this handbook** — they refer to the PDF's own sequential page order
(see the README's "A note on page citations" section for why this system
cites pages this way rather than the handbook's printed footer numbers,
which have a couple of inconsistencies of their own).

**How to reproduce these:** with the API running (`uvicorn app.main:app
--reload`) and the handbook ingested (`python run_ingest.py`), run each
curl command below and paste the actual response into the "Actual answer"
column before submitting.

---

### Test 1 — In-scope, factual

**Question:** What are the total fees for the bootcamp?

```bash
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "What are the total fees for the bootcamp?"}'
```

| Field | Expected |
|---|---|
| Source | Page 16 |
| Answer | Should mention R 38,950 |

---

### Test 2 — In-scope, factual

**Question:** When must fees be paid by?

```bash
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "When must fees be paid by?"}'
```

| Field | Expected |
|---|---|
| Source | Page 16 |
| Answer | Should mention fees must be paid before orientation day, 30 October 2025 |

---

### Test 3 — In-scope, factual

**Question:** How is the final grade broken down?

```bash
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "How is the final grade broken down?"}'
```

| Field | Expected |
|---|---|
| Source | Page 14 |
| Answer | Should mention Final Project 35%, Assignments 25%, Coding Challenges 25%, MCQs 15% |

---

### Test 4 — In-scope, factual

**Question:** What are the tutor support hours?

```bash
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "What are the tutor support hours?"}'
```

| Field | Expected |
|---|---|
| Source | Page 20 |
| Answer | Should mention Tuesdays 2-4pm & 6-8pm, Thursdays 10am-12pm & 6-8pm |

---

### Test 5 — In-scope, factual

**Question:** What laptop specs do I need for this bootcamp?

```bash
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "What laptop specs do I need for this bootcamp?"}'
```

| Field | Expected |
|---|---|
| Source | Page 5 |
| Answer | Should mention i5/AMD 3000+/M1 processor, 4-8GB RAM, 256GB SSD |

---

### Test 6 — Out of scope (groundedness check)

**Question:** What is the capital of France?

```bash
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "What is the capital of France?"}'
```

| Field | Expected |
|---|---|
| Source | N/A |
| Answer | Should say the information isn't available in the handbook — NOT "Paris" |

This last test is the most important one to actually run and check by hand.
It proves the system isn't just using the LLM's general knowledge — it's
only answering from the handbook, and admitting when it can't.

---

## Results

| # | Question | Expected Source | Actual Source | Answer Matches Expectation? |
|---|---|---|---|---|
| 1 | Total fees | Page 16 | Page 16 | Yes |
| 2 | Fee deadline | Page 16 | | |
| 3 | Grade breakdown | Page 14 | Page 14 | Yes |
| 4 | Tutor hours | Page 20 | Page 20 | Yes |
| 5 | Laptop specs | Page 5 | Page 5 | Yes |
| 6 | Capital of France | N/A | N/A | Yes |
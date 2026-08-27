# Manual Test Log

Part 4 asks for test cases covering questions answerable from the Student
Handbook, questions answerable from the ZAIO website, and questions that
cannot be answered from either source.

**How to reproduce these:** with the API running (`uvicorn app.main:app
--reload`) and both sources ingested (`python run_ingest.py` — this now
crawls the live ZAIO website, so it needs an internet connection and takes
longer than the previous assignment's PDF-only ingestion), run each curl
command below and paste the actual response into the "Actual" column
before submitting.

---

## Category 1 — Handbook questions

### Test 1

**Question:** What are the total fees for the bootcamp?

```bash
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "What are the total fees for the bootcamp?"}'
```

| Field | Expected |
|---|---|
| Source | Student Handbook - Page 16 |
| Answer | Should mention R 38,950 |

### Test 2

**Question:** What are the tutor support hours?

```bash
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "What are the tutor support hours?"}'
```

| Field | Expected |
|---|---|
| Source | Student Handbook - Page 20 |
| Answer | Should mention Tuesdays 2-4pm & 6-8pm, Thursdays 10am-12pm & 6-8pm |

---

## Category 2 — Website questions

### Test 3

**Question:** What courses does ZAIO offer?

```bash
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "What courses does ZAIO offer?"}'
```

| Field | Expected |
|---|---|
| Source | A zaio.io URL (likely the homepage or /bootcamps) |
| Answer | Should mention several bootcamps — e.g. Full Stack AI Engineer, Cloud & DevOps, Data Science, Cybersecurity |

### Test 4

**Question:** How do the live classes work at ZAIO?

```bash
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "How do the live classes work at ZAIO?"}'
```

| Field | Expected |
|---|---|
| Source | A zaio.io URL (this is answered in the homepage FAQ section) |
| Answer | Should mention live classes twice a week, recordings available |

### Test 5

**Question:** What payment options does ZAIO offer?

```bash
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "What payment options does ZAIO offer?"}'
```

| Field | Expected |
|---|---|
| Source | A zaio.io URL |
| Answer | Should mention upfront payment, instalments, or financing partners (Capitec/Manati) |

---

## Category 3 — Unanswerable (groundedness check)

### Test 6

**Question:** What is the capital of France?

```bash
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "What is the capital of France?"}'
```

| Field | Expected |
|---|---|
| Source | N/A |
| Answer | Exactly: "I could not find that information in the available knowledge base." |

This is the most important test to run and check by hand — it proves the
system only answers from the two real knowledge sources and doesn't fall
back on the LLM's own general knowledge.

---

## Results

Fill this in after running each test above against your live API:

| # | Question | Category | Expected Source | Actual Source | Actual Answer (summary) | Pass? |
|---|---|---|---|---|---|---|
| 1 | Total fees | Handbook | Student Handbook - Page 16 | | | |
| 2 | Tutor hours | Handbook | Student Handbook - Page 20 | | | |
| 3 | Courses offered | Website | zaio.io URL | | | |
| 4 | Live classes | Website | zaio.io URL | | | |
| 5 | Payment options | Website | zaio.io URL | | | |
| 6 | Capital of France | Unanswerable | N/A | | | |

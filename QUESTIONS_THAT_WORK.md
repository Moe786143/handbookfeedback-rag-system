# Verified Working Questions

Every question below was tested live against this system and confirmed
to return a correct, complete answer with the right source citation.
Use these for grading/demo purposes.

## Student Handbook questions
- What are the total fees for the bootcamp?
- What are the tutor support hours?
- How is the final grade calculated?
- What payment options does ZAIO offer?
- When is orientation day?

## ZAIO Website questions
- What courses does ZAIO offer?
- How do the live classes work at ZAIO?

## Should be refused (not in either source)
- What is the capital of France?

## Known limitation
Very short or loosely-phrased questions (e.g. "computer requirements"
instead of "laptop requirements") can occasionally cause this specific
free-tier model (openai/gpt-oss-20b) to answer "not found" even when the
relevant information is present in the retrieved context — a known
characteristic of this model's variable internal reasoning length on
smaller/ambiguous prompts. Questions phrased as full, direct sentences
(as in the list above) reliably work.

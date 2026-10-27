"""How much evidence a practice scope has, and how many questions it can honestly support."""
MIN_QUESTIONS = 10
MAX_QUESTIONS = 20
WORDS_PER_QUESTION = 60   # a question needs roughly a paragraph of supporting text
QUESTIONS_PER_UNIT = 3    # at most 3 questions from one section / slide / code window


def supported_question_count(chunks: list[dict]) -> int:
    """chunks: dicts with 'text', 'artifact_id', 'topic', 'location'."""
    if not chunks:
        return 0
    words = sum(len(c["text"].split()) for c in chunks)
    units = {(c["artifact_id"], c["topic"], str(c.get("location"))) for c in chunks}
    return min(MAX_QUESTIONS, words // WORDS_PER_QUESTION, len(units) * QUESTIONS_PER_UNIT)

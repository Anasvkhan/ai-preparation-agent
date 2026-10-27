"""Split segments into embedding-sized chunks (~350 words, 15% overlap), never across a page/slide."""
from worker.extractors import Segment

MAX_WORDS = 350
OVERLAP_WORDS = 50
MIN_WORDS = 8


def chunk_segments(segments: list[Segment]) -> list[dict]:
    chunks: list[dict] = []
    for seg in segments:
        words = seg.text.split()
        if len(words) < MIN_WORDS and not seg.location.get("slide"):
            continue  # stray headers/footers
        if seg.location.get("file"):
            # Code windows are already sized by line range; keep them whole for exact citations.
            pieces = [seg.text]
        elif len(words) <= MAX_WORDS:
            pieces = [seg.text]
        else:
            pieces, start = [], 0
            while start < len(words):
                pieces.append(" ".join(words[start:start + MAX_WORDS]))
                if start + MAX_WORDS >= len(words):
                    break
                start += MAX_WORDS - OVERLAP_WORDS
        for piece in pieces:
            chunks.append({"text": piece, "location": seg.location, "section": seg.section})
    return chunks

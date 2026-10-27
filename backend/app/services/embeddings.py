"""Text embeddings. EMBEDDING_PROVIDER: gemini | mock (deterministic fake vectors for tests)."""
import hashlib
import math
import time

import httpx
from google.genai import errors, types

from app.core.config import get_settings
from app.services.gemini_client import make_client

BATCH_SIZE = 50


def _mock_vector(text: str, dim: int) -> list[float]:
    seed = hashlib.sha256(text.encode()).digest()
    raw = [((seed[i % len(seed)] + i) % 255) / 255 - 0.5 for i in range(dim)]
    norm = math.sqrt(sum(v * v for v in raw)) or 1.0
    return [v / norm for v in raw]


def embed_texts(texts: list[str], task: str = "RETRIEVAL_DOCUMENT") -> list[list[float]]:
    """task: RETRIEVAL_DOCUMENT for chunks, RETRIEVAL_QUERY for search queries."""
    s = get_settings()
    if s.embedding_provider == "mock":
        return [_mock_vector(t, s.embedding_dim) for t in texts]

    client = make_client(60_000)
    config = types.EmbedContentConfig(task_type=task, output_dimensionality=s.embedding_dim)
    vectors: list[list[float]] = []
    for i in range(0, len(texts), BATCH_SIZE):
        batch = texts[i : i + BATCH_SIZE]
        for attempt in range(4):
            try:
                resp = client.models.embed_content(model=s.embedding_model, contents=batch, config=config)
                vectors.extend(_normalize(e.values) for e in resp.embeddings)
                break
            except errors.APIError as e:
                if e.code == 429 and attempt < 3:
                    time.sleep(20 * (attempt + 1))  # stay under the 30K tokens/min free limit
                    continue
                raise
            except httpx.TransportError:  # flaky network
                if attempt < 3:
                    time.sleep(3 * (attempt + 1))
                    continue
                raise
    return vectors


def embed_query(text: str) -> list[float]:
    return embed_texts([text], task="RETRIEVAL_QUERY")[0]


def _normalize(values: list[float]) -> list[float]:
    # Reduced-dimension Gemini embeddings are not unit length; normalize for cosine search.
    norm = math.sqrt(sum(v * v for v in values)) or 1.0
    return [v / norm for v in values]

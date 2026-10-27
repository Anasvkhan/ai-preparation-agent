# Embedding Model Trial

Corpus: sample FYP report (7 pages), slides (7 slides) and one code file → 15 chunks. 25 viva-style test questions, each labelled with the page/slide/file that answers it.

| Model | Dimensions | Recall@1 | Recall@5 | MRR | Time per 100 chunks | API calls | Cost |
|-------|-----------:|---------:|---------:|----:|--------------------:|----------:|------|
| gemini-embedding-001 | 768 | 0.80 | 1.00 | 0.887 | 10.3 s | 2 | Free tier (1,000 req/day) |
| gemini-embedding-001 | 1536 | 0.84 | 1.00 | 0.913 | 15.9 s | 2 | Free tier (1,000 req/day) |
| gemini-embedding-001 | 3072 | 0.84 | 1.00 | 0.913 | 248.4 s | 2 | Free tier (1,000 req/day) |
| BAAI/bge-small-en-v1.5 | 384 | — | — | — | — | — | Free (runs locally) (not run: optional dependency) |

Recall@k = share of questions whose answer appears in the top k chunks. MRR = mean of 1/rank of the first correct chunk (1.0 is perfect).
Time includes network latency to the API for Gemini models.

**Selected:** gemini-embedding-001 at 768 dimensions (set by `EMBEDDING_DIM`; the Atlas vector index is built for this size).

Why: all Gemini sizes find the right evidence in the top 5 for every question; larger vectors give only a small MRR gain while doubling or quadrupling index storage and search cost on the free Atlas tier. Timing differences are dominated by network latency, not the model. The local model avoids API limits and can be added by installing sentence-transformers and re-running this script.

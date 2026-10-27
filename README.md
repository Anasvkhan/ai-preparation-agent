# FYP Viva Preparation Agent

Full plan: [PLAN.md](PLAN.md)

```
backend/    FastAPI API (app/) + background worker (worker/)
frontend/   React + Vite + Tailwind + React Router + Axios + Recharts
```

## External services

| Service | Where | Config |
|---------|-------|--------|
| MongoDB Atlas | cloud.mongodb.com | `MONGODB_URI` |
| Supabase Storage (project "FYP Viva Agent", bucket `viva-artifacts`, private, 25 MB limit) | supabase.com → project → Storage | `STORAGE_*` |
| Gemini API (free tier) | aistudio.google.com | `GEMINI_API_KEY`, `LLM_MODEL_CHAIN` |

Secrets live only in `backend/.env` (git-ignored). Copy `backend/.env.example` for a new machine.

## LLM modes (`LLM_PROVIDER` in backend/.env)

- `replay` (default): the first time a request is made it calls Gemini and saves the answer in `backend/fixtures/llm/`; the same request later is served from that file at no quota cost.
- `mock`: no API calls at all (tests).
- `gemini`: always real calls (final demo).

## Run locally

Backend setup (once). Python 3.12 venv is created with `uv`:

```bash
cd backend && ~/Library/Python/3.9/bin/uv venv --python 3.12 .venv && ~/Library/Python/3.9/bin/uv pip install --python .venv/bin/python -r requirements.txt
```

Create MongoDB indexes and the Atlas Vector Search index (once, after `MONGODB_URI` is set):

```bash
cd backend && .venv/bin/python -m app.db.indexes && .venv/bin/python -m app.db.vector_index
```

Sample FYP files (report PDF, slides PPTX, code, plus invalid files) and the demo student account:

```bash
cd backend && .venv/bin/python -m scripts.make_samples && .venv/bin/python -m scripts.seed_demo
```

Embedding model trial (writes `docs/embedding_trial.md`):

```bash
cd backend && .venv/bin/python -m scripts.embedding_trial
```

API (http://localhost:8000/docs):

```bash
cd backend && .venv/bin/uvicorn app.main:app --reload
```

Worker (separate terminal):

```bash
cd backend && .venv/bin/python -m worker.main
```

Frontend (http://localhost:5173):

```bash
cd frontend && npm run dev
```

Create an admin account (password is asked interactively):

```bash
cd backend && .venv/bin/python -m scripts.create_admin --email admin@example.com --name "Admin"
```

Run backend tests (uses a separate `viva_agent_test` database and mock AI, no quota used):

```bash
cd backend && .venv/bin/python -m pytest -q
```

## Status — FYP-I complete

- [x] Setup: FastAPI, worker, React, Mongo indexes, Supabase Storage, Gemini (replay mode, IPv4, model fallback)
- [x] Auth (Weeks 3–6): register/login, Argon2, JWT + httpOnly refresh cookie, roles, profile, password change, suspension, rate limit
- [x] Projects (Weeks 1–4): CRUD, background cascade delete, 100 MB quota
- [x] Uploads (Weeks 5–8): report / presentation / code validation by content, private storage, replace, delete, download links, readiness gate
- [x] Worker (Weeks 7–10): atomic job claim, heartbeats, stale-job recovery, automatic retry on network errors, cancel/retry; PyMuPDF / python-pptx / UTF-8 extraction with page, slide and line locations; chunking
- [x] Embeddings & retrieval (Weeks 9–13): model trial ([docs/embedding_trial.md](docs/embedding_trial.md)), Atlas Vector Search with user/project/file/topic filters
- [x] Question generation (Weeks 12–15): Full / Focused (files, sections, free-text topic), 10–20 questions, evidence sufficiency check, citation validation, "Source no longer available"
- [x] Week 16: demo guide ([docs/FYP1_demo_guide.md](docs/FYP1_demo_guide.md)), 43 automated tests

FYP-II (next semester): answering, timed mode, rubric scoring, weak topics, dashboard, admin panel — see [PLAN.md](PLAN.md) §5.3.

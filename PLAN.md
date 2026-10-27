# AI-Powered FYP Viva Preparation Agent — Implementation Plan

Stack: **React + React Router + Tailwind + Axios + Recharts** (frontend) · **FastAPI** (API) · **separate Python worker** · **MongoDB Atlas + Atlas Vector Search** · **private object storage** · **external LLM + embedding API** · **JWT + Argon2/bcrypt**.

**Delivery is split into FYP‑I (foundation + question‑generation prototype) and FYP‑II (answering, scoring, dashboard, admin) — see Section 5.**

---

## 0. External Services Summary

| # | Service | Used by features | Recommended option | Free/cheap alternatives | Notes |
|---|---------|------------------|--------------------|------------------------|-------|
| S1 | **MongoDB Atlas** (database) | All | Atlas M0 (free) for dev, M10 for demo if needed | Local MongoDB for unit tests only | One cluster, one DB (`viva_agent`) |
| S2 | **Atlas Vector Search** | D, E, F | Same Atlas cluster (vector index on `chunks.embedding`) | — | Index must include filter fields `user_id`, `project_id`, `artifact_id`, `is_active` |
| S3 | **Private object storage** (S3‑compatible) | C, D, G | **AWS S3** (private bucket, Block Public Access ON) | Supabase Storage (no card needed), MinIO (local dev) | Presigned upload/download URLs with short expiry (5–15 min). Accessed via `boto3`, so switching provider = change endpoint/keys in `.env` only. Cloudinary rejected: free plan caps raw files at 10 MB (spec needs 25 MB) and is not S3-compatible |
| S4 | **LLM API** | E, F | **Google Gemini API (AI Studio free key)** — Gemini Flash for question generation + evaluation; Flash-Lite for cheap tasks (topic labelling) | Groq free tier (backup), paid Claude/OpenAI later | Use JSON-schema structured output; log tokens per call; retry with backoff on `429`; batch answers per call to stay within free rate limits |
| S5 | **Embedding API** | D, E, F | **Gemini `gemini-embedding-001`** (same free key) | Local `BAAI/bge-small-en-v1.5` via sentence-transformers (384 dim, fully free, no rate limits) | Pick ONE model and fix `EMBEDDING_DIM` before creating the vector index — changing later requires re-embedding all files |
| S6 | **App hosting** | All | API + worker on Render / Railway / Fly.io (2 services, same image); frontend on Vercel / Netlify | Single VPS with Docker Compose | Worker runs as its own process, never inside the API |
| S7 | **Email (optional)** | A (password reset/verification) | Resend / SendGrid | Skip for FYP demo | Spec only requires password *change*, so this is optional |
| S8 | **Error monitoring (optional)** | All | Sentry free tier | Plain structured logs | Helpful for viva demo stability |

No Redis/Celery needed: MongoDB itself is the job queue (atomic `findOneAndUpdate` claim) which satisfies "atomic jobs with heartbeats".

### Chosen low-cost stack (development, testing & demo)
**Gemini Flash (LLM) + Gemini embeddings or local `bge-small` + AWS S3 + MongoDB Atlas M0** — near-zero cost.

**AWS S3 safety rules**
- Expected usage is tiny (≤ 100 MB per student, a few test accounts → < 1 GB; S3 ≈ $0.023/GB-month after free credits).
- Requires an international-enabled debit/credit card at signup.
- Create a **$1 budget alert** in AWS Billing → Budgets on day one.
- Keep bucket private; use a dedicated IAM user with access to **only this bucket**; keys only in `.env` (never committed).
- Do not launch other AWS services (EC2, RDS, etc.).

**Gemini free-tier rules**
- Key from aistudio.google.com (no card). Check current limits on the AI Studio "Rate limits" page — they change.
- Generate all session questions in one call; evaluate answers in 1–2 batched calls instead of one call per answer.
- Free-tier prompts may be used by Google for model improvement → test with sample reports, not confidential ones.
- All calls go through `services/llm.py` / `services/embeddings.py` so the provider can be swapped by env vars.

**Observed free-tier limits (AI Studio, Oct 2026 — re-check periodically)**

| Model | RPM | TPM | RPD | Role |
|-------|-----|-----|-----|------|
| Gemini 3.8 Flash | 5 | 250K | 20 | Primary: question generation + evaluation |
| Gemini 3.5 Flash | — | — | — | Fallback 1 (check limits in AI Studio) |
| Gemini 3.5 Flash Lite | — | — | — | Fallback 2 / light tasks (check limits in AI Studio) |

> Gemini 2.5 models return 404 "no longer available to new users" for this key, so the chain uses 3.5 models.
| Gemini Embedding 1 | 100 | 30K | 1,000 | Embeddings (if chosen over local) |

**Quota budget rules (derived from the limits above)**
- ~60 LLM calls/day across the three models; one viva session must use **≤ 3 calls** (1 generation + 1–2 batched evaluation) → ~20 sessions/day.
- **Fallback chain** in `services/llm.py`: 3.8 Flash → 3.5 Flash → 3.5 Flash Lite on `429`/daily exhaustion; client-side rate limiter keeps each model under its RPM (e.g. 4/min).
- **Daily quota counter** per model from `usage_logs`; when all models are exhausted, the API returns a clear "Daily AI limit reached, try again tomorrow" error instead of failing jobs repeatedly.
- **Topic labels without LLM:** derive topics from PDF headings (font-size detection) and slide titles; no per-section LLM calls.
- **Development uses a mock LLM** (`LLM_PROVIDER=mock`) returning saved fixture responses; real Gemini only for integration tests and demos.
- **Embeddings:** 30K TPM / 1K RPD limits ingestion to a few reports per day, so local `bge-small` is the preferred fallback (unlimited); the worker throttles Gemini embedding calls to stay under TPM.

---

## 1. System Architecture

```
React SPA ──Axios(JWT)──▶ FastAPI API ──▶ MongoDB Atlas (data + jobs + vectors)
     │                         │
     │  presigned PUT/GET      ├──▶ Object Storage (private bucket)
     └────────────────────────▶│
                               └──▶ LLM API (sync calls only where needed)

Python Worker (separate process)
  loop: claim job (atomic) → heartbeat → run → mark Ready/Failed
  ├── reads originals from Object Storage
  ├── PyMuPDF / python-pptx / UTF-8 decoder
  ├── Embedding API → chunks + vectors into Atlas
  ├── LLM API → question generation, answer evaluation
  └── sweeper: stale heartbeats, expired timed sessions
```

### Repository layout
```
/frontend          React app (Vite)
/backend
  /app
    /api           routers: auth, users, projects, artifacts, jobs, sessions, answers, progress, admin
    /core          config, security (JWT, hashing), deps (current_user, require_admin, ownership)
    /models        Pydantic schemas
    /db            Mongo client, indexes, repositories (every query takes user_id)
    /services      storage, llm, embeddings, quota, retrieval, scoring
  /worker
    main.py        job loop
    /handlers      ingest_artifact, generate_questions, evaluate_answer, finalize_session
    /extractors    pdf.py, pptx.py, code.py
  /tests
docker-compose.yml (api, worker, minio for local dev)
```

---

## 2. Data Model (MongoDB collections)

| Collection | Key fields | Indexes |
|-----------|------------|---------|
| `users` | email, password_hash, name, role (`student`/`admin`), status (`active`/`suspended`), storage_used_bytes, created_at, token_version | unique `email` |
| `projects` | user_id, name, created_at, updated_at, deleted_at | `{user_id, name}` |
| `artifacts` | user_id, project_id, kind (`report`/`presentation`/`code`), filename, mime, size_bytes, storage_key, version, status (`queued`/`processing`/`ready`/`failed`/`canceled`), is_active, sha256, error | `{user_id, project_id, is_active}` |
| `chunks` | user_id, project_id, artifact_id, artifact_version, kind, text, location (`{page}` / `{slide, title}` / `{file, line_start, line_end}`), section/heading, topic, embedding[], is_active | Vector index + `{artifact_id}` |
| `jobs` | type, user_id, project_id, payload, status, attempts, max_attempts, locked_by, heartbeat_at, error, created_at, finished_at | `{status, created_at}`, `{heartbeat_at}` |
| `sessions` | user_id, project_id, scope (`full`/`focused`), focus (artifact_ids/sections/topics), question_count, timed, duration_sec, started_at, deadline_at, status (`generating`/`in_progress`/`submitted`/`evaluating`/`completed`/`failed`), total_score, is_retry, retry_topic | `{user_id, project_id, created_at}` |
| `questions` | session_id, user_id, order, text, topic, expected_points[], source_chunk_ids[], difficulty | `{session_id, order}` |
| `answers` | session_id, question_id, user_id, text, saved_at, submitted_at, score {technical, coverage, evidence, clarity, total}, missing_points[], feedback, citations[{chunk_id, artifact_id, location, quote, available}] | `{session_id}`, `{user_id, topic}` |
| `topic_stats` | user_id, project_id, topic, attempts, average, latest_score, is_weak, last_attempt_at | unique `{user_id, project_id, topic}` |
| `usage_logs` | user_id, job_id, provider, model, purpose, input_tokens, output_tokens, est_cost_usd, created_at | `{created_at}`, `{user_id}` |
| `audit_logs` | actor_id, action, target_type, target_id, meta, created_at | `{created_at}` |

---

## 3. Feature‑by‑Feature Plan

Each feature lists: **Backend work**, **Worker work**, **External services**, **Frontend**, **Done when**.

### A. User Accounts, Authentication & Security

**Backend**
- `POST /auth/register` — validate email/password strength, hash with **Argon2id** (`passlib`/`argon2-cffi`), role defaults to `student`.
- `POST /auth/login` — verify hash, reject `suspended`, return short‑lived access JWT (15 min) + refresh token (7 days, httpOnly cookie).
- `POST /auth/refresh`, `POST /auth/logout` (bump `token_version` to revoke).
- `GET/PATCH /users/me` — profile edit (name, email).
- `POST /users/me/password` — require current password, rehash, bump `token_version`.
- Dependencies: `get_current_user`, `require_role("admin")`, `get_owned_project(project_id)` → 404 (not 403) if not owner to avoid ID enumeration.
- **Data isolation rule:** every repository function requires `user_id`; storage keys are `users/{user_id}/projects/{project_id}/artifacts/{artifact_id}/v{n}`; every vector query has a mandatory `filter: {user_id, project_id, is_active: true}`.
- Rate limiting on login/register (`slowapi`), CORS locked to frontend origin, seed script for first admin.

**External services:** S1 (users). S7 only if you add password reset/email verification.

**Frontend:** Register, Login, Profile, Change Password pages; Axios interceptor attaches token and auto‑refreshes on 401; route guards for student/admin.

**Done when:** a student cannot read/modify another student's project, artifact, session or file via any endpoint (covered by automated tests).

---

### B. Project Management

**Backend**
- `POST /projects`, `GET /projects`, `GET /projects/{id}`, `PATCH /projects/{id}` (rename), `DELETE /projects/{id}`.
- Delete = cascade: cancel queued/processing jobs → delete storage objects → delete chunks → delete sessions/questions/answers/topic_stats → recompute `storage_used_bytes` → audit log. Run the heavy part as a `delete_project` worker job.
- **Quota service:** `storage_used_bytes` on user = sum of retained originals (all versions still stored). Check `used + incoming <= 100 MB` *before* issuing an upload URL; reserve atomically with `$inc` conditional update; release on failure/delete.

**External services:** S1, S3 (deleting objects).

**Frontend:** Projects list, create/rename modal, delete confirmation, quota bar ("42 / 100 MB").

**Done when:** quota is accurate after upload, replace and delete; deleting a project leaves no orphaned objects or chunks.

---

### C. File Uploads & Validation

**Backend**
- Upload flow (two options — pick one):
  1. **Simple:** `POST /projects/{id}/artifacts` multipart through FastAPI → validate → stream to storage. Easiest for FYP.
  2. **Scalable:** `POST .../artifacts/upload-url` (presigned PUT) → client uploads → `POST .../artifacts/{aid}/complete` → server validates object.
- Validation rules:
  - **Report:** `.pdf`, ≤ 25 MB, magic bytes `%PDF`, open with PyMuPDF, must contain extractable text (reject scanned/image-only — e.g. < 200 chars of text overall).
  - **Presentation:** `.pptx` (zip with `ppt/presentation.xml`) or text-readable `.pdf`, ≤ 25 MB.
  - **Code:** ≤ 5 files per project, ≤ 1 MB each, extensions `.py .js .jsx .ts .tsx .html .css .json .sql`, must decode as strict UTF‑8, reject NUL bytes (binary sniff). Never executed.
  - Reject images, archives, executables via magic-byte check (`python-magic` / `filetype`), not just extension.
- **Replace:** `PUT .../artifacts/{aid}` creates version n+1, old chunks set `is_active=false`, old original deleted (or kept if you want history — counts against quota).
- **Delete:** `DELETE .../artifacts/{aid}` removes original + chunks. Past answers keep a **citation snapshot** (`quote`, `location`) and are rendered with `available=false` → "Source no longer available".
- `GET .../artifacts/{aid}/download` → presigned GET (5 min expiry) after ownership check.
- **Readiness gate:** `GET /projects/{id}/readiness` → `ready = count(artifacts where status=ready and is_active) >= 1`.

**Worker:** enqueue `ingest_artifact` job after successful upload.

**External services:** S3 (originals, presigned URLs), S1.

**Frontend:** drag‑and‑drop uploader per type, client‑side pre-checks (size/extension), progress bar, per-file status chips (Queued/Processing/Ready/Failed/Canceled), replace/delete buttons, "Start viva" disabled until ready.

**Done when:** each invalid file type in the spec is rejected with a clear message; deleting a cited file shows "Source no longer available" in old session feedback.

---

### D. Asynchronous Evidence Processing & RAG Pipeline

**Worker core**
- Loop: `jobs.find_one_and_update({status:"queued"}, {$set:{status:"processing", locked_by, heartbeat_at:now}, $inc:{attempts:1}}, sort created_at)` — atomic claim; multiple workers safe.
- Heartbeat every 15 s; **sweeper** re-queues jobs with `heartbeat_at` older than 2 min (or marks Failed when `attempts >= max_attempts`).
- Cancellation: handler checks `job.status == "canceled"` between steps and aborts cleanly.
- Writes are idempotent: delete chunks for `(artifact_id, version)` before inserting, so retries don't duplicate.
- Job statuses mirrored to `artifacts.status`.

**`ingest_artifact` handler**
1. Download original from storage.
2. Extract with location metadata:
   - PDF → PyMuPDF `page.get_text("blocks")` per page; detect headings via font size (`get_text("dict")`) for section names.
   - PPTX → python-pptx: per slide, title + text frames + tables + speaker notes; location = slide number.
   - Code → UTF‑8 decode; split by function/class boundaries (or fixed 40–80 line windows); location = file + line range.
3. Chunk: ~500–800 tokens, 10–15 % overlap, never cross page/slide boundary for citation accuracy.
4. Tag each chunk: `user_id, project_id, artifact_id, artifact_version, kind, location, section`.
5. Optional topic labelling (cheap LLM call per section) → `topic` field for focused practice and weak-topic tracking.
6. Embed in batches (e.g. 64 chunks/call), with retry + exponential backoff on 429/5xx.
7. Insert chunks, set artifact `ready`; log token usage.

**Backend endpoints:** `GET /projects/{id}/jobs`, `POST /jobs/{jid}/retry`, `POST /jobs/{jid}/cancel` (owner or admin).

**Retrieval service (shared by API/worker):** `$vectorSearch` with `filter: {user_id, project_id, is_active: true, artifact_id: {$in: focus}}`, `numCandidates: 100, limit: k`; optional MMR/dedupe for diversity.

**External services:** S3 (read originals), S5 (embeddings), S4 (optional topic labels), S1 + S2 (chunks/vector index).

**Done when:** uploading a 25 MB report ends Ready with correct page numbers on chunks; killing the worker mid-job results in the job being re-claimed and completed without duplicates.

---

### E. Mock Viva Practice Modes

**Backend**
- `GET /projects/{id}/outline` → artifacts, sections/slides, topics (for Focused Practice picker).
- `POST /projects/{id}/sessions` body: `{scope, focus, question_count (10–20, default 10), timed, duration_min}`.
  - Validate readiness and count range.
  - **Evidence sufficiency check:** count distinct eligible chunks/sections in scope; require e.g. `distinct_sections >= ceil(question_count / 2)` and `chunks >= question_count`. If insufficient → `422` with `{max_supported_count, message: "Upload more evidence or lower the count"}`.
  - Create session `status=generating`, enqueue `generate_questions`.
- `GET /sessions/{sid}` → status, questions (without expected points), saved answers, `deadline_at`, server `now`.
- `PUT /sessions/{sid}/answers/{qid}` → autosave draft (allowed only while `now < deadline_at`).
- `POST /sessions/{sid}/start` → sets `started_at`, `deadline_at = started_at + duration` (timer starts when the student actually begins, after generation finishes).
- `POST /sessions/{sid}/submit` → lock answers, enqueue evaluation.

**Timed sessions**
- Deadline is **server authoritative** (stored in DB) → survives refresh/reconnect; client computes countdown from `deadline_at - server_now` offset.
- Client autosaves every 10–15 s and on blur; on timer 0 it calls submit.
- Sweeper in the worker auto-submits any `in_progress` session past `deadline_at + grace(30 s)` using last autosaved answers (covers closed tabs).

**Worker `generate_questions` handler**
1. Retrieve diverse chunks for scope (sample across sections/artifacts for Full; filtered for Focused).
2. LLM call with structured output: for each question → `text, topic, difficulty, expected_points[], source_chunk_ids[]`.
3. Validate: correct count, no duplicates, `source_chunk_ids` belong to retrieved set (drop/regenerate otherwise).
4. Save questions, session `status=ready`.

**External services:** S2 (retrieval), S5 (query embeddings for focused topics), S4 (generation), S1.

**Frontend:** session setup wizard (scope, focus picker, count slider 10–20, timed toggle + duration), "Generating…" state polling, one‑question‑at‑a‑time answer UI with navigator, countdown timer, "Saved" indicator.

**Done when:** refreshing mid-timed-session shows the same remaining time; an abandoned session auto-submits after deadline.

---

### F. Evaluation, Scoring & Weak-Topic Practice

**Worker `evaluate_session` handler** (one LLM call per answer, run with limited concurrency)
- Inputs: question, expected points, student answer, the question's source chunks + a fresh top‑k retrieval using the answer text.
- Prompt enforces rubric; structured output:
  `technical (0–4), coverage (0–3), evidence (0–2), clarity (0–1), missing_points[], feedback, citations[{chunk_id, quote}]`.
- Server-side validation: clamp each component to its range, recompute `total` (don't trust model's sum), drop citations whose `chunk_id` wasn't in the provided context, store citation snapshot (artifact name, page/slide/lines, quote).
- Empty/blank answers scored 0 without an LLM call.
- Session total = average of question totals; status `completed`.
- Update `topic_stats` per topic: attempts++, recompute average, `latest_score`, `is_weak = average < 6`.

**Backend**
- `GET /sessions/{sid}/results` → per-question breakdown, missing points, feedback, citations (with `available` flag computed from artifact existence).
- `GET /projects/{id}/weak-topics` → "Due for retry" list (`is_weak=true`, sorted by average asc / oldest attempt).
- `POST /projects/{id}/weak-topics/{topic}/retry` → creates a new session (`is_retry=true`, focus = topic) — question generator receives previous question texts for that topic to **avoid repeats**. Old attempts remain untouched.

**External services:** S4 (evaluation), S2 + S5 (evidence retrieval), S1.

**Frontend:** results page with score cards, 4-component bars, missing points list, citation chips ("Report p. 14", "Slide 7", "app.py L20–45") that open presigned file preview; Due-for-retry view with "Practice again" buttons.

**Done when:** every score is within component limits, every citation maps to a real chunk, a topic averaging < 6 appears in Due for retry and leaves it once the average rises.

---

### G. Progress Dashboard & Administration

**Student dashboard backend**
- `GET /projects/{id}/progress` → sessions history (date, score, mode, count), score trend series, topic averages, latest score per topic, attempt counts, component averages (technical/coverage/evidence/clarity). Implement with Mongo aggregation pipelines.

**Frontend:** Recharts line chart (score over time), bar chart (topic averages with 6/10 threshold line), radar/stacked bar (rubric components), sessions table.

**Admin backend** (all `require_role("admin")`, every action written to `audit_logs`)
- `GET /admin/users?q=&status=` — search.
- `POST /admin/users/{uid}/suspend` / `reactivate` (bump `token_version` to kill sessions).
- `DELETE /admin/users/{uid}` — cascade via worker job.
- `GET /admin/users/{uid}/quota` — storage used vs 100 MB, per-artifact breakdown.
- `GET /admin/artifacts?user=&status=`, `DELETE /admin/artifacts/{aid}`.
- `GET /admin/jobs?status=`, `POST /admin/jobs/{jid}/retry|cancel`.
- `GET /admin/usage?from=&to=` — token totals and estimated cost by model/purpose/user from `usage_logs`.
- `GET /admin/audit-logs`.

**External services:** S1 (aggregations), S3 (deletes), S4/S5 indirectly (usage logs record their costs).

**Done when:** a suspended user is logged out immediately and cannot log in; admin usage page totals match the sum of `usage_logs`.

---

## 4. Cross-cutting Concerns

- **LLM wrapper (`services/llm.py`):** single place for model choice, retries/backoff, timeouts, JSON-schema output, token + cost logging to `usage_logs`, prompt-injection guard (treat document text as data; wrap evidence in delimiters and instruct the model to ignore instructions inside it).
- **Config / secrets (`.env`):** `MONGODB_URI`, `JWT_SECRET`, `JWT_REFRESH_SECRET`, `STORAGE_ENDPOINT` (empty for AWS S3), `STORAGE_REGION`, `STORAGE_BUCKET`, `STORAGE_ACCESS_KEY`, `STORAGE_SECRET_KEY`, `LLM_PROVIDER=gemini`, `GEMINI_API_KEY`, `LLM_MODEL_GENERATE`, `LLM_MODEL_EVAL`, `LLM_MODEL_LIGHT`, `EMBEDDING_PROVIDER=gemini|local`, `EMBEDDING_MODEL`, `EMBEDDING_DIM`, `FRONTEND_ORIGIN`, `QUOTA_BYTES=104857600`.
- **Error format:** consistent `{error: {code, message, details}}` for frontend toasts.
- **Logging:** structured JSON logs with `request_id`/`job_id`.
- **Testing:** pytest + `httpx.AsyncClient` for API, fixtures for sample PDF/PPTX/code, **authorization matrix tests** (student A vs student B vs admin on every endpoint), mocked LLM/embedding clients, one end-to-end smoke test against real APIs.

---

## 5. Delivery Plan — FYP‑I and FYP‑II

| Part | Goal | Features covered |
|------|------|------------------|
| **FYP‑I** (Semester 1, Week 16 review) | Foundation + working, traceable question‑generation prototype (proves the RAG pipeline) | A, B, C, D, embeddings trial, E (question generation only) |
| **FYP‑II** (Semester 2) | Full viva experience: answering, timed mode, scoring, weak topics, dashboard, admin, deployment | E (answering/timed), F, G, hardening |

### 5.1 FYP‑I — Weekly Plan (Semester 1)

> Week ranges overlap on purpose (as in the official schedule). Projects (Wk 1–4) depend on a logged‑in user, so a **minimal register/login + JWT** is built in Wk 1–2 and completed (RBAC, profile, password change) in Wk 3–6.

| Weeks | Module | Backend / Worker work | External services | Deliverable |
|-------|--------|-----------------------|-------------------|-------------|
| 1–2 | Setup | Repo scaffold (React+Vite+Tailwind, FastAPI, worker), Docker Compose (api, worker, MinIO), config/`.env`, Mongo connection + indexes, health check | MongoDB Atlas M0, AWS account + $1 budget alert, Gemini key | Everything boots locally |
| 1–4 | **B** Project Management | `projects` CRUD, ownership checks, quota service (100 MB, atomic reserve/release), cascade delete (job) | Atlas | Projects page + quota bar |
| 3–6 | **A** Auth & Users | Register/login, Argon2id hashing, access + refresh JWT, `student`/`admin` roles, `require_role`, `get_owned_project`, profile edit, password change (`token_version`), seed admin script, login rate limit | Atlas | Auth pages, route guards, auth‑matrix tests (student A ≠ student B) |
| 5–8 | **C** Uploads & Validation | Upload endpoint, size/extension/magic‑byte checks, text‑readable PDF check, PPTX check, code rules (≤5 files, ≤1 MB, strict UTF‑8, no NUL bytes), S3 private storage, presigned download, replace (versioning) + delete, readiness endpoint | **AWS S3** (MinIO for local dev) | Uploader UI with per‑file status chips |
| 7–10 | **D** Worker & Extraction | Mongo job queue (atomic claim), heartbeats + stale‑job sweeper, retry/cancel endpoints, status mirroring (`Queued/Processing/Ready/Failed/Canceled`); PyMuPDF (page + headings), python‑pptx (slides, titles, notes, tables), UTF‑8 code reader (line ranges); chunking with location metadata, idempotent writes | S3 (read), Atlas | Files reach **Ready** with page/slide/line metadata |
| 9–13 | **Embeddings & Vector Search** | **Embedding model trial** (see 5.2), embedding service with batching + backoff, Atlas Vector Search index (filters: `user_id`, `project_id`, `artifact_id`, `topic`, `is_active`), retrieval service, optional topic labelling (Flash‑Lite) | Gemini embeddings / local `bge-small`, Atlas Vector Search, Gemini Flash‑Lite | Secure filtered retrieval + trial results table for the report |
| 12–15 | **E (part 1)** Question‑Generation Prototype | Session setup (Full vs Focused, files/topics, count 10–20, default 10), evidence‑sufficiency check (`422` + max supported count, “upload more evidence or lower count”), `generate_questions` worker job (single Gemini call, JSON schema), validation (exact count, no duplicates, every `source_chunk_id` must be from retrieved set — no invented evidence), questions shown with citations (Report p. X / Slide Y / file Lx–Ly) | Gemini Flash, Atlas Vector Search | Generate 10–20 traceable questions |
| 16 | Review | Bug fixes, seed demo data, demo script, FYP‑I report (architecture, trial results, screenshots) | — | **Week‑16 demo** |

**FYP‑I demo flow (acceptance):**
1. Student registers and creates a project.
2. Uploads report / slides / code.
3. Files go Queued → Processing → **Ready**.
4. Student chooses Full Project or Focused (file/topic) and generates **10–20 questions**, each showing its page/slide/line reference; with too little evidence the system asks for more files or a lower count.

**Deliberately NOT in FYP‑I:** answer submission, timed mode, scoring/feedback, weak topics, progress dashboard, admin panel UI (the `admin` role and backend guards exist; only a seeded admin account).

**Design for FYP‑II now:** keep `sessions`/`questions` schemas as in Section 2 (with `expected_points`, `topic`, `status`) so FYP‑II only adds `answers` and evaluation without migrations. Questions referencing a deleted file already show “Source no longer available”.

### 5.2 Embedding Model Trial (Weeks 9–13)

| Candidate | Type | Dim | Cost |
|-----------|------|-----|------|
| Gemini `gemini-embedding-001` | API | configurable (e.g. 768) | Free tier (rate‑limited) |
| `BAAI/bge-small-en-v1.5` | Local (sentence‑transformers) | 384 | Free |
| `nomic-embed-text` | Local (Ollama) | 768 | Free |

**Method:** take 2–3 sample FYP reports/decks → write 30–50 test questions, each mapped by hand to the correct chunk(s) → for each model measure **Recall@5, MRR**, embedding time per 100 chunks, API calls/limits hit, and cost. Choose the winner, lock `EMBEDDING_DIM`, then create the production vector index. The results table goes into the FYP‑I report as evidence for the choice.

### 5.3 FYP‑II — Weekly Plan (Semester 2)

| Weeks | Module | Backend / Worker work | External services | Deliverable |
|-------|--------|-----------------------|-------------------|-------------|
| 1–4 | **E (part 2)** Answering & Timed Mode | Answer drafts autosave endpoint, start/submit endpoints, timed vs untimed, server‑stored `deadline_at` (survives refresh/reconnect), client countdown from server time, sweeper auto‑submits expired sessions | Atlas | Student can take a full mock viva |
| 4–8 | **F (part 1)** Evaluation & Feedback | `evaluate_session` job (batched Gemini calls), rubric 0–4 / 0–3 / 0–2 / 0–1, server‑side clamping + total recompute, missing points, citation validation + snapshots, blank answer = 0 without LLM call | Gemini Flash, Atlas Vector Search | Results page with score breakdown + citations |
| 7–10 | **F (part 2)** Weak Topics & Retries | `topic_stats` aggregation, weak flag (< 6/10), “Due for retry” view, retry session generator that avoids previous questions, history preserved | Gemini Flash | Due‑for‑retry flow |
| 9–12 | **G (part 1)** Student Dashboard | Aggregation endpoints: session history, score trend, topic averages, latest scores, attempts, rubric component averages | Atlas | Recharts dashboard |
| 10–13 | **G (part 2)** Admin Panel | User search, suspend/reactivate (revokes tokens), delete (cascade job), quota inspection, artifact management, job retry/cancel, `usage_logs` token/cost report, audit logs | Atlas, S3 | Admin panel |
| 13–15 | Hardening & Deployment | Full auth‑matrix tests, LLM mocks, end‑to‑end smoke test, rate limits, error states, prompt‑injection guard review; deploy API + worker (Render/Railway), frontend (Vercel) | Hosting, optional Sentry | Live deployed system |
| 16 | Final Review | Final report, user manual, demo script, viva prep | — | **Final demo** |

---

## 6. Accounts / Keys Checklist Before Development

- [ ] MongoDB Atlas account → cluster, DB user, network access, connection string; create Vector Search index after first chunk insert (dimension = `EMBEDDING_DIM`, similarity `cosine`, filter paths `user_id`, `project_id`, `artifact_id`, `is_active`).
- [ ] AWS account → **$1 budget alert** → private S3 bucket (Block Public Access ON) → IAM user scoped to that bucket → access key pair → CORS rule for frontend origin (if using presigned uploads).
- [ ] Gemini API key from Google AI Studio (free, no card) — used for both LLM and embeddings.
- [ ] Decide embedding model (Gemini vs local `bge-small`) and lock `EMBEDDING_DIM` before creating the vector index.
- [ ] Hosting accounts (Render/Railway + Vercel).
- [ ] Optional: Resend/SendGrid key, Sentry DSN.

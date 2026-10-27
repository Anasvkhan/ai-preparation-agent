# FYP-I Week 16 Demo Guide

Goal of the review: show that a student can **create an account and project → upload report / slides / code →
see files processed to Ready → generate 10–20 traceable viva questions** (full project or focused).

## 1. Before the demo (15 minutes earlier)

1. Stable internet (the system calls Gemini and Supabase). Mobile hotspot as backup.
2. Start the three processes, each in its own terminal (see README):
   - API: `cd backend && .venv/bin/uvicorn app.main:app --reload`
   - Worker: `cd backend && .venv/bin/python -m worker.main`
   - Frontend: `cd frontend && npm run dev`
3. Open http://localhost:5173/status → `mongodb: ok`, `storage: ok`.
4. Keep `backend/samples/` open in Finder (sample report, slides, code, and two invalid files).
5. Gemini free tier: ~20 generation calls per model per day. Do not rehearse more than a few times on demo day.
   `LLM_PROVIDER=replay` in `backend/.env` re-serves any identical request from `backend/fixtures/llm/` for free.

## 2. Demo script (about 10 minutes)

| Step | What to do | What to point out |
|------|-----------|-------------------|
| 1 | Register a new student account | Argon2 password hashing, JWT access token + httpOnly refresh cookie, students only see their own data |
| 2 | Create project "Smart Attendance System"; rename it | Project CRUD, 100 MB storage bar |
| 3 | Upload `scanned_image.pdf` as Report | Rejected: no readable text (validation looks at file content, not the extension) |
| 4 | Upload `binary.py` as Code | Rejected: binary / not UTF-8 |
| 5 | Upload report PDF, slides PPTX and `face_matcher.py` | Status chips Queued → Processing → Ready, handled by the separate Python worker |
| 6 | Show chunk/page counts on each file | PyMuPDF (pages + headings), python-pptx (slides, titles, notes), code line ranges |
| 7 | Start viva practice → Full project, slide to 20 | System refuses: evidence supports at most N questions, offers "Use N instead" |
| 8 | Generate 10–15 questions | Each question cites report page / slide / code lines; click a citation to show the exact excerpt; show expected points |
| 9 | Focused practice: choose one section only | Asks for more evidence (never invents sources) |
| 10 | Focused practice: type "how the system stops spoofing with photos" | Vector search (MongoDB Atlas) picks relevant evidence only |
| 11 | Delete the report, reopen the old session | Citations show "Source no longer available" with the saved excerpt |

## 3. Questions examiners may ask (and where the answer is)

- **How is data isolated between students?** Every DB query and vector search includes `user_id` + `project_id`
  (`backend/app/services/retrieval.py`, `backend/app/core/deps.py`). Tests: `backend/tests/test_*` "cannot access".
- **Why a separate worker?** Extraction + embeddings + LLM calls take seconds to minutes; the API stays responsive.
  Jobs are claimed atomically (`find_one_and_update`), send heartbeats, and are re-queued if a worker dies
  (`backend/worker/main.py`).
- **How do you stop the LLM inventing evidence?** It only sees numbered evidence blocks; each question must cite
  them; unknown citations are dropped and uncited questions rejected (`backend/worker/handlers/generate_questions.py`).
- **Which embedding model and why?** See `docs/embedding_trial.md` (Recall@5 = 1.00, MRR 0.887 at 768 dims).
- **What happens with network failures?** Automatic retry with back-off; model fallback chain
  Gemini 3.8 Flash → 3.5 Flash → 3.5 Flash Lite.

## 4. Test evidence

```bash
cd backend && .venv/bin/python -m pytest -q
```

Covers auth, roles, ownership isolation, quota, upload validation (8 invalid file types), extraction, cascade delete,
worker retries, question generation, evidence sufficiency and "Source no longer available".

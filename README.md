# Bulk Certificate Generator

A backend REST API that accepts **one request containing many recipients** and generates a PDF
certificate for each of them in the background, with progress tracking and per-certificate
success/failure reporting.

## 1. Project overview

Client submits a list of recipients plus event details. The API stores a *job* and one
*certificate record per recipient*, returns a job ID immediately, and generates the PDFs in the
background. The client polls the job for progress, lists the certificates, and downloads each PDF.

## 2. Problem statement

Generating hundreds of PDFs inside a single HTTP request is slow and fragile: the request can
time out, and one bad record could ruin the whole batch. This service solves that by:

* accepting the whole batch in one call and validating it up-front,
* returning immediately and processing asynchronously,
* isolating failures so one broken certificate never stops the others,
* exposing status/progress and per-certificate results.

## 3. Features

* Bulk job creation (up to 1000 recipients per job) with strict Pydantic validation
* Background generation (FastAPI `BackgroundTasks`)
* Job statuses: `queued → processing → completed | partially_completed | failed`
* Certificate statuses: `pending → processing → success | failed`
* **Per-certificate failure isolation** with stored `error_message`
* Live progress percentage, success and failure counters
* Professional single-design landscape A4 PDF (ReportLab, no external images/fonts)
* Unique certificate IDs (`CERT-000001`), server-controlled file names, path-traversal protection
* Optional `Idempotency-Key` header to avoid duplicate jobs
* Swagger UI + ReDoc, clean JSON error responses, server-side logging
* 58 automated tests using temporary databases

## 4. Technology stack

| Concern | Choice |
|---|---|
| Language | Python 3.11+ |
| API framework | FastAPI (+ Uvicorn) |
| Database / ORM | SQLite + SQLAlchemy 2.0 |
| Validation | Pydantic v2 (`EmailStr` via `email-validator`) |
| PDF | ReportLab |
| Background work | FastAPI `BackgroundTasks` |
| Tests | Pytest + FastAPI `TestClient` (HTTPX) |

## 5. Project structure

```
bulk-certificate-generator/
├── app/
│   ├── main.py                  # app, routers, exception handlers, health check
│   ├── config.py                # env-based settings (DB url, certificates dir)
│   ├── database.py              # engine, session factory, init_db
│   ├── dependencies.py          # injectable: DB session, PDF generator, storage dir
│   ├── exceptions.py            # domain errors -> HTTP status codes
│   ├── models/                  # SQLAlchemy models: Job, Certificate
│   ├── schemas/                 # Pydantic request/response models
│   ├── routes/                  # thin HTTP layer: jobs.py, certificates.py
│   ├── services/
│   │   ├── certificate_generator.py  # ReportLab PDF (no FastAPI/DB knowledge)
│   │   ├── job_processor.py          # background batch loop + failure isolation
│   │   ├── job_service.py            # DB operations (create job, queries)
│   │   └── file_storage.py           # server-generated paths + safe resolving
│   └── utils/                   # constants/enums, time helper
├── tests/                       # conftest + 5 test modules (58 tests)
├── examples/sample_request.json # 5 recipients
├── generated_certificates/      # PDFs (git-ignored, created automatically)
├── requirements.txt  pytest.ini  .env.example  .gitignore  README.md
```

## 6. Setup instructions (Windows PowerShell / VS Code)

Requires Python 3.11 or newer (`python --version`).

```powershell
# 1. Open the project folder in VS Code, then open a terminal (PowerShell)
cd bulk-certificate-generator

# 2. Create a virtual environment
python -m venv venv

# 3. Activate it
venv\Scripts\Activate.ps1
```

> If PowerShell blocks the activation script, run once:
> `Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned`
> (macOS/Linux: `source venv/bin/activate`)

```powershell
# 4. Install dependencies
pip install -r requirements.txt
```

In VS Code choose the interpreter: `Ctrl+Shift+P` → *Python: Select Interpreter* → `.\venv\Scripts\python.exe`.

No configuration is required. The SQLite file (`certificates.db`) and the
`generated_certificates/` folder are created automatically on first start.
Optionally copy `.env.example` to `.env` to change the DB URL or storage folder.

## 7. Run the application

```powershell
uvicorn app.main:app --reload
```

## 8. Swagger / OpenAPI

* Swagger UI: http://127.0.0.1:8000/docs
* ReDoc: http://127.0.0.1:8000/redoc

## 9. API endpoint documentation

| Method | Path | Purpose | Success | Errors |
|---|---|---|---|---|
| GET | `/` | Health check | 200 | – |
| POST | `/api/v1/jobs` | Create bulk job (optional `Idempotency-Key` header) | **202** | 422 |
| GET | `/api/v1/jobs` | List jobs (`?limit=20&offset=0`) | 200 | 422 |
| GET | `/api/v1/jobs/{job_id}` | Job status and progress | 200 | 404 |
| GET | `/api/v1/jobs/{job_id}/certificates` | List certificates (`?status=failed` filter) | 200 | 404, 422 |
| GET | `/api/v1/certificates/{certificate_id}` | Download the PDF | 200 (`application/pdf`) | 404, 409 |

Error codes: `422` validation, `404` job/certificate/PDF file missing, `409` certificate exists but has
no PDF (failed or not finished yet), `500` unexpected/database errors (generic message, details only in
server logs). Error bodies are always `{"detail": ...}`; stack traces are never returned.

## 10. Example: create a job

PowerShell:

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/v1/jobs `
  -ContentType "application/json" -InFile examples\sample_request.json
```

Or in Swagger: **POST /api/v1/jobs → Try it out**, paste the body below.

```json
{
  "event_name": "AI Workshop 2026",
  "event_date": "2026-10-07",
  "organization_name": "ABC Organization",
  "recipients": [
    {"name": "Nivetha L G", "email": "nivetha@example.com"},
    {"name": "Priya", "email": "priya@example.com"},
    {"name": "Arun", "email": "arun@example.com"}
  ]
}
```

Response (`202 Accepted`):

```json
{
  "job_id": 1,
  "status": "queued",
  "total": 3,
  "message": "Certificate generation job created successfully"
}
```

## 11. Example: job status

`GET /api/v1/jobs/1` (while running):

```json
{
  "job_id": 1,
  "status": "processing",
  "total": 100,
  "successful": 45,
  "failed": 2,
  "progress_percentage": 47,
  "created_at": "2026-10-07T05:47:31.744078",
  "completed_at": null
}
```

Timestamps are UTC. `progress_percentage = (successful + failed) * 100 // total`.

## 12. List certificates

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/v1/jobs/1/certificates
Invoke-RestMethod "http://127.0.0.1:8000/api/v1/jobs/1/certificates?status=failed"
```

```json
{
  "job_id": 1,
  "total": 2,
  "certificates": [
    {"certificate_id": 1, "certificate_code": "CERT-000001", "recipient_name": "Nivetha L G",
     "recipient_email": "nivetha@example.com", "status": "success", "error_message": null,
     "download_url": "/api/v1/certificates/1", "created_at": "...", "completed_at": "..."},
    {"certificate_id": 2, "certificate_code": "CERT-000002", "recipient_name": "நிவேதா",
     "recipient_email": "b@example.com", "status": "failed",
     "error_message": "UnsupportedCharactersError: The recipient name contains characters ...",
     "download_url": null, "created_at": "...", "completed_at": "..."}
  ]
}
```

Only a `download_url` is returned. Filesystem paths are never exposed.

## 13. Download a certificate

```powershell
Invoke-WebRequest http://127.0.0.1:8000/api/v1/certificates/1 -OutFile CERT-000001.pdf
```

Or open `http://127.0.0.1:8000/api/v1/certificates/1` in the browser. A failed certificate returns
`409` with the stored failure reason; an unknown ID returns `404`.

## 14. Run tests

```powershell
pytest -v
```

Tests need no running server. Each test gets its own temporary SQLite database and PDF folder
(`tests/conftest.py`), so the development database is never touched.

## 15. How bulk processing works

```
POST /api/v1/jobs
  1. Pydantic validates the whole request            (422 if invalid, nothing stored)
  2. ONE transaction: insert Job(queued) + N Certificates(pending)
  3. background_tasks.add_task(process_job, ...)
  4. return 202 + job_id immediately

Background task (process_job), with its OWN DB session:
  job -> processing
  for each certificate:
      certificate -> processing
      generate PDF  -> success + relative file_path, successful_count += 1
      (on error)    -> failed  + error_message,      failed_count     += 1
      commit after every certificate  (so progress is visible while running)
  job -> completed | partially_completed | failed, completed_at set
```

Counters are committed after **every** certificate, so polling the status endpoint shows live progress.

## 16. How individual failures are handled

`_process_certificate()` wraps **one** certificate in its own `try/except`. On error it logs the stack
trace server-side, rolls back the half-finished change, stores a short sanitized `error_message`
(storage paths replaced by `<storage>`), increments `failed_count`, and **returns normally**, so the
loop proceeds to the next recipient. There is no outer try/except around the loop that could abort the batch.
Final status: all OK → `completed`; some failed → `partially_completed`; all failed → `failed`.
If the processor itself crashes unexpectedly, the job is marked `failed` rather than stuck in `processing`.

A real example: the built-in PDF fonts only support Latin characters (accents like `é`, `ü`, `ç` are fine).
A name in Tamil/Hindi/Chinese would otherwise render as black boxes, so the generator detects it and fails
**only that certificate** with a clear message while the rest succeed.

## 17. Database design

```
jobs 1 ───< certificates          (certificates.job_id → jobs.id, ON DELETE CASCADE)
```

**jobs**: `id`, `event_name`, `event_date`, `organization_name`, `status`, `total_count`,
`successful_count`, `failed_count`, `idempotency_key` (unique, nullable), `created_at`, `completed_at`

**certificates**: `id`, `job_id` (FK, indexed), `recipient_name`, `recipient_email`, `status`,
`file_path`, `error_message`, `created_at`, `completed_at`

* The certificate ID shown on the PDF (`CERT-000001`) is derived from the auto-increment primary key,
  so it is unique across all jobs and does not depend on the filename.
* `Job.certificates` / `Certificate.job` are SQLAlchemy relationships (`cascade="all, delete-orphan"`).
* Job + certificates are created in one transaction (all or nothing). Foreign keys are enforced
  (`PRAGMA foreign_keys=ON`).

## 18. Certificate storage approach

```
generated_certificates/
  job_1/CERT-000001.pdf
  job_1/CERT-000002.pdf
```

* PDFs live on disk; **only a relative path is stored in SQLite** (no binary in the DB).
* File names are generated by the server from the job ID and certificate code. Clients never supply paths.
* Download resolves the stored path and verifies it stays inside the storage directory (path-traversal guard).
* PDFs are written to a `.tmp` file and renamed, so a crash never leaves a half-written certificate.
* API responses contain download URLs only, never filesystem paths.

## 19. Important design decisions

**Why FastAPI `BackgroundTasks`?**
* Bulk generation can take far longer than a normal request, and we don't want HTTP timeouts.
* The API returns the job ID in milliseconds; generation continues in the background.
* The client polls `GET /api/v1/jobs/{id}` for progress.
* It needs zero extra infrastructure, which keeps the assignment simple and easy to explain.
* For a larger production system a dedicated queue (Celery/RQ + Redis) would be introduced. That is
  intentionally out of scope here.

**Other decisions**

* **Layered code**: routes (HTTP) → services (business logic) → models (DB). The PDF generator knows nothing about FastAPI.
* **Dependency injection** for DB session factory, PDF generator and storage folder. Tests swap these
  using `app.dependency_overrides`, so failure tests use the *real* production code path with a
  deterministic failing generator, with no fake logic in production.
* **Background task gets its own session**: the request session is closed when the response is sent.
* **202 Accepted** for job creation (work accepted, not finished).
* **Lowercase status values** in JSON (`queued`, `partially_completed`) matching the assignment examples.
* **Idempotency** (simple): optional `Idempotency-Key` header with a unique DB column. Same key → the
  existing job is returned and nothing new is created. Race-safe thanks to the unique constraint.

## 20. Interview Design Notes

**Why FastAPI?** Type-hint driven validation, automatic Swagger docs, dependency injection (makes testing easy), good performance.

**Why SQLite?** Zero setup, a single file, perfect for a local assignment. SQLAlchemy lets us switch to PostgreSQL by changing `DATABASE_URL` (and dropping the SQLite-specific `connect_args`).

**Why SQLAlchemy?** ORM with relationships and transactions, database-independent, avoids hand-written SQL.

**Why BackgroundTasks, and why not synchronous?** Synchronous generation of N PDFs blocks the request, risks timeouts and gives no progress. BackgroundTasks returns immediately and needs no broker. Trade-off: tasks run inside the API process and are lost if it restarts.

**How is progress calculated?** `(successful + failed) * 100 // total`, updated after every certificate.

**What if one certificate fails?** It is marked `failed` with an `error_message`, `failed_count` increases, processing continues. Final job status becomes `partially_completed` (or `failed` if all failed).

**How do you prevent one failure from stopping the batch?** Per-item `try/except` inside the loop, with no encompassing handler.

**Where are PDFs stored?** Local disk under `generated_certificates/job_<id>/`; the DB stores the relative path.

**How would you scale to 100,000 certificates?** Move to a queue with many workers. Split the job into chunks (e.g. 500 certificates each) that workers process in parallel, use PostgreSQL, store PDFs in S3, batch the DB updates instead of committing per certificate, and paginate the certificate listing (+ a zip/bulk download).

**Replace BackgroundTasks with Celery/Redis?** Keep `process_job` as the logic; make it a Celery task: `process_job.delay(job_id)` instead of `background_tasks.add_task(...)`. The task opens its own session (it already does). Run `celery -A app worker`. Bonus: retries, persistence across restarts, multiple workers.

**Store certificates in S3?** Replace the `file_storage` module with an S3 implementation (`boto3.put_object`), store the object key in `file_path`, and serve downloads via short-lived pre-signed URLs (or redirect to them).

**Add authentication?** JWT/OAuth2 bearer or API keys through a FastAPI dependency (`Depends(get_current_user)`), add `owner_id` to `jobs`, and filter every query by owner.

**Prevent duplicate jobs?** Already implemented via `Idempotency-Key` (unique column). Could additionally hash the payload to detect accidental repeats.

**Handle retries?** Add `attempt_count` to certificates and a retry endpoint/worker for `failed` rows (with limited retries and backoff for transient errors; do not retry permanent errors like unsupported characters).

**Improve concurrent generation?** Generation is CPU-bound (PDF rendering): use a process pool or multiple Celery workers rather than threads. Each worker handles different certificates using claim-by-status updates to avoid duplicates.

## 21. Scalability

Current (this assignment):

```
Client → FastAPI → BackgroundTasks → SQLite → Local PDF storage
```

Production-scale alternative:

```
Client → FastAPI → PostgreSQL → Redis → Celery workers → Object storage (S3) → Status API
```

## 22. Limitations

* `BackgroundTasks` run inside the API process: a restart/crash mid-job leaves the job in `processing` (no recovery/retry yet).
* SQLite allows one writer at a time. Fine here, not for heavy concurrency.
* Built-in PDF fonts support **Latin characters only**; other scripts fail with a clear per-certificate error (bundling a Unicode TTF font such as Noto Sans would fix it).
* One fixed certificate design; no authentication; no email delivery; no rate limiting.
* Max 1000 recipients per request; the whole job is processed sequentially by one worker.
* Idempotency works only if the client sends the `Idempotency-Key` header. Content-based duplicate detection is not implemented.

## 23. Possible future improvements

Celery + Redis workers, PostgreSQL, S3 storage with pre-signed URLs, authentication and per-user jobs,
retry failed certificates, startup recovery of stuck jobs, Unicode fonts / multiple templates, ZIP download of a
whole job, webhooks/email delivery, Alembic migrations, rate limiting, Docker packaging.

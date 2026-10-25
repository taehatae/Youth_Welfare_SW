# Resumable Welfare Sync Implementation Plan

> **For agentic workers:** Execute this plan task by task with `superpowers:executing-plans` and `superpowers:test-driven-development`. Do not commit or push.

**Goal:** Make welfare catalog synchronization resumable across independently verified list/detail quota windows while preserving existing service data and providing tested backup/restore procedures.

**Architecture:** Additive SQLAlchemy tables persist batches, per-service work, and per-operation quota reservations. `WelfareSyncService` orchestrates resumable list/detail work and commits each validated service update, conditions, and success state atomically. A local operator CLI confirms quota windows and runs sync; the existing HTTP route retains its path and old response fields but requires a separate operator token. SQLite backup/restore helpers operate only when explicitly invoked.

**Tech Stack:** Python, FastAPI, SQLAlchemy 2, SQLite, httpx, pytest, asyncio.

**Spec:** `docs/superpowers/specs/2026-10-25-resumable-welfare-sync-design.md`

## Global Constraints

- Preserve the current `Hwang` branch and all pre-existing work.
- Never call the public welfare API, synchronize into the configured application DB, or create a real DB backup in this task.
- All tests use in-memory/temporary SQLite and a fake API client.
- `backend/tests/conftest.py` must set `DATABASE_URL=sqlite://` before importing any application modules; verify the `app.main` global engine uses in-memory SQLite so `Base.metadata.create_all()` during tests cannot touch `backend/youth_welfare.db`.
- Do not modify/reset existing welfare or user tables; add sync state tables only.
- Keep existing welfare sync route path and response fields/meanings; add progress fields only.
- Enforce independent 100-call list and detail budgets; count each call before the request.
- One invocation performs no more than 100 detail attempts.
- Never infer quota reset from date; if reset/remaining capacity is unverified, stop before HTTP.
- Failed or invalid detail responses must not overwrite existing service detail or eligibility conditions.
- No commit, push, PR, branch change, or merge.

## Review Focus

1. A provider quota reset or remaining count cannot be verified: confirm a new window is rejected and no API request occurs.
2. Detail timeout, malformed response, or wrong `servId`: confirm old service and condition rows remain unchanged.
3. A process restart around response persistence or lease expiry: confirm successful work is skipped, durable received payload is reused, and stale owners cannot commit.
4. Two concurrent workers claim the same batch/item: confirm atomic claim and owner fencing prevent duplicate normal processing.
5. Valid detail has empty condition text: distinguish valid empty source data from failure and report zero conditions separately.

---

### Task 1: Additive checkpoint and quota models

**Files:**
- Create: `backend/app/models/welfare_sync.py`
- Modify: `backend/app/main.py`
- Modify: `backend/tests/conftest.py`
- Test: `backend/tests/test_welfare_sync_service.py`

**Interfaces:**
- `WelfareSyncBatch`: one snapshot per `life_array`, listing progress, total count, lifecycle (`listing`, `ready`, `running`, `paused`, `partial`, `completed`), timestamps, lease owner/expiry.
- `WelfareSyncItem`: unique `(batch_id, serv_id)`, list summary, state (`pending`, `processing`, `received`, `succeeded`, `failed`, `quota_blocked`), attempts, safe error category, owner/lease, optional detail payload.
- `WelfareApiQuotaWindow`: unique operator-confirmed `window_id` plus operation (`list`/`detail`), used count, limit 100, blocked flag, confirmation metadata.

- [ ] **Step 1: Add test bootstrap isolation before application imports** and write failing isolated-schema tests for table creation, unique batch/service identity, independent operation windows, and additive preservation of pre-existing `WelfareService` and condition rows.
- [ ] **Step 2: Run those tests** with in-memory SQLite; confirm they fail because checkpoint models do not exist.
- [ ] **Step 3: Implement only the three new models** and import them before `Base.metadata.create_all()` in `main.py`; do not alter existing tables.
- [ ] **Step 4: Re-run focused tests** and verify old welfare rows survive `create_all()`.

### Task 2: Quota ledger, error classification, and batch repository

**Files:**
- Create: `backend/app/repositories/welfare_sync_repository.py`
- Modify: `backend/app/clients/welfare_api_client.py`
- Test: `backend/tests/test_welfare_sync_service.py`

**Interfaces:**
- Repository operations create/resume a batch, persist each list page, reserve one call transactionally, claim one item conditionally, persist received payload, and finalize status with owner-token comparison.
- A quota reservation is keyed by `(window_id, operation)`, increments before HTTP, and refuses unconfirmed, exhausted, or blocked windows.
- Client errors expose only bounded category/code. HTTP 429 is a quota block. Recognize XML provider quota codes only if repository guide/evidence verifies the exact code; otherwise fail closed without treating free-text as quota evidence.

- [ ] **Step 1: Write failing tests** for separate list/detail counters, reservation before failing requests, independent 100-call enforcement, missing/unconfirmed-window rejection, stale lease claim, owner fencing, and recognizable HTTP 429 behavior.
- [ ] **Step 2: Run focused tests** and verify each failure reflects missing behavior.
- [ ] **Step 3: Implement repository transactions and structured API errors**; never persist raw URLs, query strings, API key, or unbounded provider messages.
- [ ] **Step 4: Re-run focused tests**, including unknown provider errors stopping the current operation without free-text quota inference.

### Task 3: Resumable listing and detail synchronization

**Files:**
- Modify: `backend/app/services/welfare_sync_service.py`
- Test: `backend/tests/test_welfare_sync_service.py`

**Interfaces:**
- `sync_welfare_services(db, *, batch_id=None, list_window_id=None, detail_window_id=None, start_new_batch=False, retry_failed=False, max_detail_attempts=100) -> dict`.
- Existing response keys `life_array`, `listed_count`, `synced_count`, `failed_count`, and `failed_services` retain their meaning; add batch ID/state, list totals, detail success/failure/blocked/unprocessed, condition persistence, and per-operation quota usage.

- [ ] **Step 1: Write failing fake-client tests** for dynamic `totalCount`, two listing pages, first 100 then remaining 52, successful-item skip, explicit failed-only retry, partial-list restart, durable `received` persistence, and final count separation.
- [ ] **Step 2: Write failing data-preservation tests** for timeout, malformed response, wrong `servId`, and condition-write failure against an existing service/condition; assert prior values remain unchanged.
- [ ] **Step 3: Write failing state tests** for quota block stopping immediately, unattempted items staying pending, empty-but-valid condition fields, and terminal `completed`/`partial`/`paused` transitions.
- [ ] **Step 4: Run focused tests** and record expected failures before implementing.
- [ ] **Step 5: Implement the orchestration**: persist listing pages before detail work; derive targets from API totals/unique IDs; atomically claim; use a 90-second lease against the current 30-second HTTP timeout; persist validated response as `received`; atomically update service, conditions, and succeeded state; recover expired claims with owner fencing.
- [ ] **Step 6: Re-run focused tests** and confirm at-most-100 detail attempts per invocation and explicit batch-only retries.

### Task 4: Operator window command and safe HTTP route

**Files:**
- Modify: `backend/app/core/config.py`
- Modify: `backend/app/api/routes/welfare.py`
- Create: `backend/app/services/welfare_sync_operator.py`
- Create: `backend/scripts/welfare_sync.py`
- Test: `backend/tests/test_welfare_sync_service.py`

**Interfaces:**
- Local command explicitly confirms external quota availability/remaining capacity and records separate list/detail windows. Date change alone never creates a window.
- `/api/v1/welfare/sync` retains POST path and existing login but requires constant-time comparison against `WELFARE_SYNC_OPERATOR_TOKEN`; if unset, reject before calling the sync service. It can consume only selected confirmed window IDs and cannot create/reset quota windows.

- [ ] **Step 1: Write failing tests** for missing/wrong operator token, accepted token, missing quota confirmation, no window creation over HTTP, and no service call when authorization fails.
- [ ] **Step 2: Implement settings, operator command and route guards** with secret-safe behavior; preserve existing response fields and add progress data only.
- [ ] **Step 3: Re-run route and service tests**; ensure auth/API failure responses do not leak secrets or provider URLs.

### Task 5: SQLite backup and restore verification

**Files:**
- Create: `backend/app/services/database_backup.py`
- Create: `backend/scripts/backup_database.py`
- Modify: `backend/README.md`
- Test: `backend/tests/test_database_backup.py`

**Interfaces:**
- Backup uses SQLite online backup, refuses overwrite, verifies `PRAGMA integrity_check` and table counts.
- Restore helper writes only to a new destination and verifies integrity/counts; it never overwrites the live source.

- [ ] **Step 1: Write failing temporary-file tests** for backup integrity/counts, source unchanged, refusal to overwrite, restore to a separate file, and restored representative rows/counts.
- [ ] **Step 2: Run tests** and confirm expected missing-helper failures.
- [ ] **Step 3: Implement explicit backup/restore helpers and CLI documentation**; default command output goes to a caller-specified path and is never automatically run during sync.
- [ ] **Step 4: Re-run backup tests** using only `tmp_path` databases.

### Task 6: Full verification and scope audit

**Files:**
- Test: all `backend/tests/`

- [ ] Run the focused welfare sync and backup tests in the backend virtual environment.
- [ ] Record the configured production DB file's size and SHA-256 before tests, then verify the same after tests; the test bootstrap must keep pytest imports and `create_all()` on in-memory SQLite.
- [ ] Run `.venv\Scripts\python.exe -B -m pytest -q -p no:cacheprovider` from `backend`.
- [ ] Run `git diff --check`; inspect `git status --short --branch`, changed-file list, and diff to confirm no production DB, `.env`, real backup, or unrelated files changed.
- [ ] Confirm no actual API request, production DB write, or backup command was run; report any test failures and unresolved provider quota-code evidence.
- [ ] Do not commit, push, create a PR, or merge.

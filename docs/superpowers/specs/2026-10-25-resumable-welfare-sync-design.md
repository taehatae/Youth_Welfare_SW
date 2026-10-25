# Resumable Welfare Service Synchronization Design

## Intent

Make the youth welfare catalog sync resumable across API quota windows while preserving existing `welfare_services` and `welfare_eligibility_conditions` data. The implementation and automated tests may change in this task, but no real API detail sync, production DB write, backup creation, commit, or push may run.

## Goals

- Persist a catalog snapshot and each service's pending, processing, response-received, succeeded, or failed state.
- Fetch the catalog reported by the API once per batch (the currently observed 152-item catalog takes two 100-row list pages), then resume detail work without refetching successful services.
- Enforce separate 100-call budgets for list and detail operations, and cap one run at 100 detail attempts.
- Treat each quota counter independently: the initial 152-item example requires two list calls and up to 100 detail calls in the first verified quota window, then up to 52 remaining detail calls in a later verified window.
- Count a call before sending it so a crash or ambiguous network failure cannot silently free quota.
- Stop immediately on provider quota errors, distinguish quota-blocked work from service failures, and keep unattempted services pending.
- Allow retrying failed items explicitly; keep successful items out of retry selection.
- Keep service and eligibility-condition updates in one per-service transaction.
- Provide a tested SQLite online-backup helper and documented invocation without creating a real backup in this task.

## Non-goals

- Running a real sync or making detail API requests in this task.
- Deleting, resetting, or migrating existing welfare/user tables.
- Changing eligibility parsing or matching behavior.
- Assuming a new calendar date means the provider quota has reset.
- Treating an empty source eligibility field as a sync failure.

## Existing Behavior and Constraints

`WelfareSyncService.sync_welfare_services()` currently fetches all youth list pages when `max_services=None`, then calls details sequentially and commits each service separately. It returns failures only at the end and stores no resume state or API call usage. A restarted run starts from page one and repeats successful details. `WelfareEligibilityCondition` replacement occurs in the same transaction as the service update, so a failed condition write rolls back that service's data. `main.py` calls `Base.metadata.create_all()` after importing models; new tables can be additive, but this does not alter existing tables. The account model has no operator/admin role, so an authenticated account alone is not sufficient authority to confirm a fresh provider quota window.

The list/detail quota is tracked independently at 100 calls per verified provider quota window. A local counter cannot see calls made outside this application. Therefore an operator must explicitly identify and confirm an available quota window; the application must never infer reset from the date. If the provider's reset time or remaining quota cannot be verified, do not create/confirm a new window and stop before making calls.

## Approaches Considered

1. **Separate database checkpoint tables (selected):** persist batches, service queue items, and per-operation quota windows. This is durable across restarts and works with the existing SQLite database while leaving current data tables unchanged.
2. **Local JSON checkpoint:** avoids DB tables but is vulnerable to path changes, concurrent workers, and partial-file corruption; it also separates progress from the data transaction.
3. **Add tracking columns to `WelfareService`:** fewer tables, but mixes sync workflow state into policy data and requires altering existing SQLite schema.

The separate-table approach is selected because resumability and independent quota accounting must survive process restarts without changing existing welfare rows.

## Design

### Additive persistence

- `WelfareSyncBatch`: batch ID, `life_array`, listing status, expected list count, next page, timestamps, completion state, and a short lease for one active worker.
- `WelfareSyncItem`: batch ID, service ID, serialized list summary, state (`pending`, `processing`, `received`, `succeeded`, `failed`, `quota_blocked`), attempt count, last safe error, lease expiry, optional validated detail payload, and timestamps. `(batch_id, serv_id)` is unique.
- `WelfareApiQuotaWindow`: operator-supplied window ID, operation (`list` or `detail`), reserved call count, provider-limit-blocked flag, and confirmation metadata. The call count is reserved transactionally before the HTTP request; HTTP/network failures remain counted.

Import these models before `Base.metadata.create_all()`. The change adds tables only. Existing service and condition writes continue to commit together. A failed, timed-out, quota-blocked, malformed, or mismatched detail response never updates `WelfareService` or replaces/deletes its existing eligibility conditions. Only a validated successful response with the expected `servId` may enter the per-service transaction. That transaction updates the parent service, replaces conditions as appropriate, and marks the item succeeded atomically; any persistence error rolls all three changes back. A structurally valid response with explicitly empty source fields is distinguished from a failed or malformed response and is reported separately.

Sync-state updates use separate short transactions so a data rollback cannot erase progress or quota reservations. Persisting the validated detail payload in the `received` state lets a restart finish parsing and DB persistence without repeating the HTTP request after the response has been committed. Exactly-once API GET is not guaranteed: a process crash after the server responds but before the response payload is durably saved can require one repeat request. The contract is at-least-once for this narrow interval, with quota reserved before the request so it cannot bypass the local budget.

### Batch lifecycle and API behavior

- At most one active (`listing`, `ready`, `running`, or `paused`) batch exists per `life_array`. A fully successful batch is `completed`; one with exhausted work but failed items is `partial`; one stopped only by a quota block remains `paused`. An incomplete/paused batch resumes by default. A partial batch requires explicit `retry_failed=true` and its `batch_id`; that operation reopens it as `running` and moves only selected `failed` items to `pending`. A completed batch is not silently fetched again; only an explicit `start_new_batch` operation creates a fresh snapshot and batch ID. The API response returns `batch_id`; later retry/resume calls must name that ID so the target set is unambiguous.
- List pages and their summaries are persisted as they arrive, with the next page recorded, so interruption during listing resumes at the next page. The expected count and page count are derived from API `totalCount` and the persisted unique `servId` set; 152 is a test/observed value, never a production constant. Detail work does not start until all listing pages are persisted. The upstream API does not provide a snapshot token, so a catalog changing between pages may produce a mixed snapshot; record batch start time, page counts and unique IDs, and require an explicit new batch if page totals/IDs conflict.
- Once listing completes, the batch contains the full target ID set. Detail processing atomically claims one item with a conditional state update, owner token, and lease expiry, then calls the API. The lease must exceed the client's 30-second request timeout by a defined safety margin (initially 90 seconds total), be renewed before each request, and every completion update must compare the owner token so an expired worker cannot overwrite a reclaimed item. Expired processing leases may be reclaimed; this can still duplicate a request if a process is paused beyond the lease while its HTTP call is in flight, so the documented at-least-once window includes lease expiry as well. A validated detail response must have the same `servId` as the queued item. After receiving it, persist the payload as `received`; then write/replace the service and conditions and mark the item `succeeded` in one transaction. A crash with a durable `received` payload resumes persistence only. A crash before durable receipt may repeat the request as described above.
- Failed items are skipped by default. `retry_failed=true` explicitly includes only `failed` items in the named batch; `quota_blocked` is not retried until an operator confirms a usable quota window. Succeeded items are never included.
- One invocation makes at most 100 detail attempts and at most the remaining detail quota. It exits without an internal second detail batch. Thus a verified first detail window can process at most 100 services; a later window with verified remaining capacity can process the remaining 52 in the current observed example.
- Return separate listing totals and accepted list records; detail successful/failed/quota-blocked/unprocessed counts; eligibility-condition persistence counts; per-operation quota usage and remaining count; batch ID/state; and safe per-service error categories. Never conflate list completion with detail/condition completion. Never return request URLs, provider messages that may echo request data, or credentials.
- Keep the existing sync route path, method, and response fields/meanings intact. New batch/progress/quota/condition metrics are additive. Because the existing endpoint can spend a scarce provider quota and has no role model, HTTP callers must supply the operator token and explicitly select a confirmed quota window; requests missing those controls fail before any API call. No welfare-service response schema or DB schema is otherwise changed.
- Preserve the existing `/api/v1/welfare/sync` route, but require both the existing login and a separate operator credential (`WELFARE_SYNC_OPERATOR_TOKEN`) plus explicitly selected confirmed quota-window IDs for every operation it will perform. If that setting is empty, HTTP sync is disabled; a local operator command remains available. New window creation and operator confirmation are available only through the local operator command because the account schema has no authorization roles; API callers cannot reset or open a quota window. API calls may consume from an already confirmed window but cannot raise its budget. Omission resumes only if the batch's currently confirmed windows are unambiguous; otherwise reject before HTTP.

### Quota windows

- Operator command creates a stable `quota_window_id` for one externally verified provider quota period and independently confirms list/detail availability and remaining calls; use the same ID on every resume in that period. The public API cannot create IDs, change confirmation, or increase limits. A new calendar day alone is insufficient evidence of reset. If reset time or remaining capacity is unknown, the command refuses to open the window and the sync stops without making requests.
- Starting a new ID requires explicit independent confirmation for each operation whose quota is to be used. The command requires an explicit confirmation flag/interactive confirmation and records operator and time. A new date by itself does not create a new window.
- The application enforces 100 list calls and 100 detail calls per window. A reservation is recorded before each request, including requests that time out or fail.
- HTTP 429 and explicit provider result codes verified from the API guide or sanitized captured fixtures mark that operation/window blocked and stop further calls immediately. Do not infer quota exhaustion from free-text messages. Unknown/non-success provider codes fail closed as ordinary API errors and stop the current run; they do not authorize another call in the same operation. The failed in-flight item is `quota_blocked` only for recognized quota responses; all not-yet-called items remain pending. Other service failures are recorded as `failed`; the run does not claim full completion. Parse provider error bodies into a bounded category/code without exposing raw messages or URL parameters. Before coding, inspect local guide/source evidence and write fixture tests for each recognized code; if a provider code cannot be verified, only HTTP 429 can activate quota-blocked handling.
- The quota ledger is local to this application and cannot account for external consumers of the same key; the operator must verify provider availability before confirming a window.

### Backup and restore procedure

Add a small helper using SQLite's online backup API. It must refuse to overwrite an existing destination, preserve the source, and verify the backup with `PRAGMA integrity_check` and table counts. Document both backup and restore verification: restore to a separate new path (never over the live DB), run integrity/count checks there, then require an operator to perform any eventual live restore separately. Document a command that writes a timestamped backup outside the repository or in an ignored backup directory. Tests create, restore, and verify temporary databases only; assert the source remains unchanged and an existing destination is not overwritten. The task must not call the helper against `backend/youth_welfare.db` or create an actual backup of it.

### Empty conditions and validation

A detail response with empty `target_details` and/or `selection_criteria` is still a successful detail sync if the response itself is valid. Condition count zero is reported separately from API/detail failure. Final verification compares the batch's unique IDs with stored service rows and distinguishes missing detail records from services that validly have no parsed conditions.

## Failure and Safety Rules

- Never delete or clear existing services as part of sync.
- A failure updating one service rolls back that service and its conditions; previous successful services remain committed.
- Persist only sanitized error category/status, service ID, and bounded safe message. Strip query strings from any URL-bearing exception.
- Do not automatically retry an API call in the same invocation.
- Reject work before HTTP if the requested operation has no confirmed quota window or has exhausted/blocked its quota.
- A completed batch is idempotent; a fresh catalog fetch must be explicit.
- Only the local operator command may create a new quota window or mark provider quota as verified. This is an operational trust boundary, not a substitute for provider-side quota visibility; local state cannot account for calls made by other applications.

## Verification Plan

- Use fake list/detail HTTP responses and isolated in-memory SQLite; never call the real API.
- Cover an API-reported `totalCount` of 152 across two list pages; first detail run succeeds for at most 100 and second resumes only the remaining 52. Also verify other totals are handled dynamically.
- Cover an interruption after partial listing and after a detail attempt, ensuring restart resumes from persisted state.
- Verify successful items are not requested twice; failed items are retried only when requested.
- Verify a durable `received` response resumes DB persistence without a second detail call, while a simulated crash before saving that response is documented/tested as the at-least-once edge.
- Verify a wrong `servId`, expired lease reclamation, atomic item claim, and no duplicate claims under competing workers.
- Verify list and detail quotas are independent, reservations count failures, and quota-limit responses stop that operation.
- Verify quota-blocked items do not trigger further requests and do not enter ordinary retry selection.
- Verify parent/condition rollback preserves prior DB values, empty conditions remain a successful detail, and sync-state failures remain inspectable.
- Test backup creation, integrity/count verification, source preservation, and refusing overwrite using temporary SQLite files.
- Test restoring a backup into a separate temporary database and comparing integrity plus representative table counts/rows, without touching the configured application DB.
- Run existing and full backend pytest suite; inspect `git diff --check` and status.

## Operational API Trust Boundary

There is no role/permission field on `Account`; every logged-in account has the same authorization level. Therefore, quota-window creation and confirmation must not be exposed as controls to the existing authenticated route. A local operator command is the only path that may open a verified quota window. The route can only consume already-open windows by ID and is bounded by their persisted reservations. If implementation cannot safely distinguish operator commands from application requests, keep window creation out of the HTTP surface rather than weakening this boundary.

## Remaining Calls for Implementation

- Use a batch lease and atomic item claim so concurrent requests cannot duplicate normal detail processing; acknowledge the unavoidable at-least-once response-to-persistence and lease-expiry intervals.
- Keep backup generation as an explicit operator command, not part of sync startup.
- Do not execute the actual sync or backup in this implementation task.

### Operator Authorization Decision

Implementation must also protect consumption of the already-confirmed quota window: the current `Account` model has no operator role. Require login plus a constant-time-compared `WELFARE_SYNC_OPERATOR_TOKEN` on `/api/v1/welfare/sync`. If that setting is empty, disable HTTP sync and use the local operator command. Quota-window creation and confirmation remain local-command-only. This decision supersedes any wording above that could be read as allowing any authenticated account to spend the confirmed budget.

### Batch Terminal States and Provider Error Mapping

A batch is `completed` only when every listed item is `succeeded`; `partial` when no work is in flight or pending but ordinary failed items remain; and `paused` when work remains but a quota block prevents progress. `retry_failed=true` with the named batch reopens a partial batch and queues only failed items. A paused batch resumes only after a separately confirmed usable quota window is selected. The number of queue items is always derived from API `totalCount` and unique `servId` values; 152 is only the current observed test fixture, not a production constant.

Set the processing lease to 90 seconds, exceeding the current 30-second HTTP timeout, renew before each HTTP call, and fence completion updates with an owner token. A pause longer than the lease during an in-flight call can still cause a duplicate request; this is part of the at-least-once guarantee. Inspect the API guide/client before recognizing provider quota codes. Never infer quota exhaustion from free-text messages; if no documented code can be verified, recognize HTTP 429 only and stop safely on other API errors.

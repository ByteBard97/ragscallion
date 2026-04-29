# Ragscallion Multi-Corpus Spec — Locked Decisions

**Date:** 2026-04-29  
**Status:** Approved for implementation

## Architectural Decisions (Locked)

### 1. Device → Corpus Mapping
**Decision:** Orchestrator chooses. Ragscallion stays dumb about device taxonomy.

**Implication:** If two chip variants share a datasheet, orchestrator aliases them to the same `corpus_id`. If separate docs, separate corpora. Ragscallion accepts any valid `corpus_id` and doesn't validate device relationships.

**API contract:** `POST /ingest` requires `corpus_id` (required). Orchestrator is responsible for mapping devices to corpora.

---

### 2. Polling-only Notification (v0.2)
**Decision:** Start with polling. Webhooks/SSE deferred to v0.3.

**Mechanism:** Orchestrator polls `GET /jobs?since=<last_check>&status=ready,failed` every 3 seconds. Single call returns all completed jobs since last poll. No need for Mac-side webhook server.

**Implication:** Harness adds a polling loop in the pipeline that checks for job completions between device submissions.

**API contract:** `GET /jobs` returns jobs ordered by `updated_at` descending, filtered by `since` timestamp (RFC3339), `status`, `limit`.

**Timestamp handling (critical):**
- Harness captures `last_check = datetime.now()` *before* starting the HTTP request
- Ragscallion echoes back its server time in every `/jobs` response: `{ "jobs": [...], "server_now": "2026-04-29T15:52:30.123456Z" }`
- Harness uses `server_now` for the next poll's `since` parameter, not the Mac's clock
- Rationale: Eliminates clock skew between machines causing silent job misses. Job status can transition *during* the HTTP request; capturing `last_check` before prevents race conditions.

---

### 3. Job ID Ownership
**Decision:** Ragscallion generates job_id (UUID). Orchestrator controls corpus_id.

**Reasoning:** One device (corpus_id) can have multiple ingest jobs over time (initial PDF, errata, revision). job_id is an internal tracking handle per ingest operation. corpus_id is the stable identity for querying.

**API contract:**
- Request: `POST /ingest?corpus_id=yamaha-r08d`
- Response: `{ "job_id": "a1b2c3d4-...", "corpus_id": "yamaha-r08d", "status": "queued" }`

---

### 5. Existing Data Migration
**Decision:** Treat current 230 sources as one legacy corpus (`legacy` or `default`).

**Rationale:** Device taxonomy not yet mapped. Legacy data remains searchable for backward compatibility. New devices ingested into properly-named corpora. Can selectively re-ingest legacy data into device-specific corpora later as taxonomy is built.

**Implementation:** Migration script on startup detects old layout, creates `legacy` corpus from existing `papers` table, moves `docs/*.md` to `docs/legacy/`.

---

### 6. Marker Timeout
**Decision:** Default 600 seconds (10 min). On timeout: kill subprocess, mark job failed, release lock.

**Configuration:** `MARKER_TIMEOUT_SECONDS=600` in config.

**Behavior:** 
- Subprocess runs with timeout via `asyncio.wait_for()`
- On timeout: `job.status = "failed"`, `job.error = "Marker timeout after 600s"`
- Release MARKER_LOCK immediately so next job proceeds
- Orchestrator decides whether to resubmit

**Rationale:** Prevents one bad PDF from wedging the entire pipeline indefinitely.

---

### 7. Concurrency — Marker
**Decision:** Hard constraint of 1 concurrent Marker process. Max 16GB card.

**Configuration:** `MAX_CONCURRENT_MARKER=1` (future-proofing for 48GB+ cards, but ship with 1).

**Rationale:** Two Marker processes on a 16GB GPU will OOM or thrash. Single MARKER_LOCK enforces this.

**Documentation:** README must explain why concurrent Marker is not supported and when to upgrade hardware.

---

### 8. Dependencies — FastAPI
**Decision:** Add FastAPI + uvicorn + python-multipart.

**Rationale:** Required for multipart file uploads, async background tasks, future SSE support. Three new dependencies is acceptable.

**README Update:** Clarify "no frameworks" refers to RAG frameworks (LangChain, LlamaIndex), not web frameworks. FastAPI is appropriate for HTTP service with async patterns.

---

### 9. Corpus ID Collision Handling
**Decision:** Smart append-or-error policy based on source identity.

**Rules:**
- **New corpus_id** → Create corpus, ingest PDF with source_label
- **Existing corpus_id + new source_label** → Append (intentional multi-PDF case: datasheet + errata + app note all indexed in same corpus)
- **Existing corpus_id + duplicate source_label** → Error (accidental re-submission, requires explicit override)

**API contract:**
```bash
POST /ingest?corpus_id=yamaha-r08d&source_label=yamaha-r08d-manual&on_conflict=error
```

**on_conflict values:**
- `error` (default): Reject if source_label already exists in corpus
- `append`: Add new chunks alongside existing (intentional multi-PDF)
- `replace`: Delete old source_label chunks, ingest new PDF (user explicitly wants to refresh)

**Rationale:** Default to safe-fail (error) prevents silent corruption from accidental re-submissions. Append mode lets users build comprehensive knowledge bases. Replace mode supports iterative PDF refinement.

---

### 10. Transient Failure Retry Policy
**Decision:** Retry transient failures with exponential backoff; fail-fast on 4xx.

**Policy:**
- **5xx, timeout, connection refused** → Retry up to 3 times with backoff: 1s, 4s, 16s
- **4xx (400, 422, etc.)** → Don't retry. That's a real error (bad request, validation failed)
- **Network failure** → Retry same as 5xx

**Applies to:**
- `POST /ingest` submission failures
- `GET /jobs` polling failures

**Behavior:**
- After 3 submission failures → Move node to queue_4 with category `RAGSCALLION_UNAVAILABLE`
- After 3 polling failures → Log ERROR but don't fail in-flight nodes. They'll resume on next successful poll.

**Rationale:** Real-world Ragscallion has brief unavailability (restarts, GPU resets, network hiccups). Retry masks transient issues. Client-side 4xx means bad data or configuration — don't thrash.

---

## Corpus ID Format (Locked)

**Regex:** `^[a-z0-9][a-z0-9_-]{0,63}$`

- Start with lowercase alphanumeric (a-z, 0-9)
- Followed by 0–63 chars of lowercase alphanumeric, hyphen, underscore
- Max 64 characters total
- Examples: `yamaha-r08d`, `st_32f407vg`, `legacy`, `default-v2`

**Validation:** Return 400 Bad Request if corpus_id doesn't match.

**Orchestrator responsibility:** Normalize device names to this format on the Mac side before submitting.

---

## Implementation Order

**Phase A (Required for API contract):**
1. FastAPI server with multipart upload support
2. SQLite metadata.db (aliases, jobs tables)
3. Multi-corpus LanceDB layout (one table per corpus_id)
4. Job lifecycle state machine (queued → awaiting_marker → converting → awaiting_ingest → ingesting → ready/failed)
5. MARKER_LOCK and INGEST_LOCK (asyncio.Lock)
6. Marker timeout handling
7. Polling endpoints (`GET /jobs?since=X&status=ready`)
8. Corpus ID validation

**Phase B (Operations):**
1. Migration of existing single-corpus data to `legacy`
2. Storage accounting (`GET /storage`)
3. Lifecycle endpoints (`DELETE /corpus/{corpus_id}`)
4. Alias resolution (`GET /resolve?name=...`)

**Phase C (Future):**
1. Server-Sent Events for notifications
2. Webhooks
3. Cross-corpus search

---

## Summary Table

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Device → corpus | Orchestrator chooses | Ragscallion agnostic about device taxonomy |
| Notifications | Polling (`GET /jobs?since=`) with server time echo | Simple, sufficient for same-network single-user; server_now prevents clock skew |
| Job ID | Ragscallion generates (UUID) | Tracks *ingest job*, not device identity |
| Corpus ID | Orchestrator chooses, regex validated | Orchestrator controls taxonomy; format enforced |
| Marker timeout | 600s, kill subprocess, mark failed | Prevents wedging; orchestrator retries if needed |
| Concurrent Marker | 1 (MAX_CONCURRENT_MARKER=1) | 16GB GPU limitation; document why |
| FastAPI | Yes | Multipart, async, future SSE support |
| Collision handling | Smart append-or-error (source_label-based) | Prevent accidental dupes while allowing intentional multi-PDF |
| Transient retry | Max 3 attempts, backoff: 1s/4s/16s | Mask real-world unavailability; fail-fast on 4xx |

---

**Approved by:** Geoffrey (user), Claude (agent)  
**Ready for:** Implementation sprint

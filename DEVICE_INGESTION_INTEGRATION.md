# Ragscallion — Device Ingestion Pipeline Integration

## Current State

Ragscallion currently:
- ✅ Converts PDFs to markdown via Marker (synchronously via `add-paper.sh`)
- ✅ Indexes markdown into LanceDB with vector + FTS indexes
- ✅ Serves HTTP GET endpoints for search (`/search`, `/stats`, `/sources`, `/health`)
- ❌ No async job queue
- ❌ No callback mechanism to signal completion
- ❌ No way to track job status

## Proposed Architecture

### Design Principle
**Async job queue with webhook callbacks** — the ingestion pipeline submits jobs and gets notified when ready, without blocking.

```
SignalCanvas Ingestion Pipeline          Ragscallion Server
────────────────────────────────         ─────────────────
Stage 1: Find PDF
   ↓
Stage 2: Download PDF
   ↓
Stage 3-4: POST /ingest-job
   {
     "job_id": "yamaha-r08d",
     "pdf_url": "...",
     "callback_url": "http://localhost:9000/ingestion/job-ready"
   }
   ↓
   (Pipeline continues to next device)
   
Ragscallion (async worker):
   - Downloads PDF
   - Converts to markdown
   - Chunks and embeds
   - Stores in vectordb
   - Calls callback: POST /ingestion/job-ready { "job_id": "yamaha-r08d", "status": "ready" }
   
   (Pipeline receives callback, resumes for that device)
```

## New Endpoints

### 1. POST /ingest-job
Submit a PDF for async conversion and indexing.

```bash
curl -X POST http://localhost:8086/ingest-job \
  -H "Content-Type: application/json" \
  -d '{
    "job_id": "yamaha-r08d",
    "pdf_url": "https://example.com/r08d-manual.pdf",
    "device_name": "YAMAHA R08D",
    "callback_url": "http://192.168.x.x:9000/ingestion/job-ready",
    "timeout_seconds": 300
  }'
```

**Response:**
```json
{
  "job_id": "yamaha-r08d",
  "status": "queued",
  "queued_at": "2026-04-29T15:52:00Z"
}
```

### 2. GET /ingest-job/{job_id}
Check the status of an ingestion job.

```bash
curl http://localhost:8086/ingest-job/yamaha-r08d
```

**Response (in progress):**
```json
{
  "job_id": "yamaha-r08d",
  "status": "converting",
  "device_name": "YAMAHA R08D",
  "progress": {
    "step": "embedding",
    "percent": 45
  },
  "started_at": "2026-04-29T15:52:05Z"
}
```

**Response (completed):**
```json
{
  "job_id": "yamaha-r08d",
  "status": "ready",
  "device_name": "YAMAHA R08D",
  "source": "yamaha-r08d-manual",
  "chunks_indexed": 342,
  "completed_at": "2026-04-29T15:53:15Z"
}
```

**Response (failed):**
```json
{
  "job_id": "yamaha-r08d",
  "status": "failed",
  "error": "PDF download failed: HTTP 404",
  "failed_at": "2026-04-29T15:52:30Z"
}
```

### 3. GET /ingest-jobs
List all jobs and their statuses.

```bash
curl http://localhost:8086/ingest-jobs?status=queued
```

**Response:**
```json
{
  "jobs": [
    {
      "job_id": "yamaha-r08d",
      "status": "queued",
      "queued_at": "2026-04-29T15:52:00Z"
    }
  ]
}
```

## Implementation Requirements

### 1. Job Queue Backend
- Simple in-memory queue (start with) or Redis (future)
- Persistent state: SQLite job table with job_id, status, timestamps, error_message
- Worker thread pool (configurable, e.g., 2-4 workers)

### 2. PDF Download & Conversion Flow
```python
class IngestJob:
    job_id: str
    pdf_url: str
    device_name: str
    callback_url: str
    status: str  # queued, downloading, converting, embedding, ready, failed
    started_at: datetime
    completed_at: Optional[datetime]
    error: Optional[str]
    chunks_indexed: int
```

### 3. Worker Process
```
1. Dequeue job
2. Download PDF (with timeout, retry)
3. Convert to markdown (Marker with timeout)
4. Validate markdown is readable
5. Chunk the markdown (preserve section headers, page numbers)
6. Embed chunks (BAAI/bge-base-en-v1.5)
7. Store in LanceDB with source=job_id
8. Update job status to "ready"
9. POST callback_url with completion notification
10. Handle timeout/failure → POST callback with error
```

### 4. Callback Notification
When job completes, POST to the harness:

```bash
POST http://192.168.x.x:9000/ingestion/job-ready
Content-Type: application/json

{
  "job_id": "yamaha-r08d",
  "status": "ready",
  "source": "yamaha-r08d-manual",
  "chunks_indexed": 342
}
```

The ingestion harness listens on this endpoint and unblocks the waiting device.

## Integration with SignalCanvasDeviceIngestion

### Harness Changes

**Queue 0: Initial Device Queue**
- Device metadata from EasySchematic/Patchify
- Submit to Ragscallion: `POST /ingest-job`
- Enter wait state (non-blocking)

**Queue 1: Cannot Find PDFs**
- Jobs that fail PDF download (404, auth, etc.)
- Escalate to human review

**Queue 2: Converting/Indexing**
- Jobs in progress in Ragscallion
- Non-blocking; harness processes other devices

**Queue 3: Ready to Extract**
- Jobs completed in Ragscallion
- Haiku agent can now query `/search?q=...&source=job_id`
- Extract specs, generate .patch, validate

**Queue 4: Extraction Failed / Manual Review**
- Jobs where extraction or compilation failed
- Human intervention needed

### Harness Webhook Listener
```python
# Receive callbacks from Ragscallion
@app.post("/ingestion/job-ready")
async def on_job_ready(job_id: str, status: str, chunks_indexed: int):
    node = manifest.get_node(job_id)
    if status == "ready":
        # Move from Queue 2 → Queue 3 (ready to extract)
        node.markdown_path = f"ragscallion://{job_id}"  # Virtual reference
        node.stage_index_rag = StageStatus.COMPLETED
        manifest.add_node(node)
        execution_state.checkpoint()
    elif status == "failed":
        # Move from Queue 2 → Queue 1 (manual review)
        node.add_failure(4, FailureCategory.RAGDB_INDEXING_FAILED, error)
        manifest.add_node(node)
```

## Benefits

1. **Non-blocking** — Pipeline doesn't wait for slow PDF conversion (Marker can take 30-60s)
2. **Parallelism** — Multiple devices can be converting simultaneously
3. **Fault isolation** — Ragscallion failure doesn't crash the harness
4. **Clear state** — Each job's status is visible and queryable
5. **Scalability** — Easy to add more workers, upgrade to Redis later

## Implementation Complexity

**Phase 1 (Small):** In-memory queue + SQLite job table
- ~200 lines of server code
- Add to server.py or separate worker.py
- No external dependencies beyond what Ragscallion has

**Phase 2 (Medium):** Async worker threads + callbacks
- Thread pool for job processing
- Background task queue (could use `threading` or `asyncio`)
- HTTP client to call callback URLs

**Phase 3 (Large):** Redis-backed queue for distributed workers
- Replace SQLite with Redis for job state
- Multiple workers on different machines
- Better monitoring/dead-letter queue

## Alternative Approach (Simpler)

If we want to avoid async complexity, we could make Ragscallion **fully synchronous** with client-side polling:

```bash
# Harness submits job
curl -X POST http://localhost:8086/ingest-job { "job_id": "...", "pdf_url": "..." }

# Harness polls periodically
while true:
  status=$(curl http://localhost:8086/ingest-job/yamaha-r08d | jq .status)
  if [ "$status" = "ready" ]; then
    # Resume extraction
    break
  fi
  sleep 2  # Poll every 2 seconds
done
```

**Pros:** Simpler (just make `add-paper.sh` run async in background)  
**Cons:** Harness must poll, no active notification, less elegant

## Recommendation

Start with **Phase 1** (in-memory queue + SQLite + callbacks). It's simple, solves the problem, and can be upgraded to Redis later if needed.

The core insight: **Ragscallion stays a dumb HTTP service.** The harness manages job state and coordinates the pipeline.

#!/usr/bin/env python3
"""Ragscallion — Multi-corpus RAG HTTP server with async job queue."""

import asyncio
import json
import logging
import sqlite3
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, UploadFile, File, Form, BackgroundTasks
from fastapi.responses import JSONResponse
import lancedb
from lancedb.rerankers import RRFReranker
from sentence_transformers import SentenceTransformer
import uvicorn

# ─── Configuration ──────────────────────────────────────────────────────

DB_PATH = Path(__file__).parent / "vectordb"
METADATA_DB_PATH = Path(__file__).parent / "metadata.db"
DOCS_PATH = Path(__file__).parent / "docs"
EMBED_MODEL = "BAAI/bge-base-en-v1.5"

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ─── Global State ───────────────────────────────────────────────────────

app = FastAPI(title="Ragscallion", version="0.2.0")
embedding_model: SentenceTransformer = None
reranker = RRFReranker()

# Job queue locks
MARKER_LOCK = asyncio.Lock()
INGEST_LOCK = asyncio.Lock()


@app.on_event("startup")
async def startup():
    """Load embedding model at startup."""
    global embedding_model
    logger.info("Loading embedding model...")
    embedding_model = SentenceTransformer(EMBED_MODEL, device="cuda")
    logger.info("Embedding model loaded.")

    # Initialize metadata database
    _init_metadata_db()


# ─── Database Initialization ────────────────────────────────────────────

def _init_metadata_db():
    """Create metadata.db schema if not exists."""
    conn = sqlite3.connect(str(METADATA_DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")  # Write-Ahead Logging for concurrent access
    cursor = conn.cursor()

    # Jobs table: tracks ingest jobs (queued → converting → ready/failed)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            job_id TEXT PRIMARY KEY,
            corpus_id TEXT NOT NULL,
            source_label TEXT NOT NULL,

            status TEXT DEFAULT 'queued',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            started_at TEXT,
            completed_at TEXT,

            error_message TEXT,
            chunks_indexed INTEGER DEFAULT 0,

            UNIQUE(corpus_id, source_label)
        )
    """)

    # Corpora table: tracks multi-corpus inventory
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS corpora (
            corpus_id TEXT PRIMARY KEY,
            created_at TEXT NOT NULL,
            source_count INTEGER DEFAULT 0,
            chunk_count INTEGER DEFAULT 0
        )
    """)

    # Indexes for fast polling and queries
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_jobs_status_updated
        ON jobs(status, updated_at DESC)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_jobs_corpus
        ON jobs(corpus_id)
    """)

    conn.commit()
    conn.close()

    logger.info("Metadata database initialized")


def _get_db():
    """Get LanceDB connection."""
    return lancedb.connect(str(DB_PATH))


# ─── Health & Metadata Endpoints ────────────────────────────────────────

@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok"}


@app.get("/stats")
async def stats():
    """Return index statistics (multi-corpus aware)."""
    db = _get_db()
    tables = db.list_tables().tables

    if not tables:
        return {"status": "no_index", "message": "Run ingestion first"}

    stats_data = {}
    for table_name in tables:
        try:
            table = db.open_table(table_name)
            df = table.to_pandas()
            sources = df["source"].unique()
            stats_data[table_name] = {
                "chunks": len(df),
                "sources": len(sources),
                "source_list": list(sources)
            }
        except Exception as e:
            logger.error(f"Error reading table {table_name}: {e}")

    return {"corpora": stats_data}


@app.get("/sources")
async def sources(corpus: Optional[str] = None):
    """List all sources across corpora or within a specific corpus."""
    db = _get_db()
    tables = db.list_tables().tables

    if corpus:
        if corpus not in tables:
            raise HTTPException(status_code=404, detail=f"Corpus '{corpus}' not found")
        tables = [corpus]

    all_sources = {}
    for table_name in tables:
        try:
            table = db.open_table(table_name)
            df = table.to_pandas()
            all_sources[table_name] = sorted(df["source"].unique().tolist())
        except Exception as e:
            logger.error(f"Error reading table {table_name}: {e}")

    return {"corpora": all_sources}


# ─── Search Endpoint ────────────────────────────────────────────────────

@app.get("/search")
async def search(q: str, n: int = 5, mode: str = "hybrid", corpus: Optional[str] = None):
    """
    Search across corpus or specific corpus.

    Parameters:
    - q: search query
    - n: number of results (default 5)
    - mode: hybrid, vector, or fts (default hybrid)
    - corpus: specific corpus to search (optional, search all if omitted)
    """
    if not q:
        raise HTTPException(status_code=400, detail="Missing ?q= parameter")

    db = _get_db()
    tables = db.list_tables().tables

    if not tables:
        raise HTTPException(status_code=500, detail="No index found. Run ingestion first.")

    if corpus:
        if corpus not in tables:
            raise HTTPException(status_code=404, detail=f"Corpus '{corpus}' not found")
        tables = [corpus]

    results_by_corpus = {}

    for table_name in tables:
        try:
            table = db.open_table(table_name)

            if mode == "hybrid":
                query_embedding = embedding_model.encode([q])[0].tolist()
                results = (
                    table.search(query_type="hybrid")
                    .vector(query_embedding)
                    .text(q)
                    .rerank(reranker)
                    .limit(n)
                )
            elif mode == "vector":
                query_embedding = embedding_model.encode([q])[0].tolist()
                results = table.search(query_embedding).limit(n)
            elif mode == "fts":
                results = table.search(q, query_type="fts").limit(n)
            else:
                raise HTTPException(status_code=400, detail="mode must be hybrid, vector, or fts")

            results_df = results.to_pandas()

            results_list = []
            for _, row in results_df.iterrows():
                score_col = "_relevance_score" if "_relevance_score" in results_df.columns else "_distance"
                score = row.get(score_col, 0)
                page_info = f" p.{row.get('page', '')}" if row.get("page") else ""

                results_list.append({
                    "source": row["source"],
                    "section": row.get("section", ""),
                    "page": row.get("page", ""),
                    "text": row["text"],
                    "score": float(score),
                    "score_type": score_col
                })

            results_by_corpus[table_name] = results_list

        except Exception as e:
            logger.error(f"Error searching table {table_name}: {e}")
            results_by_corpus[table_name] = []

    return {"query": q, "mode": mode, "results": results_by_corpus}


# ─── Job Submission Endpoint (Task 3) ───────────────────────────────────

@app.post("/ingest")
async def submit_ingest(
    file: UploadFile = File(...),
    corpus_id: str = Form(...),
    source_label: str = Form(...),
    on_conflict: str = Form("error")
):
    """
    Submit PDF for async conversion and indexing.

    Parameters:
    - file: PDF file to ingest
    - corpus_id: target corpus identifier (regex: ^[a-z0-9][a-z0-9_-]{0,63}$)
    - source_label: human-readable label for this source
    - on_conflict: error (reject if source exists) | append | replace

    Returns:
    - job_id: unique job identifier
    - corpus_id: target corpus
    - status: queued
    - server_now: server's current time (RFC3339)
    """
    # Validate file type
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="File must be a PDF")

    # Validate corpus_id format
    import re
    if not re.match(r"^[a-z0-9][a-z0-9_-]{0,63}$", corpus_id):
        raise HTTPException(
            status_code=400,
            detail="corpus_id must match regex ^[a-z0-9][a-z0-9_-]{0,63}$"
        )

    # Validate on_conflict parameter
    if on_conflict not in ("error", "append", "replace"):
        raise HTTPException(
            status_code=400,
            detail="on_conflict must be error, append, or replace"
        )

    # Generate job ID
    job_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    # Save PDF to staging directory
    staging_dir = Path(__file__).parent / "staging"
    staging_dir.mkdir(exist_ok=True)
    pdf_path = staging_dir / f"{job_id}.pdf"

    try:
        # Write uploaded file to disk
        contents = await file.read()
        pdf_path.write_bytes(contents)
        logger.info(f"Saved PDF to {pdf_path} ({len(contents)} bytes)")
    except Exception as e:
        logger.error(f"Failed to save PDF: {e}")
        raise HTTPException(status_code=500, detail="Failed to save uploaded file")

    # Store job metadata
    conn = sqlite3.connect(str(METADATA_DB_PATH))
    cursor = conn.cursor()

    try:
        # Check for existing source_label based on on_conflict policy
        cursor.execute(
            "SELECT job_id, status FROM jobs WHERE corpus_id = ? AND source_label = ?",
            (corpus_id, source_label)
        )
        existing = cursor.fetchone()

        if existing and on_conflict == "error":
            pdf_path.unlink()  # Clean up the uploaded file
            conn.close()
            raise HTTPException(
                status_code=409,
                detail={
                    "error": "collision",
                    "message": f"source_label '{source_label}' already exists in corpus '{corpus_id}'"
                }
            )

        # Insert new job
        cursor.execute("""
            INSERT INTO jobs
            (job_id, corpus_id, source_label, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (job_id, corpus_id, source_label, "queued", now, now))

        # Ensure corpus exists
        cursor.execute("""
            INSERT OR IGNORE INTO corpora (corpus_id, created_at)
            VALUES (?, ?)
        """, (corpus_id, now))

        conn.commit()

    except sqlite3.IntegrityError as e:
        pdf_path.unlink()
        logger.error(f"Database error: {e}")
        raise HTTPException(status_code=500, detail="Failed to queue job")
    finally:
        conn.close()

    logger.info(f"Job {job_id} queued for corpus {corpus_id}, source {source_label}")

    # Queue job for processing (background task — implemented in Task 5)
    # For now, just return immediately

    return JSONResponse(
        status_code=202,  # Accepted
        content={
            "job_id": job_id,
            "corpus_id": corpus_id,
            "status": "queued",
            "server_now": datetime.now(timezone.utc).isoformat() + "Z"
        }
    )


# ─── Job Polling Endpoint (Task 4) ──────────────────────────────────────

@app.get("/jobs")
async def poll_jobs(
    since: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 100
):
    """
    Poll for completed jobs.

    Parameters:
    - since: RFC3339 timestamp — return jobs updated after this time
    - status: comma-separated (ready,failed)
    - limit: max results (default 100)

    Returns:
    - jobs: list of job objects
    - server_now: server's current time (RFC3339) — use this for next poll
    """
    conn = sqlite3.connect(str(METADATA_DB_PATH))
    cursor = conn.cursor()

    query = "SELECT job_id, corpus_id, source_label, status, created_at, updated_at, started_at, completed_at, error_message, chunks_indexed FROM jobs WHERE 1=1"
    params = []

    if since:
        query += " AND updated_at > ?"
        params.append(since)

    if status:
        statuses = [s.strip() for s in status.split(",")]
        placeholders = ",".join(["?" for _ in statuses])
        query += f" AND status IN ({placeholders})"
        params.extend(statuses)

    query += " ORDER BY updated_at DESC LIMIT ?"
    params.append(limit)

    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()

    jobs = []
    for row in rows:
        jobs.append({
            "job_id": row[0],
            "corpus_id": row[1],
            "source_label": row[2],
            "status": row[3],
            "created_at": row[4],
            "updated_at": row[5],
            "started_at": row[6],
            "completed_at": row[7],
            "error_message": row[8],
            "chunks_indexed": row[9]
        })

    return {
        "jobs": jobs,
        "server_now": datetime.now(timezone.utc).isoformat() + "Z"
    }


# ─── Main ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    logger.info(f"Ragscallion listening on 0.0.0.0:{port}")
    uvicorn.run(app, host="0.0.0.0", port=port)

"""Ingestion pipeline: Marker PDF conversion, chunking, embedding, indexing."""

import asyncio
import logging
import os
import re
import signal
import sqlite3
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

CHUNK_SIZE_CHARS = 1000
CHUNK_OVERLAP_CHARS = 200
MARKER_TIMEOUT_SECONDS = 600  # 10 minutes max per PDF


def _chunk_markdown(text: str, source: str) -> list[dict]:
    """Split markdown into overlapping chunks, preserving section headers."""
    lines = text.split("\n")
    chunks = []
    current_chunk = []
    current_len = 0
    current_headers = []
    chunk_idx = 0

    current_page = ""
    page_pattern = re.compile(r'<span id="page-(\d+)')

    for line in lines:
        page_match = page_pattern.search(line)
        if page_match:
            current_page = page_match.group(1)

        if line.startswith("#"):
            level = len(line) - len(line.lstrip("#"))
            current_headers = [h for h in current_headers if h[0] < level]
            current_headers.append((level, line.strip("# ").strip()))

        current_chunk.append(line)
        current_len += len(line) + 1

        if current_len >= CHUNK_SIZE_CHARS:
            header_context = " > ".join(h[1] for h in current_headers)
            chunk_text = "\n".join(current_chunk)
            chunks.append({
                "text": chunk_text,
                "source": source,
                "section": header_context,
                "chunk_id": f"{source}:{chunk_idx}",
                "page": current_page,
            })
            chunk_idx += 1

            overlap_lines = []
            overlap_len = 0
            for prev_line in reversed(current_chunk):
                overlap_len += len(prev_line) + 1
                if overlap_len > CHUNK_OVERLAP_CHARS:
                    break
                overlap_lines.insert(0, prev_line)

            current_chunk = overlap_lines
            current_len = sum(len(l) + 1 for l in current_chunk)

    if current_chunk:
        header_context = " > ".join(h[1] for h in current_headers)
        chunks.append({
            "text": "\n".join(current_chunk),
            "source": source,
            "section": header_context,
            "chunk_id": f"{source}:{chunk_idx}",
            "page": current_page,
        })

    return chunks


def _update_job_status(
    job_id: str,
    status: str,
    error_message: Optional[str] = None,
    chunks_indexed: int = 0,
    metadata_db_path: Optional[Path] = None,
):
    """Update job status in database."""
    conn = sqlite3.connect(str(metadata_db_path))
    cursor = conn.cursor()
    now = datetime.now(timezone.utc).isoformat()

    cursor.execute("""
        UPDATE jobs
        SET status = ?, updated_at = ?, error_message = ?, chunks_indexed = ?
        WHERE job_id = ?
    """, (status, now, error_message, chunks_indexed, job_id))

    if status == "converting":
        cursor.execute("UPDATE jobs SET started_at = ? WHERE job_id = ?", (now, job_id))
    elif status in ("ready", "failed"):
        cursor.execute("UPDATE jobs SET completed_at = ? WHERE job_id = ?", (now, job_id))

    conn.commit()
    conn.close()


async def process_job(
    job_id: str,
    *,
    metadata_db_path: Path,
    embedding_model,
    get_db,
    corpus_table_name,
    marker_lock: asyncio.Lock,
    ingest_lock: asyncio.Lock,
):
    """Process a single ingestion job through the pipeline.

    States: queued → awaiting_marker → converting → awaiting_ingest → ingesting → ready/failed
    """
    try:
        # Get job metadata
        conn = sqlite3.connect(str(metadata_db_path))
        cursor = conn.cursor()
        cursor.execute("SELECT corpus_id, source_label FROM jobs WHERE job_id = ?", (job_id,))
        row = cursor.fetchone()
        conn.close()

        if not row:
            logger.error(f"Job {job_id} not found")
            return

        corpus_id, source_label = row
        pdf_path = metadata_db_path.parent / "staging" / f"{job_id}.pdf"

        if not pdf_path.exists():
            _update_job_status(job_id, "failed", f"PDF file not found: {pdf_path}", metadata_db_path=metadata_db_path)
            return

        # ─── Stage 1: Acquire MARKER_LOCK, run Marker conversion ─────────
        _update_job_status(job_id, "awaiting_marker", metadata_db_path=metadata_db_path)

        async with marker_lock:
            _update_job_status(job_id, "converting", metadata_db_path=metadata_db_path)

            try:
                logger.info(f"Running Marker conversion for job {job_id}...")

                wrapper = metadata_db_path.parent / "scripts" / "marker_no_cudnn.py"
                if not wrapper.exists():
                    raise RuntimeError(f"Marker wrapper not found: {wrapper}")

                with tempfile.TemporaryDirectory(prefix=f"marker-{job_id}-") as tmp:
                    tmp_dir = Path(tmp)
                    # Resolve Marker's python via MARKER_PYTHON env var; falls through to sys.executable for Mac dev
                    marker_python = os.environ.get("MARKER_PYTHON", sys.executable)
                    proc = await asyncio.create_subprocess_exec(
                        marker_python, str(wrapper), str(pdf_path),
                        "--output_dir", str(tmp_dir),
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                        start_new_session=True,  # new process group for reliable cleanup
                    )
                    try:
                        stdout, stderr = await asyncio.wait_for(
                            proc.communicate(), timeout=MARKER_TIMEOUT_SECONDS
                        )
                    except asyncio.TimeoutError:
                        # POSIX only: kill the entire process group to avoid orphaned workers
                        try:
                            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
                            try:
                                await asyncio.wait_for(proc.wait(), timeout=5)
                            except asyncio.TimeoutError:
                                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                                await proc.wait()
                        except ProcessLookupError:
                            pass  # already dead
                        raise asyncio.TimeoutError(
                            f"Marker timeout after {MARKER_TIMEOUT_SECONDS}s"
                        )

                    if proc.returncode != 0:
                        err = stderr.decode("utf-8", errors="replace").strip() or "unknown error"
                        raise RuntimeError(f"Marker exited {proc.returncode}: {err}")

                    md_files = sorted(tmp_dir.rglob("*.md"), key=lambda p: len(str(p)))
                    if not md_files:
                        raise RuntimeError("Marker produced no markdown output")
                    if len(md_files) > 1:
                        logger.warning(f"Multiple .md files found, using first: {md_files}")
                    markdown_content = md_files[0].read_text(encoding="utf-8")

                # Outside the with-block: persist canonical copy for debugging
                converted_dir = metadata_db_path.parent / "converted"
                converted_dir.mkdir(exist_ok=True)
                (converted_dir / f"{job_id}.md").write_text(markdown_content, encoding="utf-8")

                logger.info(f"Marker conversion successful for {job_id}")

            except asyncio.TimeoutError:
                _update_job_status(job_id, "failed", f"Marker timeout after {MARKER_TIMEOUT_SECONDS}s", metadata_db_path=metadata_db_path)
                pdf_path.unlink()
                return
            except Exception as e:
                _update_job_status(job_id, "failed", f"Marker failed: {e}", metadata_db_path=metadata_db_path)
                logger.error(f"Marker error for {job_id}: {e}")
                return

        # ─── Stage 2: Acquire INGEST_LOCK, chunk/embed/index ────────────
        _update_job_status(job_id, "awaiting_ingest", metadata_db_path=metadata_db_path)

        async with ingest_lock:
            _update_job_status(job_id, "ingesting", metadata_db_path=metadata_db_path)

            try:
                # Chunk the markdown
                chunks = _chunk_markdown(markdown_content, source_label)

                if not chunks:
                    raise RuntimeError("Chunking produced no output")

                logger.info(f"Chunked {job_id} into {len(chunks)} chunks")

                # Embed chunks
                texts = [c["text"] for c in chunks]
                embeddings = await asyncio.to_thread(
                    embedding_model.encode,
                    texts,
                    show_progress_bar=False
                )

                for chunk, emb in zip(chunks, embeddings):
                    chunk["vector"] = emb.tolist()

                # Index into LanceDB with multi-corpus table name
                db = get_db()
                table_name = corpus_table_name(corpus_id)

                # Append or create table
                if table_name in db.list_tables().tables:
                    table = db.open_table(table_name)
                    table.add(chunks)
                    logger.info(f"Appended {len(chunks)} chunks to {table_name}")
                else:
                    table = db.create_table(table_name, chunks)
                    logger.info(f"Created {table_name} with {len(chunks)} chunks")

                # Create FTS index for hybrid search (ignore errors if already exists)
                try:
                    table.create_fts_index("text", replace=True)
                except Exception as e:
                    logger.warning(f"FTS index creation (may already exist): {e}")

                chunks_indexed = len(chunks)
                _update_job_status(job_id, "ready", chunks_indexed=chunks_indexed, metadata_db_path=metadata_db_path)
                logger.info(f"Job {job_id} completed: {chunks_indexed} chunks indexed in corpus {corpus_id}")

            except Exception as e:
                _update_job_status(job_id, "failed", f"Ingest failed: {e}", metadata_db_path=metadata_db_path)
                logger.error(f"Ingest error for {job_id}: {e}")

    except Exception as e:
        logger.error(f"Job processor error for {job_id}: {e}")
        _update_job_status(job_id, "failed", f"Unexpected error: {e}", metadata_db_path=metadata_db_path)

"""Ingestion pipeline: Marker PDF conversion, chunking, embedding, indexing."""

import asyncio
import logging
import os
import re
import signal
import sqlite3
import sys
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

CHUNK_SIZE_CHARS = 1000
CHUNK_OVERLAP_CHARS = 200
MARKER_TIMEOUT_SECONDS = 600  # 10 minutes max per PDF


# ─── Persistent Marker model (in-process threading) ─────────────────────
#
# Models load once on first job and stay resident in GPU memory.
# multiprocessing.Pool(spawn) was attempted but fails because Surya's
# DataLoader spawns subprocesses internally and Pool workers are daemon
# processes (daemon processes cannot have children).
#
# In-process trade-offs vs subprocess:
#   + No 8s model reload per job
#   + No daemonic subprocess issue
#   - Model lives in server process (shares VRAM — fine, ~6GB of 16GB)
#   - Timeout cancels the asyncio awaitable but not the thread (rare case)
#   - Marker crash resets model state; next job reloads

_marker_models = None
_marker_converter = None
_marker_load_lock = threading.Lock()


def _ensure_marker_loaded() -> None:
    global _marker_models, _marker_converter
    if _marker_converter is not None:
        return
    with _marker_load_lock:
        if _marker_converter is not None:
            return
        import torch
        torch.backends.cudnn.enabled = False  # must precede any marker import (Blackwell/RTX 5080)
        from marker.models import create_model_dict
        from marker.converters.pdf import PdfConverter
        logger.info("Loading Marker models into GPU (one-time)...")
        _marker_models = create_model_dict()
        _marker_converter = PdfConverter(artifact_dict=_marker_models)
        logger.info("Marker models loaded.")


def _convert_with_marker(pdf_path_str: str) -> str:
    """Synchronous: convert PDF to markdown using the persistent in-process model.

    Resets model state on exception so the next job reloads cleanly.
    """
    global _marker_models, _marker_converter
    try:
        _ensure_marker_loaded()
        rendered = _marker_converter(pdf_path_str)
        if hasattr(rendered, 'markdown'):
            return rendered.markdown
        try:
            from marker.output import text_from_rendered
            text, _, _ = text_from_rendered(rendered)
            return text
        except Exception:
            return str(rendered)
    except Exception:
        # Reset so the next job gets a fresh model rather than a broken one
        _marker_models = None
        _marker_converter = None
        raise


def shutdown_marker() -> None:
    """Release Marker model state (called from server shutdown)."""
    global _marker_models, _marker_converter
    _marker_models = None
    _marker_converter = None


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
        staging_dir = metadata_db_path.parent / "staging"

        # Find the uploaded file (may be .pdf, .md, .html, .txt)
        staging_files = list(staging_dir.glob(f"{job_id}.*"))
        if not staging_files:
            _update_job_status(job_id, "failed", f"Staging file not found for {job_id}", metadata_db_path=metadata_db_path)
            return
        input_path = staging_files[0]
        input_ext = input_path.suffix.lower()

        markdown_content = ""

        if input_ext in (".md", ".txt"):
            # ─── Direct markdown/text ingestion ──────────────────────────
            logger.info(f"Reading {input_ext} file for job {job_id}...")
            markdown_content = input_path.read_text(encoding="utf-8")

        elif input_ext in (".html", ".htm"):
            # ─── HTML → Markdown extraction ──────────────────────────────
            logger.info(f"Converting HTML to markdown for job {job_id}...")
            html_content = input_path.read_text(encoding="utf-8")

            # Try trafilatura first (best quality), fall back to basic stripping
            try:
                import trafilatura
                markdown_content = trafilatura.extract(
                    html_content,
                    output_format="markdown",
                    include_comments=False,
                    include_tables=True,
                ) or ""
                if not markdown_content.strip():
                    raise RuntimeError("trafilatura produced empty output")
                logger.info(f"trafilatura extracted {len(markdown_content)} chars")
            except ImportError:
                logger.warning("trafilatura not installed; falling back to basic HTML stripping")
                # Basic fallback: strip tags
                import re
                # Remove script/style tags and their contents
                html_content = re.sub(r"<script[^>]*>.*?</script>", "", html_content, flags=re.DOTALL | re.IGNORECASE)
                html_content = re.sub(r"<style[^>]*>.*?</style>", "", html_content, flags=re.DOTALL | re.IGNORECASE)
                # Replace common block tags with newlines
                html_content = re.sub(r"</?(div|p|br|h[1-6]|li|tr)[^>]*>", "\n", html_content, flags=re.IGNORECASE)
                # Strip remaining tags
                html_content = re.sub(r"<[^>]+>", "", html_content)
                # Collapse whitespace
                html_content = "\n".join(line.strip() for line in html_content.splitlines() if line.strip())
                markdown_content = html_content
            except Exception as e:
                _update_job_status(job_id, "failed", f"HTML conversion failed: {e}", metadata_db_path=metadata_db_path)
                input_path.unlink()
                return

        elif input_ext == ".pdf":
            _update_job_status(job_id, "awaiting_marker", metadata_db_path=metadata_db_path)

            async with marker_lock:
                _update_job_status(job_id, "converting", metadata_db_path=metadata_db_path)
                try:
                    logger.info(f"Running Marker conversion for job {job_id}...")
                    markdown_content = await asyncio.to_thread(_convert_with_marker, str(input_path))

                    converted_dir = metadata_db_path.parent / "converted"
                    converted_dir.mkdir(exist_ok=True)
                    (converted_dir / f"{job_id}.md").write_text(markdown_content, encoding="utf-8")
                    logger.info(f"Marker conversion successful for {job_id}")

                except asyncio.CancelledError:
                    _update_job_status(job_id, "failed", "Marker cancelled", metadata_db_path=metadata_db_path)
                    input_path.unlink(missing_ok=True)
                    return
                except Exception as e:
                    _update_job_status(job_id, "failed", f"Marker failed: {e}", metadata_db_path=metadata_db_path)
                    logger.error(f"Marker error for {job_id}: {e}")
                    input_path.unlink(missing_ok=True)
                    return
        else:
            _update_job_status(job_id, "failed", f"Unsupported file type: {input_ext}", metadata_db_path=metadata_db_path)
            input_path.unlink()
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

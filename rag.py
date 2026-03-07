#!/usr/bin/env python3
"""Academic paper RAG search — CLI interface for Claude Code."""

import re
import sys
from pathlib import Path

import click
import lancedb
from lancedb.rerankers import RRFReranker
from rich.console import Console
from rich.markdown import Markdown
from sentence_transformers import SentenceTransformer

DB_PATH = Path(__file__).parent / "vectordb"
DOCS_PATH = Path(__file__).parent / "docs"
TABLE_NAME = "papers"
EMBED_MODEL = "BAAI/bge-base-en-v1.5"  # 768-dim, good for technical text
CHUNK_SIZE = 1000  # characters per chunk
CHUNK_OVERLAP = 200

console = Console(width=120)


def get_model():
    return SentenceTransformer(EMBED_MODEL, device="cuda")


# ─── Chunking ───────────────────────────────────────────────────────

def chunk_markdown(text: str, source: str) -> list[dict]:
    """Split markdown into overlapping chunks, preserving section headers."""
    lines = text.split("\n")
    chunks = []
    current_chunk = []
    current_len = 0
    current_headers = []
    chunk_idx = 0

    # Try to extract page numbers from Marker's span tags
    current_page = ""
    page_pattern = re.compile(r'<span id="page-(\d+)')

    for line in lines:
        # Track page numbers from Marker output
        page_match = page_pattern.search(line)
        if page_match:
            current_page = page_match.group(1)

        # Track headers for context
        if line.startswith("#"):
            level = len(line) - len(line.lstrip("#"))
            current_headers = [h for h in current_headers if h[0] < level]
            current_headers.append((level, line.strip("# ").strip()))

        current_chunk.append(line)
        current_len += len(line) + 1

        if current_len >= CHUNK_SIZE:
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

            # Overlap: keep last few lines
            overlap_lines = []
            overlap_len = 0
            for prev_line in reversed(current_chunk):
                overlap_len += len(prev_line) + 1
                if overlap_len > CHUNK_OVERLAP:
                    break
                overlap_lines.insert(0, prev_line)

            current_chunk = overlap_lines
            current_len = sum(len(l) + 1 for l in current_chunk)

    # Don't forget the last chunk
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


# ─── CLI ────────────────────────────────────────────────────────────

@click.group()
def cli():
    """Academic paper RAG search."""
    pass


@cli.command()
def ingest():
    """Ingest markdown files from docs/ into the vector database."""
    model = get_model()
    db = lancedb.connect(str(DB_PATH))

    all_chunks = []
    md_files = sorted(DOCS_PATH.rglob("*.md"))

    if not md_files:
        console.print(f"[red]No .md files found in {DOCS_PATH}[/red]")
        sys.exit(1)

    console.print(f"[bold]Ingesting {len(md_files)} files...[/bold]")

    for f in md_files:
        text = f.read_text(encoding="utf-8", errors="replace")
        source_name = f.stem
        chunks = chunk_markdown(text, source_name)
        all_chunks.extend(chunks)
        console.print(f"  {source_name}: {len(chunks)} chunks")

    console.print(f"\n[bold]Embedding {len(all_chunks)} total chunks...[/bold]")

    texts = [c["text"] for c in all_chunks]
    embeddings = model.encode(texts, show_progress_bar=True, batch_size=64)

    for chunk, emb in zip(all_chunks, embeddings):
        chunk["vector"] = emb.tolist()

    # Create or overwrite table
    if TABLE_NAME in db.list_tables().tables:
        db.drop_table(TABLE_NAME)

    table = db.create_table(TABLE_NAME, all_chunks)

    # Create full-text search index on the text column for hybrid search
    console.print("[bold]Creating full-text search index...[/bold]")
    table.create_fts_index("text", replace=True)

    console.print(f"\n[green]Done. {len(all_chunks)} chunks indexed with vector + FTS in {DB_PATH}[/green]")


@cli.command()
@click.argument("query")
@click.option("-n", "--top-n", default=5, help="Number of results to return")
@click.option("-s", "--source", default=None, help="Filter by source filename")
@click.option("--raw", is_flag=True, help="Plain text output (no formatting)")
@click.option("--mode", type=click.Choice(["hybrid", "vector", "fts"]), default="hybrid",
              help="Search mode: hybrid (default), vector-only, or full-text-only")
def search(query: str, top_n: int, source: str, raw: bool, mode: str):
    """Search papers with a natural language query."""
    model = get_model()
    db = lancedb.connect(str(DB_PATH))

    if TABLE_NAME not in db.list_tables().tables:
        print("ERROR: No index found. Run 'rag ingest' first.", file=sys.stderr)
        sys.exit(1)

    table = db.open_table(TABLE_NAME)

    if mode == "hybrid":
        query_embedding = model.encode([query])[0].tolist()
        reranker = RRFReranker()
        results = (
            table.search(query_type="hybrid")
            .vector(query_embedding)
            .text(query)
            .rerank(reranker)
            .limit(top_n)
        )
    elif mode == "vector":
        query_embedding = model.encode([query])[0].tolist()
        results = table.search(query_embedding).limit(top_n)
    else:  # fts
        results = table.search(query, query_type="fts").limit(top_n)

    if source:
        results = results.where(f"source = '{source}'")

    results = results.to_pandas()

    if results.empty:
        print("No results found.")
        return

    # Determine which score column is available
    score_col = "_relevance_score" if "_relevance_score" in results.columns else "_distance"

    if raw:
        for _, row in results.iterrows():
            score = row.get(score_col, 0)
            page_info = f" p.{row['page']}" if row.get("page") else ""
            print(f"--- [{row['source']}{page_info}] {row['section']} ({score_col}: {score:.4f}) ---")
            print(row["text"])
            print()
    else:
        for _, row in results.iterrows():
            score = row.get(score_col, 0)
            page_info = f" p.{row['page']}" if row.get("page") else ""
            console.rule(f"[bold cyan]{row['source']}{page_info}[/bold cyan] | {row['section']}")
            console.print(f"[dim]{score_col}: {score:.4f}[/dim]\n")
            console.print(Markdown(row["text"]))
            console.print()


@cli.command()
def stats():
    """Show index statistics."""
    db = lancedb.connect(str(DB_PATH))
    if TABLE_NAME not in db.list_tables().tables:
        print("No index found. Run 'rag ingest' first.")
        return

    table = db.open_table(TABLE_NAME)
    df = table.to_pandas()
    sources = df["source"].value_counts()

    console.print(f"[bold]Index: {len(df)} chunks from {len(sources)} sources[/bold]\n")
    for src, count in sources.items():
        console.print(f"  {src}: {count} chunks")


@cli.command()
def sources():
    """List all indexed source files."""
    db = lancedb.connect(str(DB_PATH))
    if TABLE_NAME not in db.list_tables().tables:
        print("No index found. Run 'rag ingest' first.")
        return

    table = db.open_table(TABLE_NAME)
    df = table.to_pandas()
    for src in sorted(df["source"].unique()):
        print(src)


if __name__ == "__main__":
    cli()

#!/usr/bin/env python3
"""Academic paper RAG search — CLI interface for Claude Code."""

import os
import sys
from pathlib import Path

import click
import lancedb
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

    for line in lines:
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
            })

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

    db.create_table(TABLE_NAME, all_chunks)
    console.print(f"\n[green]Done. {len(all_chunks)} chunks indexed in {DB_PATH}[/green]")


@cli.command()
@click.argument("query")
@click.option("-n", "--top-n", default=5, help="Number of results to return")
@click.option("-s", "--source", default=None, help="Filter by source filename")
@click.option("--raw", is_flag=True, help="Plain text output (no formatting)")
def search(query: str, top_n: int, source: str, raw: bool):
    """Search papers with a natural language query."""
    model = get_model()
    db = lancedb.connect(str(DB_PATH))

    if TABLE_NAME not in db.list_tables().tables:
        print("ERROR: No index found. Run 'rag ingest' first.", file=sys.stderr)
        sys.exit(1)

    table = db.open_table(TABLE_NAME)

    query_embedding = model.encode([query])[0].tolist()

    results = table.search(query_embedding).limit(top_n)

    if source:
        results = results.where(f"source = '{source}'")

    results = results.to_pandas()

    if results.empty:
        print("No results found.")
        return

    if raw:
        # Plain text output for Claude Code consumption
        for i, row in results.iterrows():
            print(f"--- [{row['source']}] {row['section']} (score: {row['_distance']:.4f}) ---")
            print(row["text"])
            print()
    else:
        for i, row in results.iterrows():
            console.rule(f"[bold cyan]{row['source']}[/bold cyan] | {row['section']}")
            console.print(f"[dim]Relevance: {1 - row['_distance']:.4f}[/dim]\n")
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

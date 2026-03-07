# RAG Server Setup Guide — Linux Box (Pop!_OS + RTX 5080)

A local academic paper search server that Claude Code queries via SSH.
No MCP, no protocol overhead — just `ssh linux-box "rag search 'your query'"`.

## Architecture

```
Mac (Claude Code)                    Linux Box (Pop!_OS)
─────────────────                    ───────────────────
bash: ssh linux "rag search ..."  →  rag CLI (Python)
                                       ├── LanceDB (embedded vector DB)
                                       ├── sentence-transformers (GPU embeddings)
                                       └── docs/ (Marker-extracted markdown)
```

**Why LanceDB over Qdrant:** For 30 papers (~2000 chunks), LanceDB is simpler —
no Docker container, no server process, just an embedded library. Qdrant is
overkill until you hit 100k+ chunks.

---

## Step 1: SSH Setup (Mac side)

Make sure you can SSH without a password prompt:

```bash
# On your Mac, if not already done:
ssh-copy-id your-user@linux-box-ip

# Test it:
ssh your-user@linux-box-ip "echo 'connected'"

# Add a shortcut to ~/.ssh/config:
cat >> ~/.ssh/config << 'EOF'

Host rag
    HostName 192.168.x.x    # <-- your Linux box IP
    User your-user           # <-- your username
    IdentityFile ~/.ssh/id_ed25519
EOF
```

Now `ssh rag "command"` works from your Mac.

---

## Step 2: Install uv on Linux box

```bash
ssh rag

# Install uv if not present
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.cargo/env  # or restart shell

# Verify
uv --version
```

---

## Step 3: Create the project

```bash
# On Linux box
mkdir -p ~/rag-server && cd ~/rag-server

# Init with uv
uv init --python 3.12
```

---

## Step 4: Install dependencies

```bash
cd ~/rag-server

uv add \
  lancedb \
  sentence-transformers \
  torch \
  tantivy \
  click \
  rich

# sentence-transformers will pull in torch with CUDA support automatically
# tantivy is for BM25 keyword search (hybrid search)
```

Verify GPU is visible:

```bash
uv run python -c "import torch; print(f'CUDA: {torch.cuda.is_available()}, GPU: {torch.cuda.get_device_name(0)}')"
# Should print: CUDA: True, GPU: NVIDIA GeForce RTX 5080
```

---

## Step 5: Copy papers to Linux box

From your Mac:

```bash
# Copy the Marker-extracted markdown files
scp -r ~/Desktop/SignalCanvas/docs/routing/extracted-markdown/ rag:~/rag-server/docs/
```

---

## Step 6: Create the RAG CLI

Create `~/rag-server/rag.py`:

```python
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
    if TABLE_NAME in db.table_names():
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

    if TABLE_NAME not in db.table_names():
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
    if TABLE_NAME not in db.table_names():
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
    if TABLE_NAME not in db.table_names():
        print("No index found. Run 'rag ingest' first.")
        return

    table = db.open_table(TABLE_NAME)
    df = table.to_pandas()
    for src in sorted(df["source"].unique()):
        print(src)


if __name__ == "__main__":
    cli()
```

Make it executable:

```bash
chmod +x ~/rag-server/rag.py
```

---

## Step 7: Create the wrapper script

Create `~/rag-server/rag` (no extension — this is what gets called):

```bash
#!/bin/bash
cd "$(dirname "$0")"
exec uv run python rag.py "$@"
```

```bash
chmod +x ~/rag-server/rag

# Add to PATH (add to ~/.bashrc or ~/.zshrc)
echo 'export PATH="$HOME/rag-server:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

---

## Step 8: Ingest the papers

```bash
# On Linux box
cd ~/rag-server
rag ingest
```

First run downloads the embedding model (~450MB) and indexes all papers.
With the RTX 5080, embedding should take seconds.

Verify:

```bash
rag stats
rag search "hyperedge routing steiner tree" --raw
```

---

## Step 9: Create the Mac-side helper script

On your Mac, in the SignalCanvas project:

Create `scripts/rag-query.sh`:

```bash
#!/bin/bash
# Query the RAG server on the Linux box
# Usage: ./scripts/rag-query.sh "your search query" [--top-n 5] [--source PaperName]
ssh rag "cd ~/rag-server && rag search '$1' --raw ${@:2}"
```

```bash
chmod +x ~/Desktop/SignalCanvas/scripts/rag-query.sh
```

---

## Step 10: Test from Mac

```bash
# From your Mac
./scripts/rag-query.sh "bundle routing heuristics for orthogonal edges"
./scripts/rag-query.sh "PathFinder negotiated congestion" --top-n 3
./scripts/rag-query.sh "port constraints" --source "Baumann2020"
```

---

## How Claude Code uses it

When I need to look something up in the papers, I'll just run:

```bash
./scripts/rag-query.sh "Wybrow interleaved heuristic Steiner tree construction"
```

And get back the relevant chunks as plain text. No MCP, no tool schema overhead,
no context tax. Just a bash command and text output.

---

## Optional: Add more papers later

1. Convert PDF to markdown with Marker (on either machine):
   ```bash
   marker_single paper.pdf --output_dir ~/rag-server/docs/
   ```
2. Re-index:
   ```bash
   ssh rag "rag ingest"
   ```

---

## Optional: HTTP endpoint (if SSH feels slow)

If SSH connection overhead bothers you, add a tiny HTTP server.
Create `~/rag-server/server.py`:

```python
"""Minimal HTTP wrapper — run with: uv run python server.py"""
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import json
import subprocess

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path != "/search":
            self.send_error(404)
            return

        params = parse_qs(parsed.query)
        query = params.get("q", [""])[0]
        top_n = params.get("n", ["5"])[0]

        if not query:
            self.send_error(400, "Missing ?q= parameter")
            return

        result = subprocess.run(
            ["uv", "run", "python", "rag.py", "search", query, "--raw", "-n", top_n],
            capture_output=True, text=True, cwd="/root/rag-server"
        )

        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(result.stdout.encode())

    def log_message(self, *args):
        pass  # silence logs

if __name__ == "__main__":
    print("RAG server on :8080")
    HTTPServer(("0.0.0.0", 8080), Handler).start()
```

Then the Mac script becomes:
```bash
curl -s "http://rag:8080/search?q=$(python3 -c 'import urllib.parse; print(urllib.parse.quote(sys.argv[1]))' "$1")"
```

But SSH is simpler to start with — no firewall config, no process management.

---

## Troubleshooting

**CUDA not found:** Install NVIDIA drivers for Pop!_OS:
```bash
sudo apt install system76-driver-nvidia
```

**Model download slow:** The BGE model downloads once (~450MB). Subsequent runs
load from `~/.cache/huggingface/`.

**SSH too slow:** Each SSH invocation has ~200ms overhead for connection setup.
If this matters, use the HTTP endpoint instead, or set up SSH multiplexing:
```
# In ~/.ssh/config on Mac
Host rag
    ControlMaster auto
    ControlPath ~/.ssh/sockets/%r@%h-%p
    ControlPersist 600
```
This keeps the SSH connection alive for 10 minutes, making subsequent calls instant.

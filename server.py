#!/usr/bin/env python3
"""Minimal HTTP wrapper for the RAG search CLI."""

import json
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs

import lancedb
from sentence_transformers import SentenceTransformer

DB_PATH = Path(__file__).parent / "vectordb"
TABLE_NAME = "papers"
EMBED_MODEL = "BAAI/bge-base-en-v1.5"

# Load model once at startup
print("Loading embedding model...", flush=True)
model = SentenceTransformer(EMBED_MODEL, device="cuda")
print("Ready.", flush=True)


def get_db():
    return lancedb.connect(str(DB_PATH))


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)

        if parsed.path == "/health":
            self._respond(200, "ok")
            return

        if parsed.path == "/search":
            self._handle_search(parse_qs(parsed.query))
            return

        if parsed.path == "/stats":
            self._handle_stats()
            return

        if parsed.path == "/sources":
            self._handle_sources()
            return

        self.send_error(404)

    def _handle_search(self, params):
        query = params.get("q", [""])[0]
        if not query:
            self.send_error(400, "Missing ?q= parameter")
            return

        top_n = int(params.get("n", ["5"])[0])
        source = params.get("source", [None])[0]

        db = get_db()
        if TABLE_NAME not in db.list_tables().tables:
            self._respond(500, "No index found. Run 'rag ingest' first.")
            return

        table = db.open_table(TABLE_NAME)
        query_embedding = model.encode([query])[0].tolist()
        results = table.search(query_embedding).limit(top_n)

        if source:
            results = results.where(f"source = '{source}'")

        results = results.to_pandas()

        output = []
        for _, row in results.iterrows():
            output.append(
                f"--- [{row['source']}] {row['section']} (score: {row['_distance']:.4f}) ---\n"
                f"{row['text']}\n"
            )

        self._respond(200, "\n".join(output) if output else "No results found.")

    def _handle_stats(self):
        db = get_db()
        if TABLE_NAME not in db.list_tables().tables:
            self._respond(200, "No index found.")
            return

        table = db.open_table(TABLE_NAME)
        df = table.to_pandas()
        sources = df["source"].value_counts()
        lines = [f"Index: {len(df)} chunks from {len(sources)} sources", ""]
        for src, count in sources.items():
            lines.append(f"  {src}: {count} chunks")
        self._respond(200, "\n".join(lines))

    def _handle_sources(self):
        db = get_db()
        if TABLE_NAME not in db.list_tables().tables:
            self._respond(200, "No index found.")
            return

        table = db.open_table(TABLE_NAME)
        df = table.to_pandas()
        self._respond(200, "\n".join(sorted(df["source"].unique())))

    def _respond(self, code, text):
        self.send_response(code)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(text.encode())

    def log_message(self, format, *args):
        # Only log errors, not every request
        if args and str(args[0]).startswith("4") or str(args[0]).startswith("5"):
            super().log_message(format, *args)


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    print(f"RAG server listening on 0.0.0.0:{port}", flush=True)
    HTTPServer(("0.0.0.0", port), Handler).serve_forever()

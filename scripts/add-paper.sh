#!/bin/bash
# Convert a PDF to markdown via Marker and add it to the RAG index.
# Usage: add-paper paper.pdf [paper2.pdf ...]
#
# Requires: marker-pdf (install with: uv tool install marker-pdf)
#
# What it does:
#   1. Converts each PDF to markdown using Marker
#   2. Moves the .md output to docs/extracted-markdown/
#   3. Re-ingests all documents into the vector database

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
DOCS_DIR="${PROJECT_DIR}/docs/extracted-markdown"
TEMP_DIR=$(mktemp -d)

trap 'rm -rf "$TEMP_DIR"' EXIT

if [ $# -eq 0 ]; then
    echo "Usage: add-paper paper.pdf [paper2.pdf ...]" >&2
    exit 1
fi

# Check for marker
if ! command -v marker_single &>/dev/null; then
    echo "Error: marker not found." >&2
    echo "Install with: uv tool install marker-pdf" >&2
    exit 1
fi

mkdir -p "$DOCS_DIR"

for pdf in "$@"; do
    if [ ! -f "$pdf" ]; then
        echo "Error: $pdf not found" >&2
        exit 1
    fi

    name=$(basename "$pdf" .pdf)
    echo "Converting: $pdf"
    marker_single "$pdf" --output_dir "$TEMP_DIR" 2>&1 | tail -1

    # Marker outputs to a subdirectory named after the file
    md_file=$(find "$TEMP_DIR" -name "*.md" -newer "$TEMP_DIR" | head -1)

    if [ -z "$md_file" ]; then
        echo "Error: Marker produced no markdown for $pdf" >&2
        exit 1
    fi

    cp "$md_file" "${DOCS_DIR}/${name}.md"
    echo "Added: ${name}.md"
done

echo ""
echo "Re-ingesting..."
cd "$PROJECT_DIR"
./rag ingest

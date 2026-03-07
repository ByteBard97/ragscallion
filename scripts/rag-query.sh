#!/bin/bash
# Query the RAG paper search server.
# Usage: rag-query "your search query" [options]
#
# Options:
#   -n NUM        Number of results (default: 5)
#   -s SOURCE     Filter by paper name
#   --sources     List all indexed papers
#   --stats       Show index statistics
#
# Examples:
#   rag-query "hyperedge routing steiner tree"
#   rag-query "port constraints" -n 3
#   rag-query "negotiated congestion" -s McMurchie1995-PathFinder-Negotiated-Congestion-Router
#   rag-query --sources
#   rag-query --stats

RAG_HOST="${RAG_HOST:-192.168.0.200}"
RAG_PORT="${RAG_PORT:-8085}"
BASE="http://${RAG_HOST}:${RAG_PORT}"

# Handle --sources and --stats before argument parsing
case "$1" in
    --sources) curl -sf "${BASE}/sources" && echo; exit ;;
    --stats)   curl -sf "${BASE}/stats" && echo; exit ;;
    --help|-h) head -17 "$0" | tail -16; exit ;;
esac

if [ -z "$1" ]; then
    echo "Usage: rag-query \"your search query\" [-n NUM] [-s SOURCE]" >&2
    exit 1
fi

QUERY="$1"; shift

TOP_N=5
SOURCE=""

while [ $# -gt 0 ]; do
    case "$1" in
        -n) TOP_N="$2"; shift 2 ;;
        -s) SOURCE="$2"; shift 2 ;;
        *)  echo "Unknown option: $1" >&2; exit 1 ;;
    esac
done

# URL-encode the query (spaces -> +, special chars -> %XX)
ENCODED=$(python3 -c "import urllib.parse, sys; print(urllib.parse.quote_plus(sys.argv[1]))" "$QUERY")

URL="${BASE}/search?q=${ENCODED}&n=${TOP_N}"
[ -n "$SOURCE" ] && URL="${URL}&source=${SOURCE}"

curl -sf "$URL"

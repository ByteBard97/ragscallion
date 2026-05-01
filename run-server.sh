#!/bin/bash
export MARKER_PYTHON=/home/geoff/.local/share/uv/tools/marker-pdf/bin/python
cd "$(dirname "$0")"
exec .venv/bin/python server.py "$@"

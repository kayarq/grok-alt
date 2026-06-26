#!/bin/bash
# Launch Grok Trace Viewer
cd "$(dirname "$0")"
exec python3 server.py "$@"
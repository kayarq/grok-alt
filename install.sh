#!/usr/bin/env bash
# Install Grok Trace Viewer into ~/.local/share/grok-trace-viewer and put a
# launcher on PATH (~/.local/bin/grok-trace-viewer).
set -euo pipefail

REPO_URL="${GROK_TRACE_VIEWER_REPO:-https://github.com/haeiau1/grok-trace-viewer.git}"
INSTALL_DIR="${GROK_TRACE_VIEWER_HOME:-$HOME/.local/share/grok-trace-viewer}"
BIN_DIR="${XDG_BIN_HOME:-$HOME/.local/bin}"
LAUNCHER="$BIN_DIR/grok-trace-viewer"

need() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Missing required command: $1" >&2
    exit 1
  }
}

need git
need python3

mkdir -p "$BIN_DIR"

if [[ -d "$INSTALL_DIR/.git" ]]; then
  echo "Updating existing install at $INSTALL_DIR …"
  git -C "$INSTALL_DIR" pull --ff-only
elif [[ -d "$INSTALL_DIR" ]]; then
  echo "Directory exists but is not a git repo: $INSTALL_DIR" >&2
  echo "Move it aside or set GROK_TRACE_VIEWER_HOME to another path." >&2
  exit 1
else
  echo "Cloning into $INSTALL_DIR …"
  git clone "$REPO_URL" "$INSTALL_DIR"
fi

chmod +x "$INSTALL_DIR/server.py" "$INSTALL_DIR/start.sh" "$INSTALL_DIR/install.sh"

cat > "$LAUNCHER" << LAUNCH
#!/usr/bin/env bash
exec python3 "$INSTALL_DIR/server.py" "\$@"
LAUNCH
chmod +x "$LAUNCHER"

echo
echo "Installed."
echo "  App dir:  $INSTALL_DIR"
echo "  Launcher: $LAUNCHER"
echo
if ! command -v grok-trace-viewer >/dev/null 2>&1; then
  echo "Add this to your shell profile if $BIN_DIR is not on PATH:"
  echo "  export PATH=\"$BIN_DIR:\$PATH\""
  echo
fi
echo "Run:"
echo "  grok-trace-viewer"
echo "  # or:  $INSTALL_DIR/start.sh"
echo
echo "Opens http://127.0.0.1:8765/ (stdlib Python only — no pip install)."

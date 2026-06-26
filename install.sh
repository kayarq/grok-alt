#!/usr/bin/env bash
# Install grok-alt (tmux + TUI companion for Grok traces).
set -euo pipefail

REPO_URL="${GROK_ALT_REPO:-https://github.com/haeiau1/grok-alt.git}"
INSTALL_DIR="${GROK_ALT_HOME:-$HOME/.local/share/grok-alt}"
BIN_DIR="${XDG_BIN_HOME:-$HOME/.local/bin}"

need() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Missing required command: $1" >&2
    exit 1
  }
}

need git
need python3

if ! command -v tmux >/dev/null 2>&1; then
  echo "Warning: tmux not found. Install it for side-by-side mode (brew install tmux)." >&2
fi

mkdir -p "$BIN_DIR"

if [[ -d "$INSTALL_DIR/.git" ]]; then
  echo "Updating existing install at $INSTALL_DIR …"
  git -C "$INSTALL_DIR" pull --ff-only
elif [[ -d "$INSTALL_DIR" ]]; then
  echo "Directory exists but is not a git repo: $INSTALL_DIR" >&2
  echo "Move it aside or set GROK_ALT_HOME to another path." >&2
  exit 1
else
  echo "Cloning into $INSTALL_DIR …"
  git clone "$REPO_URL" "$INSTALL_DIR"
fi

cd "$INSTALL_DIR"
chmod +x bin/grok-alt bin/grok-alt-tmux install.sh 2>/dev/null || true

if [[ ! -d .venv ]]; then
  echo "Creating Python venv …"
  python3 -m venv .venv
fi
echo "Installing Python deps (textual, rich) …"
.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q -r requirements.txt

ln -sfn "$INSTALL_DIR/bin/grok-alt" "$BIN_DIR/grok-alt"
ln -sfn "$INSTALL_DIR/bin/grok-alt-tmux" "$BIN_DIR/grok-alt-tmux"

echo
echo "Installed."
echo "  App dir:   $INSTALL_DIR"
echo "  Commands:  $BIN_DIR/grok-alt"
echo "             $BIN_DIR/grok-alt-tmux"
echo
if ! command -v grok-alt >/dev/null 2>&1; then
  echo "Add this to your shell profile if $BIN_DIR is not on PATH:"
  echo "  export PATH=\"$BIN_DIR:\$PATH\""
  echo
fi
echo "Quick start (tmux side-by-side — recommended):"
echo "  grok-alt tmux"
echo "  # or:  grok-alt-tmux"
echo
echo "TUI only (no tmux):"
echo "  grok-alt"
echo
echo "Requires Grok CLI on PATH or at ~/.grok/bin/grok"

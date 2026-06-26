# Grok Trace Viewer

A local web UI for reading [Grok](https://grok.x.ai) session traces and unified logs more easily.

Runs entirely on your machine (`127.0.0.1`). **Python 3 stdlib only** — no `pip install`, no Node, no database.

> **Note:** This is the **browser** trace viewer. For the terminal TUI and **side-by-side tmux** layout (traces | Grok), see the companion tool [`grok-alt`](https://github.com/haeiau1/grok-alt) if you publish it, or your local `~/.grok/worktrees/grok-alt` install. The web viewer works on its own.

## Requirements

- **Python 3.9+** (3.10+ recommended)
- Grok installed so session data exists under `~/.grok/sessions/` (and optionally `~/.grok/logs/unified.jsonl`)
- A modern browser

## Install

Pick one of the methods below.

### Option A — One-liner install (recommended for others)

After this repo is on GitHub under your account:

```bash
curl -fsSL https://raw.githubusercontent.com/haeiau1/grok-trace-viewer/main/install.sh | bash
```

That clones into `~/.local/share/grok-trace-viewer` and adds a `grok-trace-viewer` command under `~/.local/bin`.

Then run:

```bash
grok-trace-viewer
```

Ensure `~/.local/bin` is on your `PATH` (common on macOS/Linux). Add if needed:

```bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc && source ~/.zshrc
```

**Update later:**

```bash
curl -fsSL https://raw.githubusercontent.com/haeiau1/grok-trace-viewer/main/install.sh | bash
# or:
git -C ~/.local/share/grok-trace-viewer pull
```

**Custom install location:**

```bash
GROK_TRACE_VIEWER_HOME=~/tools/grok-trace-viewer \
  bash <(curl -fsSL https://raw.githubusercontent.com/haeiau1/grok-trace-viewer/main/install.sh)
```

### Option B — Clone and run (no install script)

```bash
git clone https://github.com/haeiau1/grok-trace-viewer.git
cd grok-trace-viewer
python3 server.py
```

Or:

```bash
./start.sh
```

Opens **http://127.0.0.1:8765/** in your browser.

### Option C — Download ZIP (no git)

1. On GitHub: **Code → Download ZIP**
2. Unzip anywhere
3. Run:

```bash
cd grok-trace-viewer-main   # folder name may include -main
python3 server.py
# or: ./start.sh
```

### Option D — Use the copy you already have

```bash
cd ~/Desktop/grok-trace-viewer   # or wherever you keep it
python3 server.py
```

## Usage

```bash
python3 server.py                 # default port 8765, opens browser
python3 server.py --port 9000     # different port
python3 server.py --no-open       # don't auto-open browser
python3 server.py --grok-home ~/.grok   # override GROK_HOME
```

Stop with `Ctrl+C`.

Environment:

| Variable | Meaning |
|----------|---------|
| `GROK_HOME` | Grok data root (default `~/.grok`) |

## What it reads

| Source | Path | What you get |
|--------|------|----------------|
| **Sessions** | `~/.grok/sessions/<cwd>/<session-id>/` | Full conversation traces |
| **events.jsonl** | per session | Turn/tool/permission/phase lifecycle |
| **updates.jsonl** | per session | ACP stream (user/agent/tool chunks) |
| **chat_history.jsonl** | per session | Raw model chat messages |
| **summary.json** | per session | Title, model, timestamps, counts |
| **Unified log** | `~/.grok/logs/unified.jsonl` | Runtime telemetry (shell, pager, auth, MCP, …) |

## Views

### Timeline (default)
Merged, color-coded stream of `events.jsonl` + `updates.jsonl`:
- turns / loops
- tool calls
- agent / user messages
- permissions
- phases (hidden by default — toggle off “hide phases” to see them)
- Click any card to expand full JSON

### Chat
Reconstructed conversation from `updates.jsonl` (fallback: `chat_history.jsonl`). Tool calls and results shown as blocks.

### Overview
Session metadata, token/tool stats, event-type histograms, files in the session directory.

### Unified Log
Search/filter `~/.grok/logs/unified.jsonl` by text, `msg`, `src`, or session id. Click a row for full entry JSON. **Stats** shows top message types.

## Tips

1. **Pick the session** on the left (filter by title/cwd/id).
2. Current session id is auto-filled into the log `sid` filter when you select it.
3. For debugging MCP/auth/tools, use **Unified Log** with `msg` filters like `mcp`, `tool`, `auth`.
4. For “what did the agent do?”, use **Timeline** + **Chat**.
5. Hit **Refresh** (or restart the server) after new Grok activity if the session list looks stale.

## Layout

```
grok-trace-viewer/
  server.py          # API + static file server (stdlib only)
  start.sh           # local launcher
  install.sh         # clone/update + PATH launcher for end users
  static/index.html  # UI (single page)
  README.md
  LICENSE
```

## Privacy

Runs only on `127.0.0.1`. Data never leaves your machine. Session files are read-only (the viewer does not modify Grok data).

## Uninstall

If you used `install.sh`:

```bash
rm -f ~/.local/bin/grok-trace-viewer
rm -rf ~/.local/share/grok-trace-viewer
```

If you only cloned the repo, delete that directory.

## License

MIT — see [LICENSE](LICENSE).

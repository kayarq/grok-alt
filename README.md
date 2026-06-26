# grok-alt (tmux)

Companion **trace viewer in the terminal**, designed to run **side-by-side with real Grok in tmux**.

Grok’s own UI is a closed binary (`~/.grok/bin/grok`). This tool does **not** modify it. It reads session files under `~/.grok/sessions/` and shows a readable timeline / chat / logs in a TUI on the **left** pane while you chat with Grok on the **right**.

```
┌──────────────────┬─────────────────────────────┐
│  grok-alt (TUI)  │  real Grok agent            │
│  traces / chat   │  type prompts here          │
│  ~42% width      │  ~58% width                 │
└──────────────────┴─────────────────────────────┘
```

## Requirements

| Need | Notes |
|------|--------|
| **tmux** | `brew install tmux` (macOS) or your distro package |
| **Python 3.9+** | TUI uses `textual` and `rich` (installed into a local venv) |
| **Grok CLI** | `grok` on `PATH` or `~/.grok/bin/grok` |
| **git** | For clone / one-liner install |

## Install

### Option A — One-liner (easiest for others)

```bash
curl -fsSL https://raw.githubusercontent.com/haeiau1/grok-alt/main/install.sh | bash
```

If the GitHub repository is still named `grok-trace-viewer`, use:

```bash
curl -fsSL https://raw.githubusercontent.com/haeiau1/grok-trace-viewer/main/install.sh | bash
```

This will:

1. Clone into `~/.local/share/grok-alt`
2. Create a Python venv and install `requirements.txt`
3. Symlink `grok-alt` and `grok-alt-tmux` into `~/.local/bin`

Put `~/.local/bin` on your `PATH` if needed:

```bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc && source ~/.zshrc
```

**Update later** — run the same one-liner again, or:

```bash
git -C ~/.local/share/grok-alt pull
~/.local/share/grok-alt/.venv/bin/pip install -r ~/.local/share/grok-alt/requirements.txt
```

### Option B — Clone and install yourself

```bash
git clone https://github.com/haeiau1/grok-alt.git
cd grok-alt

python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
chmod +x bin/grok-alt bin/grok-alt-tmux

# Optional: put on PATH
mkdir -p ~/.local/bin
ln -sfn "$(pwd)/bin/grok-alt" ~/.local/bin/grok-alt
ln -sfn "$(pwd)/bin/grok-alt-tmux" ~/.local/bin/grok-alt-tmux
```

(Use the `grok-trace-viewer` GitHub URL instead if the repo has not been renamed yet — contents are the same.)

### Option C — Download ZIP (no git)

1. On GitHub: **Code → Download ZIP**
2. Unzip, then from the folder:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
chmod +x bin/grok-alt bin/grok-alt-tmux
./bin/grok-alt-tmux          # or: ./bin/grok-alt tmux
```

## Usage (tmux — main workflow)

```bash
grok-alt tmux              # recommended: traces | Grok
# same thing:
grok-alt-tmux

# Pass flags through to Grok on the right pane:
grok-alt tmux -- -c                 # continue latest Grok session
grok-alt-tmux -c
grok-alt-tmux -r <session-id>       # resume a specific session
```

### tmux keys

Prefix is usually **Ctrl-b**:

| Keys | Action |
|------|--------|
| `Ctrl-b` then `←` / `→` | Switch between trace pane and Grok |
| `Ctrl-b` then `z` | Zoom current pane fullscreen |
| `Ctrl-b` then `d` | Detach (session keeps running) |
| Mouse | Drag the pane border (mouse is enabled in the session) |

```bash
tmux attach -t grok-alt              # re-attach after detach
tmux kill-session -t grok-alt        # fully quit both panes
```

If a session named `grok-alt` already exists, the launcher **attaches** instead of starting a second one. Kill it first if you want a fresh layout.

### TUI only (no tmux)

```bash
grok-alt              # open trace TUI alone
grok-alt tui          # same
grok-alt list         # print recent sessions (no UI)
grok-alt version
```

## Keys inside the TUI (left pane)

| Key | Action |
|-----|--------|
| `↑` / `↓` | Browse sessions |
| `Enter` | Load selected session (pins it; stops auto-jump) |
| `1`–`5` | Timeline · Chat · Overview · Logs · Diffs |
| `r` | Full refresh + re-follow newest session for this cwd |
| `f` | Toggle **live follow** (on by default, ~1s poll) |
| `/` | Filter sessions |
| `p` | Toggle noisy phase events in timeline |
| `t` | Toggle tool blocks in chat |
| `d` | Export selected turn under `~/grok-turn-exports/` |
| `g` | Exit TUI → launch real **Grok** (new session) |
| `c` | Exit TUI → `grok -c` |
| `R` | Exit TUI → `grok -r <selected-id>` |
| `?` | Help |
| `q` | Quit |

**Live follow:** while Grok runs on the right, the left pane polls `~/.grok/sessions`, selects the newest session for your current directory, and refreshes views when files change. Status shows `[LIVE]`. Press `f` to pause, or pick another session to pin it. Override interval with `GROK_ALT_POLL_INTERVAL=0.5`.

## What it reads

| Source | Path |
|--------|------|
| Sessions | `~/.grok/sessions/<cwd>/<session-id>/` |
| Timeline | `events.jsonl` + `updates.jsonl` |
| Chat | Rebuilt from `updates.jsonl` |
| Runtime log | `~/.grok/logs/unified.jsonl` |

Override Grok’s data root with `GROK_HOME` if needed.

## Environment variables

| Variable | Default | Meaning |
|----------|---------|---------|
| `GROK_ALT_HOME` | directory containing `bin/` + `grok_alt/` | Install root |
| `GROK_ALT_BIN` | `$GROK_ALT_HOME/bin/grok-alt` | TUI launcher (tmux script) |
| `GROK_BIN` | `~/.grok/bin/grok` | Real Grok binary |
| `GROK_ALT_TMUX_SESSION` | `grok-alt` | tmux session name |
| `GROK_ALT_POLL_INTERVAL` | `1` | Live-follow poll seconds |
| `GROK_HOME` | `~/.grok` | Sessions / logs root |
| `GROK_ALT_TURN_EXPORT_DIR` | `~/grok-turn-exports` | Turn export destination |

## Layout (repo)

```
grok-alt/
  bin/grok-alt           # CLI entry (uses .venv)
  bin/grok-alt-tmux      # tmux side-by-side launcher
  grok_alt/              # Python package (TUI + readers)
  requirements.txt       # textual, rich
  install.sh             # one-liner installer for end users
  README.md
  LICENSE
```

## Uninstall

```bash
rm -f ~/.local/bin/grok-alt ~/.local/bin/grok-alt-tmux
rm -rf ~/.local/share/grok-alt
# if you cloned elsewhere, delete that directory instead
```

## Privacy

Reads session files **locally** and never uploads them. Does not change Grok’s proprietary binary or rewrite session data (exports you trigger with `d` are written only where you configure).

## License

MIT — see [LICENSE](LICENSE).

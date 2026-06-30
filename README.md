# grok-alt v2

**Terminal companion for [Grok CLI](https://grok.com)** — a Textual TUI that reads your local session files and shows timelines, chat, tools, diffs, and logs **without modifying Grok’s binary**.

**v2** is a major pass on correctness and day-to-day use: tools are finalized at **turn boundaries** (not on misleading early “completed” events), exports and the UI show **full tool bodies**, turn selection **reveals** that turn’s tools, the **tmux left pane stays up** when installed via PATH symlinks, and **`q` can tear down the whole tmux session** so you return to the shell cleanly.

```
┌──────────────────────┬────────────────────────────┐
│  grok-alt (TUI)      │  real Grok agent           │
│  sessions · timeline │  prompts & permissions     │
│  chat · tools · diffs│  ~58% width                │
│  ~42% width          │                            │
└──────────────────────┴────────────────────────────┘
```

Grok remains the agent. grok-alt is a **read-only inspector** (plus optional turn export and “launch Grok” shortcuts).

---

## What it does

| Capability | Description |
|------------|-------------|
| **Session browser** | Lists sessions under `~/.grok/sessions/`, filter with `/`, live-follow newest session for your cwd |
| **Timeline** | Merged `events.jsonl` + `updates.jsonl` stream (turns, tools, permissions, …) |
| **Chat** | Rebuilt conversation: user prompts, agent text, **one collapsible block per tool** with full args/results |
| **Turn focus** | “Your prompts” list — select a turn to scroll there and **expand that turn’s tools** |
| **Diffs** | Code edits for the **selected turn** (or session), per-file unified diffs |
| **Overview** | Summary, models, event/update type counts |
| **Logs** | `~/.grok/logs/unified.jsonl` filtered to the selected session |
| **Turn export (`d`)** | Markdown under `~/grok-turn-exports/` (Prompt / Trace / Response + optional artifact copies) — **only when the turn is finished** |
| **tmux side-by-side** | Left = TUI, right = real `grok`; `q` in the TUI can kill the whole session |
| **Launch Grok** | `g` / `c` / `R` exit the TUI and exec Grok (standalone mode; in tmux prefer the right pane) |

It does **not** upload session data, rewrite Grok’s proprietary binary, or act as a second agent.

---

## Requirements

| Need | Notes |
|------|--------|
| **Python 3.9+** | 3.10+ recommended; uses `list[str] \| None` style with `from __future__ import annotations` |
| **textual** + **rich** | Installed into a project `.venv` via `requirements.txt` |
| **tmux** | For the recommended side-by-side layout (`grok-alt tmux`) |
| **Grok CLI** | `~/.grok/bin/grok` or `grok` on `PATH` |
| **git** | Clone / one-liner install |

---

## Setup

### Option A — One-liner (end users)

```bash
curl -fsSL https://raw.githubusercontent.com/haeiau1/grok-alt/main/install.sh | bash
```

Until this PR is merged, point at the fork PR branch or clone Option B from **kayarq/grok-alt** `develop`.

What install does:

1. Clone/update into `~/.local/share/grok-alt` (override with `GROK_ALT_HOME`)
2. Create `.venv` and `pip install -r requirements.txt`
3. Symlink `grok-alt` and `grok-alt-tmux` into `~/.local/bin` (override with `XDG_BIN_HOME`)

Ensure `~/.local/bin` is on your `PATH`:

```bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc   # or ~/.zshrc
source ~/.bashrc
```

**v2 launcher note:** wrappers resolve **symlinks** to the real install root so PATH installs use the correct venv (fixes a dead left pane when `ROOT` was wrongly `~/.local`).

Verify (must work from any directory, e.g. `/tmp`):

```bash
cd /tmp && grok-alt version && grok-alt list | head
```

### Option B — Clone (developers / this PR)

```bash
git clone https://github.com/haeiau1/grok-alt.git   # or kayarq/grok-alt until merged
cd grok-alt
git checkout develop    # v2 work branch on the fork

python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
chmod +x bin/grok-alt bin/grok-alt-tmux

# optional PATH links
mkdir -p ~/.local/bin
ln -sfn "$(pwd)/bin/grok-alt" ~/.local/bin/grok-alt
ln -sfn "$(pwd)/bin/grok-alt-tmux" ~/.local/bin/grok-alt-tmux
```

### Option C — ZIP download

Unzip, then same venv + `pip` steps as Option B; run `./bin/grok-alt-tmux` from the folder.

### Update

```bash
# install-dir update
git -C ~/.local/share/grok-alt pull
~/.local/share/grok-alt/.venv/bin/pip install -r ~/.local/share/grok-alt/requirements.txt

# or re-run the one-liner
```

### Uninstall

```bash
rm -f ~/.local/bin/grok-alt ~/.local/bin/grok-alt-tmux
rm -rf ~/.local/share/grok-alt
# delete your clone if you used Option B
```

---

## Usage

### Recommended: tmux side-by-side

```bash
grok-alt tmux              # or: grok-alt-tmux
grok-alt tmux -- -c        # pass flags through to Grok on the right
grok-alt-tmux -r <session-id>
```

| Action | How |
|--------|-----|
| Focus panes | `Ctrl-b` then `←` / `→` (default tmux prefix) |
| Zoom pane | `Ctrl-b` `z` |
| Detach (leave running) | `Ctrl-b` `d` |
| **Quit everything → shell** | **`q` or Ctrl+C in the TUI** (kills session `grok-alt`) |
| Re-attach | `tmux attach -t grok-alt` |
| Force kill | `tmux kill-session -t grok-alt` |

If session `grok-alt` already exists with a live left pane, the launcher **attaches**. If the left pane is dead, it **recreates** the session.

Disable auto-kill on quit: `GROK_ALT_KILL_TMUX_ON_QUIT=0`.

### TUI only (no tmux)

```bash
grok-alt              # default = tui
grok-alt tui
grok-alt list         # recent sessions (no UI)
grok-alt version
```

---

## TUI guide

### Layout

- **Left sidebar** — session list + filter (`/`)
- **Main tabs** — Timeline · Chat · Overview · Logs · Diffs (`1`–`5`)
- **Status line** — live mode, selected session, hints
- **Footer** — key bindings

### Keys (global, priority bindings)

| Key | Action |
|-----|--------|
| `↑` / `↓` | Move in focused list |
| `Enter` | Activate selection (session / prompt / diff file) |
| `1` … `5` | Timeline · Chat · Overview · Logs · Diffs |
| `r` | Full refresh; resume live auto-select for cwd |
| `f` | Toggle **live follow** (default on; polls ~1.5s) |
| `/` | Focus session filter |
| `p` | Toggle phase events on Timeline |
| `t` | Hide/show tool rows in Chat |
| `e` / `x` | Expand/collapse focused tool |
| `E` / `X` | Expand/collapse **all** tools |
| `[` / `]` | Move tool focus in Chat |
| `d` / `D` | **Export** selected turn (blocked if turn still running) |
| `g` | Exit TUI → `grok` (new session) |
| `c` | Exit TUI → `grok -c` |
| `R` | Exit TUI → `grok -r <selected-id>` |
| `?` | Help overlay |
| `q` / `Ctrl+C` | Quit (in tmux: end companion session) |

### Sessions & live follow

- Sessions are discovered under `GROK_HOME` (default `~/.grok`) → `sessions/<url-encoded-cwd>/<uuid>/`.
- With **live follow on** and no pin, the TUI prefers the **newest session for the current working directory**.
- **Enter** on a session pins it (stops auto-jump). **`r`** clears the pin and refreshes.

### Chat tab

- **Your prompts** (top) — every user turn; select one to:
  - Scroll the chat stream to that prompt
  - **Expand tools that belong to that turn** (no need for Expand all after switching sessions)
  - Scope **Diffs** and **export** to that turn
- **Toolbar** — Expand all tools / Collapse all (in-place; avoids remount crashes)
- **Tool rows** — click the **▶ title** (Collapsible) to open full detail: command, stdout (including terminal logs for long/background shells), file contents, greps, diffs, MCP payloads, etc.
- Tool results are assembled **per `toolCallId` once the turn completes** (or you start a new user message), so background “task started” is not treated as the final result.

### Diffs tab

- Files changed **during the selected prompt/turn** (fallback: last turn / whole session metadata).
- Pick a file on the left → colored unified diff on the right.

### Turn exports (`d` / `D` / `y`)

Writes under `GROK_ALT_TURN_EXPORT_DIR` (default `~/grok-turn-exports/`). Names include a **session title slug**, **8-char session id**, and **turn number** (plus a short prompt slug on turn folders).

| Key | Action |
|-----|--------|
| **`d`** | Export **selected** turn only |
| **`D`** | **Full chat** — all completed turns |
| **`y`** | **Range** — modal: 1-based from/to turn numbers |

**Single turn** layout:

```text
{title}_{sid8}_turn-NNN_{prompt-slug}/
  {title}_{sid8}_turn-NNN.md
  files/                         # optional artifacts (terminal logs, downloads, …)
```

**Full chat / range** layout (mother folder + one child per turn + flat md pack):

```text
{title}_{sid8}_full-chat_turns-001-0NN_<timestamp}/   # or …_range-AAA-BBB_<timestamp>/
  INDEX.md
  all-turn-md-exports/              # all turn .md copies only (no files/ trees)
    {title}_{sid8}_turn-001.md
    {title}_{sid8}_turn-002.md
    …
  {title}_{sid8}_turn-001_{prompt-slug}/   # full detail per turn
    {title}_{sid8}_turn-001.md
    files/
  {title}_{sid8}_turn-002_…/
    …
```

Markdown sections per turn: **Prompt**, **Trace** (tools + optional timeline/file changes), **Response**.

**v2 rule:** if a turn is still in progress (no `turn_completed` and no later user prompt yet), that turn is **blocked / skipped** (single-turn export warns and aborts; batch exports skip incomplete turns and list them in `INDEX.md`). After `turn_completed`, a short settle delay (`GROK_ALT_TURN_SETTLE_SECONDS`, default `1`) allows late log flushes.

### Privacy

Reads **local** session and log files only. Does not upload them. Does not rewrite Grok session data; exports you trigger go only where you configure.

---

## Data sources

| Source | Path |
|--------|------|
| Sessions | `~/.grok/sessions/<cwd-key>/<session-id>/` |
| Timeline | `events.jsonl`, `updates.jsonl` |
| Chat | Rebuilt mainly from `updates.jsonl` (fallback `chat_history.jsonl`) |
| Shell output files | Often `…/terminal/<toolCallId>.log` |
| Runtime log | `~/.grok/logs/unified.jsonl` |
| Summary | `summary.json`, `signals.json` |

Override Grok’s data root with `GROK_HOME`.

---

## Environment variables

| Variable | Default | Meaning |
|----------|---------|---------|
| `GROK_ALT_HOME` | Parent of `bin/` (resolved through symlinks) | Install / package root |
| `GROK_ALT_BIN` | `$GROK_ALT_HOME/bin/grok-alt` | TUI launcher used by tmux script |
| `GROK_BIN` | `~/.grok/bin/grok` | Real Grok binary |
| `GROK_HOME` | `~/.grok` | Sessions + logs root |
| `GROK_ALT_TMUX_SESSION` | `grok-alt` | tmux session name |
| `GROK_ALT_KILL_TMUX_ON_QUIT` | `1` | `q` kills that tmux session when running inside it |
| `GROK_ALT_POLL_INTERVAL` | `1.5` | Live-follow poll seconds |
| `GROK_ALT_TURN_EXPORT_DIR` | `~/grok-turn-exports` | Turn export destination |
| `GROK_ALT_TURN_SETTLE_SECONDS` | `1` | Wait after turn complete before export |
| `GROK_ALT_TOOL_FULL_CHARS` | `2000000` | Per-section body ceiling (UI + export) |
| `GROK_ALT_TOOL_FULL_LINES` | `500000` | Per-section line ceiling |
| `GROK_ALT_CHAT_VIEW_MAX_LINES` | `0` (unlimited) | Cap on `updates.jsonl` lines when building chat |
| `XDG_BIN_HOME` | `~/.local/bin` | Symlink target for install.sh |

---

## Repository layout

```text
grok-alt/
  bin/grok-alt           # CLI entry (venv + python -m grok_alt)
  bin/grok-alt-tmux      # tmux side-by-side launcher
  grok_alt/
    __main__.py          # tui | tmux | list | version
    core.py              # session readers, tool merge, export
    pretty.py            # Rich rendering for tools/chat
    tui.py               # Textual app
  requirements.txt       # textual, rich
  install.sh             # one-liner installer
  README.md
  LICENSE                # MIT
```

---

## Troubleshooting

| Symptom | What to try |
|---------|-------------|
| Left tmux pane empty / dies immediately | Update to v2 launchers; `cd /tmp && grok-alt version` must work; check `GROK_ALT_HOME` points at the install that has `.venv` |
| `No module named grok_alt` / `rich` | Recreate venv in install dir; reinstall requirements; don’t use a random `~/.local/.venv` |
| Tools look empty until Expand all | Select the turn in **Your prompts** (v2 expands that turn’s tools); or use Expand all on Chat |
| Export blocked | Wait for the turn to finish; status explains in-progress; then `d` |
| Stuck on old tmux layout | `tmux kill-session -t grok-alt` then `grok-alt tmux` again |
| Wrong session auto-selected | Pin with Enter on the right session; or `f` off live follow |
| TUI crash on timeline | Update to latest v2 (Rich markup escape + chat ID generation); press `r` |

---

## v2 highlights (vs earlier public release)

1. **Turn-accurate tool traces** — defer finalize until turn complete; handle `BackgroundTaskStarted` + terminal logs.
2. **Full tool fidelity** in UI and export (high limits, not 24-line previews).
3. **Export only for completed turns** (+ optional settle delay).
4. **Turn selection reveals tools** for that prompt.
5. **PATH/symlink install reliability** for the left pane.
6. **`q` ends the tmux companion session** (configurable).
7. **Crash hardening** — list refresh IDs, RichLog escaping, safer chat remounts, lighter live session index.

---

## License

MIT — see [LICENSE](LICENSE).

"""Shared Grok session/log readers for grok-alt TUI and web viewer."""

from __future__ import annotations

import json
import os
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote

GROK_HOME = Path(os.environ.get("GROK_HOME", Path.home() / ".grok")).expanduser()
SESSIONS_DIR = GROK_HOME / "sessions"
LOGS_DIR = GROK_HOME / "logs"
UNIFIED_LOG = LOGS_DIR / "unified.jsonl"
# Turn exports (d key): default ~/grok-turn-exports — override with GROK_ALT_TURN_EXPORT_DIR
TURN_EXPORT_DIR = Path(
    os.environ.get("GROK_ALT_TURN_EXPORT_DIR", Path.home() / "grok-turn-exports")
).expanduser()

UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.I,
)

DEFAULT_GROK_BIN = Path.home() / ".grok" / "bin" / "grok"


def grok_binary() -> str:
    for candidate in (
        os.environ.get("GROK_BIN"),
        str(DEFAULT_GROK_BIN),
        str(Path.home() / ".local" / "bin" / "grok"),
        "grok",
    ):
        if not candidate:
            continue
        p = Path(candidate)
        if p.is_file() and os.access(p, os.X_OK):
            return str(p)
        if candidate == "grok":
            return "grok"
    return "grok"


def decode_cwd_key(key: str) -> str:
    try:
        return unquote(key)
    except Exception:
        return key


def load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return None


def iter_jsonl(path: Path, max_lines: int | None = None):
    if not path.exists():
        return
    with path.open("r", encoding="utf-8", errors="replace") as f:
        for i, line in enumerate(f):
            if max_lines is not None and i >= max_lines:
                break
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                yield {"_raw": line, "_parse_error": True}


def line_count(path: Path) -> int:
    if not path.exists():
        return 0
    try:
        with path.open("rb") as f:
            return sum(1 for _ in f)
    except Exception:
        return 0


def list_sessions() -> list[dict]:
    sessions: list[dict] = []
    if not SESSIONS_DIR.exists():
        return sessions

    for cwd_dir in sorted(SESSIONS_DIR.iterdir()):
        if not cwd_dir.is_dir() or cwd_dir.name.startswith("."):
            continue
        if cwd_dir.name == "session_search.sqlite":
            continue
        cwd = decode_cwd_key(cwd_dir.name)
        for sess_dir in sorted(cwd_dir.iterdir(), reverse=True):
            if not sess_dir.is_dir() or not UUID_RE.match(sess_dir.name):
                continue
            summary = load_json(sess_dir / "summary.json") or {}
            info = summary.get("info") or {}
            signals = load_json(sess_dir / "signals.json") or {}
            sessions.append(
                {
                    "id": sess_dir.name,
                    "cwd": info.get("cwd") or cwd,
                    "cwd_key": cwd_dir.name,
                    "title": summary.get("generated_title")
                    or summary.get("session_summary")
                    or "(untitled)",
                    "summary": summary.get("session_summary"),
                    "created_at": summary.get("created_at"),
                    "updated_at": summary.get("updated_at")
                    or summary.get("last_active_at"),
                    "model": summary.get("current_model_id"),
                    "agent_name": summary.get("agent_name"),
                    "num_messages": summary.get("num_messages"),
                    "num_chat_messages": summary.get("num_chat_messages"),
                    "events_count": line_count(sess_dir / "events.jsonl"),
                    "updates_count": line_count(sess_dir / "updates.jsonl"),
                    "signals": signals if isinstance(signals, dict) else {},
                    "path": str(sess_dir),
                }
            )

    sessions.sort(
        key=lambda s: s.get("updated_at") or s.get("created_at") or "",
        reverse=True,
    )
    return sessions


def resolve_session(session_id: str, cwd_key: str | None = None) -> Path | None:
    if not UUID_RE.match(session_id):
        return None
    if cwd_key:
        candidate = SESSIONS_DIR / cwd_key / session_id
        if candidate.is_dir():
            return candidate
    if not SESSIONS_DIR.exists():
        return None
    for cwd_dir in SESSIONS_DIR.iterdir():
        if not cwd_dir.is_dir():
            continue
        candidate = cwd_dir / session_id
        if candidate.is_dir():
            return candidate
    return None


def session_fingerprint(sess_dir: Path | None) -> str:
    """Cheap change detector: mtimes + sizes of key session files."""
    if not sess_dir or not sess_dir.is_dir():
        return ""
    parts: list[str] = []
    for name in (
        "events.jsonl",
        "updates.jsonl",
        "summary.json",
        "signals.json",
        "chat_history.jsonl",
    ):
        p = sess_dir / name
        try:
            st = p.stat()
            parts.append(f"{name}:{st.st_mtime_ns}:{st.st_size}")
        except OSError:
            parts.append(f"{name}:0:0")
    return "|".join(parts)


def sessions_index_fingerprint(sessions: list[dict] | None = None) -> str:
    """Detect new/updated sessions without fully re-rendering every tick."""
    if sessions is None:
        sessions = list_sessions()
    # First 12 newest are enough for live-follow in tmux
    parts = []
    for s in sessions[:12]:
        parts.append(
            f"{s.get('id')}:{s.get('updated_at') or ''}:{s.get('events_count')}:{s.get('updates_count')}"
        )
    return "|".join(parts)


def prefer_session_for_cwd(sessions: list[dict], cwd: str | None = None) -> dict | None:
    """Pick the most recently updated session for a working directory."""
    if not sessions:
        return None
    target = os.path.realpath(cwd or os.getcwd())
    matches: list[dict] = []
    for s in sessions:
        scwd = s.get("cwd") or ""
        try:
            if os.path.realpath(scwd) == target:
                matches.append(s)
        except OSError:
            if scwd == cwd:
                matches.append(s)
    if matches:
        return matches[0]  # sessions are sorted newest-first
    return sessions[0]


def categorize_event(etype: str) -> str:
    if etype in ("turn_started", "turn_ended", "loop_started"):
        return "turn"
    if etype in ("tool_started", "tool_completed"):
        return "tool"
    if etype.startswith("permission"):
        return "permission"
    if etype == "phase_changed":
        return "phase"
    if etype == "first_token":
        return "stream"
    return "other"


def categorize_update(su: str) -> str:
    if su == "user_message_chunk":
        return "user"
    if su == "agent_message_chunk":
        return "agent"
    if su in ("tool_call", "tool_call_update"):
        return "tool"
    if su == "turn_completed":
        return "turn"
    if su in ("plan", "session_recap"):
        return "meta"
    return "other"


def format_event_title(ev: dict) -> str:
    etype = ev.get("type", "event")
    if etype == "tool_started":
        return f"▶ tool start: {ev.get('tool_name') or ev.get('name') or '?'}"
    if etype == "tool_completed":
        status = ev.get("status") or ev.get("result_status") or "done"
        return f"■ tool done ({status}): {ev.get('tool_name') or ev.get('name') or '?'}"
    if etype == "turn_started":
        return f"━━ turn {ev.get('turn_number', '?')} started · {ev.get('model_id', '')}"
    if etype == "turn_ended":
        return f"━━ turn {ev.get('turn_number', '?')} ended"
    if etype == "phase_changed":
        return f"phase → {ev.get('phase') or ev.get('to') or ev.get('new_phase') or '?'}"
    if etype == "permission_requested":
        return f"permission requested: {ev.get('tool_name') or ev.get('permission_type') or '?'}"
    if etype == "permission_resolved":
        return f"permission {ev.get('resolution') or ev.get('decision') or 'resolved'}"
    if etype == "first_token":
        return "first token"
    if etype == "loop_started":
        return f"loop {ev.get('loop_index', 0)} started"
    return etype


def summarize_event(ev: dict) -> str:
    parts = []
    for k in ("tool_name", "name", "phase", "to", "status", "error", "turn_number", "model_id"):
        if ev.get(k) is not None:
            if k in ("tool_name", "name") and ev.get("type") in ("tool_started", "tool_completed"):
                continue
            parts.append(f"{k}={ev[k]}")
    for k in ("input", "args", "tool_input"):
        if isinstance(ev.get(k), (dict, list, str)):
            preview = json.dumps(ev[k], ensure_ascii=False)
            if len(preview) > 200:
                preview = preview[:200] + "…"
            parts.append(preview)
            break
    return " · ".join(parts)


def format_update_title(update: dict, su: str) -> str:
    if su == "user_message_chunk":
        text = ((update.get("content") or {}).get("text") or "")[:100]
        return f"👤 user: {text}" if text else "👤 user message"
    if su == "agent_message_chunk":
        text = ((update.get("content") or {}).get("text") or "")[:100]
        return f"🤖 agent: {text}" if text else "🤖 agent message"
    if su == "tool_call":
        title = update.get("title") or update.get("toolName") or update.get("name") or "tool"
        return f"🔧 tool_call: {title}"
    if su == "tool_call_update":
        status = update.get("status") or ""
        title = update.get("title") or update.get("toolCallId") or "tool"
        return f"🔧 tool_update [{status}]: {title}" if status else f"🔧 tool_update: {title}"
    if su == "turn_completed":
        return "✓ turn completed"
    if su == "plan":
        return "📋 plan update"
    if su == "session_recap":
        return "📝 session recap"
    return su


def summarize_update(update: dict, su: str) -> str:
    if su in ("user_message_chunk", "agent_message_chunk"):
        return ((update.get("content") or {}).get("text") or "")[:400]
    if su in ("tool_call", "tool_call_update"):
        # Prefer human-readable tool summary (see format_tool_block)
        block = format_tool_block_from_update(update, phase="start" if su == "tool_call" else "result")
        if block.get("summary"):
            return block["summary"][:400]
        return ""
    return ""


# ── Tool trace formatting (readable traces) ─────────────────────────

# Display limits (env-overridable for power users)
# Preview = legacy glance mode (rarely used). Full = UI expand + turn export (default).
TOOL_PREVIEW_LINES = int(os.environ.get("GROK_ALT_TOOL_PREVIEW_LINES", "24"))
TOOL_PREVIEW_CHARS = int(os.environ.get("GROK_ALT_TOOL_PREVIEW_CHARS", "3500"))
# Full fidelity for collapsible tool bodies and exports (high ceiling; not chat "snippet" mode).
TOOL_FULL_LINES = int(os.environ.get("GROK_ALT_TOOL_FULL_LINES", "500000"))
TOOL_FULL_CHARS = int(os.environ.get("GROK_ALT_TOOL_FULL_CHARS", "2000000"))
# Back-compat aliases (export path and older callers)
TOOL_EXPORT_LINES = int(os.environ.get("GROK_ALT_TOOL_EXPORT_LINES", str(TOOL_FULL_LINES)))
TOOL_EXPORT_CHARS = int(os.environ.get("GROK_ALT_TOOL_EXPORT_CHARS", str(TOOL_FULL_CHARS)))
DIFF_CONTEXT_LINES = int(os.environ.get("GROK_ALT_DIFF_CONTEXT_LINES", "4"))
# How many updates.jsonl lines to scan (0 = no limit)
CHAT_VIEW_MAX_LINES = int(os.environ.get("GROK_ALT_CHAT_VIEW_MAX_LINES", "0"))
# Brief pause after turn_completed before treating outputs as final (seconds; used by TUI/export)
TURN_SETTLE_SECONDS = float(os.environ.get("GROK_ALT_TURN_SETTLE_SECONDS", "1.0"))

# Map Grok tool titles → (kind, variant) when ACP omits kind on streaming updates
_TITLE_KIND_HINTS: dict[str, tuple[str, str]] = {
    "run_terminal_command": ("execute", "Bash"),
    "bash": ("execute", "Bash"),
    "shell": ("execute", "Bash"),
    "read_file": ("read", "ReadFile"),
    "readfile": ("read", "ReadFile"),
    "grep": ("search", "Grep"),
    "grepsearch": ("search", "GrepSearch"),
    "search_replace": ("edit", "SearchReplace"),
    "searchreplace": ("edit", "SearchReplace"),
    "str_replace": ("edit", "SearchReplace"),
    "list_dir": ("other", "ListDir"),
    "listdir": ("other", "ListDir"),
    "todo_write": ("think", "TodoWrite"),
    "todowrite": ("think", "TodoWrite"),
    "web_search": ("search", "WebSearch"),
    "web_fetch": ("read", "WebFetch"),
    "write": ("edit", "Write"),
    "delete": ("delete", "Delete"),
}


def _short_path(path: str | None, max_len: int = 64) -> str:
    if not path:
        return "?"
    p = str(path)
    home = str(Path.home())
    if p.startswith(home):
        p = "~" + p[len(home) :]
    if len(p) <= max_len:
        return p
    return "…" + p[-(max_len - 1) :]


def _bytes_or_str(val) -> str:
    """Decode Grok tool payloads that sometimes store stdout as int byte arrays."""
    if val is None:
        return ""
    if isinstance(val, str):
        return val
    if isinstance(val, (bytes, bytearray)):
        return val.decode("utf-8", errors="replace")
    # Empty list is not useful output (common on in_progress Bash payloads)
    if isinstance(val, list) and not val:
        return ""
    if isinstance(val, list) and val and all(isinstance(x, int) for x in val):
        try:
            return bytes(val).decode("utf-8", errors="replace")
        except Exception:
            pass
    if isinstance(val, list):
        # list of strings / chunks
        if all(isinstance(x, str) for x in val):
            return "\n".join(val)
        parts = [_bytes_or_str(x) for x in val]
        return "\n".join(p for p in parts if p)
    if isinstance(val, dict):
        for k in ("text", "content", "output", "stdout", "message", "output_for_prompt"):
            if k in val and val[k] not in (None, "", [], {}):
                return _bytes_or_str(val[k])
        return json.dumps(val, ensure_ascii=False, indent=2)
    return str(val)


def _infer_kind_variant(title: str | None, tool_name: str | None, ri: dict, ro: dict) -> tuple[str | None, str | None]:
    """Best-effort kind/variant when streaming updates omit them."""
    for key in (title, tool_name):
        if not key:
            continue
        hint = _TITLE_KIND_HINTS.get(str(key).strip().lower().replace("-", "_"))
        if hint:
            return hint
        # snake_case title already
        hint = _TITLE_KIND_HINTS.get(str(key).strip().lower())
        if hint:
            return hint
    ro_type = ro.get("type") if isinstance(ro, dict) else None
    if isinstance(ro_type, str) and ro_type:
        mapped = {
            "Bash": ("execute", "Bash"),
            "ReadFile": ("read", "ReadFile"),
            "GrepSearch": ("search", "GrepSearch"),
            "SearchReplace": ("edit", "SearchReplace"),
            "ListDir": ("other", "ListDir"),
            "Todo": ("think", "TodoWrite"),
        }.get(ro_type)
        if mapped:
            return mapped
    if ri.get("command") is not None:
        return "execute", "Bash"
    if ri.get("target_file") or ri.get("path") and ri.get("offset") is not None:
        return "read", "ReadFile"
    if ri.get("pattern") is not None:
        return "search", "Grep"
    if ri.get("old_string") is not None or (ri.get("file_path") and ri.get("new_string") is not None):
        return "edit", "SearchReplace"
    if ri.get("target_directory"):
        return "other", "ListDir"
    if ri.get("todos") is not None:
        return "think", "TodoWrite"
    return None, None


def _enrich_raw_input(ri: dict, ro: dict, update: dict) -> dict:
    """Fill missing input fields from rawOutput / update (in_progress streams often only have RO)."""
    out = dict(ri) if isinstance(ri, dict) else {}
    if not isinstance(ro, dict):
        ro = {}
    # Shell: command lives on RO while running
    if not out.get("command") and ro.get("command"):
        out["command"] = ro.get("command")
    if not out.get("description") and ro.get("description"):
        out["description"] = ro.get("description")
    if not out.get("description") and update.get("description"):
        out["description"] = update.get("description")
    # Paths sometimes only on locations
    locs = update.get("locations") or []
    if locs and isinstance(locs, list) and isinstance(locs[0], dict):
        path = locs[0].get("path")
        if path:
            if not out.get("target_file") and not out.get("file_path") and not out.get("path"):
                # prefer target_file for read-like
                if out.get("old_string") is not None or out.get("new_string") is not None:
                    out.setdefault("file_path", path)
                else:
                    out.setdefault("target_file", path)
            out.setdefault("target_directory", path if "target_directory" in (ri or {}) else out.get("target_directory"))
    # cwd for shell context
    if ro.get("current_dir") and not out.get("cwd"):
        out["cwd"] = ro.get("current_dir")
    return out


def _read_text_file_capped(path: Path, *, max_chars: int) -> str | None:
    """Read a text-ish file; return None if missing/unreadable. Cap at max_chars."""
    try:
        if not path.is_file():
            return None
        # Avoid slurping huge binaries into traces
        size = path.stat().st_size
        if size <= 0:
            return ""
        # Heuristic: skip obvious binaries by extension
        if path.suffix.lower() in {
            ".png",
            ".jpg",
            ".jpeg",
            ".gif",
            ".webp",
            ".mp4",
            ".mov",
            ".pdf",
            ".zip",
            ".tar",
            ".gz",
            ".tgz",
            ".dmg",
            ".exe",
            ".bin",
            ".woff",
            ".woff2",
        }:
            return None
        data = path.read_bytes()
        # If mostly non-text, don't embed
        sample = data[:4096]
        if sample and sum(1 for b in sample if b < 9 or (13 < b < 32 and b not in (9, 10, 13))) > len(sample) * 0.15:
            return None
        text = data.decode("utf-8", errors="replace")
        if max_chars > 0 and len(text) > max_chars:
            return text[:max_chars] + f"\n… truncated at {max_chars} chars (file {path})"
        return text
    except OSError:
        return None


def _resolve_output_file_path(
    of: str,
    *,
    sess_dir: Path | None = None,
    tool_call_id: str | None = None,
) -> Path | None:
    """Map Grok output_file / terminal log references to a real path."""
    candidates: list[Path] = []
    raw = (of or "").strip()
    if raw:
        p = Path(raw).expanduser()
        candidates.append(p)
        if not p.is_absolute() and sess_dir is not None:
            candidates.append(sess_dir / p)
            candidates.append(sess_dir / "terminal" / p.name)
    if tool_call_id and sess_dir is not None:
        candidates.append(sess_dir / "terminal" / f"{tool_call_id}.log")
    for c in candidates:
        try:
            if c.is_file():
                return c
        except OSError:
            continue
    return None


def _bash_output_text(
    ro: dict,
    update: dict,
    *,
    sess_dir: Path | None = None,
    tool_call_id: str | None = None,
    read_output_files: bool = True,
    max_file_chars: int = TOOL_PREVIEW_CHARS,
) -> str:
    """Prefer the richest stdout field available during streaming.

    When Grok streams large shell output to session terminal/*.log (output_file),
    optionally read that file so traces/exports aren't just a path stub.
    """
    if not isinstance(ro, dict):
        ro = {}
    for key in ("output_for_prompt", "output", "stdout"):
        text = _bytes_or_str(ro.get(key))
        if text.strip():
            return text
    # Incremental byte deltas while still running
    delta = _bytes_or_str(ro.get("output_delta"))
    if delta.strip():
        return delta
    # Content blocks (often empty text while streaming — still try)
    text = _content_blocks_text(update.get("content"))
    if text.strip():
        return text
    # Terminal log file — read when present so exports include full command output
    of = ro.get("output_file")
    tid = tool_call_id or update.get("toolCallId")
    path = _resolve_output_file_path(
        of if isinstance(of, str) else "",
        sess_dir=sess_dir,
        tool_call_id=tid if isinstance(tid, str) else None,
    )
    if path is not None and read_output_files:
        file_text = _read_text_file_capped(path, max_chars=max_file_chars)
        if file_text is not None and file_text.strip():
            return file_text
    if of and isinstance(of, str) and of.strip():
        return f"(output streaming to file: {of})"
    if path is not None:
        return f"(output file: {path})"
    return ""


def _generic_input_dump(ri: dict, *, max_chars: int = 8000) -> str | None:
    if not ri:
        return None
    try:
        blob = json.dumps(ri, ensure_ascii=False, indent=2)
    except Exception:
        blob = str(ri)
    if len(blob) > max_chars:
        return blob[:max_chars] + "\n…"
    return blob


def _truncate_text(text: str, max_lines: int = TOOL_PREVIEW_LINES, max_chars: int = TOOL_PREVIEW_CHARS) -> tuple[str, str]:
    """Return (body, note). note is empty if not truncated."""
    if not text:
        return "", ""
    lines = text.splitlines()
    note_parts = []
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        note_parts.append(f"{max_lines} lines shown")
    body = "\n".join(lines)
    if len(body) > max_chars:
        body = body[:max_chars].rstrip() + "\n…"
        note_parts.append(f"{max_chars} chars")
    if note_parts and (len(text.splitlines()) > max_lines or len(text) > max_chars):
        total_lines = len(text.splitlines())
        note = f"… truncated ({total_lines} lines total; showing {', '.join(note_parts)})"
        return body, note
    return body, ""


def _strip_line_numbers(text: str) -> str:
    """Remove Grok read_file line prefixes like '12→' for cleaner display."""
    if not text or "→" not in text[:80]:
        # still try line-by-line
        pass
    out = []
    for line in text.splitlines():
        if "→" in line[:12]:
            # e.g. "  12→code" or "12→code"
            idx = line.find("→")
            if idx != -1 and line[:idx].strip().isdigit():
                out.append(line[idx + 1 :])
                continue
        out.append(line)
    return "\n".join(out)


def _unified_diff(old: str, new: str, path: str = "", context: int = DIFF_CONTEXT_LINES) -> str:
    """Build a compact unified diff for SearchReplace edits."""
    import difflib

    old_lines = (old or "").splitlines()
    new_lines = (new or "").splitlines()
    if old_lines == new_lines:
        return "(no textual change)"
    header = _short_path(path) if path else "file"
    diff = difflib.unified_diff(
        old_lines,
        new_lines,
        fromfile=f"a/{header}",
        tofile=f"b/{header}",
        lineterm="",
        n=context,
    )
    lines = list(diff)
    if not lines:
        # Fallback: show added/removed line counts only
        return f"~{len(old_lines)} lines → {len(new_lines)} lines (diff unavailable)"
    body = "\n".join(lines)
    # Diffs used in full-detail tool blocks — keep high ceiling (preview callers rarely hit this alone)
    body, note = _truncate_text(body, max_lines=TOOL_FULL_LINES, max_chars=TOOL_FULL_CHARS)
    if note:
        body += f"\n{note}"
    return body


def _content_blocks_text(content) -> str:
    """Extract plain text from ACP content block lists."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, dict):
        if content.get("type") == "diff":
            return _unified_diff(content.get("oldText") or "", content.get("newText") or "", content.get("path") or "")
        inner = content.get("content")
        if isinstance(inner, dict) and inner.get("text") is not None:
            return _bytes_or_str(inner.get("text"))
        if content.get("text") is not None:
            return _bytes_or_str(content.get("text"))
        return json.dumps(content, ensure_ascii=False)
    if isinstance(content, list):
        parts = []
        for block in content:
            if not isinstance(block, dict):
                parts.append(str(block))
                continue
            btype = block.get("type")
            if btype == "diff":
                parts.append(
                    _unified_diff(block.get("oldText") or "", block.get("newText") or "", block.get("path") or "")
                )
            elif btype == "content":
                inner = block.get("content") or {}
                if isinstance(inner, dict):
                    parts.append(_bytes_or_str(inner.get("text")))
                else:
                    parts.append(_bytes_or_str(inner))
            else:
                t = block.get("text")
                if t:
                    parts.append(_bytes_or_str(t))
        return "\n".join(p for p in parts if p)
    return _bytes_or_str(content)


def _tool_label(kind: str | None, variant: str | None, title: str | None) -> str:
    k = (kind or "").lower()
    v = (variant or "").lower()
    icons = {
        "read": "📖",
        "search": "🔎",
        "edit": "✏️",
        "execute": "💻",
        "think": "🧠",
        "other": "📎",
        "delete": "🗑",
        "move": "📦",
    }
    names = {
        "readfile": "read_file",
        "grepsearch": "grep",
        "searchreplace": "search_replace",
        "bash": "shell",
        "listdir": "list_dir",
        "todowrite": "todo",
        "webfetch": "web_fetch",
        "websearch": "web_search",
    }
    icon = icons.get(k, "🔧")
    if v in names:
        return f"{icon} {names[v]}"
    if k in icons:
        pretty = {
            "read": "read_file",
            "search": "grep/search",
            "edit": "edit",
            "execute": "shell",
            "think": "plan/todo",
            "other": "tool",
        }.get(k, k)
        return f"{icon} {pretty}"
    if title:
        # Prefer friendly names for Grok tool titles (run_terminal_command → shell)
        hint = _TITLE_KIND_HINTS.get(str(title).strip().lower().replace("-", "_"))
        if hint:
            ik, iv = hint
            return _tool_label(ik, iv, None)
        return f"🔧 {title[:48]}"
    return "🔧 tool"


def format_tool_block_from_update(
    update: dict,
    *,
    phase: str = "result",
    sess_dir: Path | None = None,
    max_output_file_chars: int | None = None,
    full_detail: bool = True,
) -> dict:
    """Turn a single tool_call / tool_call_update into a structured display block.

    Works for start, streaming in_progress, and completed — including Grok payloads
    where kind/title are missing on updates and stdout lives in output_for_prompt.

    full_detail=True (default): high line/char budgets for UI expand + export accuracy.
    full_detail=False: legacy short previews only.
    """
    ri_raw = update.get("rawInput") or update.get("input") or {}
    if not isinstance(ri_raw, dict):
        ri_raw = {}
    ro = update.get("rawOutput")
    if not isinstance(ro, dict):
        ro = {} if ro is None else {"_raw": ro}

    title = update.get("title") or update.get("toolName") or ""
    status = update.get("status") or ""
    locations = update.get("locations") or []
    if full_detail:
        body_lines = TOOL_FULL_LINES
        body_chars = TOOL_FULL_CHARS if max_output_file_chars is None else max_output_file_chars
        file_cap = body_chars
    else:
        body_lines = TOOL_PREVIEW_LINES
        body_chars = TOOL_PREVIEW_CHARS
        file_cap = TOOL_PREVIEW_CHARS if max_output_file_chars is None else max_output_file_chars

    def _cap(text: str, *, lines: int | None = None, chars: int | None = None) -> tuple[str, str]:
        return _truncate_text(
            text,
            max_lines=body_lines if lines is None else lines,
            max_chars=body_chars if chars is None else chars,
        )

    # Infer missing ACP metadata from title / RO type / input keys
    kind = update.get("kind")  # read | search | edit | execute | think | other
    variant = ri_raw.get("variant") or (ro.get("type") if isinstance(ro, dict) else "") or ""
    if not kind or not variant:
        ik, iv = _infer_kind_variant(title, update.get("toolName"), ri_raw, ro if isinstance(ro, dict) else {})
        kind = kind or ik
        variant = variant or iv or ""

    ri = _enrich_raw_input(ri_raw, ro if isinstance(ro, dict) else {}, update)

    # Always try to render input when we have any signal (not only on start/merged)
    show_input = phase in ("start", "merged", "result") and (
        ri
        or title
        or (isinstance(ro, dict) and (ro.get("command") or ro.get("type")))
    )

    label = _tool_label(kind, variant if isinstance(variant, str) else "", title)
    sections: list[dict] = []  # {heading, body, style}
    summary_bits: list[str] = []

    # ── Input / request side ──
    if show_input:
        if variant in ("ReadFile",) or kind == "read" or ri.get("target_file"):
            path = ri.get("target_file") or ri.get("path")
            if locations and not path:
                path = (locations[0] or {}).get("path")
            off = ri.get("offset")
            lim = ri.get("limit")
            rng = ""
            if off is not None or lim is not None:
                rng = f"  lines {off or 1}–{(off or 1) + (lim or 0) - 1 if lim else '…'}"
            summary_bits.append(f"read {_short_path(path)}{rng}")
            sections.append(
                {
                    "heading": "file",
                    "body": f"file: {_short_path(path, 120)}{rng}",
                    "style": "meta",
                    "meta": {"path": path, "start_line": off or 1},
                }
            )
        elif variant in ("Grep", "GrepSearch") or kind == "search" or ri.get("pattern"):
            pat = ri.get("pattern") or title
            where = ri.get("path") or ri.get("glob") or "(workspace)"
            extra = []
            if ri.get("glob"):
                extra.append(f"glob={ri['glob']}")
            if ri.get("head_limit"):
                extra.append(f"limit={ri['head_limit']}")
            if ri.get("type"):
                extra.append(f"type={ri['type']}")
            if ri.get("-i") or ri.get("case_insensitive"):
                extra.append("ignore_case")
            extra_s = f"  ({', '.join(extra)})" if extra else ""
            summary_bits.append(f"grep /{pat}/ in {_short_path(str(where))}{extra_s}")
            sections.append(
                {
                    "heading": "pattern",
                    "body": f"pattern: {pat}",
                    "style": "meta",
                    "meta": {"pattern": pat},
                }
            )
            sections.append(
                {
                    "heading": "scope",
                    "body": f"scope: {where}{extra_s}",
                    "style": "meta",
                    "meta": {"path": where if isinstance(where, str) and "/" in str(where) else None},
                }
            )
        elif variant in ("SearchReplace", "Write") or kind == "edit" or (
            ri.get("file_path") and (ri.get("old_string") is not None or ri.get("new_string") is not None)
        ):
            path = ri.get("file_path") or (locations[0] or {}).get("path") if locations else None
            summary_bits.append(f"edit {_short_path(path)}")
            sections.append(
                {
                    "heading": "file",
                    "body": f"file: {_short_path(path, 120)}",
                    "style": "meta",
                    "meta": {"path": path},
                }
            )
            if ri.get("replace_all"):
                sections.append({"heading": "mode", "body": "replace_all", "style": "dim"})
            # Show intended edit even while in_progress (before RO has a diff)
            if ri.get("old_string") is not None or ri.get("new_string") is not None:
                diff_text = _unified_diff(
                    ri.get("old_string") or "",
                    ri.get("new_string") or "",
                    path or "",
                )
                if diff_text:
                    sections.append(
                        {
                            "heading": "diff (requested)",
                            "body": diff_text,
                            "style": "diff",
                            "meta": {"path": path},
                        }
                    )
        elif variant in ("Bash",) or kind == "execute" or ri.get("command"):
            cmd = ri.get("command") or (ro.get("command") if isinstance(ro, dict) else "") or ""
            desc = ri.get("description") or (ro.get("description") if isinstance(ro, dict) else "") or ""
            cwd = ri.get("cwd") or (ro.get("current_dir") if isinstance(ro, dict) else "") or ""
            one = " ".join(str(cmd).split())
            if len(one) > 120:
                one = one[:117] + "…"
            summary_bits.append(f"$ {one}" if one else (desc or title or "shell"))
            if desc:
                sections.append({"heading": "why", "body": str(desc), "style": "dim"})
            if cwd:
                sections.append({"heading": "cwd", "body": _short_path(str(cwd), 120), "style": "meta"})
            if cmd:
                # Show full command in export-friendly size (truncate only extreme)
                cmd_body, note = _truncate_text(str(cmd), max_lines=40, max_chars=8000)
                sections.append(
                    {"heading": "command", "body": cmd_body + (f"\n{note}" if note else ""), "style": "cmd"}
                )
            # Extra shell args (timeout, background, …)
            extras = {
                k: ri[k]
                for k in ("timeout", "background", "block_until_ms", "working_directory")
                if ri.get(k) is not None
            }
            if extras:
                sections.append(
                    {
                        "heading": "options",
                        "body": json.dumps(extras, ensure_ascii=False),
                        "style": "meta",
                    }
                )
        elif variant in ("ListDir",) or ri.get("target_directory"):
            d = ri.get("target_directory") or (locations[0] or {}).get("path") if locations else "?"
            summary_bits.append(f"list {_short_path(d)}")
            sections.append({"heading": "dir", "body": _short_path(d, 120), "style": "meta"})
        elif variant in ("TodoWrite",) or kind == "think":
            todos = ri.get("todos") or []
            summary_bits.append(f"todos ({len(todos)} items)")
            lines = []
            for t in todos[:20]:
                if not isinstance(t, dict):
                    continue
                st = t.get("status") or "?"
                mark = {"completed": "✓", "in_progress": "…", "pending": "·", "cancelled": "✗"}.get(st, "·")
                lines.append(f"  {mark} [{st}] {t.get('content') or t.get('id')}")
            if len(todos) > 20:
                lines.append(f"  … +{len(todos) - 20} more")
            sections.append({"heading": "todos", "body": "\n".join(lines) or "(empty)", "style": "meta"})
        elif ri:
            # Unknown tool shape — dump full args so progress is never a blank label
            dump = _generic_input_dump(ri)
            if dump:
                summary_bits.append(title[:120] if title else "tool input")
                sections.append({"heading": "input", "body": dump, "style": "code"})
        elif title:
            summary_bits.append(title[:120])

    # ── Result / output side (including partial in_progress output) ──
    if phase in ("result", "merged", "start"):
        ro_type = ro.get("type") if isinstance(ro, dict) else None
        # Treat missing RO type using inferred kind
        if not ro_type and kind == "execute":
            ro_type = "Bash"
        if not ro_type and kind == "read":
            ro_type = "ReadFile"
        if not ro_type and kind == "search":
            ro_type = "GrepSearch"
        if not ro_type and kind == "edit":
            ro_type = "SearchReplace"

        if ro_type == "ReadFile" or (kind == "read" and status in ("completed", "in_progress", "")):
            fc = (ro.get("FileContent") or {}) if isinstance(ro, dict) else {}
            raw = fc.get("content") or fc.get("content_concise") or ""
            if not raw:
                raw = _content_blocks_text(update.get("content"))
            cleaned = _strip_line_numbers(_bytes_or_str(raw))
            body, note = _cap(cleaned)
            if body:
                rpath = ri.get("target_file") or (locations[0] or {}).get("path") if locations else None
                sections.append(
                    {
                        "heading": "contents",
                        "body": body + (f"\n{note}" if note else ""),
                        "style": "code",
                        "meta": {
                            "path": rpath,
                            "start_line": ri.get("offset") or 1,
                            "line_numbers": True,
                        },
                    }
                )
            if not summary_bits:
                path = ri.get("target_file") or (locations[0] or {}).get("path") if locations else "?"
                summary_bits.append(f"read {_short_path(path)} ({len(cleaned.splitlines())} lines)")

        elif ro_type == "GrepSearch" or kind == "search":
            stdout = _bytes_or_str(ro.get("stdout")) if isinstance(ro, dict) else ""
            if not stdout:
                stdout = _bytes_or_str(ro.get("output_for_prompt")) if isinstance(ro, dict) else ""
            if not stdout:
                stdout = _content_blocks_text(update.get("content"))
            matches = ro.get("match_count") if isinstance(ro, dict) else None
            files = ro.get("file_matches") if isinstance(ro, dict) else None
            meta = []
            if matches is not None:
                meta.append(f"{matches} match(es)")
            if isinstance(files, list) and files:
                meta.append(f"{len(files)} file(s)")
            if meta:
                sections.append({"heading": "stats", "body": " · ".join(meta), "style": "meta"})
            body, note = _cap(stdout)
            if body.strip():
                sections.append(
                    {
                        "heading": "matches",
                        "body": body + (f"\n{note}" if note else ""),
                        "style": "grep",
                        "meta": {"pattern": ri.get("pattern") or title},
                    }
                )
            elif status == "completed":
                sections.append({"heading": "matches", "body": "(no output / no matches)", "style": "dim"})
            if not summary_bits:
                pat = ri.get("pattern") or title or "?"
                summary_bits.append(f"grep /{pat}/ → {matches if matches is not None else '?'} hits")

        elif ro_type == "SearchReplace" or kind == "edit":
            # Prefer diff block from content
            diff_text = ""
            for block in update.get("content") or []:
                if isinstance(block, dict) and block.get("type") == "diff":
                    diff_text = _unified_diff(
                        block.get("oldText") or "",
                        block.get("newText") or "",
                        block.get("path") or ri.get("file_path") or "",
                    )
                    break
            if not diff_text and isinstance(ro, dict):
                edits = ro.get("EditsApplied") or ro.get("edits") or {}
                if isinstance(edits, dict) and (edits.get("old_string") is not None or edits.get("oldText") is not None):
                    diff_text = _unified_diff(
                        edits.get("old_string") or edits.get("oldText") or "",
                        edits.get("new_string") or edits.get("newText") or "",
                        ri.get("file_path") or "",
                    )
            # Avoid duplicating the "diff (requested)" section if identical
            has_req_diff = any(s.get("heading") == "diff (requested)" for s in sections)
            if diff_text and not has_req_diff:
                sections.append(
                    {
                        "heading": "diff",
                        "body": diff_text,
                        "style": "diff",
                        "meta": {"path": ri.get("file_path")},
                    }
                )
            elif diff_text and has_req_diff and status == "completed":
                # Rename requested → applied result is same; keep one
                pass
            if not summary_bits:
                summary_bits.append(f"edit {_short_path(ri.get('file_path'))}")

        elif ro_type == "Bash" or kind == "execute":
            out = _bash_output_text(
                ro if isinstance(ro, dict) else {},
                update,
                sess_dir=sess_dir,
                tool_call_id=update.get("toolCallId"),
                max_file_chars=file_cap,
            )
            err = _bytes_or_str(ro.get("stderr")) if isinstance(ro, dict) else ""
            code = ro.get("exit_code") if isinstance(ro, dict) else None
            timed_out = ro.get("timed_out") if isinstance(ro, dict) else None
            truncated = ro.get("truncated") if isinstance(ro, dict) else None
            total_bytes = ro.get("total_bytes") if isinstance(ro, dict) else None
            of_path = _resolve_output_file_path(
                (ro.get("output_file") if isinstance(ro, dict) else None) or "",
                sess_dir=sess_dir,
                tool_call_id=update.get("toolCallId"),
            )
            # Prefer full terminal log over short "Background task started" stubs
            if of_path is not None and (not out or len(out) < 200 or out.startswith("Background task")):
                file_text = _read_text_file_capped(of_path, max_chars=file_cap)
                if file_text is not None and file_text.strip() and len(file_text) > len(out or ""):
                    out = file_text
            if status == "in_progress" and not (out and len(out) > 200):
                sections.append({"heading": "progress", "body": "running… (partial output below)", "style": "dim"})
            if code is not None and status == "completed":
                sections.append({"heading": "exit", "body": str(code), "style": "meta" if code == 0 else "err"})
            elif code is not None and status == "in_progress":
                # Grok sometimes pre-fills exit_code=0 while still streaming — show as tentative
                sections.append({"heading": "exit (tentative)", "body": str(code), "style": "dim"})
            meta_bits = []
            if timed_out:
                meta_bits.append("timed_out")
            if truncated:
                meta_bits.append("truncated")
            if total_bytes is not None:
                meta_bits.append(f"{total_bytes} bytes")
            if of_path is not None:
                meta_bits.append(f"log={of_path}")
                sections.append(
                    {
                        "heading": "output_file",
                        "body": str(of_path),
                        "style": "meta",
                        "meta": {"path": str(of_path), "artifact": True},
                    }
                )
            if meta_bits:
                sections.append({"heading": "stream", "body": " · ".join(meta_bits), "style": "meta"})
            if out:
                body, note = _cap(out)
                sections.append(
                    {
                        "heading": "stdout" if status == "completed" else "stdout (live)",
                        "body": body + (f"\n{note}" if note else ""),
                        "style": "shell",
                    }
                )
            elif status == "in_progress":
                sections.append(
                    {
                        "heading": "stdout (live)",
                        "body": "(no output yet — command still running)",
                        "style": "dim",
                    }
                )
            if err and err.strip():
                body, note = _cap(err)
                sections.append({"heading": "stderr", "body": body + (f"\n{note}" if note else ""), "style": "err"})

        elif ro_type == "ListDir":
            lc = (ro.get("Content") or {}) if isinstance(ro, dict) else {}
            listing = lc.get("content") or _content_blocks_text(update.get("content"))
            if not listing and isinstance(ro, dict):
                listing = ro.get("output_for_prompt") or ""
            body, note = _cap(_bytes_or_str(listing))
            if body:
                sections.append({"heading": "listing", "body": body + (f"\n{note}" if note else ""), "style": "code"})

        elif ro_type == "Todo" or variant in ("TodoWrite",):
            pass  # todos already rendered from input; skip noisy JSON echo
        else:
            # Generic payload — always surface something useful while running
            extra = _content_blocks_text(update.get("content"))
            if not extra and isinstance(ro, dict):
                extra = _bytes_or_str(ro.get("output_for_prompt")) or _bytes_or_str(ro.get("output"))
            if not extra and ro:
                extra = json.dumps(ro, ensure_ascii=False, indent=2) if isinstance(ro, dict) else _bytes_or_str(ro)
            if extra and extra.strip() and extra.strip() not in ("{'type': 'text', 'text': ''}", "[]", "{}"):
                body, note = _cap(extra)
                if body.strip():
                    sections.append(
                        {
                            "heading": "output" if status == "completed" else "output (live)",
                            "body": body + (f"\n{note}" if note else ""),
                            "style": "code",
                        }
                    )

    # Last resort: never leave an in_progress tool as only a label
    if not sections and (status == "in_progress" or phase == "merged"):
        dump = _generic_input_dump(ri) or _generic_input_dump(
            {k: update.get(k) for k in ("title", "toolName", "toolCallId", "status", "kind") if update.get(k)}
        )
        if dump:
            sections.append({"heading": "raw", "body": dump, "style": "code"})
        if isinstance(ro, dict) and ro:
            try:
                ro_dump = json.dumps(ro, ensure_ascii=False, indent=2)
            except Exception:
                ro_dump = str(ro)
            if len(ro_dump) > 12000:
                ro_dump = ro_dump[:12000] + "\n…"
            sections.append({"heading": "rawOutput", "body": ro_dump, "style": "code"})

    summary = " · ".join(summary_bits) if summary_bits else (title[:100] if title else label)
    # Avoid summary == label noise for in_progress (user's complaint case)
    if summary == label and ri.get("command"):
        one = " ".join(str(ri["command"]).split())
        summary = f"$ {one[:117]}…" if len(one) > 120 else f"$ {one}"
    return {
        "role": "tool",
        "label": label,
        "kind": kind or (variant.lower() if isinstance(variant, str) else "") or "tool",
        "variant": variant,
        "title": title,
        "status": status,
        "summary": summary,
        "sections": sections,
        "tool_call_id": update.get("toolCallId"),
        "phase": phase,
        "raw_input": ri,
        "raw_output": ro if isinstance(ro, dict) else {},
    }


def _ro_type(update: dict | None) -> str:
    if not update or not isinstance(update, dict):
        return ""
    ro = update.get("rawOutput")
    if isinstance(ro, dict):
        return str(ro.get("type") or "")
    return ""


def _is_background_start_update(update: dict | None) -> bool:
    """Grok marks background shell handoff as status=completed with this RO type — not final output."""
    return _ro_type(update) == "BackgroundTaskStarted"


def merge_tool_trace(
    start_update: dict | None,
    result_updates: list[dict],
    *,
    sess_dir: Path | None = None,
    max_output_file_chars: int | None = None,
    full_detail: bool = True,
) -> dict:
    """Merge tool_call + subsequent tool_call_update(s) into one readable block.

    Does not treat BackgroundTaskStarted as a final result; prefers richest Bash /
    terminal-log payload so long-running tools get one accurate block.
    """
    # Prefer real completed results; ignore "completed" background handoffs
    best = None
    bg_start = None
    in_progress_list: list[dict] = []
    for u in result_updates:
        if _is_background_start_update(u):
            bg_start = u
            # Still useful for output_file / command, but not as primary "done" status
            in_progress_list.append(u)
            continue
        if u.get("status") == "completed":
            best = u
        elif u.get("status") == "in_progress" or u.get("rawOutput") or u.get("content"):
            in_progress_list.append(u)
        elif u.get("kind") or u.get("rawInput"):
            in_progress_list.append(u)

    def _richness(u: dict) -> int:
        score = 0
        ro = u.get("rawOutput")
        if isinstance(ro, dict):
            score += 10
            if ro.get("type") == "BackgroundTaskStarted":
                score -= 50  # never win on richness alone
            for k in ("output_for_prompt", "output", "stdout", "FileContent", "Content", "stderr", "command"):
                v = ro.get(k)
                if v not in (None, "", [], {}):
                    score += 5 + min(len(_bytes_or_str(v)), 50000) // 200
            of = ro.get("output_file")
            if of and sess_dir is not None:
                path = _resolve_output_file_path(
                    of if isinstance(of, str) else "",
                    sess_dir=sess_dir,
                    tool_call_id=u.get("toolCallId") if isinstance(u.get("toolCallId"), str) else None,
                )
                if path is not None:
                    try:
                        score += 20 + min(path.stat().st_size, 500_000) // 500
                    except OSError:
                        score += 5
        if u.get("content"):
            score += 3
        if u.get("rawInput"):
            score += 4
        if u.get("title"):
            score += 1
        if u.get("status") == "completed" and not _is_background_start_update(u):
            score += 15
        return score

    richest_ip = max(in_progress_list, key=_richness) if in_progress_list else None
    # Prefer true completed; else richest stream; never prefer bg-start alone if we have Bash chunks
    if best is not None:
        primary = best
    elif richest_ip is not None:
        primary = richest_ip
    elif result_updates:
        primary = result_updates[-1]
    else:
        primary = {}
    # Overlay start input onto primary for full context
    merged = dict(primary)
    if start_update:
        ri = start_update.get("rawInput") or start_update.get("input")
        # Prefer start's full input; streaming updates often omit it
        if ri:
            merged["rawInput"] = ri
        if start_update.get("title"):
            # Prefer non-empty title from start (updates often have title="")
            if not (merged.get("title") or "").strip():
                merged["title"] = start_update.get("title")
        if start_update.get("toolName") and not merged.get("toolName"):
            merged["toolName"] = start_update.get("toolName")
        if start_update.get("kind") and not merged.get("kind"):
            merged["kind"] = start_update.get("kind")
        if start_update.get("locations") and not merged.get("locations"):
            merged["locations"] = start_update.get("locations")
        if start_update.get("toolCallId") and not merged.get("toolCallId"):
            merged["toolCallId"] = start_update.get("toolCallId")

    # Carry richest streaming / bg-start fields when primary is sparse or is still bg-start
    donors = [u for u in (richest_ip, bg_start) if u and u is not primary]
    for donor in donors:
        if not merged.get("kind") and donor.get("kind"):
            merged["kind"] = donor.get("kind")
        if not merged.get("rawInput") and donor.get("rawInput"):
            merged["rawInput"] = donor.get("rawInput")
        if not (merged.get("title") or "").strip() and donor.get("title"):
            merged["title"] = donor.get("title")
        if not merged.get("locations") and donor.get("locations"):
            merged["locations"] = donor.get("locations")
        if donor.get("content"):
            if not any(
                isinstance(b, dict) and b.get("type") == "diff" for b in (merged.get("content") or [])
            ):
                if any(
                    isinstance(b, dict) and b.get("type") == "diff" for b in (donor.get("content") or [])
                ):
                    merged["content"] = donor.get("content")
        mro = merged.get("rawOutput") if isinstance(merged.get("rawOutput"), dict) else {}
        dro = donor.get("rawOutput") if isinstance(donor.get("rawOutput"), dict) else {}
        if not dro:
            continue
        # Prefer Bash (or any non-BackgroundTaskStarted) RO over handoff-only RO
        if _ro_type(merged) == "BackgroundTaskStarted" and dro.get("type") not in (
            None,
            "",
            "BackgroundTaskStarted",
        ):
            combo = dict(mro)
            combo.update(dro)
            merged["rawOutput"] = combo
            continue
        if dro and (
            not mro
            or _ro_type(merged) == "BackgroundTaskStarted"
            or (
                not _bytes_or_str(mro.get("output_for_prompt") or mro.get("output") or mro.get("stdout"))
                and _bytes_or_str(dro.get("output_for_prompt") or dro.get("output") or dro.get("stdout"))
            )
        ):
            combo = dict(dro)
            combo.update({k: v for k, v in mro.items() if v not in (None, "", [], {})})
            a = _bytes_or_str(mro.get("output_for_prompt") or mro.get("output") or mro.get("stdout"))
            b = _bytes_or_str(dro.get("output_for_prompt") or dro.get("output") or dro.get("stdout"))
            if len(b) > len(a):
                for k in ("output_for_prompt", "output", "stdout"):
                    if dro.get(k) not in (None, "", [], {}):
                        combo[k] = dro.get(k)
                        break
            # Preserve output_file from bg start if missing
            if not combo.get("output_file") and mro.get("output_file"):
                combo["output_file"] = mro.get("output_file")
            if not combo.get("output_file") and dro.get("output_file"):
                combo["output_file"] = dro.get("output_file")
            merged["rawOutput"] = combo

    # Promote to Bash for formatting when we have shell signals but RO type is still handoff
    mro = merged.get("rawOutput") if isinstance(merged.get("rawOutput"), dict) else {}
    if mro.get("type") == "BackgroundTaskStarted" or (
        not mro.get("type")
        and (
            mro.get("output_file")
            or (start_update or {}).get("title") in ("run_terminal_command", "bash", "shell")
            or ((start_update or {}).get("rawInput") or {}).get("command")
        )
    ):
        mro = dict(mro)
        if mro.get("type") == "BackgroundTaskStarted":
            # Keep output_file; present as Bash so stdout path + log read runs
            mro["type"] = "Bash"
            if not merged.get("kind"):
                merged["kind"] = "execute"
        elif not mro.get("type") and (
            mro.get("output_file") or ((start_update or {}).get("rawInput") or {}).get("command")
        ):
            mro["type"] = "Bash"
            if not merged.get("kind"):
                merged["kind"] = "execute"
        merged["rawOutput"] = mro

    # Terminal log size (for status): if we have real log bytes, treat as completed once
    # the turn assembler flushes (we only merge at turn boundaries now).
    log_bytes = 0
    tid_for_log = merged.get("toolCallId") or (start_update or {}).get("toolCallId")
    of_raw = mro.get("output_file") if isinstance(mro, dict) else None
    if sess_dir is not None:
        log_path = _resolve_output_file_path(
            of_raw if isinstance(of_raw, str) else "",
            sess_dir=sess_dir,
            tool_call_id=tid_for_log if isinstance(tid_for_log, str) else None,
        )
        if log_path is not None:
            try:
                log_bytes = log_path.stat().st_size
            except OSError:
                log_bytes = 0

    # Status: true completed wins; else if we have a non-trivial terminal log, seal as completed
    # (background tools often never emit a second completed). Else keep stream status.
    if best is not None:
        merged["status"] = "completed"
    elif log_bytes > 64:
        merged["status"] = "completed"
    elif best is None and bg_start is not None and richest_ip is bg_start and log_bytes <= 64:
        merged["status"] = "in_progress"
    elif richest_ip is not None and not merged.get("status"):
        merged["status"] = richest_ip.get("status") or "in_progress"

    # Only start exists (tool just kicked off)
    if not result_updates and start_update:
        merged = dict(start_update)
        if not merged.get("status"):
            merged["status"] = "in_progress"

    file_cap = TOOL_FULL_CHARS if max_output_file_chars is None else max_output_file_chars
    block = format_tool_block_from_update(
        merged,
        phase="merged",
        sess_dir=sess_dir,
        max_output_file_chars=file_cap,
        full_detail=full_detail,
    )
    block["kind_phase"] = "trace"
    return block


def build_timeline(sess_dir: Path, limit: int = 5000, hide_phases: bool = True) -> list[dict]:
    items: list[dict] = []

    for ev in iter_jsonl(sess_dir / "events.jsonl", max_lines=limit):
        if ev.get("_parse_error"):
            continue
        etype = ev.get("type", "event")
        cat = categorize_event(etype)
        if hide_phases and cat == "phase":
            continue
        items.append(
            {
                "source": "events",
                "ts": ev.get("ts"),
                "sort_key": ev.get("ts") or "",
                "kind": etype,
                "category": cat,
                "title": format_event_title(ev),
                "detail": summarize_event(ev),
                "raw": ev,
            }
        )

    for up in iter_jsonl(sess_dir / "updates.jsonl", max_lines=limit):
        if up.get("_parse_error"):
            continue
        params = up.get("params") or {}
        update = params.get("update") or {}
        su = update.get("sessionUpdate") or update.get("kind") or up.get("method", "update")
        meta = params.get("_meta") or {}
        agent_ms = meta.get("agentTimestampMs") or (update.get("_meta") or {}).get("agentTimestampMs")
        ts_iso = None
        if agent_ms:
            try:
                ts_iso = datetime.fromtimestamp(agent_ms / 1000, tz=timezone.utc).isoformat()
            except Exception:
                pass
        if not ts_iso and up.get("timestamp"):
            try:
                ts = up["timestamp"]
                if ts > 1e12:
                    ts = ts / 1000
                ts_iso = datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
            except Exception:
                pass
        cat = categorize_update(su)
        items.append(
            {
                "source": "updates",
                "ts": ts_iso,
                "sort_key": ts_iso or str(up.get("timestamp") or ""),
                "kind": su,
                "category": cat,
                "title": format_update_title(update, su),
                "detail": summarize_update(update, su),
                "raw": up,
            }
        )

    items.sort(key=lambda x: x.get("sort_key") or "")
    return items


def build_chat_view(
    sess_dir: Path,
    limit: int | None = None,
    *,
    max_output_file_chars: int | None = None,
    full_detail: bool = True,
) -> list[dict]:
    """Build readable chat + tool traces from updates.jsonl.

    Tool calls are merged by toolCallId into **one block per tool**, finalized only
    when the turn completes (turn_completed), the next user prompt starts, or the
    stream ends — never on the first status=completed (background handoffs).

    full_detail=True keeps full tool bodies for UI expand and exports.
    """
    if limit is None:
        limit = CHAT_VIEW_MAX_LINES if CHAT_VIEW_MAX_LINES > 0 else None
    # iter_jsonl: None max_lines = no limit
    max_lines = limit if limit and limit > 0 else None
    file_cap = TOOL_FULL_CHARS if max_output_file_chars is None else max_output_file_chars

    messages: list[dict] = []
    buf_user: list[str] = []
    buf_agent: list[str] = []
    # toolCallId -> {"start": update|None, "updates": [update, ...]}
    open_tools: dict[str, dict] = {}
    tool_order: list[str] = []  # preserve first-seen order for orphan flushes

    def flush_user():
        nonlocal buf_user
        if buf_user:
            messages.append({"role": "user", "text": "".join(buf_user)})
            buf_user = []

    def flush_agent():
        nonlocal buf_agent
        if buf_agent:
            messages.append({"role": "assistant", "text": "".join(buf_agent)})
            buf_agent = []

    def flush_tool(tid: str) -> None:
        slot = open_tools.pop(tid, None)
        if not slot:
            return
        if tid in tool_order:
            tool_order.remove(tid)
        block = merge_tool_trace(
            slot.get("start"),
            slot.get("updates") or [],
            sess_dir=sess_dir,
            max_output_file_chars=file_cap,
            full_detail=full_detail,
        )
        messages.append(block)

    def flush_all_tools():
        for tid in list(tool_order):
            flush_tool(tid)
        open_tools.clear()
        tool_order.clear()

    for up in iter_jsonl(sess_dir / "updates.jsonl", max_lines=max_lines):
        if up.get("_parse_error"):
            continue
        update = ((up.get("params") or {}).get("update")) or {}
        su = update.get("sessionUpdate")
        if su == "user_message_chunk":
            # Next user turn: seal prior tools with everything collected so far
            flush_all_tools()
            flush_agent()
            buf_user.append(((update.get("content") or {}).get("text")) or "")
        elif su == "agent_message_chunk":
            # Keep tools open across agent text within the same turn (accuracy > live partials)
            flush_user()
            buf_agent.append(((update.get("content") or {}).get("text")) or "")
        elif su == "tool_call":
            flush_user()
            flush_agent()
            tid = update.get("toolCallId") or f"_anon_{len(tool_order)}"
            if tid not in open_tools:
                open_tools[tid] = {"start": update, "updates": []}
                tool_order.append(tid)
            else:
                # Same id again: keep accumulating (do not emit a second block)
                open_tools[tid]["start"] = update
        elif su == "tool_call_update":
            tid = update.get("toolCallId") or (tool_order[-1] if tool_order else None)
            if not tid:
                flush_user()
                flush_agent()
                messages.append(
                    format_tool_block_from_update(
                        update,
                        phase="result",
                        sess_dir=sess_dir,
                        max_output_file_chars=file_cap,
                        full_detail=full_detail,
                    )
                )
                continue
            if tid not in open_tools:
                open_tools[tid] = {"start": None, "updates": []}
                tool_order.append(tid)
            open_tools[tid]["updates"].append(update)
            # Do NOT flush on status=completed — wait for turn_completed / next user / EOF
        elif su == "turn_completed":
            flush_all_tools()
            flush_user()
            flush_agent()
            messages.append({"role": "system", "text": "— turn completed —"})

    flush_all_tools()
    flush_user()
    flush_agent()

    if messages:
        return messages

    for row in iter_jsonl(sess_dir / "chat_history.jsonl", max_lines=max_lines):
        if row.get("_parse_error"):
            continue
        role = row.get("type") or row.get("role") or "unknown"
        content = row.get("content")
        if isinstance(content, list):
            texts = []
            for block in content:
                if isinstance(block, dict) and block.get("text"):
                    texts.append(block["text"])
                elif isinstance(block, str):
                    texts.append(block)
            content = "\n".join(texts)
        elif not isinstance(content, str):
            content = json.dumps(content, ensure_ascii=False) if content is not None else ""
        messages.append({"role": role, "text": content})
    return messages


def prompt_turn_status(sess_dir: Path, prompt_index: int, *, limit: int | None = None) -> dict:
    """Whether a user prompt/turn has finished in updates.jsonl.

    A turn is complete when we have seen ``turn_completed`` after that prompt and
    before the next user prompt, **or** a later user prompt has started (prior turn
    was sealed). The latest turn is incomplete until ``turn_completed`` (or EOF with
    no open tools — still treated incomplete if tools were in flight without turn_completed).

    Returns dict: complete (bool), reason (str), saw_turn_completed (bool), has_later_user (bool).
    """
    if limit is None:
        limit = CHAT_VIEW_MAX_LINES if CHAT_VIEW_MAX_LINES > 0 else None
    max_lines = limit if limit and limit > 0 else None

    current_prompt = -1
    in_user_chunk = False
    saw_turn_completed_for_target = False
    has_later_user = False
    open_tools_after_target = False
    tool_ids_open: set[str] = set()

    for up in iter_jsonl(sess_dir / "updates.jsonl", max_lines=max_lines):
        if up.get("_parse_error"):
            continue
        update = ((up.get("params") or {}).get("update")) or {}
        su = update.get("sessionUpdate")
        if su == "user_message_chunk":
            if not in_user_chunk:
                current_prompt += 1
                in_user_chunk = True
                if current_prompt > prompt_index:
                    has_later_user = True
                    break
            continue
        if su:
            in_user_chunk = False
        if current_prompt < prompt_index:
            continue
        if current_prompt > prompt_index:
            has_later_user = True
            break
        # current_prompt == prompt_index
        if su == "tool_call":
            tid = update.get("toolCallId")
            if tid:
                tool_ids_open.add(tid)
        elif su == "tool_call_update":
            tid = update.get("toolCallId")
            if tid:
                tool_ids_open.add(tid)
            # BackgroundTaskStarted is not "tools done"
            if (
                update.get("status") == "completed"
                and not _is_background_start_update(update)
                and tid
            ):
                pass  # still wait for turn_completed for accuracy
        elif su == "turn_completed":
            saw_turn_completed_for_target = True
            tool_ids_open.clear()

    if has_later_user:
        return {
            "complete": True,
            "reason": "later_user_prompt",
            "saw_turn_completed": saw_turn_completed_for_target,
            "has_later_user": True,
        }
    if saw_turn_completed_for_target:
        return {
            "complete": True,
            "reason": "turn_completed",
            "saw_turn_completed": True,
            "has_later_user": False,
        }
    open_tools_after_target = bool(tool_ids_open)
    return {
        "complete": False,
        "reason": "turn_in_progress" if (current_prompt >= prompt_index) else "prompt_not_found",
        "saw_turn_completed": False,
        "has_later_user": False,
        "open_tool_ids": len(tool_ids_open),
    }


class TurnIncompleteError(RuntimeError):
    """Raised when exporting a turn that has not finished yet."""

    def __init__(self, prompt_index: int, status: dict):
        self.prompt_index = prompt_index
        self.status = status
        super().__init__(
            f"Turn {prompt_index + 1} is still in progress "
            f"({status.get('reason', 'unknown')}). Wait until the agent finishes, then export."
        )


def session_overview(sess_dir: Path) -> dict:
    summary = load_json(sess_dir / "summary.json") or {}
    signals = load_json(sess_dir / "signals.json") or {}
    event_types: dict[str, int] = {}
    for ev in iter_jsonl(sess_dir / "events.jsonl", max_lines=10000):
        if ev.get("_parse_error"):
            continue
        t = ev.get("type", "?")
        event_types[t] = event_types.get(t, 0) + 1
    update_types: dict[str, int] = {}
    for up in iter_jsonl(sess_dir / "updates.jsonl", max_lines=10000):
        if up.get("_parse_error"):
            continue
        su = ((up.get("params") or {}).get("update") or {}).get("sessionUpdate") or up.get("method") or "?"
        update_types[su] = update_types.get(su, 0) + 1
    return {
        "summary": summary,
        "signals": signals,
        "event_types": dict(sorted(event_types.items(), key=lambda x: -x[1])),
        "update_types": dict(sorted(update_types.items(), key=lambda x: -x[1])),
        "path": str(sess_dir),
        "files": sorted(p.name for p in sess_dir.iterdir() if p.is_file()),
    }


def search_unified_log(
    q: str = "",
    msg: str = "",
    src: str = "",
    sid: str = "",
    limit: int = 200,
) -> list[dict]:
    if not UNIFIED_LOG.exists():
        return []
    q_l = q.lower().strip()
    msg_l = msg.lower().strip()
    src_l = src.lower().strip()
    sid_l = sid.strip()
    lines = UNIFIED_LOG.read_text(encoding="utf-8", errors="replace").splitlines()
    hits: list[dict] = []
    for line in reversed(lines):
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if sid_l and (obj.get("sid") or "") != sid_l:
            continue
        if src_l and src_l not in (obj.get("src") or "").lower():
            continue
        if msg_l and msg_l not in (obj.get("msg") or "").lower():
            continue
        if q_l and q_l not in json.dumps(obj, ensure_ascii=False).lower():
            continue
        hits.append(obj)
        if len(hits) >= limit:
            break
    hits.reverse()
    return hits


def fmt_time(ts: str | None) -> str:
    if not ts:
        return "—"
    try:
        d = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return d.strftime("%H:%M:%S")
    except Exception:
        return str(ts)[11:19] if len(str(ts)) > 19 else str(ts)[:8]


def fmt_date(ts: str | None) -> str:
    if not ts:
        return ""
    try:
        d = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return d.strftime("%b %d %H:%M")
    except Exception:
        return str(ts)[:16]


def iter_prompt_turn_updates(sess_dir: Path, limit: int = 5000):
    """Yield (prompt_index, update_dict, sessionUpdate) for each updates.jsonl row.

    prompt_index matches build_chat_view user prompts: 0 = first user message,
    1 = second, …  -1 = before any user prompt (rare system/setup only).
    """
    current_prompt = -1
    in_user_chunk = False
    for up in iter_jsonl(sess_dir / "updates.jsonl", max_lines=limit):
        if up.get("_parse_error"):
            continue
        update = ((up.get("params") or {}).get("update")) or {}
        su = update.get("sessionUpdate")
        if su == "user_message_chunk":
            if not in_user_chunk:
                current_prompt += 1
                in_user_chunk = True
        elif su:
            in_user_chunk = False
        yield current_prompt, update, su


def build_session_file_changes(
    sess_dir: Path,
    limit: int = 5000,
    *,
    prompt_index: int | None = None,
) -> dict:
    """Collect code edits grouped by file.

    Args:
        prompt_index: If set (0-based), only edits that happened *after* that user
            prompt and *before* the next user prompt (one chat turn). If None,
            include the whole session.

    Returns dict with files[], totals, plus prompt_index / prompt_count metadata.
    """
    by_path: dict[str, list[dict]] = {}
    order: list[str] = []
    hunk_i = 0
    max_prompt_seen = -1

    def _add_hunk(
        path: str | None,
        old: str,
        new: str,
        tool_call_id: str | None = None,
        *,
        turn: int = -1,
    ) -> None:
        nonlocal hunk_i
        if prompt_index is not None and turn != prompt_index:
            return
        if not path:
            path = "(unknown file)"
        path = str(path)
        if old == new:
            return
        hunk_i += 1
        diff = _unified_diff(old or "", new or "", path)
        if path not in by_path:
            by_path[path] = []
            order.append(path)
        by_path[path].append(
            {
                "index": hunk_i,
                "old": old or "",
                "new": new or "",
                "diff": diff,
                "tool_call_id": tool_call_id,
                "prompt_index": turn,
            }
        )

    for turn, update, su in iter_prompt_turn_updates(sess_dir, limit=limit):
        if turn > max_prompt_seen:
            max_prompt_seen = turn
        if su not in ("tool_call", "tool_call_update"):
            continue
        tid = update.get("toolCallId")
        ri = update.get("rawInput") or {}
        if not isinstance(ri, dict):
            ri = {}
        ro = update.get("rawOutput")
        if not isinstance(ro, dict):
            ro = {}

        # Direct search_replace input on tool_call
        if su == "tool_call" and ri.get("old_string") is not None and ri.get("file_path"):
            _add_hunk(
                ri.get("file_path"),
                ri.get("old_string") or "",
                ri.get("new_string") or "",
                tid,
                turn=turn,
            )
            continue

        if su != "tool_call_update":
            continue

        # Diff blocks in content (preferred for applied edits)
        for block in update.get("content") or []:
            if isinstance(block, dict) and block.get("type") == "diff":
                _add_hunk(
                    block.get("path") or ri.get("file_path"),
                    block.get("oldText") or "",
                    block.get("newText") or "",
                    tid,
                    turn=turn,
                )

        # Completed SearchReplace payload
        if ro.get("type") == "SearchReplace":
            edits = ro.get("EditsApplied") or ro.get("edits") or {}
            if isinstance(edits, dict):
                _add_hunk(
                    ri.get("file_path"),
                    edits.get("old_string") or edits.get("oldText") or "",
                    edits.get("new_string") or edits.get("newText") or "",
                    tid,
                    turn=turn,
                )
        elif ri.get("variant") in ("SearchReplace",) or update.get("kind") == "edit":
            if ri.get("old_string") is not None and ri.get("file_path"):
                has_diff_block = any(
                    isinstance(b, dict) and b.get("type") == "diff" for b in (update.get("content") or [])
                )
                if not has_diff_block:
                    _add_hunk(
                        ri.get("file_path"),
                        ri.get("old_string") or "",
                        ri.get("new_string") or "",
                        tid,
                        turn=turn,
                    )

    files_out: list[dict] = []
    total_added = total_removed = 0
    for path in order:
        hunks = by_path[path]
        # Dedupe identical consecutive hunks (call + update duplicates)
        deduped: list[dict] = []
        seen_sig: set[str] = set()
        for h in hunks:
            sig = f"{h['old']!r}||{h['new']!r}"
            if sig in seen_sig:
                continue
            seen_sig.add(sig)
            deduped.append(h)
        added = removed = 0
        for h in deduped:
            for line in (h.get("diff") or "").splitlines():
                if line.startswith("+") and not line.startswith("+++"):
                    added += 1
                elif line.startswith("-") and not line.startswith("---"):
                    removed += 1
        total_added += added
        total_removed += removed
        files_out.append(
            {
                "path": path,
                "short_path": _short_path(path, 64),
                "hunks": deduped,
                "hunk_count": len(deduped),
                "lines_added": added,
                "lines_removed": removed,
            }
        )

    prompt_count = max_prompt_seen + 1 if max_prompt_seen >= 0 else 0
    return {
        "files": files_out,
        "total_hunks": sum(f["hunk_count"] for f in files_out),
        "total_files": len(files_out),
        "total_added": total_added,
        "total_removed": total_removed,
        "prompt_index": prompt_index,
        "prompt_count": prompt_count,
        "scoped": prompt_index is not None,
    }


_ABS_PATH_RE = re.compile(
    r"(?:^|[\s\"'`=\(\[\{,])("
    r"/(?:Users|home|tmp|var|opt|private|Library)[^\s\"'<>|]+"
    r"|~/(?:[^\s\"'<>|]+))"
)


def _candidate_paths_from_text(text: str) -> list[str]:
    if not text:
        return []
    found: list[str] = []
    for m in _ABS_PATH_RE.finditer(text):
        p = m.group(1).rstrip(".,;:)]}'\"")
        if p:
            found.append(p)
    for m in re.finditer(r"(/(?:Users|home|tmp|var|opt)[^\s\"'<>|]{3,})", text):
        p = m.group(1).rstrip(".,;:)]}'\"")
        if p and p not in found:
            found.append(p)
    return found


def _is_downloadish_path(path: Path | str) -> bool:
    """True for user-facing outputs / media, not arbitrary source we merely read."""
    try:
        p = Path(str(path)).expanduser()
        s = str(p).lower()
        name = p.name.lower()
    except Exception:
        return False
    # Always keep session terminal logs
    if "/terminal/" in s and s.endswith(".log"):
        return True
    # User download / desktop / temp media
    location_ok = any(
        x in s
        for x in (
            "/downloads/",
            "/desktop/",
            "/tmp/",
            "/var/folders/",
            "/grok-turn-exports/",
            "/trace-exports/",
            "/.grok/trace-exports/",
        )
    )
    media_ext = name.endswith(
        (
            ".png",
            ".jpg",
            ".jpeg",
            ".webp",
            ".gif",
            ".mp4",
            ".mov",
            ".webm",
            ".pdf",
            ".tar.gz",
            ".tgz",
            ".zip",
            ".csv",
            ".xlsx",
            ".docx",
            ".pptx",
            ".opus",
            ".mp3",
            ".wav",
        )
    )
    # Explicit export markdown from prior runs is fine; don't vacuum all .md sources
    if name.startswith("turn-") and name.endswith(".md"):
        return True
    if location_ok and (media_ext or name.endswith((".log", ".json", ".txt", ".md", ".html"))):
        return True
    if media_ext and location_ok:
        return True
    # Generated images often land under /var/folders or tmp without "downloads"
    if media_ext and ("/var/folders/" in s or "/tmp/" in s or "/private/var/" in s):
        return True
    return False


def collect_turn_artifacts(sess_dir: Path, tools: list[dict]) -> list[dict]:
    """Filesystem artifacts produced/downloaded this turn (logs + user-facing outputs).

    Intentionally skips source files that were only *read* (skills, repo paths, etc.).
    """
    seen: set[str] = set()
    artifacts: list[dict] = []

    def add(path: Path | str | None, *, kind: str, source: str, force: bool = False) -> None:
        if not path:
            return
        try:
            p = Path(str(path)).expanduser()
            if not p.is_file():
                return
            if not force and not _is_downloadish_path(p):
                return
            # Terminal logs always allowed
            if force or (sess_dir / "terminal") in p.parents or p.parent == (sess_dir / "terminal"):
                pass
            key = str(p.resolve())
        except OSError:
            return
        if key in seen:
            return
        try:
            size = p.stat().st_size
        except OSError:
            return
        if size > 50 * 1024 * 1024:
            return
        seen.add(key)
        artifacts.append(
            {
                "path": key,
                "name": p.name,
                "kind": kind,
                "source": source,
                "size": size,
            }
        )

    for block in tools:
        tid = block.get("tool_call_id")
        if tid:
            add(
                sess_dir / "terminal" / f"{tid}.log",
                kind="terminal_log",
                source=f"tool:{tid}",
                force=True,
            )
        ro = block.get("raw_output") if isinstance(block.get("raw_output"), dict) else {}
        of = ro.get("output_file") if isinstance(ro, dict) else None
        resolved = _resolve_output_file_path(
            of if isinstance(of, str) else "",
            sess_dir=sess_dir,
            tool_call_id=tid if isinstance(tid, str) else None,
        )
        if resolved is not None:
            add(resolved, kind="output_file", source=f"tool:{tid or '?'}", force=True)
        blobs: list[str] = []
        ri = block.get("raw_input")
        if isinstance(ri, dict):
            try:
                blobs.append(json.dumps(ri, ensure_ascii=False))
            except Exception:
                blobs.append(str(ri))
        for sec in block.get("sections") or []:
            if not isinstance(sec, dict):
                continue
            meta = sec.get("meta") or {}
            # Only explicit artifact markers (output_file section), not every read path
            if meta.get("artifact") and sec.get("body"):
                add(sec.get("body"), kind="artifact", source=sec.get("heading") or "section", force=True)
            body = sec.get("body") or ""
            if body:
                blobs.append(body)
        for blob in blobs:
            for cand in _candidate_paths_from_text(blob):
                add(cand, kind="referenced", source=f"tool:{tid or block.get('label') or '?'}")

    return artifacts


def build_turn_bundle(
    sess_dir: Path,
    prompt_index: int,
    *,
    limit: int | None = None,
    require_complete: bool = False,
) -> dict:
    """One user turn as Prompt + Trace (tools/events) + Response + artifacts.

    prompt_index is 0-based and matches build_chat_view user messages and
    build_session_file_changes(prompt_index=…).

    If require_complete is True and the turn has not finished, raises TurnIncompleteError.
    """
    status = prompt_turn_status(sess_dir, prompt_index, limit=limit)
    if require_complete and not status.get("complete"):
        raise TurnIncompleteError(prompt_index, status)

    # Full fidelity: no line-scan default cap; full tool bodies
    msgs = build_chat_view(
        sess_dir,
        limit=limit,
        max_output_file_chars=TOOL_FULL_CHARS,
        full_detail=True,
    )
    prompt_text = ""
    response_parts: list[str] = []
    tools: list[dict] = []
    user_i = -1
    in_turn = False
    for m in msgs:
        role = m.get("role")
        if role == "user":
            user_i += 1
            if user_i == prompt_index:
                in_turn = True
                prompt_text = m.get("text") or ""
                response_parts = []
                tools = []
                continue
            if in_turn and user_i > prompt_index:
                break
        if not in_turn:
            continue
        if role in ("assistant", "agent"):
            t = m.get("text") or ""
            if t:
                response_parts.append(t)
        elif role == "tool":
            tools.append(m)

    timeline_lines: list[str] = []
    ev_limit = limit if limit and limit > 0 else None
    for ev in iter_jsonl(sess_dir / "events.jsonl", max_lines=ev_limit):
        if ev.get("_parse_error"):
            continue
        tn = ev.get("turn_number")
        if tn is not None:
            try:
                if int(tn) - 1 == prompt_index:
                    timeline_lines.append(
                        f"{fmt_time(ev.get('timestamp') or ev.get('ts'))}  "
                        f"{format_event_title(ev)}"
                    )
            except (TypeError, ValueError):
                pass

    trace_sections: list[str] = []
    for i, block in enumerate(tools, 1):
        label = block.get("label") or block.get("tool_name") or block.get("title") or "tool"
        tool_status = block.get("status") or ""
        summary = block.get("summary") or block.get("title") or ""
        head = f"### Tool {i}: {label}"
        if tool_status:
            head += f" [{tool_status}]"
        lines = [head]
        if summary and summary != label:
            lines.append(summary)
        sections = list(block.get("sections") or [])
        if len(sections) <= 1 and block.get("raw_input"):
            dump = _generic_input_dump(block["raw_input"], max_chars=TOOL_FULL_CHARS)
            if dump and not any(s.get("heading") == "input" for s in sections):
                sections.append({"heading": "input (full)", "body": dump, "style": "code"})
        for sec in sections:
            h = sec.get("heading") or sec.get("style") or "section"
            body = sec.get("body") or ""
            if body and len(body) > TOOL_FULL_CHARS:
                body = body[:TOOL_FULL_CHARS] + f"\n… truncated at {TOOL_FULL_CHARS} chars"
            lines.append(f"\n#### {h}")
            if body:
                style = sec.get("style") or ""
                if style in ("cmd", "shell", "code", "diff", "grep") or "\n" in body:
                    fence = "diff" if style == "diff" else ("bash" if style in ("cmd", "shell") else "")
                    lines.append(f"```{fence}".rstrip())
                    lines.append(body)
                    lines.append("```")
                else:
                    lines.append(body)
        if block.get("content") is not None and not sections:
            content = block.get("content")
            if not isinstance(content, str):
                content = json.dumps(content, ensure_ascii=False, indent=2)
            lines.append("\n#### content")
            lines.append("```")
            lines.append(content if len(content) < TOOL_FULL_CHARS else content[:TOOL_FULL_CHARS] + "\n…")
            lines.append("```")
        if tool_status == "in_progress" and len(lines) <= 2:
            lines.append("\n_(tool still running — partial args/output above if available)_")
        trace_sections.append("\n".join(lines))

    if timeline_lines:
        trace_sections.append("### Timeline events\n" + "\n".join(timeline_lines))

    fc_limit = limit if limit and limit > 0 else 50000
    file_changes = build_session_file_changes(sess_dir, prompt_index=prompt_index, limit=fc_limit)
    if file_changes.get("files"):
        fc_lines = ["### File changes this turn"]
        for f in file_changes["files"]:
            path = f.get("path") or "?"
            a = f.get("lines_added") or 0
            r = f.get("lines_removed") or 0
            fc_lines.append(f"- {path}  (+{a} / -{r})")
            for hunk in (f.get("hunks") or [])[:20]:
                diff = hunk.get("diff") or hunk.get("unified") or ""
                if diff:
                    fc_lines.append("```diff")
                    fc_lines.append(diff if len(diff) < 12000 else diff[:12000] + "\n…")
                    fc_lines.append("```")
        trace_sections.append("\n".join(fc_lines))

    artifacts = collect_turn_artifacts(sess_dir, tools)
    response_text = "\n\n".join(response_parts).strip()
    trace_text = "\n\n".join(trace_sections).strip()
    prompt_count = sum(1 for m in msgs if m.get("role") == "user")

    files_md = ""
    if artifacts:
        fl = ["## Files", ""]
        fl.append("Artifacts referenced or produced this turn (copied beside this markdown on export):")
        fl.append("")
        for a in artifacts:
            fl.append(f"- `{a['name']}` — {a['kind']} ({a['size']} bytes)  \n  `{a['path']}`")
        files_md = "\n".join(fl) + "\n\n"

    markdown = (
        f"# Turn {prompt_index + 1}"
        f"{f' / {prompt_count}' if prompt_count else ''}\n\n"
        f"## Prompt\n\n{prompt_text or '_(empty)_'}\n\n"
        f"## Trace\n\n{trace_text or '_(no tool / event trace for this turn)_'}\n\n"
        f"{files_md}"
        f"## Response\n\n{response_text or '_(no agent response yet)_'}\n"
    )

    return {
        "prompt_index": prompt_index,
        "prompt_count": prompt_count,
        "prompt": prompt_text,
        "trace": trace_text,
        "response": response_text,
        "tools": tools,
        "file_changes": file_changes,
        "artifacts": artifacts,
        "markdown": markdown,
        "turn_status": status,
    }


def default_turn_export_dir() -> Path:
    """Directory for turn exports (d key). Default: ~/grok-turn-exports."""
    return TURN_EXPORT_DIR


def export_turn_to_file(
    sess_dir: Path,
    prompt_index: int,
    dest: Path | None = None,
    *,
    session_id: str | None = None,
    copy_artifacts: bool = True,
    require_complete: bool = True,
    settle_seconds: float | None = None,
) -> Path:
    """Write turn bundle under ~/grok-turn-exports (or GROK_ALT_TURN_EXPORT_DIR).

    Layout::

        ~/grok-turn-exports/turn-<sid8>-<nnn>.md
        ~/grok-turn-exports/turn-<sid8>-<nnn>-files/<artifacts>

    By default refuses in-progress turns (require_complete=True). Optional settle
    delay waits for late log flushes after turn_completed.

    Returns the markdown path.
    """
    import time

    st = prompt_turn_status(sess_dir, prompt_index)
    if require_complete and not st.get("complete"):
        raise TurnIncompleteError(prompt_index, st)
    wait = TURN_SETTLE_SECONDS if settle_seconds is None else settle_seconds
    if wait > 0 and st.get("complete") and st.get("reason") == "turn_completed":
        time.sleep(wait)

    bundle = build_turn_bundle(sess_dir, prompt_index, require_complete=require_complete)
    sid = session_id or sess_dir.name
    stem = f"turn-{sid[:8]}-{prompt_index + 1:03d}"
    if dest is None:
        out_dir = default_turn_export_dir()
        out_dir.mkdir(parents=True, exist_ok=True)
        dest = out_dir / f"{stem}.md"
    else:
        dest = Path(dest).expanduser()
        if dest.is_dir() or str(dest).endswith(os.sep):
            dest.mkdir(parents=True, exist_ok=True)
            dest = dest / f"{stem}.md"
        else:
            dest.parent.mkdir(parents=True, exist_ok=True)

    copied: list[dict] = []
    if copy_artifacts and bundle.get("artifacts"):
        files_dir = dest.parent / f"{stem}-files"
        files_dir.mkdir(parents=True, exist_ok=True)
        used_names: set[str] = set()
        for art in bundle["artifacts"]:
            src = Path(art["path"])
            name = art.get("name") or src.name
            base, ext = os.path.splitext(name)
            candidate = name
            n = 2
            while candidate in used_names or (files_dir / candidate).exists():
                candidate = f"{base}-{n}{ext}"
                n += 1
            used_names.add(candidate)
            target = files_dir / candidate
            try:
                shutil.copy2(src, target)
                copied.append({**art, "exported_as": str(target.resolve())})
            except OSError:
                continue
        if copied:
            extra = ["## Files (copied)", ""]
            for c in copied:
                rel = Path(c["exported_as"]).name
                extra.append(
                    f"- [`{rel}`](./{stem}-files/{rel}) — {c['kind']} "
                    f"({c['size']} bytes)  \n  source: `{c['path']}`"
                )
            extra_md = "\n".join(extra) + "\n\n"
            md = bundle["markdown"]
            md = md.replace("## Response\n", extra_md + "## Response\n", 1)
            bundle = {**bundle, "markdown": md, "copied_artifacts": copied}

    meta = (
        f"<!-- session={sid} prompt_index={prompt_index} "
        f"exported_from=grok-alt export_dir={dest.parent} -->\n\n"
    )
    dest.write_text(meta + bundle["markdown"], encoding="utf-8")
    return dest.resolve()

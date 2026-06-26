#!/usr/bin/env python3
"""Grok Trace Viewer — local server for reading Grok sessions & unified logs."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import webbrowser
from datetime import datetime, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

GROK_HOME = Path(os.environ.get("GROK_HOME", Path.home() / ".grok")).expanduser()
SESSIONS_DIR = GROK_HOME / "sessions"
LOGS_DIR = GROK_HOME / "logs"
UNIFIED_LOG = LOGS_DIR / "unified.jsonl"
STATIC_DIR = Path(__file__).resolve().parent / "static"

UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.I,
)


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
            events_path = sess_dir / "events.jsonl"
            updates_path = sess_dir / "updates.jsonl"
            chat_path = sess_dir / "chat_history.jsonl"

            def line_count(p: Path) -> int:
                if not p.exists():
                    return 0
                try:
                    with p.open("rb") as f:
                        return sum(1 for _ in f)
                except Exception:
                    return 0

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
                    "events_count": line_count(events_path),
                    "updates_count": line_count(updates_path),
                    "chat_count": line_count(chat_path),
                    "has_terminal": (sess_dir / "terminal").is_dir(),
                    "has_subagents": (sess_dir / "subagents").is_dir(),
                    "signals": {
                        k: signals.get(k)
                        for k in (
                            "total_tokens",
                            "tool_calls",
                            "turns",
                            "input_tokens",
                            "output_tokens",
                        )
                        if k in signals
                    }
                    if isinstance(signals, dict)
                    else {},
                    "path": str(sess_dir),
                }
            )

    sessions.sort(key=lambda s: s.get("updated_at") or s.get("created_at") or "", reverse=True)
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


def build_timeline(sess_dir: Path, limit: int = 5000) -> list[dict]:
    """Merge events + updates into a readable timeline."""
    items: list[dict] = []

    for ev in iter_jsonl(sess_dir / "events.jsonl", max_lines=limit):
        if ev.get("_parse_error"):
            continue
        etype = ev.get("type", "event")
        items.append(
            {
                "source": "events",
                "ts": ev.get("ts"),
                "sort_key": ev.get("ts") or "",
                "kind": etype,
                "category": categorize_event(etype),
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
        meta = (params.get("_meta") or {}) if isinstance(params, dict) else {}
        agent_ms = meta.get("agentTimestampMs") or update.get("_meta", {}).get("agentTimestampMs")
        ts_iso = None
        if agent_ms:
            try:
                ts_iso = datetime.fromtimestamp(agent_ms / 1000, tz=timezone.utc).isoformat()
            except Exception:
                pass
        if not ts_iso and up.get("timestamp"):
            try:
                # sometimes epoch seconds
                ts = up["timestamp"]
                if ts > 1e12:
                    ts = ts / 1000
                ts_iso = datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
            except Exception:
                pass

        items.append(
            {
                "source": "updates",
                "ts": ts_iso,
                "sort_key": ts_iso or str(up.get("timestamp") or ""),
                "kind": su,
                "category": categorize_update(su),
                "title": format_update_title(update, su),
                "detail": summarize_update(update, su),
                "raw": up,
            }
        )

    items.sort(key=lambda x: x.get("sort_key") or "")
    return items


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
    if su in ("user_message_chunk",):
        return "user"
    if su in ("agent_message_chunk",):
        return "agent"
    if su in ("tool_call", "tool_call_update"):
        return "tool"
    if su in ("turn_completed",):
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
        if ev.get(k) is not None and k not in ("type",):
            if k in ("tool_name", "name") and ev.get("type") in ("tool_started", "tool_completed"):
                continue
            parts.append(f"{k}={ev[k]}")
    # common nested tool input preview
    for k in ("input", "args", "tool_input"):
        if isinstance(ev.get(k), (dict, list, str)):
            preview = json.dumps(ev[k], ensure_ascii=False)
            if len(preview) > 240:
                preview = preview[:240] + "…"
            parts.append(preview)
            break
    return " · ".join(parts)


def format_update_title(update: dict, su: str) -> str:
    if su == "user_message_chunk":
        text = ((update.get("content") or {}).get("text") or "")[:80]
        return f"👤 user: {text}" if text else "👤 user message"
    if su == "agent_message_chunk":
        text = ((update.get("content") or {}).get("text") or "")[:80]
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
        return ((update.get("content") or {}).get("text") or "")[:500]
    if su == "tool_call":
        parts = []
        for k in ("toolName", "name", "kind", "title"):
            if update.get(k):
                parts.append(str(update[k]))
        content = update.get("content") or update.get("rawInput") or update.get("input")
        if content is not None:
            s = content if isinstance(content, str) else json.dumps(content, ensure_ascii=False)
            parts.append(s[:400] + ("…" if len(s) > 400 else ""))
        return " · ".join(parts)
    if su == "tool_call_update":
        parts = []
        if update.get("status"):
            parts.append(f"status={update['status']}")
        for k in ("content", "rawOutput", "output"):
            if update.get(k) is not None:
                s = update[k] if isinstance(update[k], str) else json.dumps(update[k], ensure_ascii=False)
                parts.append(s[:400] + ("…" if len(s) > 400 else ""))
                break
        return " · ".join(parts)
    if su == "plan":
        entries = update.get("entries") or update.get("plan") or []
        if isinstance(entries, list):
            return f"{len(entries)} plan items"
    return ""


def build_chat_view(sess_dir: Path, limit: int = 2000) -> list[dict]:
    """Reconstruct chat-ish stream from updates + chat_history."""
    messages: list[dict] = []

    # Prefer updates for conversation fidelity
    buf_user = []
    buf_agent = []
    tools: list[dict] = []

    def flush_user():
        nonlocal buf_user
        if buf_user:
            messages.append({"role": "user", "text": "".join(buf_user), "source": "updates"})
            buf_user = []

    def flush_agent():
        nonlocal buf_agent
        if buf_agent:
            messages.append({"role": "assistant", "text": "".join(buf_agent), "source": "updates"})
            buf_agent = []

    for up in iter_jsonl(sess_dir / "updates.jsonl", max_lines=limit):
        if up.get("_parse_error"):
            continue
        update = ((up.get("params") or {}).get("update")) or {}
        su = update.get("sessionUpdate")
        if su == "user_message_chunk":
            flush_agent()
            text = ((update.get("content") or {}).get("text")) or ""
            buf_user.append(text)
        elif su == "agent_message_chunk":
            flush_user()
            text = ((update.get("content") or {}).get("text")) or ""
            buf_agent.append(text)
        elif su == "tool_call":
            flush_user()
            flush_agent()
            messages.append(
                {
                    "role": "tool",
                    "kind": "call",
                    "title": update.get("title") or update.get("toolName") or "tool",
                    "tool_name": update.get("toolName") or update.get("name"),
                    "tool_call_id": update.get("toolCallId") or update.get("id"),
                    "status": update.get("status"),
                    "content": update.get("rawInput") or update.get("input") or update.get("content"),
                    "source": "updates",
                }
            )
        elif su == "tool_call_update":
            messages.append(
                {
                    "role": "tool",
                    "kind": "update",
                    "title": update.get("title") or update.get("toolCallId") or "tool",
                    "tool_call_id": update.get("toolCallId") or update.get("id"),
                    "status": update.get("status"),
                    "content": update.get("rawOutput") or update.get("content") or update.get("output"),
                    "source": "updates",
                }
            )
        elif su == "turn_completed":
            flush_user()
            flush_agent()
            messages.append({"role": "system", "text": "— turn completed —", "source": "updates"})

    flush_user()
    flush_agent()

    if messages:
        return messages

    # Fallback: chat_history.jsonl
    for row in iter_jsonl(sess_dir / "chat_history.jsonl", max_lines=limit):
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
        messages.append({"role": role, "text": content, "source": "chat_history"})
    return messages


def search_unified_log(
    q: str = "",
    msg: str = "",
    src: str = "",
    sid: str = "",
    limit: int = 500,
    offset: int = 0,
    tail: bool = True,
) -> dict:
    if not UNIFIED_LOG.exists():
        return {"entries": [], "total_scanned": 0, "path": str(UNIFIED_LOG), "exists": False}

    q_l = q.lower().strip()
    msg_l = msg.lower().strip()
    src_l = src.lower().strip()
    sid_l = sid.strip()

    # For performance on large files: scan from end if tail=True
    entries: list[dict] = []
    scanned = 0
    matched_before_offset = 0

    def matches(obj: dict) -> bool:
        if sid_l and (obj.get("sid") or "") != sid_l:
            return False
        if src_l and src_l not in (obj.get("src") or "").lower():
            return False
        if msg_l and msg_l not in (obj.get("msg") or "").lower():
            return False
        if q_l:
            blob = json.dumps(obj, ensure_ascii=False).lower()
            if q_l not in blob:
                return False
        return True

    # Read all lines (file is ~1MB currently; fine). Use ring buffer if huge later.
    lines = UNIFIED_LOG.read_text(encoding="utf-8", errors="replace").splitlines()
    if tail:
        lines = list(reversed(lines))

    for line in lines:
        scanned += 1
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            obj = {"_raw": line, "_parse_error": True}
        if not matches(obj):
            continue
        if matched_before_offset < offset:
            matched_before_offset += 1
            continue
        entries.append(obj)
        if len(entries) >= limit:
            break

    if tail:
        entries.reverse()

    return {
        "entries": entries,
        "total_scanned": scanned,
        "returned": len(entries),
        "offset": offset,
        "limit": limit,
        "path": str(UNIFIED_LOG),
        "exists": True,
        "file_size": UNIFIED_LOG.stat().st_size,
    }


def session_overview(sess_dir: Path) -> dict:
    summary = load_json(sess_dir / "summary.json") or {}
    signals = load_json(sess_dir / "signals.json") or {}
    files = sorted(p.name for p in sess_dir.iterdir() if p.is_file())
    dirs = sorted(p.name for p in sess_dir.iterdir() if p.is_dir())

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
        "files": files,
        "dirs": dirs,
        "event_types": dict(sorted(event_types.items(), key=lambda x: -x[1])),
        "update_types": dict(sorted(update_types.items(), key=lambda x: -x[1])),
        "path": str(sess_dir),
    }


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(STATIC_DIR), **kwargs)

    def log_message(self, fmt, *args):
        # quieter default
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query)

        if path.startswith("/api/"):
            return self.handle_api(path, qs)

        # SPA fallback
        if path == "/" or not Path(STATIC_DIR / path.lstrip("/")).exists():
            if path != "/" and not path.startswith("/api/"):
                # try static first via parent — only fallback for non-file routes
                candidate = STATIC_DIR / path.lstrip("/")
                if candidate.is_file():
                    return super().do_GET()
            self.path = "/index.html"
        return super().do_GET()

    def send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def handle_api(self, path: str, qs: dict):
        try:
            if path == "/api/health":
                return self.send_json(
                    {
                        "ok": True,
                        "grok_home": str(GROK_HOME),
                        "sessions_dir": str(SESSIONS_DIR),
                        "sessions_exist": SESSIONS_DIR.exists(),
                        "unified_log": str(UNIFIED_LOG),
                        "unified_log_exists": UNIFIED_LOG.exists(),
                    }
                )

            if path == "/api/sessions":
                return self.send_json({"sessions": list_sessions()})

            if path.startswith("/api/session/"):
                parts = path.strip("/").split("/")
                # /api/session/<id>/...
                if len(parts) < 3:
                    return self.send_json({"error": "missing session id"}, 400)
                session_id = parts[2]
                cwd_key = (qs.get("cwd_key") or [None])[0]
                sess_dir = resolve_session(session_id, cwd_key)
                if not sess_dir:
                    return self.send_json({"error": "session not found", "id": session_id}, 404)

                sub = parts[3] if len(parts) > 3 else "overview"
                limit = int((qs.get("limit") or ["5000"])[0])

                if sub == "overview":
                    return self.send_json(session_overview(sess_dir))
                if sub == "timeline":
                    return self.send_json({"timeline": build_timeline(sess_dir, limit=limit)})
                if sub == "chat":
                    return self.send_json({"messages": build_chat_view(sess_dir, limit=limit)})
                if sub == "events":
                    events = list(iter_jsonl(sess_dir / "events.jsonl", max_lines=limit))
                    return self.send_json({"events": events, "count": len(events)})
                if sub == "updates":
                    updates = list(iter_jsonl(sess_dir / "updates.jsonl", max_lines=limit))
                    return self.send_json({"updates": updates, "count": len(updates)})
                if sub == "chat_history":
                    rows = list(iter_jsonl(sess_dir / "chat_history.jsonl", max_lines=limit))
                    return self.send_json({"rows": rows, "count": len(rows)})
                if sub == "file":
                    name = (qs.get("name") or [""])[0]
                    if not name or "/" in name or ".." in name:
                        return self.send_json({"error": "invalid file name"}, 400)
                    fp = sess_dir / name
                    if not fp.is_file():
                        return self.send_json({"error": "file not found"}, 404)
                    text = fp.read_text(encoding="utf-8", errors="replace")
                    if len(text) > 2_000_000:
                        text = text[:2_000_000] + "\n… [truncated]"
                    return self.send_json({"name": name, "content": text, "size": fp.stat().st_size})
                if sub == "raw":
                    name = (qs.get("name") or ["summary.json"])[0]
                    if not name or "/" in name or ".." in name:
                        return self.send_json({"error": "invalid name"}, 400)
                    fp = sess_dir / name
                    if not fp.is_file():
                        return self.send_json({"error": "not found"}, 404)
                    if name.endswith(".json"):
                        return self.send_json(load_json(fp))
                    rows = list(iter_jsonl(fp, max_lines=limit))
                    return self.send_json({"rows": rows, "count": len(rows), "file": name})

                return self.send_json({"error": f"unknown subresource: {sub}"}, 404)

            if path == "/api/logs/unified":
                q = (qs.get("q") or [""])[0]
                msg = (qs.get("msg") or [""])[0]
                src = (qs.get("src") or [""])[0]
                sid = (qs.get("sid") or [""])[0]
                limit = int((qs.get("limit") or ["300"])[0])
                offset = int((qs.get("offset") or ["0"])[0])
                return self.send_json(
                    search_unified_log(q=q, msg=msg, src=src, sid=sid, limit=limit, offset=offset)
                )

            if path == "/api/logs/stats":
                stats = {"path": str(UNIFIED_LOG), "exists": UNIFIED_LOG.exists()}
                if UNIFIED_LOG.exists():
                    stats["size"] = UNIFIED_LOG.stat().st_size
                    msgs: dict[str, int] = {}
                    srcs: dict[str, int] = {}
                    for i, row in enumerate(iter_jsonl(UNIFIED_LOG, max_lines=20000)):
                        if row.get("_parse_error"):
                            continue
                        m = row.get("msg") or "?"
                        s = row.get("src") or "?"
                        msgs[m] = msgs.get(m, 0) + 1
                        srcs[s] = srcs.get(s, 0) + 1
                    stats["top_msgs"] = sorted(msgs.items(), key=lambda x: -x[1])[:40]
                    stats["top_srcs"] = sorted(srcs.items(), key=lambda x: -x[1])[:20]
                    stats["scanned"] = i + 1
                return self.send_json(stats)

            return self.send_json({"error": "not found", "path": path}, 404)
        except Exception as e:
            return self.send_json({"error": str(e), "type": type(e).__name__}, 500)


def find_free_port(host: str, preferred: int, tries: int = 20) -> int:
    """Return preferred port if free, else the next available port."""
    import socket

    for port in range(preferred, preferred + tries):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s.bind((host, port))
                return port
            except OSError:
                continue
    raise OSError(f"No free port in range {preferred}–{preferred + tries - 1}")


class ReuseAddrHTTPServer(ThreadingHTTPServer):
    allow_reuse_address = True


def main():
    parser = argparse.ArgumentParser(description="Grok Trace Viewer")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument(
        "--strict-port",
        action="store_true",
        help="Fail if --port is busy instead of trying the next port",
    )
    parser.add_argument("--no-open", action="store_true", help="Don't open browser")
    parser.add_argument("--grok-home", default=None, help="Override GROK_HOME")
    args = parser.parse_args()

    global GROK_HOME, SESSIONS_DIR, LOGS_DIR, UNIFIED_LOG
    if args.grok_home:
        GROK_HOME = Path(args.grok_home).expanduser()
        SESSIONS_DIR = GROK_HOME / "sessions"
        LOGS_DIR = GROK_HOME / "logs"
        UNIFIED_LOG = LOGS_DIR / "unified.jsonl"

    if not STATIC_DIR.exists():
        print(f"Missing static dir: {STATIC_DIR}", file=sys.stderr)
        sys.exit(1)

    port = args.port
    if args.strict_port:
        try:
            server = ReuseAddrHTTPServer((args.host, port), Handler)
        except OSError as e:
            print(
                f"Port {port} is already in use.\n"
                f"  Stop the other instance:  lsof -ti :{port} | xargs kill\n"
                f"  Or use another port:      python3 server.py --port {port + 1}",
                file=sys.stderr,
            )
            sys.exit(1)
    else:
        try:
            port = find_free_port(args.host, args.port)
        except OSError as e:
            print(str(e), file=sys.stderr)
            sys.exit(1)
        if port != args.port:
            print(f"Port {args.port} busy — using {port} instead.\n")
        server = ReuseAddrHTTPServer((args.host, port), Handler)

    url = f"http://{args.host}:{port}/"
    print(f"Grok Trace Viewer")
    print(f"  URL:        {url}")
    print(f"  GROK_HOME:  {GROK_HOME}")
    print(f"  sessions:   {SESSIONS_DIR} ({'ok' if SESSIONS_DIR.exists() else 'MISSING'})")
    print(f"  logs:       {UNIFIED_LOG} ({'ok' if UNIFIED_LOG.exists() else 'MISSING'})")
    print("  Press Ctrl+C to stop.\n")

    if not args.no_open:
        try:
            webbrowser.open(url)
        except Exception:
            pass

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nBye.")
        server.shutdown()


if __name__ == "__main__":
    main()

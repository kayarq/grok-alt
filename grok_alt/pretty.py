"""Pretty terminal rendering — syntax colors, paths, grep hits, diffs (Grok-TUI parity+)."""

from __future__ import annotations

import json
import re
from pathlib import Path

from rich.console import Group, RenderableType
from rich.syntax import Syntax
from rich.text import Text

from . import themes

# Legacy default; live theme via themes.syntax_theme()
_SYNTAX_THEME = "monokai"
_MAX_SYNTAX_LINES = 120
_MAX_SYNTAX_CHARS = 12000

_EXT_LANG = {
    ".py": "python",
    ".pyi": "python",
    ".js": "javascript",
    ".jsx": "jsx",
    ".ts": "typescript",
    ".tsx": "tsx",
    ".json": "json",
    ".md": "markdown",
    ".markdown": "markdown",
    ".sh": "bash",
    ".bash": "bash",
    ".zsh": "bash",
    ".toml": "toml",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".css": "css",
    ".html": "html",
    ".xml": "xml",
    ".sql": "sql",
    ".rs": "rust",
    ".go": "go",
    ".rb": "ruby",
    ".java": "java",
    ".c": "c",
    ".h": "c",
    ".cpp": "cpp",
    ".hpp": "cpp",
    ".swift": "swift",
    ".kt": "kotlin",
    ".lua": "lua",
    ".diff": "diff",
    ".patch": "diff",
}

_GREP_LINE_RE = re.compile(
    r"^(?P<path>[^:\n]+?)(?::(?P<line>\d+))?(?::(?P<col>\d+))?(?::\s*|\s+)(?P<rest>.*)$"
)
_PATH_IN_TEXT_RE = re.compile(
    r"(~?/?(?:Users|home|tmp|var|opt|System|Library|\.grok|\.local)[^\s\"'<>]+|"
    r"(?:[A-Za-z]:)?(?:/[\w.\-@+]+)+/\S+|"
    r"\./[\w.\-/]+)"
)


def lang_for_path(path: str | None) -> str:
    if not path:
        return "text"
    return _EXT_LANG.get(Path(str(path)).suffix.lower(), "text")


def short_path(path: str | None, max_len: int = 56) -> str:
    if not path:
        return "?"
    p = str(path)
    home = str(Path.home())
    if p.startswith(home):
        p = "~" + p[len(home) :]
    if len(p) <= max_len:
        return p
    return "…" + p[-(max_len - 1) :]


def path_text(path: str | None, *, bold: bool = True) -> Text:
    label = short_path(path, 72)
    return Text(label, style=themes.rich_style("path") if bold else themes.rich_style("path_dim"))


def section_label(name: str) -> Text:
    return Text(f"▸ {name}", style=themes.rich_style("section"))


def render_code(
    code: str,
    *,
    path: str | None = None,
    language: str | None = None,
    line_numbers: bool = True,
    start_line: int = 1,
) -> RenderableType:
    if not code or not str(code).strip():
        return Text("(empty)", style=themes.rich_style("empty"))
    lang = language or lang_for_path(path)
    lines = code.splitlines()
    note = ""
    if len(lines) > _MAX_SYNTAX_LINES:
        code = "\n".join(lines[:_MAX_SYNTAX_LINES])
        note = f"\n… truncated ({len(lines)} lines; showing {_MAX_SYNTAX_LINES})"
    elif len(code) > _MAX_SYNTAX_CHARS:
        code = code[:_MAX_SYNTAX_CHARS] + "\n…"
        note = "\n… truncated (char limit)"
    try:
        syn = Syntax(
            code,
            lang if lang != "text" else "text",
            theme=themes.syntax_theme(),
            line_numbers=line_numbers and lang not in ("text", "markdown"),
            start_line=max(1, int(start_line or 1)),
            word_wrap=True,
            background_color="default",
        )
    except Exception:
        return Text(code + note, style=themes.rich_style("dim"))
    if note:
        return Group(syn, Text(note, style=themes.rich_style("dim") + " italic"))
    return syn


def render_diff(diff_text: str) -> Text:
    out = Text()
    for i, line in enumerate(diff_text.splitlines() or [diff_text]):
        if i:
            out.append("\n")
        if line.startswith("+++ ") or line.startswith("--- "):
            out.append(line, style=themes.rich_style("diff_meta"))
        elif line.startswith("@@"):
            out.append(line, style=themes.rich_style("diff_hunk"))
        elif line.startswith("+") and not line.startswith("+++"):
            out.append(line, style=themes.rich_style("diff_add"))
        elif line.startswith("-") and not line.startswith("---"):
            out.append(line, style=themes.rich_style("diff_del"))
        elif line.startswith("diff ") or line.startswith("index "):
            out.append(line, style=themes.rich_style("diff_file"))
        else:
            out.append(line, style=themes.rich_style("dim"))
    return out


def _append_match_rest(out: Text, rest: str, pat_re: re.Pattern | None) -> None:
    if not pat_re or not rest:
        out.append(rest, style=themes.rich_style("body"))
        return
    pos = 0
    for m in pat_re.finditer(rest):
        if m.start() > pos:
            out.append(rest[pos : m.start()], style=themes.rich_style("body"))
        out.append(m.group(0), style=themes.rich_style("grep_hit"))
        pos = m.end()
    if pos < len(rest):
        out.append(rest[pos:], style=themes.rich_style("body"))


def _append_with_paths(out: Text, line: str, pat_re: re.Pattern | None) -> None:
    last = 0
    for m in _PATH_IN_TEXT_RE.finditer(line):
        if m.start() > last:
            chunk = line[last : m.start()]
            if pat_re:
                _append_match_rest(out, chunk, pat_re)
            else:
                out.append(chunk, style=themes.rich_style("dim"))
        out.append(short_path(m.group(0), 60), style=themes.rich_style("path_dim"))
        last = m.end()
    tail = line[last:]
    if pat_re and tail:
        _append_match_rest(out, tail, pat_re)
    elif tail:
        out.append(tail, style=themes.rich_style("dim"))


def render_grep_output(text: str, *, pattern: str | None = None) -> Text:
    out = Text()
    pat_re = None
    if pattern:
        try:
            pat_re = re.compile(re.escape(pattern), re.I)
        except re.error:
            pat_re = None
    for i, line in enumerate(text.splitlines() or [text]):
        if i:
            out.append("\n")
        if "workspace_result" in line or (line.strip().startswith("<") and line.strip().endswith(">")):
            out.append(line, style=themes.rich_style("dim"))
            continue
        if "No matches found" in line:
            out.append(line, style=themes.rich_style("grep_warn"))
            continue
        if line.strip().startswith("Found "):
            out.append(line, style=themes.rich_style("diff_add"))
            continue
        m = _GREP_LINE_RE.match(line)
        path = (m.group("path") if m else "") or ""
        if m and ("/" in path or path.startswith("~") or path.startswith(".")):
            out.append(short_path(path, 50), style=themes.rich_style("grep_path"))
            ln = m.group("line")
            if ln:
                out.append(":", style=themes.rich_style("dim"))
                out.append(ln, style=themes.rich_style("grep_line"))
            out.append(":", style=themes.rich_style("dim"))
            out.append(" ")
            _append_match_rest(out, m.group("rest") or "", pat_re)
        else:
            _append_with_paths(out, line, pat_re)
    return out


def render_shell_output(text: str) -> Text:
    out = Text()
    for i, line in enumerate(text.splitlines() or [text]):
        if i:
            out.append("\n")
        low = line.lower()
        if "error" in low or "traceback" in low or "failed" in low:
            out.append(line, style=themes.rich_style("diff_del"))
        elif "warning" in low:
            out.append(line, style=themes.rich_style("grep_warn"))
        elif line.startswith("$") or line.startswith("# "):
            out.append(line, style=themes.rich_style("diff_file"))
        else:
            _append_with_paths(out, line, None)
    return out


def render_meta_kv(text: str) -> Text:
    if ":" in text and len(text) < 240:
        k, _, v = text.partition(":")
        ks, vs = k.strip(), v.strip()
        if ks and not ks.startswith("/") and "/" not in ks.split()[0]:
            if "/" in vs or vs.startswith("~") or vs.startswith("./"):
                return Text.assemble((ks, themes.rich_style("meta_key")), (": ", themes.rich_style("dim")), path_text(vs, bold=False))
            return Text.assemble((ks, themes.rich_style("meta_key")), (":", themes.rich_style("dim")), (v, themes.rich_style("meta_val")))
    t = Text()
    _append_with_paths(t, text, None)
    return t


def render_command(cmd: str) -> Text:
    return Text.assemble(("$ ", themes.rich_style("cmd")), (cmd, themes.rich_style("cmd_body")))


def render_section_body(style: str, body: str, *, meta: dict | None = None) -> RenderableType:
    meta = meta or {}
    if not body and style != "meta":
        return Text("(empty)", style=themes.rich_style("empty"))
    if style == "diff":
        return render_diff(body)
    if style in ("grep", "search"):
        return render_grep_output(body, pattern=meta.get("pattern"))
    if style == "code":
        path = meta.get("path")
        lang = meta.get("language")
        if path or lang:
            return render_code(
                body,
                path=path,
                language=lang,
                line_numbers=meta.get("line_numbers", True),
                start_line=int(meta.get("start_line") or 1),
            )
        guess = "json" if body.lstrip().startswith(("{", "[")) else "text"
        return render_code(body, language=guess, line_numbers=False)
    if style == "cmd":
        return render_command(body)
    if style == "err":
        return Text(body, style=themes.rich_style("err"))
    if style == "meta":
        return render_meta_kv(body)
    if style in ("stdout", "shell"):
        return render_shell_output(body)
    if style == "dim":
        t = Text(body, style="dim")
        return t
    t = Text()
    _append_with_paths(t, body, None)
    return t


def render_tool_detail(tool_msg: dict) -> RenderableType:
    parts: list[RenderableType] = []
    summary = str(tool_msg.get("summary") or "")
    if summary:
        parts.append(Text(summary, style=themes.rich_style("section")))

    sections = tool_msg.get("sections") or []
    if not sections and tool_msg.get("content") is not None:
        content = tool_msg.get("content")
        if not isinstance(content, str):
            content = json.dumps(content, ensure_ascii=False, indent=2)
        parts.append(render_section_body("code", content[:4000], meta={"language": "json"}))
        return Group(*parts) if len(parts) > 1 else (parts[0] if parts else Text("(empty)", style="dim"))

    for sec in sections:
        heading = sec.get("heading") or ""
        body = sec.get("body") or ""
        style = sec.get("style") or "code"
        meta = dict(sec.get("meta") or {})
        if heading:
            parts.append(section_label(heading))
        eff = style
        if heading == "matches":
            eff = "grep"
        elif heading == "contents":
            eff = "code"
        elif heading == "stdout":
            eff = "shell"
        elif heading == "stderr":
            eff = "err"
        elif heading == "command":
            eff = "cmd"
        elif heading == "diff":
            eff = "diff"
        elif heading in ("file", "dir", "pattern", "scope", "exit", "stats", "mode", "why"):
            eff = "meta" if heading != "why" else "dim"
        parts.append(render_section_body(eff, body, meta=meta))

    if not parts:
        return Text("(no extra detail)", style="dim")
    return Group(*parts)


def render_agent_message(text: str) -> RenderableType:
    if not text:
        return Text("", style=themes.rich_style("dim"))
    fence_re = re.compile(r"```(\w+)?\n(.*?)```", re.S)
    parts: list[RenderableType] = []
    pos = 0
    for m in fence_re.finditer(text):
        if m.start() > pos:
            parts.append(Text(text[pos : m.start()], style=themes.rich_style("agent_body")))
        lang = (m.group(1) or "text").strip()
        parts.append(render_code((m.group(2) or "").rstrip("\n"), language=lang, line_numbers=False))
        pos = m.end()
    if pos < len(text):
        parts.append(Text(text[pos:], style=themes.rich_style("agent_body")))
    if not parts:
        return Text(text, style=themes.rich_style("agent_body"))
    return parts[0] if len(parts) == 1 else Group(*parts)


def render_user_message(text: str, *, num: int, total: int) -> RenderableType:
    head = Text.assemble(
        ("══ USER ", themes.rich_style("user_head")),
        (f"#{num}", themes.rich_style("user_head")),
        (" ══", themes.rich_style("user_head")),
        (f"  prompt {num}/{total}", themes.rich_style("dim")),
    )
    return Group(head, Text(text or "", style=themes.rich_style("user_body")))


def render_agent_header() -> Text:
    return Text("══ AGENT ══", style=themes.rich_style("agent_head"))

"""UI themes for grok-alt TUI. Cycle with ``m`` or set GROK_ALT_THEME=night|day|indigo."""

from __future__ import annotations

import os
from pathlib import Path

THEME_IDS = ("night", "day", "indigo")
THEME_LABELS = {
    "night": "Night (default dark)",
    "day": "Day (soft light)",
    "indigo": "Indigo / forest",
}

# Shared geometry (no palette)
_LAYOUT = """
Screen { width: 100%; height: 100%; }

#sidebar {
    width: 30%;
    min-width: 18;
    max-width: 36;
}

#main {
    width: 1fr;
    min-width: 20;
    overflow-x: auto;
}

#session-filter { margin: 0 1; dock: top; }
#session-list { height: 1fr; }
ListItem { padding: 0 1; }

#status-line { dock: bottom; height: 1; padding: 0 1; }

TabbedContent { height: 1fr; width: 100%; }
TabPane { width: 100%; height: 1fr; }

RichLog {
    height: 1fr;
    width: 100%;
    min-width: 1;
    border: none;
    overflow-x: auto;
}

#chat-pane { height: 1fr; width: 100%; }
#prompt-nav-wrap {
    height: 14;
    min-height: 8;
    max-height: 18;
    width: 100%;
    layout: vertical;
}
#prompt-nav-header { height: 1; padding: 0 1; dock: top; }
#prompt-nav { height: 1fr; min-height: 6; overflow-y: auto; }
#prompt-nav ListItem { padding: 0 1; height: 2; }

#chat-toolbar {
    height: auto;
    min-height: 3;
    max-height: 5;
    width: 100%;
    padding: 0 1;
    overflow-x: auto;
}
#chat-toolbar Button { margin: 0 1 0 0; min-width: 12; max-width: 22; }
#chat-toolbar-hint { padding: 0 1; width: 1fr; min-width: 0; }

#chat-stream {
    height: 1fr;
    width: 100%;
    min-width: 1;
    padding: 0 1 1 1;
    overflow-x: hidden;
    overflow-y: auto;
}
#chat-stream .chat-block {
    width: 100%;
    max-width: 100%;
    margin: 0 0 1 0;
    padding: 0 1;
}
#chat-stream .chat-user {
    width: 100%;
    padding: 0 1;
    margin-bottom: 1;
}
#chat-stream .chat-agent {
    width: 100%;
    padding: 0 1;
    margin-bottom: 1;
}
#chat-stream .chat-system { width: 100%; margin: 0 0 1 0; }
#chat-stream Collapsible {
    width: 100%;
    max-width: 100%;
    margin: 0 0 1 0;
    padding: 0;
}
#chat-stream CollapsibleTitle {
    width: 100%;
    max-width: 100%;
    overflow: hidden;
}
#chat-stream .tool-body {
    width: 100%;
    max-width: 100%;
    padding: 0 1 1 2;
}
#chat-stream .chat-footer { width: 100%; margin-top: 1; }

#diffs-pane { height: 1fr; width: 100%; }
#diff-files-wrap { width: 32%; min-width: 16; max-width: 42; }
#diff-files-header { height: 1; padding: 0 1; }
#diff-file-list { height: 1fr; }
#diff-file-list ListItem { padding: 0 1; height: 3; }
#diff-detail-wrap { width: 1fr; min-width: 20; }
#diff-detail-header {
    height: auto;
    min-height: 2;
    max-height: 4;
    padding: 0 1;
}
#diff-detail-scroll {
    height: 1fr;
    width: 100%;
    padding: 0 1 1 1;
}
#diff-detail-body { width: 100%; }

#help-dialog {
    width: 72;
    height: auto;
    max-height: 90%;
    padding: 1 2;
}
#help-title { margin-bottom: 1; }
"""

# Night — current GitHub-dark look (default)
_NIGHT = """
Screen.theme-night { background: #0d1117; color: #e6edf3; }
Screen.theme-night #sidebar { background: #161b22; border-right: solid #30363d; }
Screen.theme-night ListView { background: #161b22; }
Screen.theme-night ListItem.--highlight { background: #1c2d41; }
Screen.theme-night #status-line { background: #161b22; color: #8b949e; }
Screen.theme-night RichLog {
    background: #0d1117;
    color: #e6edf3;
    scrollbar-background: #161b22;
    scrollbar-color: #30363d;
}
Screen.theme-night #prompt-nav-wrap { background: #161b22; border-bottom: solid #30363d; }
Screen.theme-night #prompt-nav-header { color: #8b949e; background: #21262d; }
Screen.theme-night #prompt-nav { background: #161b22; scrollbar-background: #161b22; scrollbar-color: #30363d; }
Screen.theme-night #prompt-nav ListItem.--highlight { background: #238636; }
Screen.theme-night #chat-toolbar { background: #21262d; border-bottom: solid #30363d; }
Screen.theme-night #chat-toolbar-hint { color: #8b949e; }
Screen.theme-night #chat-stream {
    background: #0d1117;
    scrollbar-background: #161b22;
    scrollbar-color: #30363d;
}
Screen.theme-night #chat-stream .chat-user { background: #12261e; border-left: solid #3fb950; }
Screen.theme-night #chat-stream .chat-agent { background: #0d1b2a; border-left: solid #58a6ff; }
Screen.theme-night #chat-stream .chat-system { color: #8b949e; }
Screen.theme-night #chat-stream Collapsible { background: #161b22; border-left: solid #d29922; }
Screen.theme-night #chat-stream CollapsibleTitle { background: #21262d; color: #e6edf3; }
Screen.theme-night #chat-stream CollapsibleTitle:hover { background: #30363d; color: #f0e68c; }
Screen.theme-night #chat-stream .tool-body { background: #0d1117; }
Screen.theme-night #chat-stream .chat-footer { color: #8b949e; }
Screen.theme-night #diff-files-wrap { background: #161b22; border-right: solid #30363d; }
Screen.theme-night #diff-files-header { color: #8b949e; background: #21262d; }
Screen.theme-night #diff-file-list { background: #161b22; }
Screen.theme-night #diff-file-list ListItem.--highlight { background: #1f3d2a; }
Screen.theme-night #diff-detail-wrap { background: #0d1117; }
Screen.theme-night #diff-detail-header {
    color: #e6edf3;
    background: #21262d;
    border-bottom: solid #30363d;
}
Screen.theme-night #diff-detail-scroll { background: #0d1117; }
Screen.theme-night #help-dialog { background: #161b22; border: solid #58a6ff; }
Screen.theme-night #help-title { color: #58a6ff; }
Screen.theme-night #help-body { color: #e6edf3; }
"""

# Day — soft off-white / paper
_DAY = """
Screen.theme-day { background: #f4f1ea; color: #1c1917; }
Screen.theme-day #sidebar { background: #ebe6dc; border-right: solid #d6d0c4; }
Screen.theme-day ListView { background: #ebe6dc; }
Screen.theme-day ListItem.--highlight { background: #d4e4f7; }
Screen.theme-day #status-line { background: #e5dfd3; color: #57534e; }
Screen.theme-day RichLog {
    background: #faf8f4;
    color: #1c1917;
    scrollbar-background: #e5dfd3;
    scrollbar-color: #a8a29e;
}
Screen.theme-day #prompt-nav-wrap { background: #ebe6dc; border-bottom: solid #d6d0c4; }
Screen.theme-day #prompt-nav-header { color: #57534e; background: #e0d9cc; }
Screen.theme-day #prompt-nav { background: #ebe6dc; scrollbar-background: #e5dfd3; scrollbar-color: #a8a29e; }
Screen.theme-day #prompt-nav ListItem.--highlight { background: #bbf7d0; }
Screen.theme-day #chat-toolbar { background: #e0d9cc; border-bottom: solid #d6d0c4; }
Screen.theme-day #chat-toolbar-hint { color: #57534e; }
Screen.theme-day #chat-stream {
    background: #faf8f4;
    scrollbar-background: #e5dfd3;
    scrollbar-color: #a8a29e;
}
Screen.theme-day #chat-stream .chat-user { background: #dcfce7; border-left: solid #16a34a; }
Screen.theme-day #chat-stream .chat-agent { background: #dbeafe; border-left: solid #2563eb; }
Screen.theme-day #chat-stream .chat-system { color: #78716c; }
Screen.theme-day #chat-stream Collapsible { background: #ebe6dc; border-left: solid #ca8a04; }
Screen.theme-day #chat-stream CollapsibleTitle { background: #e0d9cc; color: #1c1917; }
Screen.theme-day #chat-stream CollapsibleTitle:hover { background: #d6d0c4; color: #854d0e; }
Screen.theme-day #chat-stream .tool-body { background: #faf8f4; }
Screen.theme-day #chat-stream .chat-footer { color: #78716c; }
Screen.theme-day #diff-files-wrap { background: #ebe6dc; border-right: solid #d6d0c4; }
Screen.theme-day #diff-files-header { color: #57534e; background: #e0d9cc; }
Screen.theme-day #diff-file-list { background: #ebe6dc; }
Screen.theme-day #diff-file-list ListItem.--highlight { background: #bbf7d0; }
Screen.theme-day #diff-detail-wrap { background: #faf8f4; }
Screen.theme-day #diff-detail-header {
    color: #1c1917;
    background: #e0d9cc;
    border-bottom: solid #d6d0c4;
}
Screen.theme-day #diff-detail-scroll { background: #faf8f4; }
Screen.theme-day #help-dialog { background: #faf8f4; border: solid #2563eb; }
Screen.theme-day #help-title { color: #1d4ed8; }
Screen.theme-day #help-body { color: #1c1917; }
"""

# Indigo + dark green (teal forest accents on deep indigo base)
_INDIGO = """
Screen.theme-indigo { background: #0c1222; color: #e2e8f0; }
Screen.theme-indigo #sidebar { background: #111827; border-right: solid #1e3a5f; }
Screen.theme-indigo ListView { background: #111827; }
Screen.theme-indigo ListItem.--highlight { background: #1e3a5f; }
Screen.theme-indigo #status-line { background: #0f172a; color: #94a3b8; }
Screen.theme-indigo RichLog {
    background: #0c1222;
    color: #e2e8f0;
    scrollbar-background: #111827;
    scrollbar-color: #334155;
}
Screen.theme-indigo #prompt-nav-wrap { background: #111827; border-bottom: solid #1e3a5f; }
Screen.theme-indigo #prompt-nav-header { color: #94a3b8; background: #0f172a; }
Screen.theme-indigo #prompt-nav { background: #111827; scrollbar-background: #111827; scrollbar-color: #334155; }
Screen.theme-indigo #prompt-nav ListItem.--highlight { background: #065f46; }
Screen.theme-indigo #chat-toolbar { background: #0f172a; border-bottom: solid #1e3a5f; }
Screen.theme-indigo #chat-toolbar-hint { color: #94a3b8; }
Screen.theme-indigo #chat-stream {
    background: #0c1222;
    scrollbar-background: #111827;
    scrollbar-color: #334155;
}
Screen.theme-indigo #chat-stream .chat-user { background: #052e1c; border-left: solid #34d399; }
Screen.theme-indigo #chat-stream .chat-agent { background: #1e1b4b; border-left: solid #818cf8; }
Screen.theme-indigo #chat-stream .chat-system { color: #94a3b8; }
Screen.theme-indigo #chat-stream Collapsible { background: #111827; border-left: solid #2dd4bf; }
Screen.theme-indigo #chat-stream CollapsibleTitle { background: #0f172a; color: #e2e8f0; }
Screen.theme-indigo #chat-stream CollapsibleTitle:hover { background: #1e3a5f; color: #5eead4; }
Screen.theme-indigo #chat-stream .tool-body { background: #0c1222; }
Screen.theme-indigo #chat-stream .chat-footer { color: #94a3b8; }
Screen.theme-indigo #diff-files-wrap { background: #111827; border-right: solid #1e3a5f; }
Screen.theme-indigo #diff-files-header { color: #94a3b8; background: #0f172a; }
Screen.theme-indigo #diff-file-list { background: #111827; }
Screen.theme-indigo #diff-file-list ListItem.--highlight { background: #064e3b; }
Screen.theme-indigo #diff-detail-wrap { background: #0c1222; }
Screen.theme-indigo #diff-detail-header {
    color: #e2e8f0;
    background: #0f172a;
    border-bottom: solid #1e3a5f;
}
Screen.theme-indigo #diff-detail-scroll { background: #0c1222; }
Screen.theme-indigo #help-dialog { background: #111827; border: solid #818cf8; }
Screen.theme-indigo #help-title { color: #a5b4fc; }
Screen.theme-indigo #help-body { color: #e2e8f0; }
"""

APP_CSS = _LAYOUT + _NIGHT + _DAY + _INDIGO


def config_path() -> Path:
    xdg = os.environ.get("XDG_CONFIG_HOME")
    if xdg:
        return Path(xdg) / "grok-alt" / "theme"
    return Path.home() / ".config" / "grok-alt" / "theme"


def normalize_theme(name: str | None) -> str:
    n = (name or "").strip().lower()
    aliases = {
        "default": "night",
        "dark": "night",
        "light": "day",
        "white": "day",
        "forest": "indigo",
        "teal": "indigo",
        "green": "indigo",
    }
    n = aliases.get(n, n)
    if n in THEME_IDS:
        return n
    return "night"


def load_theme() -> str:
    env = os.environ.get("GROK_ALT_THEME")
    if env:
        return normalize_theme(env)
    path = config_path()
    try:
        if path.is_file():
            return normalize_theme(path.read_text(encoding="utf-8").strip())
    except OSError:
        pass
    return "night"


def save_theme(name: str) -> None:
    name = normalize_theme(name)
    path = config_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(name + "\n", encoding="utf-8")
    except OSError:
        pass


def next_theme(current: str) -> str:
    cur = normalize_theme(current)
    i = THEME_IDS.index(cur) if cur in THEME_IDS else 0
    return THEME_IDS[(i + 1) % len(THEME_IDS)]


def theme_class(name: str) -> str:
    return f"theme-{normalize_theme(name)}"

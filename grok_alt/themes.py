"""UI themes for grok-alt TUI. Cycle with ``m`` or set GROK_ALT_THEME=night|day|indigo.

Covers chrome (sidebar, tabs, inputs, logs, chat panes) plus semantic Rich styles
used by ``pretty`` so body text is not stuck on grey/white across themes.
"""

from __future__ import annotations

import os
from pathlib import Path

THEME_IDS = ("night", "day", "indigo")
THEME_LABELS = {
    "night": "Night (slate dark)",
    "day": "Day (soft light)",
    "indigo": "Indigo / forest",
}

# Rich / timeline markup styles per theme (semantic roles — not generic white/grey)
RICH_STYLES: dict[str, dict[str, str]] = {
    "night": {
        "path": "bold bright_cyan",
        "path_dim": "cyan",
        "section": "bold bright_yellow",
        "meta_key": "bold bright_blue",
        "meta_val": "bright_white",
        "body": "bright_white",
        "dim": "grey70",
        "user_head": "bold bright_green",
        "user_body": "bright_white",
        "agent_head": "bold bright_cyan",
        "agent_body": "bright_white",
        "cmd": "bold bright_green",
        "cmd_body": "bright_white",
        "diff_meta": "bold bright_white",
        "diff_hunk": "bold bright_cyan",
        "diff_add": "bright_green",
        "diff_del": "bright_red",
        "diff_file": "bold magenta",
        "grep_path": "bold bright_cyan",
        "grep_line": "bold bright_yellow",
        "grep_hit": "black on bright_yellow",
        "grep_ok": "bright_green",
        "grep_warn": "bright_yellow",
        "err": "bold bright_red",
        "warn": "bright_yellow",
        "shell_ok": "bright_white",
        "empty": "grey50",
        "syntax": "monokai",
        # RichLog / timeline (Textual markup tags)
        "tl_time": "dim cyan",
        "tl_turn": "green",
        "tl_tool": "yellow",
        "tl_user": "bright_green",
        "tl_agent": "cyan",
        "tl_perm": "red",
        "tl_stream": "magenta",
        "tl_meta": "blue",
        "tl_other": "white",
        "tl_detail": "grey70",
        "ov_key": "bold cyan",
        "ov_val": "white",
        "log_src": "magenta",
        "log_msg": "cyan",
        "sess_title": "bold white",
        "sess_meta": "dim",
        "prompt_num": "bold bright_green",
        "prompt_meta": "dim",
        "diff_list_path": "bold cyan",
        "diff_list_meta": "dim",
        "footer": "dim",
    },
    "day": {
        "path": "bold dark_blue",
        "path_dim": "blue",
        "section": "bold dark_orange3",
        "meta_key": "bold dark_blue",
        "meta_val": "grey19",
        "body": "grey11",
        "dim": "grey42",
        "user_head": "bold dark_green",
        "user_body": "grey11",
        "agent_head": "bold blue",
        "agent_body": "grey11",
        "cmd": "bold dark_green",
        "cmd_body": "grey11",
        "diff_meta": "bold grey19",
        "diff_hunk": "bold blue",
        "diff_add": "dark_green",
        "diff_del": "dark_red",
        "diff_file": "bold purple",
        "grep_path": "bold dark_blue",
        "grep_line": "bold dark_orange3",
        "grep_hit": "black on yellow",
        "grep_ok": "dark_green",
        "grep_warn": "dark_orange3",
        "err": "bold dark_red",
        "warn": "dark_orange3",
        "shell_ok": "grey11",
        "empty": "grey50",
        "syntax": "default",
        "tl_time": "dim blue",
        "tl_turn": "dark_green",
        "tl_tool": "dark_orange3",
        "tl_user": "dark_green",
        "tl_agent": "blue",
        "tl_perm": "dark_red",
        "tl_stream": "purple",
        "tl_meta": "dark_blue",
        "tl_other": "grey19",
        "tl_detail": "grey42",
        "ov_key": "bold blue",
        "ov_val": "grey11",
        "log_src": "purple",
        "log_msg": "dark_blue",
        "sess_title": "bold grey11",
        "sess_meta": "dim",
        "prompt_num": "bold dark_green",
        "prompt_meta": "dim",
        "diff_list_path": "bold dark_blue",
        "diff_list_meta": "dim",
        "footer": "dim",
    },
    "indigo": {
        "path": "bold bright_cyan",
        "path_dim": "cyan",
        "section": "bold bright_green",
        "meta_key": "bold #a5b4fc",
        "meta_val": "#e0e7ff",
        "body": "#e2e8f0",
        "dim": "#94a3b8",
        "user_head": "bold #34d399",
        "user_body": "#ecfdf5",
        "agent_head": "bold #a5b4fc",
        "agent_body": "#e0e7ff",
        "cmd": "bold #2dd4bf",
        "cmd_body": "#f0fdfa",
        "diff_meta": "bold #e2e8f0",
        "diff_hunk": "bold #818cf8",
        "diff_add": "#4ade80",
        "diff_del": "#f87171",
        "diff_file": "bold #c084fc",
        "grep_path": "bold #67e8f9",
        "grep_line": "bold #fbbf24",
        "grep_hit": "black on #fde047",
        "grep_ok": "#4ade80",
        "grep_warn": "#fbbf24",
        "err": "bold #f87171",
        "warn": "#fbbf24",
        "shell_ok": "#e2e8f0",
        "empty": "#64748b",
        "syntax": "dracula",
        "tl_time": "dim #67e8f9",
        "tl_turn": "#34d399",
        "tl_tool": "#fbbf24",
        "tl_user": "#4ade80",
        "tl_agent": "#818cf8",
        "tl_perm": "#f87171",
        "tl_stream": "#c084fc",
        "tl_meta": "#67e8f9",
        "tl_other": "#cbd5e1",
        "tl_detail": "#94a3b8",
        "ov_key": "bold #a5b4fc",
        "ov_val": "#e2e8f0",
        "log_src": "#c084fc",
        "log_msg": "#67e8f9",
        "sess_title": "bold #e0e7ff",
        "sess_meta": "dim",
        "prompt_num": "bold #34d399",
        "prompt_meta": "dim",
        "diff_list_path": "bold #67e8f9",
        "diff_list_meta": "dim",
        "footer": "dim",
    },
}

_LAYOUT = """
Screen { width: 100%; height: 100%; }

#sidebar { width: 30%; min-width: 18; max-width: 36; }
#main { width: 1fr; min-width: 20; overflow-x: auto; }
#session-filter { margin: 0 1; dock: top; }
#session-list { height: 1fr; }
ListItem { padding: 0 1; }
#status-line { dock: bottom; height: 1; padding: 0 1; }
TabbedContent { height: 1fr; width: 100%; }
TabPane { width: 100%; height: 1fr; }
RichLog { height: 1fr; width: 100%; min-width: 1; border: none; overflow-x: auto; }
#chat-pane { height: 1fr; width: 100%; }
#prompt-nav-wrap { height: 14; min-height: 8; max-height: 18; width: 100%; layout: vertical; }
#prompt-nav-header { height: 1; padding: 0 1; dock: top; }
#prompt-nav { height: 1fr; min-height: 6; overflow-y: auto; }
#prompt-nav ListItem { padding: 0 1; height: 2; }
#chat-toolbar { height: auto; min-height: 3; max-height: 5; width: 100%; padding: 0 1; overflow-x: auto; }
#chat-toolbar Button { margin: 0 1 0 0; min-width: 12; max-width: 22; }
#chat-toolbar-hint { padding: 0 1; width: 1fr; min-width: 0; }
#chat-stream { height: 1fr; width: 100%; min-width: 1; padding: 0 1 1 1; overflow-x: hidden; overflow-y: auto; }
#chat-stream .chat-block { width: 100%; max-width: 100%; margin: 0 0 1 0; padding: 0 1; }
#chat-stream .chat-user { width: 100%; padding: 0 1; margin-bottom: 1; }
#chat-stream .chat-agent { width: 100%; padding: 0 1; margin-bottom: 1; }
#chat-stream .chat-system { width: 100%; margin: 0 0 1 0; }
#chat-stream Collapsible { width: 100%; max-width: 100%; margin: 0 0 1 0; padding: 0; }
#chat-stream CollapsibleTitle { width: 100%; max-width: 100%; overflow: hidden; }
#chat-stream .tool-body { width: 100%; max-width: 100%; padding: 0 1 1 2; }
#chat-stream .chat-footer { width: 100%; margin-top: 1; }
#diffs-pane { height: 1fr; width: 100%; }
#diff-files-wrap { width: 32%; min-width: 16; max-width: 42; }
#diff-files-header { height: 1; padding: 0 1; }
#diff-file-list { height: 1fr; }
#diff-file-list ListItem { padding: 0 1; height: 3; }
#diff-detail-wrap { width: 1fr; min-width: 20; }
#diff-detail-header { height: auto; min-height: 2; max-height: 4; padding: 0 1; }
#diff-detail-scroll { height: 1fr; width: 100%; padding: 0 1 1 1; }
#diff-detail-body { width: 100%; }
#help-dialog { width: 72; height: auto; max-height: 90%; padding: 1 2; }
#help-title { margin-bottom: 1; }
Header { dock: top; }
Footer { dock: bottom; }
"""

# Night: cool slate — blue sidebar vs charcoal main (clearly distinct from indigo)
_NIGHT = """
Screen.theme-night { background: #0d1117; color: #e6edf3; }
Screen.theme-night Header { background: #010409; color: #58a6ff; text-style: bold; }
Screen.theme-night Footer { background: #010409; color: #8b949e; }
Screen.theme-night #sidebar { background: #161b22; border-right: solid #388bfd; }
Screen.theme-night #main { background: #0d1117; }
Screen.theme-night Input { background: #21262d; color: #e6edf3; border: tall #388bfd; }
Screen.theme-night Input:focus { border: tall #58a6ff; }
Screen.theme-night ListView { background: #161b22; color: #c9d1d9; }
Screen.theme-night ListItem.--highlight { background: #1f6feb; color: #ffffff; }
Screen.theme-night #status-line { background: #161b22; color: #79c0ff; border-top: solid #30363d; }
Screen.theme-night Tabs { background: #161b22; }
Screen.theme-night Tab { color: #8b949e; }
Screen.theme-night Tab.-active { color: #58a6ff; text-style: bold; background: #0d1117; }
Screen.theme-night Underline { background: #388bfd; }
Screen.theme-night Button { background: #21262d; color: #58a6ff; border: tall #388bfd; }
Screen.theme-night Button.-primary { background: #1f6feb; color: #ffffff; }
Screen.theme-night Button:hover { background: #30363d; }
Screen.theme-night RichLog { background: #0d1117; color: #c9d1d9; scrollbar-background: #161b22; scrollbar-color: #388bfd; }
Screen.theme-night #prompt-nav-wrap { background: #161b22; border-bottom: solid #388bfd; }
Screen.theme-night #prompt-nav-header { color: #79c0ff; background: #0d419d; text-style: bold; }
Screen.theme-night #prompt-nav { background: #0d1117; scrollbar-background: #161b22; scrollbar-color: #388bfd; }
Screen.theme-night #prompt-nav ListItem.--highlight { background: #238636; color: #ffffff; }
Screen.theme-night #chat-toolbar { background: #161b22; border-bottom: solid #30363d; }
Screen.theme-night #chat-toolbar-hint { color: #8b949e; }
Screen.theme-night #chat-stream { background: #010409; scrollbar-background: #161b22; scrollbar-color: #388bfd; }
Screen.theme-night #chat-stream .chat-user { background: #033a16; border-left: solid #3fb950; color: #aff5b4; }
Screen.theme-night #chat-stream .chat-agent { background: #0c2d6b; border-left: solid #58a6ff; color: #a5d6ff; }
Screen.theme-night #chat-stream .chat-system { color: #d2a8ff; }
Screen.theme-night #chat-stream Collapsible { background: #161b22; border-left: solid #d29922; }
Screen.theme-night #chat-stream CollapsibleTitle { background: #9e6a03; color: #ffffff; text-style: bold; }
Screen.theme-night #chat-stream CollapsibleTitle:hover { background: #bb8009; color: #fff8c5; }
Screen.theme-night #chat-stream .tool-body { background: #0d1117; color: #e6edf3; }
Screen.theme-night #chat-stream .chat-footer { color: #8b949e; }
Screen.theme-night #diff-files-wrap { background: #161b22; border-right: solid #3fb950; }
Screen.theme-night #diff-files-header { color: #3fb950; background: #033a16; text-style: bold; }
Screen.theme-night #diff-file-list { background: #0d1117; }
Screen.theme-night #diff-file-list ListItem.--highlight { background: #238636; color: #ffffff; }
Screen.theme-night #diff-detail-wrap { background: #010409; }
Screen.theme-night #diff-detail-header { color: #ffa657; background: #3d2000; border-bottom: solid #d29922; text-style: bold; }
Screen.theme-night #diff-detail-scroll { background: #0d1117; }
Screen.theme-night #help-dialog { background: #161b22; border: solid #58a6ff; }
Screen.theme-night #help-title { color: #58a6ff; text-style: bold; }
Screen.theme-night #help-body { color: #c9d1d9; }
"""

# Day: warm paper — cream main, sage sidebar, colored accents
_DAY = """
Screen.theme-day { background: #f7f3eb; color: #1c1917; }
Screen.theme-day Header { background: #e8e0d0; color: #1d4ed8; text-style: bold; }
Screen.theme-day Footer { background: #e8e0d0; color: #57534e; }
Screen.theme-day #sidebar { background: #e4efe6; border-right: solid #16a34a; }
Screen.theme-day #main { background: #f7f3eb; }
Screen.theme-day Input { background: #ffffff; color: #1c1917; border: tall #2563eb; }
Screen.theme-day Input:focus { border: tall #1d4ed8; background: #eff6ff; }
Screen.theme-day ListView { background: #e4efe6; color: #1c1917; }
Screen.theme-day ListItem.--highlight { background: #bfdbfe; color: #1e3a8a; text-style: bold; }
Screen.theme-day #status-line { background: #fde68a; color: #78350f; border-top: solid #ca8a04; text-style: bold; }
Screen.theme-day Tabs { background: #e8e0d0; }
Screen.theme-day Tab { color: #57534e; }
Screen.theme-day Tab.-active { color: #1d4ed8; text-style: bold; background: #f7f3eb; }
Screen.theme-day Underline { background: #2563eb; }
Screen.theme-day Button { background: #ffffff; color: #1d4ed8; border: tall #2563eb; }
Screen.theme-day Button.-primary { background: #2563eb; color: #ffffff; }
Screen.theme-day Button:hover { background: #dbeafe; }
Screen.theme-day RichLog { background: #fffef9; color: #1c1917; scrollbar-background: #e8e0d0; scrollbar-color: #2563eb; }
Screen.theme-day #prompt-nav-wrap { background: #dcfce7; border-bottom: solid #16a34a; }
Screen.theme-day #prompt-nav-header { color: #14532d; background: #86efac; text-style: bold; }
Screen.theme-day #prompt-nav { background: #f0fdf4; scrollbar-background: #dcfce7; scrollbar-color: #16a34a; }
Screen.theme-day #prompt-nav ListItem.--highlight { background: #22c55e; color: #052e16; text-style: bold; }
Screen.theme-day #chat-toolbar { background: #e0e7ff; border-bottom: solid #6366f1; }
Screen.theme-day #chat-toolbar-hint { color: #4338ca; }
Screen.theme-day #chat-stream { background: #fffef9; scrollbar-background: #e8e0d0; scrollbar-color: #ca8a04; }
Screen.theme-day #chat-stream .chat-user { background: #dcfce7; border-left: solid #16a34a; color: #14532d; }
Screen.theme-day #chat-stream .chat-agent { background: #dbeafe; border-left: solid #2563eb; color: #1e3a8a; }
Screen.theme-day #chat-stream .chat-system { color: #7c3aed; }
Screen.theme-day #chat-stream Collapsible { background: #fef3c7; border-left: solid #d97706; }
Screen.theme-day #chat-stream CollapsibleTitle { background: #f59e0b; color: #1c1917; text-style: bold; }
Screen.theme-day #chat-stream CollapsibleTitle:hover { background: #d97706; color: #ffffff; }
Screen.theme-day #chat-stream .tool-body { background: #fffbeb; color: #1c1917; }
Screen.theme-day #chat-stream .chat-footer { color: #78716c; }
Screen.theme-day #diff-files-wrap { background: #ecfdf5; border-right: solid #059669; }
Screen.theme-day #diff-files-header { color: #064e3b; background: #6ee7b7; text-style: bold; }
Screen.theme-day #diff-file-list { background: #f0fdf4; }
Screen.theme-day #diff-file-list ListItem.--highlight { background: #10b981; color: #022c22; text-style: bold; }
Screen.theme-day #diff-detail-wrap { background: #fffef9; }
Screen.theme-day #diff-detail-header { color: #9a3412; background: #fed7aa; border-bottom: solid #ea580c; text-style: bold; }
Screen.theme-day #diff-detail-scroll { background: #fff7ed; }
Screen.theme-day #help-dialog { background: #ffffff; border: solid #2563eb; }
Screen.theme-day #help-title { color: #1d4ed8; text-style: bold; }
Screen.theme-day #help-body { color: #1c1917; }
"""

# Indigo: violet chrome + emerald tools/users (very different from night's blue/grey)
_INDIGO = """
Screen.theme-indigo { background: #0a0f1e; color: #e2e8f0; }
Screen.theme-indigo Header { background: #1e1b4b; color: #a5b4fc; text-style: bold; }
Screen.theme-indigo Footer { background: #1e1b4b; color: #94a3b8; }
Screen.theme-indigo #sidebar { background: #13251c; border-right: solid #34d399; }
Screen.theme-indigo #main { background: #0a0f1e; }
Screen.theme-indigo Input { background: #1e1b4b; color: #e0e7ff; border: tall #6366f1; }
Screen.theme-indigo Input:focus { border: tall #a5b4fc; background: #312e81; }
Screen.theme-indigo ListView { background: #13251c; color: #d1fae5; }
Screen.theme-indigo ListItem.--highlight { background: #065f46; color: #ecfdf5; text-style: bold; }
Screen.theme-indigo #status-line { background: #1e1b4b; color: #c4b5fd; border-top: solid #4c1d95; }
Screen.theme-indigo Tabs { background: #1e1b4b; }
Screen.theme-indigo Tab { color: #94a3b8; }
Screen.theme-indigo Tab.-active { color: #5eead4; text-style: bold; background: #0a0f1e; }
Screen.theme-indigo Underline { background: #2dd4bf; }
Screen.theme-indigo Button { background: #312e81; color: #c4b5fd; border: tall #6366f1; }
Screen.theme-indigo Button.-primary { background: #059669; color: #ecfdf5; }
Screen.theme-indigo Button:hover { background: #4338ca; color: #ffffff; }
Screen.theme-indigo RichLog { background: #0a0f1e; color: #e2e8f0; scrollbar-background: #1e1b4b; scrollbar-color: #2dd4bf; }
Screen.theme-indigo #prompt-nav-wrap { background: #052e1c; border-bottom: solid #34d399; }
Screen.theme-indigo #prompt-nav-header { color: #ecfdf5; background: #047857; text-style: bold; }
Screen.theme-indigo #prompt-nav { background: #0a0f1e; scrollbar-background: #13251c; scrollbar-color: #34d399; }
Screen.theme-indigo #prompt-nav ListItem.--highlight { background: #10b981; color: #022c22; text-style: bold; }
Screen.theme-indigo #chat-toolbar { background: #1e1b4b; border-bottom: solid #6366f1; }
Screen.theme-indigo #chat-toolbar-hint { color: #a5b4fc; }
Screen.theme-indigo #chat-stream { background: #070b14; scrollbar-background: #1e1b4b; scrollbar-color: #6366f1; }
Screen.theme-indigo #chat-stream .chat-user { background: #052e1c; border-left: solid #34d399; color: #a7f3d0; }
Screen.theme-indigo #chat-stream .chat-agent { background: #1e1b4b; border-left: solid #818cf8; color: #c7d2fe; }
Screen.theme-indigo #chat-stream .chat-system { color: #f0abfc; }
Screen.theme-indigo #chat-stream Collapsible { background: #134e4a; border-left: solid #2dd4bf; }
Screen.theme-indigo #chat-stream CollapsibleTitle { background: #0f766e; color: #f0fdfa; text-style: bold; }
Screen.theme-indigo #chat-stream CollapsibleTitle:hover { background: #14b8a6; color: #042f2e; }
Screen.theme-indigo #chat-stream .tool-body { background: #0a0f1e; color: #e2e8f0; }
Screen.theme-indigo #chat-stream .chat-footer { color: #94a3b8; }
Screen.theme-indigo #diff-files-wrap { background: #1e1b4b; border-right: solid #818cf8; }
Screen.theme-indigo #diff-files-header { color: #e0e7ff; background: #4338ca; text-style: bold; }
Screen.theme-indigo #diff-file-list { background: #0a0f1e; }
Screen.theme-indigo #diff-file-list ListItem.--highlight { background: #6366f1; color: #ffffff; text-style: bold; }
Screen.theme-indigo #diff-detail-wrap { background: #070b14; }
Screen.theme-indigo #diff-detail-header { color: #5eead4; background: #134e4a; border-bottom: solid #2dd4bf; text-style: bold; }
Screen.theme-indigo #diff-detail-scroll { background: #0a0f1e; }
Screen.theme-indigo #help-dialog { background: #1e1b4b; border: solid #2dd4bf; }
Screen.theme-indigo #help-title { color: #5eead4; text-style: bold; }
Screen.theme-indigo #help-body { color: #e2e8f0; }
"""

APP_CSS = _LAYOUT + _NIGHT + _DAY + _INDIGO

_active_theme = "night"


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
        "slate": "night",
        "light": "day",
        "white": "day",
        "paper": "day",
        "forest": "indigo",
        "teal": "indigo",
        "green": "indigo",
        "violet": "indigo",
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


def set_active_theme(name: str) -> str:
    """Set global theme id used by rich_style() / pretty."""
    global _active_theme
    _active_theme = normalize_theme(name)
    return _active_theme


def active_theme() -> str:
    return _active_theme


def rich_style(role: str, default: str = "white") -> str:
    """Semantic Rich style string for the active theme."""
    pal = RICH_STYLES.get(_active_theme) or RICH_STYLES["night"]
    return pal.get(role, default)


def syntax_theme() -> str:
    return rich_style("syntax", "monokai")

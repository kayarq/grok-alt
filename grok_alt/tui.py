"""Grok-alt TUI — readable session traces in the terminal."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from rich.markup import escape as rich_escape
from rich.text import Text
from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.timer import Timer
from textual.widgets import (
    Button,
    Collapsible,
    Footer,
    Header,
    Input,
    Label,
    ListItem,
    ListView,
    RichLog,
    Static,
    TabbedContent,
    TabPane,
)

from . import core
from . import pretty
from . import logo as logo_mod

# Live-follow poll interval (seconds). Slightly gentler default — full chat remounts are expensive.
LIVE_POLL_INTERVAL = float(os.environ.get("GROK_ALT_POLL_INTERVAL", "1.5"))


class HelpScreen(ModalScreen[None]):
    BINDINGS = [Binding("escape", "dismiss", "Close"), Binding("q", "dismiss", "Close")]

    def compose(self) -> ComposeResult:
        yield Vertical(
            Static("[b]grok-alt — keyboard help[/b]", id="help-title"),
            Static(
                """
[b]Navigation[/b]
  ↑/↓ or j/k     Move session list / scroll
  Tab / 1-5      Timeline · Chat · Overview · Logs · Diffs
  Enter          Open selected session trace
  r              Refresh session list & current view
  /              Focus session filter

[b]Chat · user prompts[/b]
  In Chat tab, top list = all your prompts (newest last).
  ↑/↓ then Enter  Jump chat view to that prompt + following reply
  Click a row     Same jump (no more scrolling the whole log)
  List scrolls    All turns are selectable (scroll with ↑/↓ or mouse)
  d / D           Export selected turn → ~/grok-turn-exports (full tools; blocked if turn still running)

[b]Chat · tools (click to expand)[/b]
  Each tool is a clickable row (▸ title) — click to open/close details.
  Toolbar        [Expand all tools] [Collapse all] buttons above chat
  e / E          Keyboard: expand focused / all (optional; click is primary)
  t              Hide tool rows entirely

[b]Diffs tab (5)[/b]
  All code edits in this session, grouped by file.
  Left list      Click a file → colored unified diff on the right
  Shows          +added / -removed line counts per file

[b]Grok integration[/b]
  g              Launch real Grok in this cwd (new session)
  c              Continue latest Grok session (grok -c)
  R              Resume selected session (grok -r <id>)

[b]View[/b]
  p              Toggle phase events in timeline
  t              Hide/show tool lines in chat
  e/x · E/X      Expand one tool / all tools (works without clicking chat)
  [ / ]          Move tool focus in chat
  f              Toggle live auto-follow (on by default)
  q / Ctrl+C     Quit (in tmux: ends whole grok-alt session → back to shell)

[dim]Live mode polls session files so traces update while you chat.
Select a prompt to scroll there and expand that turn's tools. Official Grok: g / c / R.[/dim]
""",
                id="help-body",
            ),
            Button("Close", variant="primary", id="help-close"),
            id="help-dialog",
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "help-close":
            self.dismiss()


class GrokAltApp(App):
    """Readable Grok traces + launch hooks for the real Grok binary."""

    TITLE = "grok-alt"
    SUB_TITLE = "trace TUI · companion to Grok"
    CSS = """
    Screen { background: #0d1117; width: 100%; height: 100%; }

    /* Overlay so logo never steals layout rows / breaks RichLog resize */
    #app-logo {
        layer: overlay;
        dock: right;
        width: 26;
        height: 13;
        offset: 0 1;
        margin: 0 1 0 0;
        background: #0d1117 80%;
        color: #58a6ff;
    }

    #sidebar {
        width: 30%;
        min-width: 18;
        max-width: 36;
        background: #161b22;
        border-right: solid #30363d;
    }

    #main {
        width: 1fr;
        min-width: 20;
        overflow-x: auto;
    }

    #session-filter { margin: 0 1; dock: top; }
    #session-list { height: 1fr; }

    ListView { background: #161b22; }
    ListItem { padding: 0 1; }
    ListItem.--highlight { background: #1c2d41; }

    #status-line {
        dock: bottom;
        height: 1;
        background: #161b22;
        color: #8b949e;
        padding: 0 1;
    }

    TabbedContent { height: 1fr; width: 100%; }
    TabPane { width: 100%; height: 1fr; }

    RichLog {
        background: #0d1117;
        color: #e6edf3;
        height: 1fr;
        width: 100%;
        min-width: 1;
        border: none;
        scrollbar-background: #161b22;
        scrollbar-color: #30363d;
        overflow-x: auto;
    }

    #chat-pane { height: 1fr; width: 100%; }
    #prompt-nav-wrap {
        height: 14;
        min-height: 8;
        max-height: 18;
        width: 100%;
        background: #161b22;
        border-bottom: solid #30363d;
        layout: vertical;
    }
    #prompt-nav-header {
        height: 1;
        padding: 0 1;
        color: #8b949e;
        background: #21262d;
        dock: top;
    }
    #prompt-nav {
        height: 1fr;
        min-height: 6;
        background: #161b22;
        overflow-y: auto;
        scrollbar-background: #161b22;
        scrollbar-color: #30363d;
    }
    #prompt-nav ListItem { padding: 0 1; height: 2; }
    #prompt-nav ListItem.--highlight { background: #238636; }

    #chat-toolbar {
        height: auto;
        min-height: 3;
        max-height: 5;
        width: 100%;
        padding: 0 1;
        background: #21262d;
        border-bottom: solid #30363d;
        overflow-x: auto;
    }
    #chat-toolbar Button { margin: 0 1 0 0; min-width: 12; max-width: 22; }
    #chat-toolbar-hint { color: #8b949e; padding: 0 1; width: 1fr; min-width: 0; }
    #chat-stream {
        height: 1fr;
        width: 100%;
        min-width: 1;
        background: #0d1117;
        padding: 0 1 1 1;
        scrollbar-background: #161b22;
        scrollbar-color: #30363d;
        overflow-x: hidden;
        overflow-y: auto;
    }
    #chat-stream .chat-block { width: 100%; max-width: 100%; margin: 0 0 1 0; padding: 0 1; }
    #chat-stream .chat-user {
        width: 100%;
        background: #12261e;
        border-left: solid #3fb950;
        padding: 0 1;
        margin-bottom: 1;
    }
    #chat-stream .chat-agent {
        width: 100%;
        background: #0d1b2a;
        border-left: solid #58a6ff;
        padding: 0 1;
        margin-bottom: 1;
    }
    #chat-stream .chat-system { width: 100%; color: #8b949e; margin: 0 0 1 0; }
    #chat-stream Collapsible {
        width: 100%;
        max-width: 100%;
        margin: 0 0 1 0;
        background: #161b22;
        border-left: solid #d29922;
        padding: 0;
    }
    #chat-stream CollapsibleTitle {
        width: 100%;
        max-width: 100%;
        background: #21262d;
        color: #e6edf3;
        overflow: hidden;
    }
    #chat-stream CollapsibleTitle:hover { background: #30363d; color: #f0e68c; }
    #chat-stream .tool-body {
        width: 100%;
        max-width: 100%;
        padding: 0 1 1 2;
        background: #0d1117;
    }
    #chat-stream .chat-footer { width: 100%; color: #8b949e; margin-top: 1; }

    #diffs-pane { height: 1fr; width: 100%; }
    #diff-files-wrap {
        width: 32%;
        min-width: 16;
        max-width: 42;
        background: #161b22;
        border-right: solid #30363d;
    }
    #diff-files-header { height: 1; padding: 0 1; color: #8b949e; background: #21262d; }
    #diff-file-list { height: 1fr; background: #161b22; }
    #diff-file-list ListItem { padding: 0 1; height: 3; }
    #diff-file-list ListItem.--highlight { background: #1f3d2a; }
    #diff-detail-wrap { width: 1fr; min-width: 20; background: #0d1117; }
    #diff-detail-header {
        height: auto;
        min-height: 2;
        max-height: 4;
        padding: 0 1;
        color: #e6edf3;
        background: #21262d;
        border-bottom: solid #30363d;
    }
    #diff-detail-scroll { height: 1fr; width: 100%; padding: 0 1 1 1; background: #0d1117; }
    #diff-detail-body { width: 100%; }

    #help-dialog {
        width: 72;
        height: auto;
        max-height: 90%;
        background: #161b22;
        border: solid #58a6ff;
        padding: 1 2;
    }
    #help-title { color: #58a6ff; margin-bottom: 1; }
    #help-body { color: #e6edf3; }
    """

    # priority=True: work even when focus is on ListView / Input / RichLog (tmux UX)
    BINDINGS = [
        Binding("q", "quit_app", "Quit", priority=True),
        Binding("ctrl+c", "quit_app", "Quit", show=False, priority=True),
        Binding("question_mark", "help", "Help", priority=True),
        Binding("r", "refresh", "Refresh", priority=True),
        Binding("f", "toggle_live", "Live", priority=True),
        Binding("g", "launch_grok", "Grok", priority=True),
        Binding("c", "continue_grok", "Continue", priority=True),
        Binding("R", "resume_grok", "Resume", priority=True),
        Binding("d", "export_turn", "ExportTurn", priority=True),
        Binding("D", "export_turn", "ExportTurn", show=False, priority=True),
        Binding("p", "toggle_phases", "Phases", priority=True),
        Binding("t", "toggle_tools", "Tools", priority=True),
        Binding("e", "toggle_tool_expand", "Expand", priority=True),
        Binding("E", "toggle_all_tools_expand", "ExpandAll", priority=True),
        # Alternates if e/E is eaten by terminal/tmux (still priority app-wide)
        Binding("x", "toggle_tool_expand", "Expand", show=False, priority=True),
        Binding("X", "toggle_all_tools_expand", "ExpandAll", show=False, priority=True),
        # Brackets: multiple key ids for terminal/tmux compatibility
        Binding("left_square_bracket", "tool_focus_prev", "Tool↑", show=False, priority=True),
        Binding("right_square_bracket", "tool_focus_next", "Tool↓", show=False, priority=True),
        Binding("shift+left_square_bracket", "tool_focus_prev", "Tool↑", show=False, priority=True),
        Binding("shift+right_square_bracket", "tool_focus_next", "Tool↓", show=False, priority=True),
        Binding("slash", "focus_filter", "Filter", priority=True),
        Binding("1", "show_tab('timeline')", "TL", show=False, priority=True),
        Binding("2", "show_tab('chat')", "Chat", show=False, priority=True),
        Binding("3", "show_tab('overview')", "OV", show=False, priority=True),
        Binding("4", "show_tab('logs')", "Log", show=False, priority=True),
        Binding("5", "show_tab('diffs')", "Diff", show=False, priority=True),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.sessions: list[dict] = []
        self._by_id: dict[str, dict] = {}
        self.selected: dict | None = None
        self.hide_phases = True
        self.hide_tools_in_chat = False
        # Chat tools: collapsed one-liners by default; e/E expand details
        self._tools_expand_all = False
        self._tools_expanded: set[str] = set()  # keys that are expanded (when not expand-all)
        self._chat_tools: list[dict] = []  # {key, msg, widget_id, num}
        self._tool_id_to_key: dict[str, str] = {}  # widget id -> tool key
        self._tool_focus_idx: int = -1
        self._expand_session_id: str | None = None  # reset expand state on session switch
        self._rendering_chat = False
        self._last_chat_fp = ""  # session data fingerprint (not expand state)
        self._last_chat_structure_sig = ""  # roles/tool ids — skip full remount when stable
        self._chat_msgs: list[dict] = []  # last built message list (for in-place tool updates)
        self._diff_files: list[dict] = []  # session file changes for Diffs tab
        self._diff_by_id: dict[str, dict] = {}
        self._diff_selected_path: str | None = None
        self._diff_list_gen = 0
        self._populating_diff_list = False
        # Which user prompt/turn drives the Diffs tab (0-based; None = not chosen yet)
        self._selected_prompt_index: int | None = None
        self._filter = ""
        # Live follow: auto-pick newest session for cwd + re-render on file changes
        self.live_follow = True
        self._poll_timer: Timer | None = None
        self._last_index_fp = ""
        self._last_session_fp = ""
        self._last_unified_mtime_ns = 0
        self._user_pinned_session = False  # True after explicit list selection
        self._suppress_select_event = False
        self._populating_list = False  # re-entrancy guard (live poll vs filter/refresh)
        self._list_gen = 0  # bumps widget ids so stale ListItems never collide
        # Chat prompt navigator: line offsets into #log-chat for each user turn
        self._prompt_line_offsets: list[int] = []
        self._prompt_texts: list[str] = []
        self._prompt_nav_gen = 0
        self._populating_prompts = False
        self._pending_prompt_jump: int | None = None
        self._last_prompt_nav_key: tuple | None = None  # skip ListView rebuild when unchanged

    @staticmethod
    def _safe_list_index(lv: ListView, index: int | None) -> None:
        """Set ListView.index without crashing if children were rebuilt mid-event.

        Textual raises ValueError: ListItem(id='pn…') is not in list when the
        highlighted child was removed by a live refresh (left pane dies in tmux).
        """
        try:
            if index is None:
                try:
                    lv.index = None  # type: ignore[assignment]
                except Exception:
                    pass
                return
            children = list(lv.children)
            if not children:
                return
            idx = int(index)
            if idx < 0 or idx >= len(children):
                return
            # Ensure target is still a direct child (stale widgets after clear)
            target = children[idx]
            if target not in lv.children:
                return
            lv.index = idx
        except ValueError:
            pass
        except Exception:
            pass

    def _reset_list_view(self, lv: ListView) -> None:
        """Drop all ListView children and clear highlight so no stale ListItem remains."""
        try:
            self._safe_list_index(lv, None)
        except Exception:
            pass
        try:
            lv.clear()
        except Exception:
            pass
        for child in list(lv.children):
            try:
                child.remove()
            except Exception:
                pass
        try:
            self._safe_list_index(lv, None)
        except Exception:
            pass

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        try:
            yield Static(logo_mod.logo_renderable(), id="app-logo", markup=False)
        except Exception:
            pass
        with Horizontal():
            with Vertical(id="sidebar"):
                yield Input(placeholder="Filter sessions…  (/)", id="session-filter")
                yield ListView(id="session-list")
            with Vertical(id="main"):
                with TabbedContent(initial="timeline"):
                    with TabPane("Timeline", id="timeline"):
                        yield RichLog(
                            id="log-timeline",
                            highlight=True,
                            markup=True,
                            wrap=True,
                            auto_scroll=False,
                            min_width=1,
                        )
                    with TabPane("Chat", id="chat"):
                        with Vertical(id="chat-pane"):
                            with Vertical(id="prompt-nav-wrap"):
                                yield Static(
                                    "[b]Your prompts[/b]  [dim]· ↑/↓ scroll all turns · Enter jump · d export turn[/dim]",
                                    id="prompt-nav-header",
                                )
                                yield ListView(id="prompt-nav")
                            with Horizontal(id="chat-toolbar"):
                                yield Button("Expand all tools", id="btn-tools-expand-all", variant="primary")
                                yield Button("Collapse all", id="btn-tools-collapse-all", variant="default")
                                yield Static(
                                    "[dim]Tip: click a tool row (▸ …) to expand/collapse that tool[/dim]",
                                    id="chat-toolbar-hint",
                                )
                            yield VerticalScroll(id="chat-stream")
                    with TabPane("Overview", id="overview"):
                        yield RichLog(
                            id="log-overview",
                            highlight=True,
                            markup=True,
                            wrap=True,
                            auto_scroll=False,
                            min_width=1,
                        )
                    with TabPane("Logs", id="logs"):
                        yield RichLog(
                            id="log-unified",
                            highlight=True,
                            markup=True,
                            wrap=True,
                            auto_scroll=False,
                            min_width=1,
                        )
                    with TabPane("Diffs", id="diffs"):
                        with Horizontal(id="diffs-pane"):
                            with Vertical(id="diff-files-wrap"):
                                yield Static(
                                    "[b]Changed files[/b]  [dim]· for selected prompt · click file[/dim]",
                                    id="diff-files-header",
                                    markup=True,
                                )
                                yield ListView(id="diff-file-list")
                            with Vertical(id="diff-detail-wrap"):
                                yield Static(
                                    "[dim]Select a file on the left to see its changes[/dim]",
                                    id="diff-detail-header",
                                    markup=True,
                                )
                                with VerticalScroll(id="diff-detail-scroll"):
                                    yield Static("", id="diff-detail-body", markup=False, shrink=True)
                yield Static("Loading…", id="status-line")
        yield Footer()

    def on_mount(self) -> None:
        self.refresh_sessions(auto_select=True)
        self._start_live_poll()
        self.set_status(
            f"GROK_HOME={core.GROK_HOME} · sessions={'ok' if core.SESSIONS_DIR.exists() else 'missing'} · "
            f"live={'on' if self.live_follow else 'off'} · ? help · q quit"
        )

    def _start_live_poll(self) -> None:
        if self._poll_timer is not None:
            self._poll_timer.stop()
        self._poll_timer = self.set_interval(LIVE_POLL_INTERVAL, self._live_tick)

    def action_toggle_live(self) -> None:
        self.live_follow = not self.live_follow
        if self.live_follow:
            self._user_pinned_session = False
            self._live_tick(force=True)
            self.set_status("Live follow ON — auto-updates traces while Grok runs")
            self.notify("Live follow enabled")
        else:
            self.set_status("Live follow OFF — press r to refresh manually")
            self.notify("Live follow disabled")

    def set_status(self, msg: str) -> None:
        self.query_one("#status-line", Static).update(msg)


    def action_help(self) -> None:
        self.push_screen(HelpScreen())

    def action_quit_app(self) -> None:
        """Leave the TUI; under grok-alt-tmux, kill that session so you return to the shell."""
        self._shutdown_tmux_companion()
        self.exit()

    def _shutdown_tmux_companion(self) -> None:
        """Kill the dedicated tmux session (default name ``grok-alt``) when quitting from inside it.

        Set ``GROK_ALT_KILL_TMUX_ON_QUIT=0`` to only exit the TUI pane (old behaviour).
        Standalone ``grok-alt`` outside tmux is unchanged.
        """
        if not os.environ.get("TMUX"):
            return
        if os.environ.get("GROK_ALT_KILL_TMUX_ON_QUIT", "1").lower() in ("0", "false", "no"):
            return
        session = os.environ.get("GROK_ALT_TMUX_SESSION", "grok-alt")
        try:
            cur = subprocess.run(
                ["tmux", "display-message", "-p", "#S"],
                capture_output=True,
                text=True,
                timeout=2,
            )
            cur_name = (cur.stdout or "").strip()
        except Exception:
            cur_name = ""
        # Only kill our companion session, not a random tmux the user happened to run TUI in
        if cur_name and cur_name != session:
            return
        try:
            subprocess.Popen(
                ["tmux", "kill-session", "-t", f"={session}"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
        except Exception:
            pass

    def _ensure_chat_ready_for_tools(self) -> bool:
        """Switch to Chat tab and ensure tool list is built. Returns False if impossible."""
        try:
            tabs = self.query_one(TabbedContent)
            if tabs.active != "chat":
                tabs.active = "chat"
        except Exception:
            pass
        if not self.selected:
            self.set_status("Select a session first (Enter in the list)")
            return False
        if not self._chat_tools:
            self.render_chat()
        return True

    def action_focus_filter(self) -> None:
        self.query_one("#session-filter", Input).focus()

    def action_toggle_phases(self) -> None:
        self.hide_phases = not self.hide_phases
        self.set_status(f"Phases {'hidden' if self.hide_phases else 'shown'}")
        if self.selected:
            self.render_timeline()

    def action_toggle_tools(self) -> None:
        self.hide_tools_in_chat = not self.hide_tools_in_chat
        self._last_chat_fp = ""
        self.set_status(
            f"Tool rows in chat: {'hidden' if self.hide_tools_in_chat else 'shown (click row or toolbar to expand)'}"
        )
        if self.selected:
            self.render_chat(force=True)

    @on(Button.Pressed, "#btn-tools-expand-all")
    def on_tools_expand_all_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        # In-place only — full render_chat remount crashes with many tool rows
        self._apply_all_tools_collapsed(False)

    @on(Button.Pressed, "#btn-tools-collapse-all")
    def on_tools_collapse_all_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        self._apply_all_tools_collapsed(True)

    def _apply_all_tools_collapsed(self, collapsed: bool) -> None:
        """Expand/collapse every tool Collapsible without remounting the chat tree.

        Remounting 100+ widgets from a button handler was killing the TUI in tmux.
        """
        if self.hide_tools_in_chat:
            self.set_status("Tools are hidden — press t to show tool rows first")
            return
        if not self._ensure_chat_ready_for_tools():
            return
        if not self._chat_tools:
            self.set_status("No tools in this chat — select a session with tool activity")
            return

        self._rendering_chat = True  # suppress Collapsed/Expanded handlers during bulk update
        try:
            self._tools_expand_all = not collapsed
            if collapsed:
                self._tools_expanded.clear()
            else:
                self._tools_expanded = {t["key"] for t in self._chat_tools if t.get("key")}

            updated = 0
            for t in self._chat_tools:
                wid = t.get("widget_id")
                if not wid:
                    continue
                try:
                    col = self.query_one(f"#{wid}", Collapsible)
                    if col.collapsed != collapsed:
                        col.collapsed = collapsed
                    updated += 1
                except Exception:
                    continue
        finally:
            self._rendering_chat = False

        n = len(self._chat_tools)
        if collapsed:
            self.set_status(f"Collapsed {updated}/{n} tools — click any ▸ row to open one")
        else:
            self.set_status(f"Expanded {updated}/{n} tools — click a row or Collapse all to close")

    def _tool_detail_renderable(self, msg: dict):
        try:
            return pretty.render_tool_detail(msg)
        except Exception:
            return self._tool_detail_markup(msg)

    def _update_tool_collapsible(self, wid: str, msg: dict, *, tool_num: int = 1) -> bool:
        """Refresh title + body of an existing tool Collapsible without destroying its chrome.

        Textual's Collapsible owns a CollapsibleTitle child — never remove_children() on
        the Collapsible itself or the ▶ header / toggle is gone.
        """
        if not wid:
            return False
        try:
            col = self.query_one(f"#{wid}", Collapsible)
        except Exception:
            return False
        try:
            col.title = self._tool_collapsible_title(msg, tool_num=tool_num)
        except Exception:
            pass
        detail = self._tool_detail_renderable(msg)
        try:
            body = col.query_one(".tool-body", Static)
            body.update(detail)
            return True
        except Exception:
            pass
        # Body missing — mount only into Contents, never wipe CollapsibleTitle
        try:
            contents = col.query_one(Collapsible.Contents)
            for child in list(contents.children):
                try:
                    child.remove()
                except Exception:
                    pass
            contents.mount(Static(detail, classes="tool-body", markup=False, shrink=True))
            return True
        except Exception:
            return False

    @staticmethod
    def _chat_structure_sig(msgs: list[dict]) -> str:
        """Cheap signature: when stable, live updates can patch tools in place (no remount)."""
        parts: list[str] = []
        tool_i = 0
        for m in msgs:
            role = m.get("role") or "?"
            if role == "tool":
                tool_i += 1
                tid = m.get("tool_call_id") or f"i{tool_i}"
                parts.append(
                    f"t:{tid}:{m.get('status') or ''}:"
                    f"{(m.get('summary') or '')[:64]}:{(m.get('label') or '')[:24]}"
                )
            elif role == "user":
                t = m.get("text") or ""
                parts.append(f"u:{len(t)}:{hash(t) & 0xFFFF:x}")
            elif role in ("assistant", "agent"):
                t = m.get("text") or ""
                parts.append(f"a:{len(t)}:{hash(t) & 0xFFFF:x}")
            elif role == "system":
                parts.append(f"s:{(m.get('text') or '')[:40]}")
            else:
                parts.append(role)
        return "|".join(parts)

    def _patch_chat_tools_in_place(self, msgs: list[dict]) -> bool:
        """Update tool titles/bodies without tearing down the chat widget tree."""
        if self.hide_tools_in_chat:
            return False
        tool_msgs = [m for m in msgs if m.get("role") == "tool"]
        if len(tool_msgs) != len(self._chat_tools):
            return False
        for t, m in zip(self._chat_tools, tool_msgs):
            tid = m.get("tool_call_id")
            old_tid = (t.get("msg") or {}).get("tool_call_id")
            if tid and old_tid and tid != old_tid:
                return False
            t["msg"] = m
            wid = t.get("widget_id")
            if not wid:
                continue
            if not self._update_tool_collapsible(wid, m, tool_num=int(t.get("num") or 1)):
                return False
        self._chat_msgs = msgs
        prompts = [m.get("text") or "" for m in msgs if m.get("role") == "user"]
        self._prompt_texts = prompts
        self._render_prompt_nav(prompts)
        return True

    @on(Collapsible.Expanded)
    def on_tool_collapsible_expanded(self, event: Collapsible.Expanded) -> None:
        """Keep expand-state in sync when user clicks a tool row open."""
        if self._rendering_chat:
            return
        w = event.collapsible
        wid = str(w.id or "")
        if not wid.startswith("tool-"):
            return
        key = self._tool_id_to_key.get(wid)
        if not key:
            return
        if not self._tools_expand_all:
            self._tools_expanded.add(key)
        for i, t in enumerate(self._chat_tools):
            if t.get("key") == key:
                self._tool_focus_idx = i
                # Refresh body from latest msg (title already on widget)
                self._update_tool_collapsible(wid, t.get("msg") or {}, tool_num=int(t.get("num") or 1))
                break
        try:
            label = getattr(event.collapsible, "title", None) or key
            self.set_status(f"Tool expanded (click title again to collapse) · {str(label)[:55]}")
        except Exception:
            pass

    @on(Collapsible.Collapsed)
    def on_tool_collapsible_collapsed(self, event: Collapsible.Collapsed) -> None:
        """Keep expand-state in sync when user clicks a tool row closed."""
        if self._rendering_chat:
            return
        w = event.collapsible
        wid = str(w.id or "")
        if not wid.startswith("tool-"):
            return
        key = self._tool_id_to_key.get(wid)
        if not key:
            return
        if self._tools_expand_all:
            # Leaving "all open" mode: remember every other tool as still open
            self._tools_expand_all = False
            self._tools_expanded = {
                t["key"] for t in self._chat_tools if t.get("key") and t["key"] != key
            }
        else:
            self._tools_expanded.discard(key)
        # Do NOT remove Collapsible children — that destroys CollapsibleTitle (no header/toggle).
        try:
            self.set_status("Tool collapsed — click another ▸ row or use Expand all tools")
        except Exception:
            pass

    @staticmethod
    def _tool_widget_id(index: int, key: str) -> str:
        # Unique per chat position (keys can repeat in theory)
        safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in key)[:60]
        return f"tool-{index}-{safe}"

    def action_toggle_tool_expand(self) -> None:
        """Keyboard fallback: expand/collapse focused tool (prefer click on tool row)."""
        if self.hide_tools_in_chat:
            self.set_status("Tools are hidden — press t to show tool rows first")
            return
        if not self._ensure_chat_ready_for_tools():
            return
        if not self._chat_tools:
            self.set_status("No tools — select a session and open Chat (2)")
            return
        if self._tools_expand_all:
            self._tools_expand_all = False
            self._tools_expanded.clear()
        idx = self._tool_focus_idx
        if idx < 0 or idx >= len(self._chat_tools):
            idx = len(self._chat_tools) - 1
            self._tool_focus_idx = idx
        key = self._chat_tools[idx]["key"]
        wid = self._chat_tools[idx].get("widget_id")
        # Toggle via widget if present (no full re-render — smoother)
        if wid:
            try:
                col = self.query_one(f"#{wid}", Collapsible)
                col.collapsed = not col.collapsed
                if col.collapsed:
                    self._tools_expanded.discard(key)
                    state = "collapsed"
                else:
                    self._tools_expanded.add(key)
                    state = "expanded"
                label = self._chat_tools[idx]["msg"].get("summary") or key
                self.set_status(f"Tool {idx + 1}/{len(self._chat_tools)} {state} · or click the row directly")
                self._scroll_to_tool(idx)
                return
            except Exception:
                pass
        if key in self._tools_expanded:
            self._tools_expanded.discard(key)
        else:
            self._tools_expanded.add(key)
        if self.selected:
            self.render_chat()
        self._scroll_to_tool(idx)

    def action_toggle_all_tools_expand(self) -> None:
        """Keyboard: toggle all tools expanded/collapsed (in-place, no remount)."""
        if self.hide_tools_in_chat:
            self.set_status("Tools are hidden — press t to show tool rows first")
            return
        if not self._ensure_chat_ready_for_tools():
            return
        # If currently all-expanded, collapse; otherwise expand all
        want_collapse = self._tools_expand_all or (
            bool(self._chat_tools)
            and all(self._is_tool_expanded(t["key"]) for t in self._chat_tools if t.get("key"))
        )
        self._apply_all_tools_collapsed(want_collapse)

    def action_tool_focus_prev(self) -> None:
        self._move_tool_focus(-1)

    def action_tool_focus_next(self) -> None:
        self._move_tool_focus(1)

    def _move_tool_focus(self, delta: int) -> None:
        if self.hide_tools_in_chat:
            self.set_status("Tools are hidden — press t to show tool lines first")
            return
        if not self._ensure_chat_ready_for_tools():
            return
        if not self._chat_tools:
            self.set_status("No tools to focus in this session")
            return
        n = len(self._chat_tools)
        if self._tool_focus_idx < 0:
            self._tool_focus_idx = n - 1 if delta < 0 else 0
        else:
            self._tool_focus_idx = (self._tool_focus_idx + delta) % n
        if self.selected:
            self.render_chat()
        t = self._chat_tools[self._tool_focus_idx]
        summary = t["msg"].get("summary") or t["msg"].get("label") or ""
        expanded = self._is_tool_expanded(t["key"])
        self.set_status(
            f"Tool focus {self._tool_focus_idx + 1}/{n} "
            f"[{'▾ open' if expanded else '▸ shut'}]: {str(summary)[:55]}  · e toggle"
        )
        self._scroll_to_tool(self._tool_focus_idx)

    def _is_tool_expanded(self, key: str) -> bool:
        if self._tools_expand_all or key in self._tools_expanded:
            return True
        # Auto-expand tools that are still running so progress isn't just a title line
        for t in self._chat_tools or []:
            if t.get("key") == key:
                st = (t.get("msg") or {}).get("status") or ""
                if st == "in_progress":
                    return True
                break
        return False

    @staticmethod
    def _tool_key(msg: dict, index: int) -> str:
        tid = msg.get("tool_call_id")
        if tid:
            return str(tid)
        # Stable-ish fallback from summary+kind
        return f"idx:{index}:{msg.get('kind', '')}:{msg.get('variant', '')}:{hash(msg.get('summary') or msg.get('title') or '') & 0xFFFF:x}"

    def _scroll_to_tool(self, idx: int) -> None:
        if idx < 0 or idx >= len(self._chat_tools):
            return
        wid = self._chat_tools[idx].get("widget_id")
        if not wid:
            return
        try:
            stream = self.query_one("#chat-stream", VerticalScroll)
            w = self.query_one(f"#{wid}")
            stream.scroll_to_widget(w, animate=False, top=True)
        except Exception:
            pass

    def _reset_tool_expand_if_session_changed(self) -> None:
        sid = self.selected.get("id") if self.selected else None
        if sid != self._expand_session_id:
            self._expand_session_id = sid
            self._tools_expand_all = False
            self._tools_expanded.clear()
            self._tool_focus_idx = -1
            self._last_chat_fp = ""
            self._last_chat_structure_sig = ""
            self._chat_msgs = []
            self._selected_prompt_index = None  # new session → re-resolve prompt for diffs
            self._diff_selected_path = None
            self._last_prompt_nav_key = None  # force prompt ListView rebuild

    def action_show_tab(self, tab_id: str) -> None:
        tabs = self.query_one(TabbedContent)
        tabs.active = tab_id
        # Chat tools need a render pass so e/E/[ /] have data immediately
        if tab_id == "chat" and self.selected:
            self.render_chat()
        elif tab_id == "diffs" and self.selected:
            self.render_diffs()

    def action_refresh(self) -> None:
        self._user_pinned_session = False
        self.refresh_sessions(auto_select=True, force_render=True)
        self.set_status("Refreshed")

    @on(Input.Changed, "#session-filter")
    def on_filter_changed(self, event: Input.Changed) -> None:
        self._filter = event.value.strip().lower()
        self.populate_session_list()

    def refresh_sessions(self, *, auto_select: bool = False, force_render: bool = False) -> None:
        self.sessions = core.list_sessions()
        self._last_index_fp = core.sessions_index_fingerprint(self.sessions)
        self.populate_session_list()
        if auto_select and self.live_follow and not self._user_pinned_session:
            self._auto_select_best_session(force_render=force_render)
        elif force_render and self.selected:
            # Refresh selected entry metadata from latest list
            sid = self.selected.get("id")
            for s in self.sessions:
                if s.get("id") == sid:
                    self.selected = s
                    break
            self.load_selected_views(force=True)

    def populate_session_list(self) -> None:
        """Rebuild sidebar session list.

        Live-follow calls this often. Textual's ListView.clear() can leave stale
        children in the node map briefly; re-using session-derived widget IDs then
        raises DuplicateIds and kills the whole app (tmux left pane vanishes).
        Use generation-scoped index IDs so refreshes never collide.
        """
        if self._populating_list:
            return
        self._populating_list = True
        try:
            lv = self.query_one("#session-list", ListView)
            prev_sid = self.selected.get("id") if self.selected else None
            self._reset_list_view(lv)
            self._by_id.clear()
            self._list_gen += 1
            gen = self._list_gen
            q = self._filter
            shown = 0
            highlight_index: int | None = None
            for s in self.sessions:
                blob = " ".join(
                    str(x or "")
                    for x in (s.get("title"), s.get("cwd"), s.get("id"), s.get("model"), s.get("summary"))
                ).lower()
                if q and q not in blob:
                    continue
                sid = s["id"]
                title = (s.get("title") or "(untitled)")[:48]
                meta = f"{core.fmt_date(s.get('updated_at'))} · {(s.get('model') or '')[:16]}"
                if s.get("events_count"):
                    meta += f" · {s['events_count']}ev"
                # Generation + index: unique even if a prior clear left orphans behind.
                item_id = f"si{gen}-{shown}"
                lv.append(
                    ListItem(
                        Label(f"[b]{self._escape(title)}[/b]\n[dim]{self._escape(meta)}[/dim]"),
                        id=item_id,
                    )
                )
                self._by_id[item_id] = s
                if prev_sid and sid == prev_sid:
                    highlight_index = shown
                shown += 1
            if shown == 0:
                lv.append(ListItem(Label("[dim]No sessions[/dim]"), id=f"si{gen}-empty"))
            elif highlight_index is not None:
                try:
                    self._suppress_select_event = True
                    self._safe_list_index(lv, highlight_index)
                finally:
                    self._suppress_select_event = False
        except Exception as e:
            # Never let a list refresh take down the TUI (esp. in tmux).
            try:
                self.set_status(f"session list refresh error: {e}")
            except Exception:
                pass
        finally:
            self._populating_list = False

    def _auto_select_best_session(self, *, force_render: bool = False) -> None:
        """Follow newest session for current cwd (tmux side-by-side workflow)."""
        best = core.prefer_session_for_cwd(self.sessions, os.getcwd())
        if not best:
            return
        prev_id = self.selected.get("id") if self.selected else None
        changed_session = prev_id != best.get("id")
        self.selected = best
        if changed_session:
            self._last_session_fp = ""
            self._highlight_selected_in_list()
        self.load_selected_views(force=force_render or changed_session)

    def _highlight_selected_in_list(self) -> None:
        if not self.selected:
            return
        target_sid = self.selected.get("id")
        if not target_sid:
            return
        lv = self.query_one("#session-list", ListView)
        for i, child in enumerate(lv.children):
            wid = getattr(child, "id", None)
            data = self._by_id.get(wid) if wid else None
            if isinstance(data, dict) and data.get("id") == target_sid:
                try:
                    self._suppress_select_event = True
                    self._safe_list_index(lv, i)
                finally:
                    self._suppress_select_event = False
                break

    def _live_tick(self, force: bool = False) -> None:
        """Periodic poll: update session list + re-render views when files change."""
        if not self.live_follow and not force:
            return
        try:
            self._live_tick_inner(force=force)
        except Exception as e:
            # Guard the timer callback — an uncaught error exits Textual and drops the tmux pane.
            try:
                self.set_status(f"live poll error: {type(e).__name__}: {e}")
            except Exception:
                pass

    def _live_tick_inner(self, *, force: bool = False) -> None:
        try:
            # Light index for poll (no full line_count over every session file)
            sessions = core.list_sessions_light() if not force else core.list_sessions()
        except Exception:
            return
        index_fp = core.sessions_index_fingerprint(sessions)
        index_changed = index_fp != self._last_index_fp
        if index_changed:
            self.sessions = sessions
            self._last_index_fp = index_fp
            self.populate_session_list()

        if self.live_follow and not self._user_pinned_session:
            best = core.prefer_session_for_cwd(sessions, os.getcwd())
            if best and (not self.selected or self.selected.get("id") != best.get("id")):
                self.selected = best
                self._last_session_fp = ""
                self._highlight_selected_in_list()

        if not self.selected and sessions:
            # Nothing selected yet — attach to best match
            if self.live_follow:
                self._auto_select_best_session(force_render=True)
            return

        if not self.selected:
            return

        # Keep selected dict metadata fresh from list
        sid = self.selected.get("id")
        for s in sessions:
            if s.get("id") == sid:
                self.selected = s
                break

        sess_dir = self._sess_dir()
        sess_fp = core.session_fingerprint(sess_dir)
        unified_mtime = 0
        try:
            if core.UNIFIED_LOG.exists():
                unified_mtime = core.UNIFIED_LOG.stat().st_mtime_ns
        except OSError:
            pass

        session_changed = sess_fp != self._last_session_fp
        logs_changed = unified_mtime != self._last_unified_mtime_ns
        if force or session_changed or logs_changed:
            self._last_session_fp = sess_fp
            self._last_unified_mtime_ns = unified_mtime
            # Live updates: refresh timeline/logs always; chat only if session files changed
            # (avoids remounting 100+ collapsibles every second → crash/freeze in tmux)
            try:
                if session_changed or force:
                    # Full panes + chat; chat still uses incremental patch when structure stable
                    self.load_selected_views(force=True)
                else:
                    # Lightweight live tick: timeline/logs + incremental chat (no full remount storm)
                    self.load_selected_views(force=False, chat_only_if_needed=True)
            except Exception:
                pass
            live_tag = "LIVE" if self.live_follow else "paused"
            title = (self.selected.get("title") or "")[:32]
            try:
                self.set_status(
                    f"[{live_tag}] {sid[:8] if sid else '—'}… · {title} · "
                    f"auto-refresh {LIVE_POLL_INTERVAL:.0f}s · expand tools · r refresh"
                )
            except Exception:
                pass

    @staticmethod
    def _escape(text: str) -> str:
        """Escape for RichLog markup=True (tool titles often contain ``[`` / ``]``)."""
        if text is None:
            return ""
        return rich_escape(str(text))

    def _log_write(self, log: RichLog, line: str) -> None:
        """Write to RichLog; never let a single bad line kill the app."""
        try:
            log.write(line)
        except Exception:
            try:
                # Fallback: plain text, no markup interpretation
                log.write(Text(str(line)))
            except Exception:
                pass

    @on(ListView.Selected, "#session-list")
    def on_session_selected(self, event: ListView.Selected) -> None:
        if self._suppress_select_event:
            return
        item = event.item
        if not item:
            return
        key = item.id or ""
        data = self._by_id.get(key)
        if not isinstance(data, dict) or not data.get("id"):
            return
        # User explicitly picked a session — stop auto-jumping away
        self._user_pinned_session = True
        self.selected = data
        self._last_session_fp = ""
        self.load_selected_views(force=True)

    def load_selected_views(self, *, force: bool = False, chat_only_if_needed: bool = False) -> None:
        if not self.selected:
            return
        sess_dir = self._sess_dir()
        if not force:
            fp = core.session_fingerprint(sess_dir)
            if fp and fp == self._last_session_fp:
                return
            self._last_session_fp = fp
        else:
            self._last_session_fp = core.session_fingerprint(sess_dir)
        try:
            if core.UNIFIED_LOG.exists():
                self._last_unified_mtime_ns = core.UNIFIED_LOG.stat().st_mtime_ns
        except OSError:
            pass
        # Heavy panes: skip on lightweight live ticks when only session files changed
        # (chat handles its own incremental path). Force / session switch still paints all.
        paint_all = force or not chat_only_if_needed
        panes = (
            ("timeline", self.render_timeline),
            ("overview", self.render_overview),
            ("logs", self.render_logs),
            ("diffs", self.render_diffs),
        )
        if paint_all:
            for name, fn in panes:
                try:
                    fn()
                except Exception as e:
                    try:
                        self.set_status(f"{name} render error: {type(e).__name__}")
                    except Exception:
                        pass
        else:
            # Live: timeline + logs are cheap RichLog clears; skip overview/diffs unless on that tab
            try:
                tabs = self.query_one(TabbedContent)
                active = tabs.active
            except Exception:
                active = "timeline"
            try:
                self.render_timeline()
            except Exception:
                pass
            try:
                self.render_logs()
            except Exception:
                pass
            if active == "overview":
                try:
                    self.render_overview()
                except Exception:
                    pass
            elif active == "diffs":
                try:
                    self.render_diffs()
                except Exception:
                    pass
        # Chat: prefer incremental patch; full remount only when structure changes or forced
        try:
            self.render_chat(force=force)
        except Exception as e:
            try:
                self.set_status(f"chat render error: {type(e).__name__}: {e}")
            except Exception:
                pass
        sid = self.selected["id"]
        live_tag = "LIVE" if self.live_follow else "manual"
        self.set_status(
            f"[{live_tag}] Session {sid[:8]}… · {self.selected.get('title', '')[:36]} · "
            f"f live · r refresh · click tools to expand"
        )

    def _sess_dir(self) -> Path | None:
        if not self.selected:
            return None
        return core.resolve_session(self.selected["id"], self.selected.get("cwd_key"))

    def render_timeline(self) -> None:
        log = self.query_one("#log-timeline", RichLog)
        try:
            log.clear()
        except Exception:
            pass
        sess_dir = self._sess_dir()
        if not sess_dir:
            self._log_write(log, "[red]Session path not found[/red]")
            return
        try:
            items = core.build_timeline(sess_dir, hide_phases=self.hide_phases)
        except Exception as e:
            self._log_write(log, f"[red]timeline error: {type(e).__name__}[/red]")
            return
        if not items:
            self._log_write(log, "[dim]No timeline events[/dim]")
            return
        cat_style = {
            "turn": "green",
            "tool": "yellow",
            "user": "bright_green",
            "agent": "cyan",
            "phase": "dim",
            "permission": "red",
            "stream": "magenta",
            "meta": "blue",
            "other": "white",
        }
        # Cap rows so huge sessions cannot OOM / hang the left pane
        max_items = 800
        shown = items[-max_items:] if len(items) > max_items else items
        for it in shown:
            style = cat_style.get(it.get("category", "other"), "white")
            ts = self._escape(core.fmt_time(it.get("ts")))
            title = self._escape(it.get("title") or "")
            self._log_write(log, f"[dim]{ts}[/dim] [{style}]●[/{style}] {title}")
            detail = it.get("detail")
            if detail:
                lines = str(detail).splitlines() or [str(detail)]
                for i, line in enumerate(lines[:3]):
                    d = self._escape(line[:200])
                    self._log_write(log, f"         [dim]{d}[/dim]")
                if len(lines) > 3:
                    self._log_write(
                        log,
                        f"         [dim]… +{len(lines) - 3} more (see Chat tab for full tool trace)[/dim]",
                    )
        extra = f" (showing last {max_items})" if len(items) > max_items else ""
        self._log_write(
            log,
            f"\n[dim]{len(items)} items{extra} · phases "
            f"{'hidden' if self.hide_phases else 'shown'} · "
            f"press p to toggle · Chat tab has full tool diffs/reads[/dim]",
        )

    def render_chat(self, *, force: bool = True) -> None:
        """Chat stream: incremental when structure stable; lazy full tool bodies on expand."""
        if self._rendering_chat:
            return
        sess_dir = self._sess_dir()
        chat_fp = ""
        if sess_dir:
            chat_fp = core.session_fingerprint(sess_dir) or ""
            if self.hide_tools_in_chat:
                chat_fp += "|hide_tools"
        # Unchanged session files and not forced → nothing to do (expand state is not in fp)
        if not force and chat_fp and chat_fp == self._last_chat_fp and self._chat_tools:
            return

        self._reset_tool_expand_if_session_changed()

        if not sess_dir:
            stream = self.query_one("#chat-stream", VerticalScroll)
            self._rendering_chat = True
            try:
                stream.remove_children()
                stream.mount(
                    Static("[red]Session path not found[/red]", classes="chat-block", markup=True)
                )
                self._chat_tools = []
                self._tool_id_to_key = {}
                self._chat_msgs = []
                self._last_chat_structure_sig = ""
                self._render_prompt_nav([])
            finally:
                self._rendering_chat = False
            return

        try:
            msgs = core.build_chat_view(
                sess_dir,
                max_output_file_chars=core.TOOL_FULL_CHARS,
                full_detail=True,
            )
        except Exception as e:
            self.set_status(f"chat build error: {type(e).__name__}: {e}")
            return

        struct_sig = self._chat_structure_sig(msgs)
        # Same shape of conversation → patch tool titles/bodies in place (fast live path)
        if (
            not force
            and struct_sig
            and struct_sig == self._last_chat_structure_sig
            and self._chat_tools
        ):
            if self._patch_chat_tools_in_place(msgs):
                self._last_chat_fp = chat_fp
                return

        stream = self.query_one("#chat-stream", VerticalScroll)
        self._rendering_chat = True
        try:
            try:
                stream.remove_children()
            except Exception:
                pass
            self._prompt_line_offsets = []
            self._prompt_texts = []
            self._chat_tools = []
            self._tool_id_to_key = {}
            self._chat_msgs = msgs

            if not msgs:
                stream.mount(Static("[dim]No chat content[/dim]", classes="chat-block", markup=True))
                self._render_prompt_nav([])
                self._last_chat_fp = chat_fp
                self._last_chat_structure_sig = struct_sig
                return

            user_total = self._count_user_msgs(msgs)
            count = 0
            user_n = 0
            tool_n = 0
            current_prompt = -1  # 0-based; tools after a user msg belong to that turn
            for m in msgs:
                role = m.get("role", "?")
                if self.hide_tools_in_chat and role == "tool":
                    continue
                count += 1
                if role == "user":
                    user_n += 1
                    current_prompt = user_n - 1
                    text = m.get("text") or ""
                    self._prompt_texts.append(text)
                    stream.mount(
                        Static(
                            pretty.render_user_message(text, num=user_n, total=user_total),
                            id=f"prompt-block-{user_n - 1}",
                            classes="chat-user chat-block",
                            markup=False,
                            shrink=True,
                        )
                    )
                elif role in ("assistant", "agent"):
                    from rich.console import Group as RichGroup

                    agent_block = RichGroup(
                        pretty.render_agent_header(),
                        pretty.render_agent_message(m.get("text") or ""),
                    )
                    stream.mount(
                        Static(
                            agent_block,
                            classes="chat-agent chat-block",
                            markup=False,
                            shrink=True,
                        )
                    )
                elif role == "tool":
                    tool_n += 1
                    key = self._tool_key(m, tool_n - 1)
                    wid = self._tool_widget_id(tool_n, key)
                    # Open tools for the selected / last turn so picking a session isn't "blank until Expand all"
                    turn_pi = current_prompt
                    focus_pi = self._selected_prompt_index
                    if focus_pi is None and self._prompt_texts:
                        focus_pi = len(self._prompt_texts)  # not yet appended for this user; use after loop default
                    # During build, prefer explicit selection; else we'll expand last turn after nav is set
                    expanded = self._is_tool_expanded(key) or (
                        focus_pi is not None and turn_pi == focus_pi
                    )
                    self._tool_id_to_key[wid] = key
                    self._chat_tools.append(
                        {
                            "key": key,
                            "msg": m,
                            "widget_id": wid,
                            "num": tool_n,
                            "prompt_index": turn_pi,
                        }
                    )
                    title = self._tool_collapsible_title(m, tool_num=tool_n)
                    # Full body always mounted; CollapsibleTitle provides ▶ toggle (do not strip children later)
                    col = Collapsible(
                        Static(
                            self._tool_detail_renderable(m),
                            classes="tool-body",
                            markup=False,
                            shrink=True,
                        ),
                        title=title,
                        collapsed=not expanded,
                        id=wid,
                    )
                    stream.mount(col)
                    if expanded and key:
                        self._tools_expanded.add(key)
                elif role == "system":
                    stream.mount(
                        Static(
                            f"[dim]{self._escape(m.get('text') or '')}[/dim]",
                            classes="chat-system chat-block",
                            markup=True,
                            shrink=True,
                        )
                    )

            n_tools = len(self._chat_tools)
            n_open = n_tools if self._tools_expand_all else sum(
                1 for t in self._chat_tools if t["key"] in self._tools_expanded
            )
            stream.mount(
                Static(
                    f"[dim]{count} blocks · {user_n} prompt(s) · {n_tools} tool(s) "
                    f"({n_open} open) · select a prompt = expand that turn · q quits tmux session[/dim]",
                    classes="chat-footer",
                    markup=True,
                    shrink=True,
                )
            )
            self._render_prompt_nav(self._prompt_texts)
            if self._prompt_texts and self._selected_prompt_index is None:
                self._selected_prompt_index = len(self._prompt_texts) - 1
            elif self._selected_prompt_index is not None and self._prompt_texts:
                if self._selected_prompt_index >= len(self._prompt_texts):
                    self._selected_prompt_index = len(self._prompt_texts) - 1
            self._last_chat_fp = chat_fp
            self._last_chat_structure_sig = struct_sig
        finally:
            self._rendering_chat = False
        # After first paint for a session, open the focused turn (selected or last)
        reveal_idx = self._pending_prompt_jump
        if reveal_idx is None and self._selected_prompt_index is not None:
            reveal_idx = self._selected_prompt_index
        if self._pending_prompt_jump is not None:
            idx = self._pending_prompt_jump
            self._pending_prompt_jump = None
            self._set_selected_prompt_index(idx)
            self.call_after_refresh(lambda i=idx: self._reveal_turn(i))
        elif reveal_idx is not None and self._prompt_texts:
            self.call_after_refresh(lambda i=reveal_idx: self._reveal_turn(i, scroll=True))

    @staticmethod
    def _count_user_msgs(msgs: list[dict]) -> int:
        return sum(1 for m in msgs if m.get("role") == "user")

    def _tool_status_plain(self, status: str) -> str:
        if status == "completed":
            return "✓"
        if status == "in_progress":
            return "…"
        return status or ""

    def _tool_section_hint(self, m: dict) -> str:
        """Short hint of what expand will reveal."""
        secs = m.get("sections") or []
        if not secs:
            if m.get("content") is not None:
                return "raw payload"
            return "details"
        names = []
        for s in secs:
            h = s.get("heading") or s.get("style") or ""
            if h and h not in names:
                names.append(str(h))
        if not names:
            return f"{len(secs)} section(s)"
        shown = ", ".join(names[:4])
        if len(names) > 4:
            shown += "…"
        return shown

    def _tool_collapsible_title(self, m: dict, *, tool_num: int) -> str:
        """One-line title on clickable header (kept short for narrow tmux panes)."""
        label = str(m.get("label") or m.get("tool_name") or m.get("title") or "tool")
        summary = str(m.get("summary") or m.get("title") or "")
        # Very short in narrow panes — full detail is inside when expanded
        if len(summary) > 48:
            summary = summary[:45] + "…"
        if len(label) > 28:
            label = label[:25] + "…"
        st = self._tool_status_plain(m.get("status") or "")
        st_s = f" {st}" if st else ""
        hint = self._tool_section_hint(m)
        if len(hint) > 20:
            hint = hint[:17] + "…"
        # Total budget ~90 chars so it fits ~50-col tmux left pane without clipping
        title = f"#{tool_num} {label}{st_s} | {summary} | {hint}"
        if len(title) > 95:
            title = title[:92] + "…"
        return title

    def _tool_detail_markup(self, m: dict) -> str:
        """Full tool body as Rich markup for inside the collapsible."""
        lines: list[str] = []
        summary = str(m.get("summary") or "")
        if summary:
            lines.append(f"[white]{self._escape(summary)}[/white]")
        if m.get("sections") is not None or m.get("label"):
            for sec in m.get("sections") or []:
                heading = sec.get("heading") or ""
                body = sec.get("body") or ""
                style = sec.get("style") or "code"
                if heading:
                    lines.append(f"[dim]▸ {self._escape(heading)}[/dim]")
                if not body:
                    continue
                if style == "diff":
                    lines.extend(self._diff_markup_lines(body))
                elif style == "err":
                    for line in body.splitlines() or [body]:
                        lines.append(f"[red]{self._escape(line)}[/red]")
                elif style == "cmd":
                    for line in body.splitlines() or [body]:
                        lines.append(f"[magenta]{self._escape(line)}[/magenta]")
                elif style == "meta":
                    lines.append(f"[cyan]{self._escape(body)}[/cyan]")
                elif style == "dim":
                    lines.append(f"[dim]{self._escape(body)}[/dim]")
                else:
                    for line in body.splitlines() or [body]:
                        lines.append(f"[dim]{self._escape(line)}[/dim]")
            if not lines:
                lines.append("[dim](no extra detail)[/dim]")
            return "\n".join(lines)

        # Legacy fallback
        content = m.get("content")
        if content is not None:
            if not isinstance(content, str):
                content = json.dumps(content, ensure_ascii=False, indent=2)
            if len(content) > 2000:
                content = content[:2000] + "\n…"
            lines.append(f"[dim]{self._escape(content)}[/dim]")
        return "\n".join(lines) if lines else "[dim](empty)[/dim]"

    def _diff_markup_lines(self, diff_text: str) -> list[str]:
        out: list[str] = []
        for line in diff_text.splitlines() or [diff_text]:
            esc = self._escape(line)
            if line.startswith("+++") or line.startswith("---"):
                out.append(f"[bold]{esc}[/bold]")
            elif line.startswith("@@"):
                out.append(f"[cyan]{esc}[/cyan]")
            elif line.startswith("+") and not line.startswith("+++"):
                out.append(f"[green]{esc}[/green]")
            elif line.startswith("-") and not line.startswith("---"):
                out.append(f"[red]{esc}[/red]")
            else:
                out.append(f"[dim]{esc}[/dim]")
        return out

    @staticmethod
    def _prompt_preview(text: str, max_len: int = 72) -> str:
        one_line = " ".join((text or "").split())
        if len(one_line) <= max_len:
            return one_line or "(empty prompt)"
        return one_line[: max_len - 1] + "…"

    def _render_prompt_nav(self, prompts: list[str]) -> None:
        """Fill the Chat-tab prompt index (all user turns, clickable)."""
        if self._populating_prompts:
            return
        # Avoid thrashing ListView on every live chat rebuild when prompts unchanged
        # (was a common cause of ValueError: ListItem(id='pn…') is not in list).
        nav_key = (len(prompts), tuple(prompts))
        prefer_idx = self._selected_prompt_index
        if prefer_idx is None and prompts:
            prefer_idx = len(prompts) - 1
        if (
            nav_key == self._last_prompt_nav_key
            and prefer_idx is not None
            and prompts
        ):
            # Only re-highlight / scroll; do not clear children
            try:
                lv = self.query_one("#prompt-nav", ListView)
                self._suppress_select_event = True
                self._safe_list_index(lv, prefer_idx)
            except Exception:
                pass
            finally:
                try:
                    self._suppress_select_event = False
                except Exception:
                    pass
            try:
                gen = self._prompt_nav_gen
                self.call_after_refresh(
                    lambda g=gen, i=prefer_idx: self._ensure_prompt_nav_visible(i, expect_gen=g)
                )
            except Exception:
                pass
            return

        self._populating_prompts = True
        try:
            lv = self.query_one("#prompt-nav", ListView)
            self._reset_list_view(lv)
            self._prompt_nav_gen += 1
            gen = self._prompt_nav_gen
            total = len(prompts)
            self._last_prompt_nav_key = nav_key
            if total == 0:
                lv.append(
                    ListItem(
                        Label("[dim]No user prompts in this session yet[/dim]"),
                        id=f"pn{gen}-empty",
                    )
                )
                return
            for i, text in enumerate(prompts):
                preview = self._escape(self._prompt_preview(text))
                # Show newest at bottom (natural order = turn order)
                label = (
                    f"[bold bright_green]#{i + 1}[/bold bright_green]  "
                    f"[dim]{i + 1}/{total}[/dim]\n{preview}"
                )
                lv.append(ListItem(Label(label), id=f"pn{gen}-{i}"))
            # Prefer selected prompt; else last (most recent)
            hi = prefer_idx if prefer_idx is not None else total - 1
            if hi < 0:
                hi = 0
            if hi >= total:
                hi = total - 1
            try:
                self._suppress_select_event = True
                self._safe_list_index(lv, hi)
            finally:
                self._suppress_select_event = False
            hdr = self.query_one("#prompt-nav-header", Static)
            hdr.update(
                f"[b]Your prompts[/b]  [dim]· {total} turn(s) · "
                f"↑/↓ scrolls full list · Enter jump · d = export (after turn finishes)[/dim]"
            )
            # Defer scroll; ignore if another rebuild happened (gen mismatch)
            try:
                self.call_after_refresh(
                    lambda g=gen, i=hi: self._ensure_prompt_nav_visible(i, expect_gen=g)
                )
            except Exception:
                pass
        except Exception as e:
            try:
                self.set_status(f"prompt list error: {type(e).__name__}")
            except Exception:
                pass
        finally:
            self._populating_prompts = False

    def _ensure_prompt_nav_visible(self, index: int, *, expect_gen: int | None = None) -> None:
        """Scroll prompt ListView so index is on-screen (fixes last-rows clipping)."""
        if index < 0:
            return
        if expect_gen is not None and expect_gen != self._prompt_nav_gen:
            return  # list was rebuilt; old callback is stale
        if self._populating_prompts:
            return
        try:
            lv = self.query_one("#prompt-nav", ListView)
            children = list(lv.children)
            if index >= len(children):
                return
            item = children[index]
            if item not in lv.children:
                return
            # Prefer ListView API when available
            scroll_to = getattr(lv, "scroll_to_widget", None)
            if callable(scroll_to):
                try:
                    scroll_to(item, animate=False, top=False)
                except ValueError:
                    pass
            else:
                self._suppress_select_event = True
                try:
                    self._safe_list_index(lv, index)
                finally:
                    self._suppress_select_event = False
        except ValueError:
            pass
        except Exception:
            pass

    def _scroll_chat_to_prompt(self, index: int) -> None:
        """Scroll chat stream so the chosen user prompt is in view."""
        if index < 0 or index >= len(self._prompt_texts):
            return
        wid = f"prompt-block-{index}"
        try:
            stream = self.query_one("#chat-stream", VerticalScroll)
            w = self.query_one(f"#{wid}")
            stream.scroll_to_widget(w, animate=False, top=True)
        except Exception:
            pass

    def _expand_tools_for_prompt(self, prompt_index: int) -> int:
        """Open all tool collapsibles that belong to this user turn. Returns how many opened."""
        if prompt_index < 0:
            return 0
        opened = 0
        self._rendering_chat = True
        try:
            for t in self._chat_tools:
                if t.get("prompt_index") != prompt_index:
                    continue
                key = t.get("key")
                wid = t.get("widget_id")
                if key:
                    self._tools_expanded.add(key)
                if not wid:
                    continue
                try:
                    col = self.query_one(f"#{wid}", Collapsible)
                    if col.collapsed:
                        col.collapsed = False
                    opened += 1
                except Exception:
                    continue
        finally:
            self._rendering_chat = False
        return opened

    def _reveal_turn(self, index: int, *, scroll: bool = True) -> None:
        """Select a user turn: expand its tools and scroll the chat stream to that prompt.

        Fixes “switched session / picked a turn but only Expand all shows anything”.
        """
        if index is None or index < 0:
            return
        if self._prompt_texts and index >= len(self._prompt_texts):
            index = len(self._prompt_texts) - 1
        self._selected_prompt_index = index
        n_open = self._expand_tools_for_prompt(index)
        if scroll:
            self._scroll_chat_to_prompt(index)
        total = len(self._prompt_texts) or 1
        preview = ""
        if 0 <= index < len(self._prompt_texts):
            preview = self._prompt_preview(self._prompt_texts[index], 40)
        try:
            self.set_status(
                f"Turn #{index + 1}/{total} · {n_open} tool(s) expanded · "
                f"5 = diffs · d = export · q = quit"
                + (f" · {preview}" if preview else "")
            )
        except Exception:
            pass
        try:
            self.query_one("#chat-stream", VerticalScroll).focus()
        except Exception:
            pass

    def _set_selected_prompt_index(self, idx: int | None) -> None:
        """Pin which user prompt/turn the Diffs tab (and status) refer to."""
        if idx is None:
            self._selected_prompt_index = None
            return
        try:
            idx = int(idx)
        except (TypeError, ValueError):
            return
        if idx < 0:
            return
        prev = self._selected_prompt_index
        self._selected_prompt_index = idx
        # Refresh diffs when turn changes (cheap compared to full chat remount)
        if prev != idx and self.selected:
            try:
                tabs = self.query_one(TabbedContent)
                if tabs.active == "diffs":
                    self.render_diffs()
            except Exception:
                pass

    def _resolve_prompt_index_for_diffs(self) -> int | None:
        """Prompt/turn to scope diffs: explicit selection, else last prompt in session."""
        if self._selected_prompt_index is not None:
            return self._selected_prompt_index
        if self._prompt_texts:
            return len(self._prompt_texts) - 1
        # Chat not built yet — count from session data
        sess_dir = self._sess_dir()
        if not sess_dir:
            return None
        try:
            all_data = core.build_session_file_changes(sess_dir, prompt_index=None)
            pc = all_data.get("prompt_count") or 0
            if pc > 0:
                return pc - 1
        except Exception:
            pass
        return None

    @on(ListView.Selected, "#prompt-nav")
    def on_prompt_nav_selected(self, event: ListView.Selected) -> None:
        if self._suppress_select_event:
            return
        item = event.item
        if not item or not item.id:
            return
        # id format: pn{gen}-{index}
        try:
            idx = int(str(item.id).rsplit("-", 1)[-1])
        except ValueError:
            return
        # Scope Diffs tab to this user prompt/turn
        self._set_selected_prompt_index(idx)
        # Keep highlight row fully in the prompt list viewport (gen-guarded)
        gen = self._prompt_nav_gen
        self.call_after_refresh(
            lambda g=gen, i=idx: self._ensure_prompt_nav_visible(i, expect_gen=g)
        )
        # Switch focus to chat body, scroll, and expand tools for this turn
        try:
            tabs = self.query_one(TabbedContent)
            tabs.active = "chat"
        except Exception:
            pass
        if not self._prompt_texts:
            # Chat not rendered yet — queue reveal after next render
            self._pending_prompt_jump = idx
            self.render_chat(force=True)
            return
        self._reveal_turn(idx, scroll=True)

    def render_diffs(self) -> None:
        """Populate Diffs tab for the *selected user prompt/turn* only (not whole session)."""
        sess_dir = self._sess_dir()
        hdr = self.query_one("#diff-files-header", Static)
        detail_hdr = self.query_one("#diff-detail-header", Static)
        detail_body = self.query_one("#diff-detail-body", Static)

        if not sess_dir:
            self._diff_files = []
            self._diff_by_id = {}
            self._populate_diff_file_list([])
            hdr.update("[b]Changed files[/b]  [dim]· no session[/dim]")
            detail_hdr.update("[red]Session path not found[/red]")
            detail_body.update("")
            return

        prompt_idx = self._resolve_prompt_index_for_diffs()
        # Remember resolved default so header stays stable
        if self._selected_prompt_index is None and prompt_idx is not None:
            self._selected_prompt_index = prompt_idx

        try:
            data = core.build_session_file_changes(sess_dir, prompt_index=prompt_idx)
        except Exception as e:
            self._diff_files = []
            self._populate_diff_file_list([])
            hdr.update("[b]Changed files[/b]")
            detail_hdr.update(f"[red]Failed to load diffs: {self._escape(str(e))}[/red]")
            detail_body.update("")
            return

        files = data.get("files") or []
        self._diff_files = files
        tf = data.get("total_files", 0)
        th = data.get("total_hunks", 0)
        ta = data.get("total_added", 0)
        tr = data.get("total_removed", 0)
        pc = data.get("prompt_count") or 0
        pi = data.get("prompt_index")
        if pi is not None and pc > 0:
            scope = f"prompt #{pi + 1}/{pc} only"
        elif pi is not None:
            scope = f"prompt #{pi + 1} only"
        else:
            scope = "whole session"
        # Prompt preview in header when available
        prompt_hint = ""
        if pi is not None and pi < len(self._prompt_texts):
            prompt_hint = f" · {self._escape(self._prompt_preview(self._prompt_texts[pi], 28))}"
        hdr.update(
            f"[b]Changed files[/b]  [dim]· {scope}{prompt_hint}[/dim]\n"
            f"[dim]{tf} file(s) · {th} edit(s) · [/dim][green]+{ta}[/green][dim]/[/dim][red]-{tr}[/red]"
        )

        if not files:
            self._populate_diff_file_list([])
            if pi is not None:
                detail_hdr.update(
                    f"[dim]No code edits during prompt #{pi + 1}"
                    f"{f'/{pc}' if pc else ''}. "
                    f"Pick another prompt in Chat (top list), or agent made no edits this turn.[/dim]"
                )
            else:
                detail_hdr.update(
                    "[dim]No code edits yet. Select a prompt in Chat (Your prompts list), then open Diffs.[/dim]"
                )
            detail_body.update("")
            self._diff_selected_path = None
            return

        self._populate_diff_file_list(files)
        paths = {f.get("path") for f in files}
        if self._diff_selected_path not in paths:
            self._diff_selected_path = files[0].get("path")
        self._show_diff_for_path(self._diff_selected_path)

    def _populate_diff_file_list(self, files: list[dict]) -> None:
        if self._populating_diff_list:
            return
        self._populating_diff_list = True
        try:
            lv = self.query_one("#diff-file-list", ListView)
            self._reset_list_view(lv)
            self._diff_by_id.clear()
            self._diff_list_gen += 1
            gen = self._diff_list_gen
            if not files:
                lv.append(ListItem(Label("[dim]No changed files[/dim]"), id=f"df{gen}-empty"))
                return
            sel_idx = 0
            for i, f in enumerate(files):
                path = f.get("path") or "?"
                short = f.get("short_path") or pretty.short_path(path, 40)
                hc = f.get("hunk_count", 0)
                add = f.get("lines_added", 0)
                rem = f.get("lines_removed", 0)
                item_id = f"df{gen}-{i}"
                self._diff_by_id[item_id] = f
                label = (
                    f"[bold cyan]{self._escape(short)}[/bold cyan]\n"
                    f"[dim]{hc} edit(s) · [/dim][green]+{add}[/green][dim] / [/dim][red]-{rem}[/red]"
                )
                lv.append(ListItem(Label(label), id=item_id))
                if path == self._diff_selected_path:
                    sel_idx = i
            try:
                self._suppress_select_event = True
                self._safe_list_index(lv, sel_idx)
            finally:
                self._suppress_select_event = False
        except Exception as e:
            try:
                self.set_status(f"diff list error: {type(e).__name__}")
            except Exception:
                pass
        finally:
            self._populating_diff_list = False

    def _show_diff_for_path(self, path: str | None) -> None:
        detail_hdr = self.query_one("#diff-detail-header", Static)
        detail_body = self.query_one("#diff-detail-body", Static)
        if not path:
            detail_hdr.update("[dim]Select a file[/dim]")
            detail_body.update("")
            return
        fmeta = next((f for f in self._diff_files if f.get("path") == path), None)
        if not fmeta:
            detail_hdr.update(f"[dim]No data for {self._escape(str(path)[:60])}[/dim]")
            detail_body.update("")
            return

        short = fmeta.get("short_path") or pretty.short_path(path, 72)
        hc = fmeta.get("hunk_count", 0)
        add = fmeta.get("lines_added", 0)
        rem = fmeta.get("lines_removed", 0)
        detail_hdr.update(
            f"[bold]{self._escape(short)}[/bold]\n"
            f"[dim]{self._escape(str(path)[:100])} · {hc} hunk(s) · [/dim]"
            f"[green]+{add}[/green][dim] / [/dim][red]-{rem}[/red]"
        )

        from rich.console import Group as RichGroup
        from rich.rule import Rule
        from rich.text import Text as RichText

        parts: list = []
        hunks = fmeta.get("hunks") or []
        for hi, h in enumerate(hunks, 1):
            parts.append(
                RichText.assemble(
                    (f"── edit #{h.get('index', hi)} ", "bold yellow"),
                    (f"({hi}/{len(hunks)})", "dim"),
                )
            )
            parts.append(pretty.render_diff(h.get("diff") or "(empty diff)"))
            if hi < len(hunks):
                parts.append(RichText(""))
                parts.append(Rule(style="dim"))
                parts.append(RichText(""))
        if not parts:
            parts.append(RichText("(no hunks)", style="dim"))
        try:
            detail_body.update(RichGroup(*parts))
        except Exception:
            # Fallback: plain markup string
            lines = [f"=== {short} ==="]
            for h in hunks:
                lines.append(h.get("diff") or "")
                lines.append("")
            detail_body.update("\n".join(lines))

    @on(ListView.Selected, "#diff-file-list")
    def on_diff_file_selected(self, event: ListView.Selected) -> None:
        if self._suppress_select_event:
            return
        item = event.item
        if not item or not item.id:
            return
        fmeta = self._diff_by_id.get(item.id)
        if not fmeta:
            return
        path = fmeta.get("path")
        self._diff_selected_path = path
        self._show_diff_for_path(path)
        try:
            self.set_status(f"Diffs · {fmeta.get('short_path') or path} · {fmeta.get('hunk_count', 0)} edit(s)")
        except Exception:
            pass

    def render_overview(self) -> None:
        log = self.query_one("#log-overview", RichLog)
        log.clear()
        sess_dir = self._sess_dir()
        if not sess_dir:
            log.write("[red]Session path not found[/red]")
            return
        ov = core.session_overview(sess_dir)
        s = ov.get("summary") or {}
        sig = ov.get("signals") or {}
        info = s.get("info") or {}
        log.write("[bold]Session overview[/bold]\n")
        log.write(f"  [cyan]title[/cyan]  {self._escape(s.get('generated_title') or s.get('session_summary') or '—')}")
        log.write(f"  [cyan]id[/cyan]     {info.get('id') or self.selected and self.selected.get('id')}")
        log.write(f"  [cyan]cwd[/cyan]    {self._escape(info.get('cwd') or self.selected and self.selected.get('cwd') or '—')}")
        log.write(f"  [cyan]model[/cyan]  {s.get('current_model_id') or '—'}")
        log.write(f"  [cyan]agent[/cyan]  {s.get('agent_name') or '—'}")
        log.write(f"  [cyan]msgs[/cyan]   {s.get('num_messages')} total · {s.get('num_chat_messages')} chat")
        log.write(f"  [cyan]tokens[/cyan] {sig.get('total_tokens', '—')} · tools {sig.get('tool_calls', '—')}")
        log.write(f"  [cyan]created[/cyan] {s.get('created_at') or '—'}")
        log.write(f"  [cyan]updated[/cyan] {s.get('updated_at') or s.get('last_active_at') or '—'}")
        log.write(f"  [cyan]path[/cyan]   {self._escape(ov.get('path') or '')}")

        log.write("\n[bold]Event types[/bold] (events.jsonl)")
        for k, v in list((ov.get("event_types") or {}).items())[:20]:
            log.write(f"  {k:28} {v}")
        log.write("\n[bold]Update types[/bold] (updates.jsonl)")
        for k, v in list((ov.get("update_types") or {}).items())[:20]:
            log.write(f"  {k:28} {v}")
        files = ov.get("files") or []
        if files:
            log.write(f"\n[bold]Files[/bold]  {', '.join(files[:20])}")
        # Quick pointer to Diffs tab
        try:
            pi = self._resolve_prompt_index_for_diffs()
            ch = core.build_session_file_changes(sess_dir, prompt_index=pi)
            if ch.get("total_files") or ch.get("prompt_count"):
                scope = f"prompt #{(pi or 0) + 1}" if pi is not None else "session"
                log.write(
                    f"\n[bold]Code changes[/bold] ({scope})  {ch['total_files']} file(s) · "
                    f"{ch['total_hunks']} edit(s) · [green]+{ch['total_added']}[/green]/[red]-{ch['total_removed']}[/red]"
                )
                log.write("[dim]Press 5 for Diffs · pick a prompt in Chat first to scope by turn[/dim]")
        except Exception:
            pass

    def render_logs(self) -> None:
        log = self.query_one("#log-unified", RichLog)
        log.clear()
        sid = self.selected["id"] if self.selected else ""
        entries = core.search_unified_log(sid=sid, limit=120)
        if not entries:
            log.write(f"[dim]No unified log entries for sid={sid[:8] if sid else '—'}…[/dim]")
            log.write(f"[dim]Log file: {core.UNIFIED_LOG}[/dim]")
            return
        for e in entries:
            ts = core.fmt_time(e.get("ts"))
            src = e.get("src") or "?"
            msg = e.get("msg") or "?"
            ctx = e.get("ctx")
            extra = ""
            if isinstance(ctx, dict):
                extra = " " + json.dumps(ctx, ensure_ascii=False)[:100]
            log.write(f"[dim]{ts}[/dim] [magenta]{src}[/magenta] [cyan]{self._escape(msg)}[/cyan][dim]{self._escape(extra)}[/dim]")
        log.write(f"\n[dim]{len(entries)} log lines · filtered to this session[/dim]")

    # ── Launch real Grok ──────────────────────────────────────────

    def action_launch_grok(self) -> None:
        self._exec_grok([])

    def action_continue_grok(self) -> None:
        self._exec_grok(["-c"])

    def action_resume_grok(self) -> None:
        if not self.selected:
            self.set_status("Select a session first, then press R to resume")
            self.notify("No session selected", severity="warning")
            return
        sid = self.selected["id"]
        cwd = self.selected.get("cwd") or os.getcwd()
        self._exec_grok(["-r", sid], cwd=cwd)

    def _exec_grok(self, extra_args: list[str], cwd: str | None = None) -> None:
        """Exit this TUI and replace the process with real Grok."""
        bin_path = core.grok_binary()
        args = [bin_path, *extra_args]
        work_dir = cwd or os.getcwd()
        self.set_status(f"Launching: {' '.join(args)}  (cwd={work_dir})")
        # Give a brief visual cue then exec
        self.exit(result=("exec", args, work_dir))


    def action_export_turn(self) -> None:
        """Save selected turn as markdown: ## Prompt / ## Trace / ## Response.

        Blocks while the turn is still in progress (accuracy over partial exports).
        """
        if not self.selected:
            self.set_status("Select a session first, then pick a prompt and press d")
            self.notify("No session selected", severity="warning")
            return
        sess_dir = self._sess_dir()
        if not sess_dir:
            self.notify("Session path not found", severity="error")
            return
        # Prefer explicit prompt selection; else last prompt in nav / session
        idx = self._selected_prompt_index
        if idx is None:
            idx = self._resolve_prompt_index_for_diffs()
        if idx is None:
            # Try ListView highlight
            try:
                lv = self.query_one("#prompt-nav", ListView)
                if lv.index is not None and lv.index >= 0:
                    idx = int(lv.index)
            except Exception:
                pass
        if idx is None:
            self.set_status("No prompt/turn to export — open Chat (2) and select a prompt")
            self.notify("Pick a prompt in Chat first", severity="warning")
            return
        idx = int(idx)
        turn_st = core.prompt_turn_status(sess_dir, idx)
        if not turn_st.get("complete"):
            msg = (
                f"Turn #{idx + 1} is still in progress — export blocked until the agent "
                f"finishes this turn (then wait ~{core.TURN_SETTLE_SECONDS:.0f}s and press d again)."
            )
            self.set_status(msg)
            self.notify(
                "Turn still running — wait for it to finish, then export",
                severity="warning",
            )
            return
        try:
            path = core.export_turn_to_file(
                sess_dir,
                idx,
                session_id=self.selected.get("id"),
                require_complete=True,
            )
        except core.TurnIncompleteError as e:
            self.set_status(str(e))
            self.notify("Turn still running — export blocked", severity="warning")
            return
        except Exception as e:
            self.notify(f"Export failed: {e}", severity="error")
            self.set_status(f"export error: {type(e).__name__}: {e}")
            return
        self._selected_prompt_index = idx
        files_dir = path.parent / f"{path.stem}-files"
        extra = ""
        if files_dir.is_dir():
            n = sum(1 for _ in files_dir.iterdir() if _.is_file())
            if n:
                extra = f" + {n} file(s) in {files_dir.name}/"
        self.set_status(f"Exported turn #{idx + 1} → {path}{extra}")
        self.notify(f"Saved {path.name}{extra}")


def run_tui() -> int:
    app = GrokAltApp()
    result = app.run()
    if isinstance(result, tuple) and result and result[0] == "exec":
        _, args, work_dir = result
        try:
            os.chdir(work_dir)
        except OSError:
            pass
        print(f"\n→ launching Grok: {' '.join(args)}\n", flush=True)
        os.execvp(args[0], args)
    return 0

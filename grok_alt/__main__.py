"""python -m grok_alt entry point."""

from __future__ import annotations

import argparse
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="grok-alt",
        description="Grok companion: session traces in the terminal, especially side-by-side in tmux.",
    )
    parser.add_argument(
        "mode",
        nargs="?",
        default="tui",
        choices=("tui", "tmux", "list", "version"),
        help="tui (default) | tmux | list | version",
    )
    args, extra = parser.parse_known_args(argv)

    if args.mode == "version":
        from . import __version__

        print(f"grok-alt {__version__}")
        return 0

    if args.mode == "list":
        from . import core

        sessions = core.list_sessions()
        for s in sessions[:40]:
            print(
                f"{s['id'][:8]}…  {(s.get('updated_at') or '')[:19]:19}  "
                f"{(s.get('title') or '(untitled)')[:50]}"
            )
        print(f"\n{len(sessions)} sessions under {core.SESSIONS_DIR}")
        return 0

    if args.mode == "tmux":
        import os
        from pathlib import Path

        launcher = Path(__file__).resolve().parent.parent / "bin" / "grok-alt-tmux"
        if not launcher.exists():
            print(f"Missing tmux launcher: {launcher}", file=sys.stderr)
            return 1
        cmd = [str(launcher), *extra]
        os.execv(cmd[0], cmd)

    if extra:
        print(f"Unknown extra arguments: {extra}", file=sys.stderr)
        print("Tip: use  grok-alt tmux -- -c   to pass flags to Grok", file=sys.stderr)
        return 2
    from .tui import run_tui

    return run_tui()


if __name__ == "__main__":
    raise SystemExit(main())

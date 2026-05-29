"""Hook scripts for OpenCode before_turn/after_turn integration.

OpenCode calls these as subprocess hooks before/after each agent turn.
Uses AgentMemory for context injection (before) and extraction (after).
"""

import sys
import os
from pathlib import Path

SISYPHUS_SRC = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(SISYPHUS_SRC))


def before_turn():
    """Called by OpenCode before each agent turn."""
    from sisyphus.memory.store import MemoryStore
    from sisyphus.memory.context import AgentMemory

    store = MemoryStore(Path.home() / ".omo" / "memory")
    memory = AgentMemory(store)
    query = sys.stdin.read().strip() if not sys.stdin.isatty() else ""
    ctx = memory.before_turn(query=query, max_chars=3000)
    if ctx:
        print(ctx)


def after_turn():
    """Called by OpenCode after each agent response.

    Writes ALL turns to session log. Only stores significant turns
    to MemoryStore when signal words trigger.
    """
    from sisyphus.memory.store import MemoryStore
    from sisyphus.memory.context import AgentMemory
    from sisyphus.memory.trigger import l0_signal_words
    from datetime import datetime

    turn = sys.stdin.read().strip() if not sys.stdin.isatty() else ""
    if not turn:
        return

    ts = datetime.now().astimezone()
    date_str = ts.strftime("%Y-%m-%d")

    # Always write to session log
    session_dir = Path.home() / ".omo" / "sessions"
    session_dir.mkdir(parents=True, exist_ok=True)
    session_file = session_dir / f"{date_str}.md"
    entry = f"\n---\n## {ts.strftime('%H:%M:%S')}\n\n{turn[:2000]}\n"
    with open(session_file, "a") as f:
        f.write(entry)

    # Only store to MemoryStore when signal words trigger
    trigger = l0_signal_words(turn)
    if trigger.should_trigger:
        store = MemoryStore(Path.home() / ".omo" / "memory")
        store.create_if_new(
            title=f"Conversation {ts.strftime('%Y-%m-%dT%H%M%S')}",
            type="conversation",
            content=turn[:2000],
            tags=["raw", "conversation", "auto", f"trigger:{trigger.reason}"],
        )
        memory = AgentMemory(store)
        memory.after_turn(turn=turn)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "before_turn":
        before_turn()
    elif cmd == "after_turn":
        after_turn()
    else:
        print(f"Usage: python -m sisyphus.agent.hooks [before_turn|after_turn]", file=sys.stderr)
        sys.exit(1)

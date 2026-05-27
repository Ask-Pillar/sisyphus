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
    """Called by OpenCode after each agent response."""
    from sisyphus.memory.store import MemoryStore
    from sisyphus.memory.context import AgentMemory

    store = MemoryStore(Path.home() / ".omo" / "memory")
    memory = AgentMemory(store)
    turn = sys.stdin.read().strip() if not sys.stdin.isatty() else ""
    if turn:
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

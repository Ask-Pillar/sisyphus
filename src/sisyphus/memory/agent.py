"""Agent memory sandbox — isolated memory environments for sub-agents.

Each agent gets its own directory under .omo/memory/agents/<name>/
with independent Store, RefinedStore, and INDEX.
"""

from pathlib import Path
from typing import List

from sisyphus.memory.store import MemoryStore
from sisyphus.memory.refined import RefinedStore


class AgentSandbox:
    def __init__(self, base_path: Path, name: str):
        self.name = name
        self.root = base_path / "memory" / "agents" / name
        self.root.mkdir(parents=True, exist_ok=True)
        self.store = MemoryStore(self.root)
        self.refined = RefinedStore(self.root)

    def list_memories(self) -> List:
        return self.store.list()

    def list_refined(self, type_filter: str = None) -> List:
        return self.refined.list_refined(type_filter=type_filter)

    def stats(self) -> dict:
        return {
            "agent": self.name,
            "raw": len(self.store.list()),
            "refined": len(self.refined.list_refined()),
            "path": str(self.root),
        }


class AgentRegistry:
    def __init__(self, base_path: Path):
        self.base_path = base_path
        self._agents_dir = base_path / "memory" / "agents"
        self._agents_dir.mkdir(parents=True, exist_ok=True)

    def all(self) -> List[str]:
        return sorted(d.name for d in self._agents_dir.iterdir()
                      if d.is_dir())

    def get(self, name: str) -> AgentSandbox:
        return AgentSandbox(self.base_path, name)

    def create(self, name: str) -> AgentSandbox:
        return self.get(name)

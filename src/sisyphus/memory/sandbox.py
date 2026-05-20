"""Agent memory sandbox — isolated memory environment per sub-agent.

Each persistent sub-agent gets its own directory:
  .omo/memory/agents/<agent_name>/
      ├── INDEX.md
      ├── raw/
      └── refined/
"""

from pathlib import Path
from typing import List, Optional
from dataclasses import dataclass

from sisyphus.memory.store import MemoryStore
from sisyphus.memory.refined import RefinedStore


@dataclass
class AgentInfo:
    name: str
    path: Path
    memory_count: int
    refined_count: int


class AgentSandbox:
    def __init__(self, base_path: Path):
        self.agents_root = Path(base_path) / "memory" / "agents"
        self.agents_root.mkdir(parents=True, exist_ok=True)

    def create(self, name: str) -> None:
        """Create a sandbox for a new agent."""
        path = self.agents_root / name
        path.mkdir(parents=True, exist_ok=True)

    def delete(self, name: str) -> bool:
        """Delete an agent's sandbox. Returns True if existed."""
        path = self.agents_root / name
        if not path.exists():
            return False
        import shutil
        shutil.rmtree(path)
        return True

    def list(self) -> List[AgentInfo]:
        """List all agent sandboxes with metadata."""
        results = []
        for entry in sorted(self.agents_root.iterdir()):
            if not entry.is_dir():
                continue
            raw_path = entry / "raw"
            refined_path = entry / "refined"
            raw_count = len(list(raw_path.glob("*.md"))) if raw_path.exists() else 0
            refined_count = len(list(refined_path.glob("*.md"))) if refined_path.exists() else 0
            results.append(AgentInfo(
                name=entry.name,
                path=entry,
                memory_count=raw_count,
                refined_count=refined_count,
            ))
        return results

    def store_for(self, name: str) -> Optional[MemoryStore]:
        """Get the MemoryStore for an agent's sandbox."""
        path = self.agents_root / name
        if not path.exists():
            return None
        return MemoryStore(path)

    def refined_for(self, name: str) -> Optional[RefinedStore]:
        """Get the RefinedStore for an agent's sandbox."""
        path = self.agents_root / name
        if not path.exists():
            return None
        return RefinedStore(path)

"""Pool registry — multi-namespace memory pools.

~/.omo/
├── personal/          # 个人记忆池 (偏好/习惯/反馈)
├── projects/          # 项目记忆池 (按 git remote hash 隔离)
│   └── {hash}/
├── knowledge/         # 知识库池 (按领域分区)
│   └── {domain}/
├── shared/            # 跨项目共享池
└── config.yaml        # 池权重 + 默认 scope
"""

import hashlib
import subprocess
from pathlib import Path
from typing import Optional, List, Dict

from sisyphus.memory.store import MemoryStore

DEFAULT_CONFIG = {
    "pools": {
        "personal": {"weight": 0.5, "enabled": True},
        "project": {"weight": 0.3, "enabled": True},
        "knowledge": {"weight": 0.1, "enabled": False},
        "shared": {"weight": 0.1, "enabled": True},
    },
    "default_scope": ["personal", "project"],
    "max_raw_per_pool": 1000,
}


class PoolRegistry:
    """Manage multiple memory pools with namespace isolation."""

    def __init__(self, base_path: Optional[Path] = None):
        self.base_path = base_path or Path.home() / ".omo"
        self.config = dict(DEFAULT_CONFIG)

    def init_structure(self):
        """Create namespace directories if they don't exist."""
        for name in ["personal", "projects", "knowledge", "shared"]:
            (self.base_path / name).mkdir(parents=True, exist_ok=True)
        config_file = self.base_path / "config.yaml"
        if not config_file.exists():
            import yaml
            config_file.write_text(yaml.dump(DEFAULT_CONFIG, default_flow_style=False, allow_unicode=True))

    def get_store(self, pool: str, sub: str = "") -> MemoryStore:
        dir_name = {"project": "projects", "knowledge": "knowledge"}.get(pool, pool)
        pool_dir = self.base_path / dir_name / sub if sub else self.base_path / dir_name
        return MemoryStore(pool_dir / "memory")

    def active_pools(self, scope: Optional[List[str]] = None) -> List[str]:
        """Return list of active pool names for given scope."""
        scope = scope or self.config.get("default_scope", ["personal"])
        return [p for p in scope if self.config.get("pools", {}).get(p, {}).get("enabled", False)]

    def current_project_hash(self) -> str:
        """Derive a stable hash from the current git remote URL."""
        try:
            result = subprocess.run(["git", "remote", "get-url", "origin"],
                                    capture_output=True, text=True, timeout=3)
            url = result.stdout.strip()
            if url:
                return hashlib.sha256(url.encode()).hexdigest()[:12]
        except Exception:
            pass
        return "local"

    def project_store(self) -> MemoryStore:
        """Get the MemoryStore for the current project."""
        h = self.current_project_hash()
        return self.get_store("projects", h)

    def import_to_pool(self, pool: str, title: str, content: str, **kwargs):
        """Import a memory into a specific pool."""
        store = self.get_store(pool)
        return store.create_if_new(title=title, content=content, **kwargs)

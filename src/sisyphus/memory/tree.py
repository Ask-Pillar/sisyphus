"""TreeStore — hierarchical memory tree.

Structure:
    tree/
        _meta.json   # fast lookup: node_id → {parent_id, level, title}
        l0.json       # single root node (global summary)
        l1/           # type/cluster summaries  (level 1)
        l2/           # leaf nodes (individual memories, level 2)
"""

import json
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from sisyphus.memory.utils import atomic_write, DirLock


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id(prefix: str = "n") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


@dataclass
class TreeNode:
    id: str
    parent_id: Optional[str]
    level: int  # 0=root, 1=cluster, 2=leaf
    title: str
    summary: str
    children: List[str] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""


class TreeStore:
    """File-based memory tree with atomic meta updates."""

    def __init__(self, base_path: Path):
        self._tree_root = Path(base_path) / "tree"
        self._meta_path = self._tree_root / "_meta.json"
        self._l0_path = self._tree_root / "l0.json"
        self._l1_dir = self._tree_root / "l1"
        self._l2_dir = self._tree_root / "l2"
        self._init_dirs()

    # ── public API ──────────────────────────────────────────────

    def add_leaf(self, parent_l1_id: str, title: str, summary: str = "") -> TreeNode:
        """Add a leaf node under the given L1 parent. Returns the new node."""
        node = TreeNode(
            id=_new_id("mem"),
            parent_id=parent_l1_id,
            level=2,
            title=title,
            summary=summary,
            created_at=_now(),
            updated_at=_now(),
        )
        self._write_node(node)
        self._update_meta_add(node)
        return node

    def get_node(self, node_id: str) -> Optional[TreeNode]:
        path = self._node_path(node_id)
        if not path.exists():
            return None
        return self._read_node(path)

    def get_subtree(self, l1_id: str) -> List[TreeNode]:
        """Return the L1 node and all its leaf children."""
        meta = self._load_meta()
        if l1_id not in meta:
            return []
        l1_node = self.get_node(l1_id)
        if l1_node is None:
            return []
        children = []
        for cid in l1_node.children:
            child = self.get_node(cid)
            if child is not None:
                children.append(child)
        return [l1_node] + children

    def get_path(self, node_id: str) -> List[TreeNode]:
        """Return the ancestor chain from root to the given node."""
        meta = self._load_meta()
        chain: List[TreeNode] = []
        current_id = node_id
        for _ in range(3):  # max depth = 3 (l0→l1→l2)
            info = meta.get(current_id)
            if info is None:
                break
            node = self.get_node(current_id)
            if node is None:
                break
            chain.insert(0, node)
            pid = info.get("parent_id")
            if pid is None:
                break
            current_id = pid
        return chain

    def list_nodes(self, level: Optional[int] = None) -> List[TreeNode]:
        """List all nodes, optionally filtered by level."""
        meta = self._load_meta()
        nodes = []
        for nid in meta:
            if level is not None and meta[nid].get("level") != level:
                continue
            node = self.get_node(nid)
            if node is not None:
                nodes.append(node)
        return sorted(nodes, key=lambda n: n.created_at)

    # ── lazy init ───────────────────────────────────────────────

    def _init_dirs(self, force_l0: bool = True):
        self._tree_root.mkdir(parents=True, exist_ok=True)
        self._l1_dir.mkdir(parents=True, exist_ok=True)
        self._l2_dir.mkdir(parents=True, exist_ok=True)
        if not self._meta_path.exists():
            meta = {}
            if force_l0:
                meta["l0"] = {"parent_id": None, "level": 0, "title": "Memory Root"}
            self._save_meta(meta)
        if force_l0 and not self._l0_path.exists():
            self._write_node(TreeNode(
                id="l0", parent_id=None, level=0,
                title="Memory Root", summary="",
            ))

    # ── meta management ─────────────────────────────────────────

    def _load_meta(self) -> Dict:
        if not self._meta_path.exists():
            return {}
        raw = self._meta_path.read_text()
        if not raw.strip():
            return {}
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            return {}

    def _save_meta(self, meta: Dict):
        atomic_write(self._meta_path, json.dumps(meta, ensure_ascii=False, indent=2))

    def _update_meta_add(self, node: TreeNode):
        with DirLock(self._tree_root / "_lock", "meta", timeout=10):
            meta = self._load_meta()
            meta[node.id] = {"parent_id": node.parent_id, "level": node.level, "title": node.title}
            # Also update parent's children list
            if node.parent_id and node.parent_id in meta:
                parent_node = self.get_node(node.parent_id)
                if parent_node is not None and node.id not in parent_node.children:
                    parent_node.children.append(node.id)
                    self._write_node(parent_node)
            self._save_meta(meta)

    # ── node file I/O ───────────────────────────────────────────

    def _node_path(self, node_id: str) -> Path:
        if node_id == "l0":
            return self._l0_path
        meta = self._load_meta()
        info = meta.get(node_id, {})
        level = info.get("level", 2)
        if level == 1:
            return self._l1_dir / f"{node_id}.json"
        return self._l2_dir / f"{node_id}.json"

    def _write_node(self, node: TreeNode):
        path = self._path_for_level(node.id, node.level)
        path.parent.mkdir(parents=True, exist_ok=True)
        data = asdict(node)
        atomic_write(path, json.dumps(data, ensure_ascii=False, indent=2))

    def _path_for_level(self, node_id: str, level: int) -> Path:
        if node_id == "l0" or level == 0:
            return self._l0_path
        if level == 1:
            return self._l1_dir / f"{node_id}.json"
        return self._l2_dir / f"{node_id}.json"

    def _read_node(self, path: Path) -> Optional[TreeNode]:
        try:
            data = json.loads(path.read_text())
            return TreeNode(**data)
        except (json.JSONDecodeError, KeyError, TypeError):
            return None

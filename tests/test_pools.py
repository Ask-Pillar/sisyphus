"""Tests for pool registry and namespace isolation."""
import pytest
import tempfile
from pathlib import Path
from sisyphus.memory.pools import PoolRegistry


class TestPoolRegistry:
    def test_init_creates_directories(self, tmp_path):
        reg = PoolRegistry(tmp_path / ".omo")
        reg.init_structure()
        assert (tmp_path / ".omo" / "personal").is_dir()
        assert (tmp_path / ".omo" / "projects").is_dir()
        assert (tmp_path / ".omo" / "knowledge").is_dir()
        assert (tmp_path / ".omo" / "shared").is_dir()
        assert (tmp_path / ".omo" / "config.yaml").is_file()

    def test_get_personal_store(self, tmp_path):
        reg = PoolRegistry(tmp_path / ".omo")
        reg.init_structure()
        store = reg.get_store("personal")
        assert store.base_path.name == "memory"
        assert "personal" in str(store.base_path)

    def test_get_project_store(self, tmp_path):
        reg = PoolRegistry(tmp_path / ".omo")
        reg.init_structure()
        store = reg.get_store("projects", "abc123")
        assert "projects" in str(store.base_path)
        assert "abc123" in str(store.base_path)

    def test_pool_isolation(self, tmp_path):
        reg = PoolRegistry(tmp_path / ".omo")
        reg.init_structure()
        s1 = reg.get_store("personal")
        s2 = reg.get_store("shared")
        s1.create(title="only in personal", type="note", content="p")
        s2.create(title="only in shared", type="note", content="s")
        assert len(s1.list()) == 1
        assert len(s2.list()) == 1
        assert s1.list()[0].title == "only in personal"
        assert s2.list()[0].title == "only in shared"

    def test_active_pools(self, tmp_path):
        reg = PoolRegistry(tmp_path / ".omo")
        pools = reg.active_pools(["personal", "project"])
        assert "personal" in pools
        assert "project" in pools

    def test_current_project_hash(self):
        reg = PoolRegistry()
        h = reg.current_project_hash()
        assert len(h) == 12 or h == "local"

    def test_import_to_pool(self, tmp_path):
        reg = PoolRegistry(tmp_path / ".omo")
        reg.init_structure()
        mem = reg.import_to_pool("personal", title="test", content="hello")
        assert mem.id is not None
        assert mem.title == "test"

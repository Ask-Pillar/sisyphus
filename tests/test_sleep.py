import tempfile
from pathlib import Path

from sisyphus.memory.store import MemoryStore
from sisyphus.pipeline.sleep import SleepPipeline


def _create_memories(n=25):
    tmp = Path(tempfile.mkdtemp()) / "mem"
    store = MemoryStore(base_path=tmp)
    for i in range(n):
        store.create(title="test_%d" % i, type="test", content="test content %d" % i, tags=["test"], importance=0.5)
    return tmp


def test_sleep_skipped_below_threshold():
    base = _create_memories(10)
    sp = SleepPipeline(base)
    result = sp.run()
    assert result["status"] == "skipped"


def test_sleep_force_runs_below_threshold():
    base = _create_memories(10)
    sp = SleepPipeline(base)
    result = sp.run(force=True)
    assert "tree" in result


def test_sleep_runs_tree_step():
    base = _create_memories(25)
    sp = SleepPipeline(base)
    result = sp.run(steps=["tree"])
    assert "tree" in result
    assert result["tree"]["status"] == "ok"


def test_sleep_no_llm_skips_dream():
    base = _create_memories(25)
    sp = SleepPipeline(base)
    result = sp.run(steps=["dream"])
    assert "dream" in result
    assert result["dream"]["status"] == "skipped"


def test_sleep_unknown_step_skipped():
    base = _create_memories(25)
    sp = SleepPipeline(base)
    result = sp.run(steps=["nonexistent"])
    assert "nonexistent" in result
    assert result["nonexistent"]["status"] == "skipped"


def test_sleep_idempotent():
    base = _create_memories(25)
    sp = SleepPipeline(base)
    r1 = sp.run(steps=["tree"], force=True)
    r2 = sp.run(steps=["tree"], force=True)
    assert r1["tree"]["status"] == "ok"
    assert r2["tree"]["status"] == "ok"

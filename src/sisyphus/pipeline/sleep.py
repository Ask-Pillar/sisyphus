"""SleepPipeline — unified pipeline with DirLock + 6-step flow + subagent.

Merged from: memory/pipeline.py + pipeline/sleep.py
"""
from pathlib import Path
from typing import Optional, List
from sisyphus.memory.store import MemoryStore
from sisyphus.memory.refined import RefinedStore
from sisyphus.memory.tree import TreeStore
from sisyphus.memory.tree_builder import TreeBuilder
from sisyphus.memory.utils import DirLock


class SleepPipeline:
    """Unified memory processing pipeline with DirLock + logging + subagent.

    Steps: loop → compress → dream → tree → moc → link
    """

    def __init__(
        self,
        base_path: Path,
        compress_threshold: int = 20,
        subagent=None,
    ):
        # Normalize: accept both ~/.omo and ~/.omo/memory
        bp = Path(base_path)
        if bp.name == "memory" or (bp / "INDEX.md").exists():
            memory_path = bp
        else:
            memory_path = bp / "memory"
        memory_path.mkdir(parents=True, exist_ok=True)
        self.base_path = memory_path
        self.compress_threshold = compress_threshold
        self.store = MemoryStore(memory_path)
        self.refined = RefinedStore(memory_path)
        self.tree = TreeStore(memory_path)
        self._lock = DirLock(memory_path / "_lock")

        # Optional: LogStore + SubagentLauncher (lazy import to avoid circular deps)
        self._logger = None
        self._subagent = subagent

    @property
    def logger(self):
        if self._logger is None:
            from sisyphus.memory.log import LogStore
            log_base = self.base_path.parent if self.base_path.name == "memory" else self.base_path
            self._logger = LogStore(log_base)
        return self._logger

    @property
    def subagent(self):
        if self._subagent is None:
            from sisyphus.memory.subagent import SubagentLauncher
            self._subagent = SubagentLauncher(store_path=self.base_path)
        return self._subagent

    def run(
        self,
        steps: Optional[List[str]] = None,
        force: bool = False,
        use_llm: bool = False,
    ) -> dict:
        steps = steps or ["loop", "compress", "dream", "tree", "moc", "link"]
        raw_count = len(self.store.list())

        if raw_count < 20 and not force:
            return {"status": "skipped", "reason": f"RAW < 20 ({raw_count}), use force=True", "results": {}}

        log = self.logger.create_log("pipeline", body=f"Starting: {', '.join(steps)}")
        with self._lock:
            results = {}
            for step in steps:
                try:
                    handler = getattr(self, "_step_" + step, None)
                    if handler:
                        results[step] = handler(use_llm=use_llm)
                    else:
                        results[step] = {"status": "skipped", "reason": "no handler"}
                except Exception as e:
                    results[step] = {"status": "error", "error": str(e)}
            body = " → ".join(f"{k}:{v.get('status','?')}" for k, v in results.items())
            self.logger.update_log(log.id, status="completed", body=body)
            # Return step results at both top-level and nested for backward compat
            out = {"status": "completed", "results": results}
            out.update(results)
            return out

    # ── Steps ──

    def _step_loop(self, **_kw):
        from sisyphus.memory.loop import LoopDetector
        if len(self.store.list()) < 3:
            return {"status": "skipped", "reason": "RAW < 3"}
        loops = LoopDetector(self.store, self.refined).detect()
        return {"status": "ok", "loops_found": len(loops)}

    def _step_compress(self, use_llm=False, **_kw):
        raw = len(self.store.list())
        if raw <= self.compress_threshold:
            return {"status": "skipped", "reason": f"RAW {raw} <= {self.compress_threshold}"}
        if not use_llm:
            return {"status": "skipped", "reason": "use_llm=False"}
        from sisyphus.memory.compression import Compressor
        Compressor(store=self.store, subagent=self.subagent).run()
        return {"status": "ok"}

    def _step_dream(self, use_llm=False, **_kw):
        unprocessed = [m for m in self.store.list() if not m.refined_by]
        if len(unprocessed) < 3:
            return {"status": "skipped", "reason": f"unprocessed < 3 ({len(unprocessed)})"}
        if not use_llm:
            return {"status": "skipped", "reason": "use_llm=False"}
        from sisyphus.memory.dream import DreamEngine
        DreamEngine(store=self.store, refined_store=self.refined, subagent=self.subagent).dream()
        return {"status": "ok"}

    def _step_tree(self, **_kw):
        TreeBuilder(self.tree, self.store, self.refined).build()
        return {"status": "ok"}

    def _step_moc(self, **_kw):
        from sisyphus.memory.moc import MocGenerator
        MocGenerator(self.store, refined_store=self.refined).generate()
        return {"status": "ok"}

    def _should_link(self) -> bool:
        return len(self.store.list()) >= 2

    def _step_link(self, **_kw):
        if len(self.store.list()) < 2:
            return {"status": "skipped", "reason": "RAW < 2"}
        from sisyphus.memory.link import LinkCleaner
        result = LinkCleaner(self.store).clean()
        return {"status": "ok", **result}

    # ── Public guards for auto-trigger ──

    def _should_compress(self) -> bool:
        return len(self.store.list()) > self.compress_threshold

    def _should_dream(self) -> bool:
        unprocessed = [m for m in self.store.list() if not m.refined_by]
        return len(unprocessed) >= 3

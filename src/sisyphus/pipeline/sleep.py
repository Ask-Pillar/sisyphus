from pathlib import Path
from sisyphus.memory.store import MemoryStore
from sisyphus.memory.refined import RefinedStore
from sisyphus.memory.tree import TreeStore
from sisyphus.memory.tree_builder import TreeBuilder
from sisyphus.memory.utils import DirLock


class SleepPipeline:
    def __init__(self, base_path: Path):
        self.base_path = base_path
        self.store = MemoryStore(base_path)
        self.refined = RefinedStore(base_path)
        self.tree = TreeStore(base_path)
        self._lock = DirLock(Path(base_path) / "_lock")

    def run(self, steps=None, force=False, use_llm=False):
        steps = steps or ["loop", "compress", "dream", "tree", "moc", "link"]
        raw_count = len(self.store.list())
        if raw_count < 20 and not force:
            return {"status": "skipped", "reason": "RAW < 20, use force=True"}

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
            return results

    def _step_loop(self, **_kw):
        try:
            from sisyphus.memory.loop import LoopDetector
            loops = LoopDetector(self.store).detect()
            return {"status": "ok", "loops_found": len(loops)}
        except ImportError:
            return {"status": "skipped", "reason": "LoopDetector not available"}

    def _step_compress(self, use_llm=False):
        if not use_llm:
            return {"status": "skipped", "reason": "no LLM, use_llm=False"}
        try:
            from sisyphus.memory.compressor import Compressor
            Compressor(self.store).compress(threshold=20, keep_recent=5)
            return {"status": "ok"}
        except ImportError:
            return {"status": "skipped", "reason": "Compressor not available"}

    def _step_dream(self, use_llm=False):
        if not use_llm:
            return {"status": "skipped", "reason": "no LLM, use_llm=False"}
        try:
            from sisyphus.memory.dream import DreamEngine
            DreamEngine(self.store).reflect_all()
            return {"status": "ok"}
        except ImportError:
            return {"status": "skipped", "reason": "DreamEngine not available"}

    def _step_tree(self, **_kw):
        TreeBuilder(self.tree, self.store, self.refined).build()
        return {"status": "ok"}

    def _step_moc(self, **_kw):
        try:
            from sisyphus.memory.moc import MocGenerator
            MocGenerator(self.store, self.refined).generate()
            return {"status": "ok"}
        except ImportError:
            return {"status": "skipped", "reason": "MocGenerator not available"}

    def _step_link(self, **_kw):
        try:
            from sisyphus.memory.links import LinkCleaner
            LinkCleaner(self.store.base_path).clean()
            return {"status": "ok"}
        except ImportError:
            return {"status": "skipped", "reason": "LinkCleaner not available"}

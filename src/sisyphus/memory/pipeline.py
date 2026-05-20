"""Auto-trigger pipeline for memory processing via subagent."""

from pathlib import Path
from typing import Optional

from sisyphus.memory.store import MemoryStore
from sisyphus.memory.refined import RefinedStore
from sisyphus.memory.moc import MocGenerator
from sisyphus.memory.log import LogStore
from sisyphus.memory.subagent import SubagentLauncher


class Pipeline:
    """Auto-trigger processing pipeline using subagent for LLM work."""

    def __init__(self, base_path: Path, compress_threshold: int = 20, subagent=None):
        self.compress_threshold = compress_threshold
        memory_path = Path(base_path) / "memory"
        self.store = MemoryStore(memory_path)
        self.refined = RefinedStore(memory_path)
        self.logger = LogStore(base_path)
        self.moc = MocGenerator(self.store, refined_store=self.refined)
        self.subagent = subagent or SubagentLauncher(store_path=memory_path)

    def run(self) -> dict:
        """Execute one pipeline cycle. Returns result dict with status and steps."""
        log = self.logger.create_log("pipeline", body="Pipeline cycle started.")
        steps = []
        try:
            if self._should_compress():
                self._run_compress()
                steps.append("compress")
            if self._should_dream():
                self._run_dream()
                steps.append("dream")
            self._run_index()
            steps.append("index")
            if self._should_link():
                self._run_link()
                steps.append("link")
            if self._should_detect_loop():
                self._run_detect_loop()
                steps.append("detect-loop")
            status = "completed"
            body = "Steps: " + ", ".join(steps)
        except Exception as exc:
            status = "failed"
            body = str(exc)
        self.logger.update_log(log.id, status=status, body=body)
        return {"status": status, "steps": steps}

    def _run_detect_loop(self):
        try:
            from sisyphus.memory.loop import LoopDetector

            detector = LoopDetector(self.store, self.refined)
            loops = detector.detect()
            if loops:
                self.logger.create_log(
                    "detect-loop", body=f"Detected {len(loops)} loop(s)."
                )
        except Exception as exc:
            self.logger.create_log("detect-loop", body=f"Loop detect skipped: {exc}")

    def _should_detect_loop(self) -> bool:
        return len(self.store.list()) >= 3

    def _should_compress(self) -> bool:
        raw_count = len(self.store.list())
        return raw_count > self.compress_threshold

    def _run_compress(self):
        try:
            from sisyphus.memory.compression import Compressor

            comp = Compressor(store=self.store, subagent=self.subagent)
            comp.run()
            self.logger.create_log(
                "compress",
                body=f"Compressed store ({self.compress_threshold}+ memories).",
            )
        except Exception as exc:
            self.logger.create_log("compress", body=f"Compress skipped: {exc}")

    def _run_index(self):
        self.moc.generate()
        self.logger.create_log("index", body="INDEX.md regenerated.")

    def _should_dream(self) -> bool:
        unprocessed = [m for m in self.store.list() if not m.refined_by]
        return len(unprocessed) >= 3

    def _run_dream(self):
        try:
            from sisyphus.memory.dream import DreamEngine

            engine = DreamEngine(
                store=self.store, refined_store=self.refined, subagent=self.subagent
            )
            reflections = engine.dream()
            self.logger.create_log(
                "dream",
                body=f"Dream: {len(reflections)} reflections from pipeline.",
            )
        except Exception as exc:
            self.logger.create_log("dream", body=f"Dream skipped: {exc}")

    def _should_link(self) -> bool:
        return len(self.store.list()) >= 2

    def _run_link(self):
        try:
            from sisyphus.memory.link import LinkCleaner

            cleaner = LinkCleaner(self.store)
            result = cleaner.clean()
            self.logger.create_log(
                "link",
                body=f"Link clean: {result['total_cleaned']} memories cleaned.",
            )
        except Exception as exc:
            self.logger.create_log("link", body=f"Link skipped: {exc}")

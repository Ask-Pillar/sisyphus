"""Auto-trigger pipeline for memory processing.

Runs after each conversation turn:
  1. extractMemories (every turn)
  2. Loop detection (every turn - v1.1+)
  3. Trigger detection:
     - RAW count > threshold → compress
     - Last dream > 24h + new sessions >= 5 → dream (v1.1+)
     - Refined changed → index
  4. Structured logging for every step
"""

from pathlib import Path
from typing import Optional

from sisyphus.memory.store import MemoryStore
from sisyphus.memory.refined import RefinedStore
from sisyphus.memory.moc import MocGenerator
from sisyphus.memory.log import LogStore, _now


class Pipeline:
    """Auto-trigger processing pipeline for memory operations."""

    def __init__(self, base_path: Path, compress_threshold: int = 20):
        self.compress_threshold = compress_threshold
        memory_path = Path(base_path) / "memory"
        self.store = MemoryStore(memory_path)
        self.refined = RefinedStore(memory_path)
        self.logger = LogStore(base_path)
        self.moc = MocGenerator(self.store, refined_store=self.refined)

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
            status = "completed"
            body = "Steps: " + ", ".join(steps)
        except Exception as exc:
            status = "failed"
            body = str(exc)
        self.logger.update_log(log.id, status=status, body=body)
        return {"status": status, "steps": steps}

    def _should_compress(self) -> bool:
        raw_count = len(self.store.list())
        return raw_count > self.compress_threshold

    def _run_compress(self):
        try:
            from sisyphus.memory.compression import AnnealCompressor
            from sisyphus.memory.llm import LLMClient
            llm = LLMClient()
            comp = AnnealCompressor(store=self.store, llm_client=llm)
            comp.compress()
            self.logger.create_log("compress", body=f"Compressed store ({self.compress_threshold}+ memories).")
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
            from sisyphus.memory.llm import LLMClient
            llm = LLMClient()
            engine = DreamEngine(store=self.store, refined_store=self.refined, llm_client=llm)
            reflections = engine.dream()
            self.logger.create_log("dream", body=f"Dream: {len(reflections)} reflections from pipeline.")
        except Exception as exc:
            self.logger.create_log("dream", body=f"Dream skipped: {exc}")

    def _should_link(self) -> bool:
        return len(self.store.list()) >= 2

    def _run_link(self):
        try:
            from sisyphus.memory.link import LinkAnalyzer
            analyzer = LinkAnalyzer(self.store)
            pairs = analyzer.analyze()
            self.logger.create_log("link", body=f"Link: {len(pairs)} pairs linked.")
        except Exception as exc:
            self.logger.create_log("link", body=f"Link skipped: {exc}")

"""Memory compression — anneal old memories into one summary via subagent."""

from sisyphus.memory.subagent import SubagentLauncher


class Compressor:
    """Annealing-style compression via subagent subprocess.

    The subagent handles LLM calls + file operations.
    Main process only gets back the deleted count.
    """

    def __init__(self, store, subagent, threshold=20, keep_recent=5):
        self.store = store
        self.subagent = subagent
        self.threshold = threshold
        self.keep_recent = keep_recent

    def run(self):
        all_memories = self.store.list()
        if len(all_memories) <= self.threshold:
            return 0

        result = self.subagent.compress(
            threshold=self.threshold,
            keep_recent=self.keep_recent,
        )
        return result.get("deleted_count", 0)


AnnealCompressor = Compressor  # backward compat for pipeline.py

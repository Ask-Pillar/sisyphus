# ADR-002: Frozen Memory Snapshot

## Status

Accepted (2026-05-20)

## Context

LLM interactions have two competing constraints:

1. **Prefix cache**: System prompt content that doesn't change between turns preserves KV cache, reducing latency and cost. Any change invalidates the cache.
2. **Fresh memories**: The LLM needs access to the most relevant memories for good decisions.

Earlier approaches either loaded all memories fresh each turn (cache-unfriendly) or injected nothing and relied on tool calls (latency per turn).

## Decision

Introduce a **FrozenSnapshot** that:

- Builds once at session start: recalls relevant memories using the LLM side-channel (ADR-001), formats them as a markdown block.
- Caches the result: `build()` returns the cached string on subsequent calls regardless of `query` parameter.
- Injects into the system prompt: the snapshot is part of the prompt prefix, never a mid-turn tool call.
- Never changes mid-session: the LLM always sees the same snapshot, preserving prefix cache across all turns.

This is inspired by Hermes Agent's snapshot approach, but simplified to use the existing LLM-based recall (ADR-001 Recall layer) instead of SQLite FTS5.

## Consequences

### Positive

- **Prefix cache preserved**: snapshot is constant across all turns in a session.
- **Zero per-turn cost**: no tool call or recomputation on each turn.
- **Simple implementation**: ~70 lines, no dependencies beyond existing Recall layer.
- **Configurable caps**: `max_memories` and `max_chars` prevent snapshot bloat.

### Negative

- **Stale by design**: memories created mid-session won't appear until the next session.
- **First-turn latency**: initial `build()` calls LLM for recall (same as any recall operation).
- **Cold start**: new users with no memories get an empty snapshot block.

### Mitigations

- Staleness is acceptable because (a) sessions are short in practice, and (b) the memory tool is still available for ad-hoc operations mid-session.
- Empty snapshot includes a clear "No memories yet" message so the LLM knows the system is working, just empty.
- `reset()` method is available for testing and for scenarios that explicitly want to refresh mid-session (currently unused in production path).

## Implementation

```python
class FrozenSnapshot:
    def __init__(self, recall, max_memories=5, max_chars=2000):
        self._cached = None
        # ...

    def build(self, query="") -> str:
        if self._cached is not None:
            return self._cached
        memories = self.recall.search(query=query, top_k=self.max_memories)
        self._cached = self._format(memories)
        return self._cached
```

## Tests

8 tests covering:

| Test | Validates |
|------|-----------|
| `test_empty_store_returns_empty_snapshot` | No memories → empty block |
| `test_snapshot_includes_memories` | Memories appear in output |
| `test_snapshot_is_deterministic` | Same query → same result |
| `test_snapshot_passes_query_to_recall` | Query forwarded correctly |
| `test_snapshot_respects_max_memories` | Upper bound on memory count |
| `test_snapshot_respects_max_chars` | Upper bound on total chars |
| `test_snapshot_format_is_parseable` | Valid XML-ish markers |
| `test_multiple_builds_same_result` | Cache returns same regardless of query |

"""Subagent — run LLM memory processing in a child process.

Main process → writes task file → spawns child → child does LLM + file IO
→ writes result → parent reads result.

This keeps LLM responses and file operations OUT of the main process context,
so the main agent's context window doesn't get polluted with raw LLM output.
"""

import json
import logging
import os
import subprocess
import sys
import tempfile
from dataclasses import asdict
from pathlib import Path
from typing import Any, List, Optional

from sisyphus.memory.llm import LLMClient
from sisyphus.memory.store import Memory, MemoryStore
from sisyphus.memory.refined import RefinedStore

logger = logging.getLogger(__name__)

# ── Prompt templates (moved from dream.py / compression.py / recall.py) ──

DREAM_PROMPT = """You are a memory reflection system. Analyze the following memories and identify patterns, principles, and insights.

For each insight, return a JSON object with:
- "title": concise insight title (under 80 chars)
- "content": detailed explanation of the pattern/principle
- "importance": 1-10 score for how important this insight is
- "evidence": list of memory IDs that support this insight (can be empty if none match)

Return ONLY valid JSON with this structure:
{{"reflections": [{{"title": "...", "content": "...", "importance": 8, "evidence": ["mem_id1", "mem_id2"]}}]}}

Memories to analyze:
{memories}"""

COMPRESSION_PROMPT = """Compress the following memories into ONE concise summary.
Keep all unique facts, decisions, and patterns. Remove redundancy.

Output valid JSON only: {{"title": "...", "content": "..."}}

Memories to compress:
{text}"""

RECALL_SEARCH_PROMPT = """You are a memory retrieval system. Given a user query and a list of available memories, select the memories that are relevant to the query.

Return ONLY a JSON object with this exact structure:
{{"memory_ids": ["mem_id1", "mem_id2", ...]}}

If no memories are relevant, return {{"memory_ids": []}}

Available memories:
{index}

User query: {query}"""

CLASSIFY_TYPES_PROMPT = """Given a user query and a list of memory types, select which types are relevant to the query.

Return ONLY a JSON object with this exact structure:
{{"types": ["type1", "type2"]}}

If no types are relevant, return {{"types": []}}

Available types: {types}

User query: {query}"""

RECALL_RELEVANT_PROMPT = """Rate the relevance of this memory to the query from 0.0 to 1.0.
Return ONLY a JSON object: {{"relevance": 0.0}}

Memory ({mem_type}): {mem_title}
Content: {mem_content}

Query: {query}
Relevance:"""


# ── SubagentLauncher — main process side ──

class SubagentLauncher:
    """Dispatches LLM memory tasks to a child subprocess.

    The subprocess handles: LLM API calls, response parsing, and file writes.
    The main process only receives a structured summary and does bookkeeping.

    Usage::

        subagent = SubagentLauncher(store_path=Path("/path/to/memory"))
        result = subagent.dream(memories)
        print(result["created_ids"])
    """

    def __init__(self, store_path: Path, fixture_path: Optional[str] = None):
        self.store_path = Path(store_path)
        self.fixture_path = fixture_path

    # ── Public API ──

    def dream(self, memories: List[Memory]) -> dict:
        """Run dream reflection in subagent.

        Subagent creates refined/reflection/*.md files directly.
        Returns::

            {"status": "ok", "created_ids": [...], "reflections": [
                {"id": "ref_xxx", "title": "...", "evidence": [...]}
            ]}
        """
        return self._run("dream", memories=memories)

    def compress(self, threshold: int = 20, keep_recent: int = 5) -> dict:
        """Run compression in subagent.

        Subagent lists store, creates compressed memory, deletes old ones.
        Returns::

            {"status": "ok", "deleted_count": 15, "summary": {"id": ..., "title": ...}}
        """
        return self._run("compress", threshold=threshold, keep_recent=keep_recent)

    def recall_search(self, memories: List[Memory], query: str) -> dict:
        """Run recall search in subagent.

        Returns::

            {"status": "ok", "memory_ids": ["mem_1", "mem_2"]}
        """
        return self._run("recall_search", memories=memories, query=query)

    def recall_relevant(self, memory: Memory, query: str) -> dict:
        """Run relevance scoring in subagent.

        Returns::

            {"status": "ok", "relevance": 0.85}
        """
        return self._run("recall_relevant", memory=memory, query=query)

    def extract_turn(self, turn: str) -> dict:
        """Extract memories from a conversation turn.

        Returns::

            {"status": "ok", "memories": [
                {"type": "decision", "title": "...", "content": "...", "tags": [...]}
            ]}
        """
        return self._run("extract_turn", turn=turn)

    def classify_types(self, types: List[str], query: str) -> dict:
        """Classify which memory types are relevant to a query.

        Returns::

            {"status": "ok", "types": ["lesson", "pattern"]}
        """
        return self._run("classify_types", types=types, query=query)

    # ── Internals ──

    def _serialize(self, value: Any) -> Any:
        """Recursively serialize Memory objects to dicts."""
        if isinstance(value, Memory):
            return asdict(value)
        if isinstance(value, list):
            return [self._serialize(v) for v in value]
        return value

    def _run(self, task_type: str, **kwargs) -> dict:
        """Write task → spawn subprocess → read result → cleanup."""
        # Build task payload
        task: dict = {
            "task_type": task_type,
            "store_path": str(self.store_path),
        }
        for k, v in kwargs.items():
            task[k] = self._serialize(v)

        # Write to temp file
        fd, task_path = tempfile.mkstemp(suffix=".json", prefix="sisyphus_task_")
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(task, f)

            # Ensure subprocess can find the sisyphus package
            env = os.environ.copy()
            _src_dir = str(Path(__file__).resolve().parent.parent.parent)
            env.setdefault("PYTHONPATH", _src_dir)
            existing = env.get("PYTHONPATH", "")
            if _src_dir not in existing.split(":"):
                env["PYTHONPATH"] = f"{_src_dir}:{existing}" if existing else _src_dir

            # Spawn subprocess
            cmd = [sys.executable, "-m", "sisyphus.memory.subagent", task_path]
            if self.fixture_path:
                cmd.extend(["--fixture", self.fixture_path])
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120,
                env=env,
            )

            if proc.returncode != 0:
                err = proc.stderr.strip() or f"exit code {proc.returncode}"
                return {"status": "error", "message": err}

            # Read result
            result_path = task_path + ".result"
            if not os.path.exists(result_path):
                return {"status": "error", "message": "Subagent produced no result file"}

            with open(result_path, "r") as f:
                return json.load(f)

        except FileNotFoundError:
            return {"status": "error", "message": "Python interpreter not found"}
        except subprocess.TimeoutExpired:
            return {"status": "error", "message": "Subagent timed out"}
        except json.JSONDecodeError:
            return {"status": "error", "message": "Subagent returned invalid JSON"}
        except Exception as exc:
            return {"status": "error", "message": f"{type(exc).__name__}: {exc}"}
        finally:
            # Cleanup temp files
            for p in (task_path, task_path + ".result"):
                try:
                    os.unlink(p)
                except OSError:
                    pass


# ═══════════════════════════════════════════════════════════════════════════════
# Subprocess entrypoint — runs when called as ``python -m sisyphus.memory.subagent``
# ═══════════════════════════════════════════════════════════════════════════════

def _load_task(task_path: str) -> tuple:
    """Parse task file and deserialize Memory fields.

    Returns (task_type, store_path, memories, memory, rest).
    """
    with open(task_path, "r") as f:
        task = json.load(f)

    task_type = task.pop("task_type", None)
    store_path = task.pop("store_path", None)

    memories_raw = task.pop("memories", None)
    memories: List[Memory] = [Memory(**m) for m in memories_raw] if memories_raw else []

    memory_raw = task.pop("memory", None)
    memory: Optional[Memory] = Memory(**memory_raw) if memory_raw else None

    return task_type, store_path, memories, memory, task


def main():
    """Entrypoint for subagent subprocess.

    Signature::

        python -m sisyphus.memory.subagent <task.json> [--fixture <fixture.json>]

    With --fixture, reads canned responses from the fixture file instead of
    calling LLM. The fixture maps task_type → result dict::

        {"dream": {"status":"ok","reflections":[...]},
         "recall_search": {"status":"ok","memory_ids":[...]}, ...}

    Writes result to ``<task.json>.result``.
    """
    if len(sys.argv) < 2:
        sys.stderr.write("Usage: python -m sisyphus.memory.subagent <task.json> [--fixture <fixture.json>]\n")
        sys.exit(1)

    task_path = sys.argv[1]
    fixture_path = None
    if len(sys.argv) >= 4 and sys.argv[2] == "--fixture":
        fixture_path = sys.argv[3]

    task_type, store_path, memories, memory, rest = _load_task(task_path)

    if fixture_path:
        try:
            with open(fixture_path, "r") as f:
                fixtures = json.load(f)
            result = fixtures.get(task_type)
            if result is None:
                result = {"status": "error", "message": f"No fixture for task_type={task_type}"}
        except Exception as exc:
            result = {"status": "error", "message": f"Fixture error: {type(exc).__name__}: {exc}"}
    else:
        try:
            if task_type == "dream":
                result = _handle_dream(Path(store_path), memories)
            elif task_type == "compress":
                result = _handle_compress(
                    Path(store_path),
                    threshold=rest.get("threshold", 20),
                    keep_recent=rest.get("keep_recent", 5),
                )
            elif task_type == "recall_search":
                result = _handle_recall_search(memories, rest.get("query", ""))
            elif task_type == "recall_relevant":
                result = _handle_recall_relevant(memory, rest.get("query", ""))
            elif task_type == "classify_types":
                result = _handle_classify_types(rest.get("types", []), rest.get("query", ""))
            else:
                result = {"status": "error", "message": f"Unknown task type: {task_type}"}
        except Exception as exc:
            result = {"status": "error", "message": f"{type(exc).__name__}: {exc}"}

    result_path = task_path + ".result"
    with open(result_path, "w") as f:
        json.dump(result, f)


# ═══════════════════════════════════════════════════════════════════════════════
# Task handlers — run inside the subprocess
# ═══════════════════════════════════════════════════════════════════════════════

def _handle_dream(store_path: Path, memories: List[Memory]) -> dict:
    llm = LLMClient()
    lines = []
    for m in memories:
        tags = f" [{', '.join(m.tags)}]" if m.tags else ""
        lines.append(f"[{m.id}] ({m.type}) {m.title}{tags}")
        if m.content:
            lines.append(f"    {m.content[:200]}")
    formatted = "\n".join(lines)
    prompt = DREAM_PROMPT.format(memories=formatted)

    try:
        raw = llm.chat([
            {"role": "system", "content": "You are a memory reflection system."},
            {"role": "user", "content": prompt},
        ])
    except RuntimeError as e:
        return {"status": "skipped", "message": str(e), "created_ids": [], "reflections": []}

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {"status": "ok", "created_ids": [], "reflections": [],
                "message": "LLM returned invalid JSON"}
    reflections_data = data.get("reflections", [])
    if not reflections_data:
        return {"status": "ok", "created_ids": [], "reflections": []}

    refined = RefinedStore(store_path)
    created = []
    for rd in reflections_data:
        mem = refined.create_reflection(
            title=rd.get("title", "Untitled"),
            content=rd.get("content", ""),
            evidence=rd.get("evidence", []),
            importance=rd.get("importance", 5),
            input_count=len(memories),
            llm_calls=1,
        )
        created.append({"id": mem.id, "title": mem.title, "evidence": mem.evidence})

    return {
        "status": "ok",
        "created_ids": [c["id"] for c in created],
        "reflections": created,
    }


def _handle_compress(store_path: Path, threshold: int = 20, keep_recent: int = 5) -> dict:
    llm = LLMClient()
    store = MemoryStore(store_path)

    all_memories = store.list()
    if len(all_memories) <= threshold:
        return {"status": "ok", "deleted_count": 0, "summary": None}

    sorted_mems = sorted(all_memories, key=lambda m: m.created_at or "")
    old_mems = sorted_mems[:-keep_recent]
    if not old_mems:
        return {"status": "ok", "deleted_count": 0, "summary": None}

    lines = []
    for m in old_mems:
        lines.append(f"[{m.created_at[:10]}] ({m.type}) {m.title}")
        lines.append(m.content[:500])
        lines.append("---")
    text = "\n".join(lines)

    try:
        response = llm.chat(messages=[
            {"role": "system", "content": "You are a memory summarizer."},
            {"role": "user", "content": COMPRESSION_PROMPT.format(text=text)},
        ])
        data = json.loads(response)
    except RuntimeError as e:
        return {"status": "skipped", "message": str(e), "deleted_count": 0, "summary": None}
    except Exception as e:
        return {"status": "error", "message": str(e), "deleted_count": 0, "summary": None}

    summary = store.create(
        title="[compressed] " + data.get("title", "Untitled"),
        type="compressed",
        content=data.get("content", ""),
    )

    deleted_ids = [m.id for m in old_mems]
    for m in old_mems:
        store.delete(m.id)

    return {
        "status": "ok",
        "deleted_count": len(old_mems),
        "summary": {"id": summary.id, "title": summary.title},
        "deleted_ids": deleted_ids,
    }


def _handle_recall_search(memories: List[Memory], query: str) -> dict:
    if not memories or not query.strip():
        return {"status": "ok", "memory_ids": []}

    llm = LLMClient()
    lines = []
    for m in memories:
        created = m.created_at[:10] if m.created_at else ""
        tags = f" [{', '.join(m.tags)}]" if m.tags else ""
        lines.append(f"- {m.id} | type={m.type} | {m.title}{tags} | {created}")
    index_text = "\n".join(lines)
    prompt = RECALL_SEARCH_PROMPT.format(index=index_text, query=query)

    try:
        response = llm.chat([
            {"role": "system", "content": "You are a precise memory retrieval system. Respond only with valid JSON."},
            {"role": "user", "content": prompt},
        ])
    except RuntimeError as e:
        return {"status": "skipped", "message": str(e), "memory_ids": []}

    response = response.strip()
    if response.startswith("```"):
        response = response.split("\n", 1)[-1]
        response = response.rsplit("\n", 1)[0] if "```" in response else response
    try:
        data = json.loads(response)
        return {"status": "ok", "memory_ids": data.get("memory_ids", [])}
    except json.JSONDecodeError:
        return {"status": "ok", "memory_ids": [], "message": "LLM returned invalid JSON"}


def _handle_recall_relevant(memory: Optional[Memory], query: str) -> dict:
    if not memory or not query.strip():
        return {"status": "ok", "relevance": 0.0}

    llm = LLMClient()
    prompt = RECALL_RELEVANT_PROMPT.format(
        mem_type=memory.type,
        mem_title=memory.title,
        mem_content=memory.content[:200],
        query=query,
    )

    try:
        response = llm.chat([{"role": "user", "content": prompt}])
    except RuntimeError as e:
        return {"status": "skipped", "message": str(e), "relevance": 0.0}

    try:
        data = json.loads(response.strip())
        return {"status": "ok", "relevance": float(data.get("relevance", 0.0))}
    except (json.JSONDecodeError, ValueError, TypeError):
        return {"status": "ok", "relevance": 0.0, "message": "LLM returned invalid relevance"}


def _handle_classify_types(types: List[str], query: str) -> dict:
    if not types or not query.strip():
        return {"status": "ok", "types": list(types)}

    llm = LLMClient()
    prompt = CLASSIFY_TYPES_PROMPT.format(types=", ".join(types), query=query)

    try:
        response = llm.chat([
            {"role": "system", "content": "You are a precise type classifier. Respond only with valid JSON."},
            {"role": "user", "content": prompt},
        ])
    except RuntimeError as e:
        return {"status": "skipped", "message": str(e), "types": list(types)}

    response = response.strip()
    if response.startswith("```"):
        response = response.split("\n", 1)[-1]
        response = response.rsplit("\n", 1)[0] if "```" in response else response
    try:
        data = json.loads(response)
        selected = data.get("types", [])
        valid = [t for t in selected if t in types]
        return {"status": "ok", "types": valid}
    except (json.JSONDecodeError, ValueError):
        return {"status": "ok", "types": list(types), "message": "LLM returned invalid JSON, fell back to all types"}


if __name__ == "__main__":
    main()

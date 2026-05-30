"""MCP stdio server for Sisyphus memory.

Usage:
    PYTHONPATH=src python -m sisyphus.server.mcp

Then configure in any MCP client:
    {
        "mcpServers": {
            "sisyphus": {
                "command": "python",
                "args": ["-m", "sisyphus.server.mcp"],
                "env": {"PYTHONPATH": "src"}
            }
        }
    }
"""

import json
import sys
import traceback
from pathlib import Path
from typing import Any, Callable, Dict

from sisyphus.memory.store import MemoryStore
from sisyphus.memory.refined import RefinedStore
from sisyphus.memory.tree import TreeStore
from sisyphus.memory.tree_builder import TreeBuilder
from sisyphus.memory.retrieval import ContextRetriever
from sisyphus.memory.retrieval import BM25Ranker
from sisyphus.pipeline.sleep import SleepPipeline

STORE_PATH = Path.home() / ".omo" / "memory"

_store = None
_refined = None
_tree = None
_retriever = None


def _setup():
    global _store, _refined, _tree, _retriever
    if _retriever is not None:
        return
    _store = MemoryStore(base_path=STORE_PATH)
    _refined = RefinedStore(base_path=STORE_PATH)
    _tree = TreeStore(base_path=STORE_PATH)
    if not _tree.list_nodes(level=1):
        TreeBuilder(_tree, _store, _refined).build()
    _retriever = ContextRetriever(_store, _refined, subagent=None, tree=_tree)


def _handle_write(args: Dict[str, Any]) -> Dict[str, Any]:
    title = args["title"]
    mem_type = args.get("type", "note")
    content = args.get("content", "")
    tags = args.get("tags", [])
    importance = args.get("importance", 5)
    _setup()
    mem = _store.create_if_new(title=title, type=mem_type, content=content, tags=tags, importance=importance)
    return {"id": mem.id, "title": mem.title, "types": mem.types}


def _handle_search(args: Dict[str, Any]) -> Dict[str, Any]:
    query = args.get("query", "")
    top_k = args.get("top_k", 5)
    _setup()
    results = _retriever.retrieve(query, top_k=top_k)
    items = [{"title": m.title, "types": m.types, "content": m.content[:200], "tags": m.tags} for m, s in results]
    return {"results": items, "count": len(items)}


def _handle_context(args: Dict[str, Any]) -> Dict[str, Any]:
    _setup()
    results = _retriever.retrieve("", top_k=8)
    items = [{"title": m.title, "types": m.types} for m, s in results]
    return {"context": items, "count": len(items)}


def _handle_stats(args: Dict[str, Any]) -> Dict[str, Any]:
    _setup()
    all_mems = _store.list()
    refined_mems = _refined.list_refined()
    by_type = {}
    for m in all_mems + refined_mems:
        for t in (m.types or []):
            by_type[t] = by_type.get(t, 0) + 1
    return {
        "total_raw": len(all_mems),
        "total_refined": len(refined_mems),
        "by_type": by_type,
    }


def _handle_get(args: Dict[str, Any]) -> Dict[str, Any]:
    mem_id = args["id"]
    _setup()
    mem = _store.get(mem_id)
    if mem is None:
        return {"error": f"Memory {mem_id} not found"}
    return {
        "id": mem.id, "types": mem.types, "title": mem.title,
        "content": mem.content, "tags": mem.tags,
        "importance": mem.importance, "status": mem.status,
        "created_at": mem.created_at, "updated_at": mem.updated_at,
    }


def _handle_list(args: Dict[str, Any]) -> Dict[str, Any]:
    type_filter = args.get("type", None)
    _setup()
    mems = _store.list()
    refined = _refined.list_refined()
    seen_ids = set()
    all_mems = []
    for m in mems + [m for m in refined if type_filter is None or (m.types and type_filter in m.types)]:
        if m.id not in seen_ids:
            seen_ids.add(m.id)
            all_mems.append(m)
    return {
        "total": len(all_mems),
        "memories": [
            {"id": m.id, "types": m.types, "title": m.title, "importance": m.importance, "created_at": m.created_at}
            for m in all_mems
        ],
    }


def _handle_delete(args: Dict[str, Any]) -> Dict[str, Any]:
    mem_id = args["id"]
    _setup()
    _store.delete(mem_id)
    return {"deleted": mem_id}


def _handle_import(args: Dict[str, Any]) -> Dict[str, Any]:
    _setup()
    from sisyphus.server.importer import import_memories
    source = args.get("path", "")
    result = import_memories(_store, source)
    return result


def _handle_import_knowledge(args: Dict[str, Any]) -> Dict[str, Any]:
    """Import documents into the knowledge base pool."""
    from sisyphus.memory.knowledge import KnowledgeBase
    domain = args.get("domain", "default")
    source = args.get("path", "")
    kb = KnowledgeBase(domain=domain)
    if not source:
        return {"error": "path is required"}
    import os
    if os.path.isdir(source):
        return kb.import_directory(source, recursive=args.get("recursive", True))
    return {"chunks": kb.import_file(source)}


def _handle_pipeline(args: Dict[str, Any]) -> Dict[str, Any]:
    _setup()
    pipeline = SleepPipeline(STORE_PATH)
    force = args.get("force", False)
    use_llm = args.get("use_llm", False)
    result = pipeline.run(force=force, use_llm=use_llm)
    return result


def _handle_rate(args: Dict[str, Any]) -> Dict[str, Any]:
    _setup()
    mem_id = args["id"]
    score = args["score"]
    ok = _store.rate(mem_id, score)
    return {"rated": mem_id, "score": score} if ok else {"error": "memory not found"}


def _handle_dismiss(args: Dict[str, Any]) -> Dict[str, Any]:
    _setup()
    mem_id = args["id"]
    ok = _store.dismiss(mem_id)
    return {"dismissed": mem_id} if ok else {"error": "memory not found"}


def _handle_switch_scope(args: Dict[str, Any]) -> Dict[str, Any]:
    from sisyphus.memory.pools import PoolRegistry
    registry = PoolRegistry()
    scope = args.get("scope", ["personal", "project"])
    pools = registry.active_pools(scope)
    return {"active_pools": pools, "scope": scope}


def _handle_list_pools(args: Dict[str, Any]) -> Dict[str, Any]:
    from sisyphus.memory.pools import PoolRegistry
    registry = PoolRegistry()
    all_pools = registry.config.get("pools", {})
    return {
        "pools": {k: {"weight": v["weight"], "enabled": v["enabled"]} for k, v in all_pools.items()},
        "active": registry.active_pools(),
    }


TOOLS: Dict[str, Dict[str, Any]] = {
    "write_memory": {
        "description": "记录一条新记忆",
        "inputSchema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "记忆标题"},
                "type": {"type": "string", "description": "记忆类型（lesson/pattern/note/idea 等）"},
                "content": {"type": "string", "description": "记忆内容"},
                "tags": {"type": "array", "items": {"type": "string"}},
                "importance": {"type": "integer", "description": "重要性 1-10"},
            },
            "required": ["title"],
        },
    },
    "search_memory": {
        "description": "搜索相关记忆，返回上下文块和记忆列表",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "搜索关键词"},
                "top_k": {"type": "integer", "description": "返回条数上限"},
            },
        },
    },
    "get_context": {
        "description": "获取当前查询相关的记忆上下文块（<sisyphus_context>），用于注入 agent prompt",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "当前对话内容"},
            },
        },
    },
    "memory_stats": {
        "description": "查看记忆统计概览",
        "inputSchema": {"type": "object", "properties": {}},
    },
    "get_memory": {
        "description": "根据 ID 获取单条记忆详情",
        "inputSchema": {
            "type": "object",
            "properties": {
                "id": {"type": "string", "description": "记忆 ID"},
            },
            "required": ["id"],
        },
    },
    "list_memories": {
        "description": "列出所有记忆，可按类型过滤",
        "inputSchema": {
            "type": "object",
            "properties": {
                "type": {"type": "string", "description": "可选，按类型过滤"},
            },
        },
    },
    "delete_memory": {
        "description": "删除一条记忆",
        "inputSchema": {
            "type": "object",
            "properties": {
                "id": {"type": "string", "description": "要删除的记忆 ID"},
            },
            "required": ["id"],
        },
    },
    "run_pipeline": {
        "description": "执行离线巩固流水线（Sleep Pipeline）",
        "inputSchema": {
            "type": "object",
            "properties": {
                "force": {"type": "boolean", "description": "强制运行（即使 RAW < 20）"},
                "use_llm": {"type": "boolean", "description": "启用 LLM（Dream+Compress）"},
            },
        },
    },
    "import_memories": {
        "description": "一键导入历史记忆（.md 文件 / .jsonl 文件 / 目录扫描）",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "文件路径或目录路径"},
            },
            "required": ["path"],
        },
    },
    "import_knowledge": {
        "description": "导入文档到知识库（.md/.txt/.jsonl/.csv → SQLite FTS5）",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "文件或目录路径"},
                "domain": {"type": "string", "description": "知识领域（默认 default）"},
                "recursive": {"type": "boolean", "description": "目录递归导入（默认 true）"},
            },
            "required": ["path"],
        },
    },
    "rate_memory": {
        "description": "给记忆打分 (1-5)，影响排序权重",
        "inputSchema": {
            "type": "object",
            "properties": {
                "id": {"type": "string", "description": "记忆 ID"},
                "score": {"type": "integer", "description": "评分 1-5"},
            },
            "required": ["id", "score"],
        },
    },
    "dismiss_memory": {
        "description": "不再推荐这条记忆",
        "inputSchema": {
            "type": "object",
            "properties": {
                "id": {"type": "string", "description": "要屏蔽的记忆 ID"},
            },
            "required": ["id"],
        },
    },
    "switch_scope": {
        "description": "切换检索范围",
        "inputSchema": {
            "type": "object",
            "properties": {
                "scope": {"type": "array", "items": {"type": "string"}, "description": "激活的池列表"},
            },
        },
    },
    "list_pools": {
        "description": "列出所有池及其状态",
        "inputSchema": {"type": "object", "properties": {}},
    },
}

HANDLERS: Dict[str, Callable] = {
    "write_memory": _handle_write,
    "search_memory": _handle_search,
    "get_context": _handle_context,
    "memory_stats": _handle_stats,
    "get_memory": _handle_get,
    "list_memories": _handle_list,
    "delete_memory": _handle_delete,
    "run_pipeline": _handle_pipeline,
    "import_memories": _handle_import,
    "import_knowledge": _handle_import_knowledge,
    "rate_memory": _handle_rate,
    "dismiss_memory": _handle_dismiss,
    "switch_scope": _handle_switch_scope,
    "list_pools": _handle_list_pools,
}


def _send(msg: Dict[str, Any]):
    line = json.dumps(msg, ensure_ascii=False)
    sys.stdout.write(line + "\n")
    sys.stdout.flush()


def _handle_request(msg: Dict[str, Any]):
    req_id = msg.get("id")
    method = msg.get("method", "")
    params = msg.get("params", {}) or {}

    if method == "initialize":
        _send({
            "jsonrpc": "2.0", "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "serverInfo": {"name": "sisyphus-memory", "version": "1.0"},
                "capabilities": {"tools": {}},
            },
        })
        return

    if method == "notifications/initialized":
        return

    if method == "tools/list":
        _send({
            "jsonrpc": "2.0", "id": req_id,
            "result": {"tools": [
                {"name": k, **v} for k, v in TOOLS.items()
            ]},
        })
        return

    if method == "tools/call":
        name = params.get("name", "")
        arguments = params.get("arguments", {})
        handler = HANDLERS.get(name)
        if not handler:
            _send({
                "jsonrpc": "2.0", "id": req_id,
                "error": {"code": -32601, "message": f"Unknown tool: {name}"},
            })
            return
        try:
            result = handler(arguments)
            _send({
                "jsonrpc": "2.0", "id": req_id,
                "result": {
                    "content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False, indent=2)}],
                },
            })
        except Exception as e:
            _send({
                "jsonrpc": "2.0", "id": req_id,
                "error": {"code": -32603, "message": str(e)},
            })
        return

    _send({
        "jsonrpc": "2.0", "id": req_id,
        "error": {"code": -32601, "message": f"Unknown method: {method}"},
    })


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
            _handle_request(msg)
        except json.JSONDecodeError:
            continue
        except Exception:
            traceback.print_exc(file=sys.stderr)


if __name__ == "__main__":
    main()

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
from sisyphus.memory.context import AgentMemory
from sisyphus.memory.subagent import SubagentLauncher
from sisyphus.memory.pipeline import Pipeline

STORE_PATH = Path.home() / ".omo" / "memory"

# Module-level singleton, initialised once on first use
_agent: AgentMemory = None


def _setup() -> AgentMemory:
    global _agent
    if _agent is not None:
        return _agent
    store = MemoryStore(base_path=STORE_PATH)
    refined = RefinedStore(base_path=STORE_PATH)
    subagent = SubagentLauncher(store_path=STORE_PATH)
    _agent = AgentMemory(store, refined, subagent=subagent)
    return _agent


def _handle_write(args: Dict[str, Any]) -> Dict[str, Any]:
    title = args["title"]
    mem_type = args.get("type", "note")
    content = args.get("content", "")
    tags = args.get("tags", [])
    importance = args.get("importance", 5)
    agent = _setup()
    mem = agent.record(title=title, type=mem_type, content=content, tags=tags, importance=importance)
    return {"id": mem.id, "title": mem.title, "type": mem.type}


def _handle_search(args: Dict[str, Any]) -> Dict[str, Any]:
    query = args.get("query", "")
    top_k = args.get("top_k", 8)
    agent = _setup()
    ctx = agent.before_turn(query=query)
    results = agent.retriever.retrieve(query=query, top_k=top_k)
    return {
        "context": ctx,
        "results": [
            {
                "id": m.id, "type": m.type, "title": m.title,
                "content": m.content[:200], "importance": m.importance,
                "score": round(float(s), 4),
            }
            for m, s in results
        ],
    }


def _handle_context(args: Dict[str, Any]) -> Dict[str, Any]:
    query = args.get("query", "")
    top_k = args.get("top_k", 8)
    agent = _setup()
    ctx = agent.before_turn(query=query)
    return {"context": ctx}


def _handle_stats(args: Dict[str, Any]) -> Dict[str, Any]:
    agent = _setup()
    store = agent.store
    refined = agent.refined
    all_mems = store.list()
    refined_mems = refined.list_refined()
    by_type = {}
    for m in all_mems + refined_mems:
        by_type[m.type] = by_type.get(m.type, 0) + 1
    return {
        "total_raw": len(all_mems),
        "total_refined": len(refined_mems),
        "by_type": by_type,
    }


def _handle_get(args: Dict[str, Any]) -> Dict[str, Any]:
    mem_id = args["id"]
    agent = _setup()
    mem = agent.store.get(mem_id)
    if mem is None:
        return {"error": f"Memory {mem_id} not found"}
    return {
        "id": mem.id, "type": mem.type, "title": mem.title,
        "content": mem.content, "tags": mem.tags,
        "importance": mem.importance, "status": mem.status,
        "created_at": mem.created_at, "updated_at": mem.updated_at,
    }


def _handle_list(args: Dict[str, Any]) -> Dict[str, Any]:
    type_filter = args.get("type", None)
    agent = _setup()
    mems = agent.store.list(type_filter=type_filter)
    refined = agent.refined.list_refined()
    seen_ids = set()
    all_mems = []
    for m in mems + [m for m in refined if type_filter is None or m.type == type_filter]:
        if m.id not in seen_ids:
            seen_ids.add(m.id)
            all_mems.append(m)
    return {
        "total": len(all_mems),
        "memories": [
            {
                "id": m.id, "type": m.type, "title": m.title,
                "importance": m.importance, "created_at": m.created_at,
            }
            for m in all_mems
        ],
    }


def _handle_delete(args: Dict[str, Any]) -> Dict[str, Any]:
    mem_id = args["id"]
    agent = _setup()
    agent.store.delete(mem_id)
    return {"deleted": mem_id}


def _handle_pipeline(args: Dict[str, Any]) -> Dict[str, Any]:
    agent = _setup()
    pipeline = Pipeline(base_path=STORE_PATH.parent, subagent=agent.subagent)
    result = pipeline.run()
    return result


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
        "description": "执行记忆流水线（压缩、梦境、索引、链接、循环检测）",
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

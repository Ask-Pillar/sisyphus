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

STORE_PATH = Path.home() / ".omo" / "memory"


def _setup() -> AgentMemory:
    store = MemoryStore(base_path=STORE_PATH)
    refined = RefinedStore(base_path=STORE_PATH)
    subagent = SubagentLauncher(store_path=STORE_PATH)
    return AgentMemory(store, refined, subagent=subagent)


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
    store = agent.store
    results = []
    for m in store.list():
        if not query or query.lower() in m.title.lower() or query.lower() in m.content.lower():
            results.append({
                "id": m.id, "type": m.type, "title": m.title,
                "content": m.content[:200], "importance": m.importance,
            })
            if len(results) >= top_k:
                break
    return {
        "context": ctx,
        "results": results,
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
}

HANDLERS: Dict[str, Callable] = {
    "write_memory": _handle_write,
    "search_memory": _handle_search,
    "get_context": _handle_context,
    "memory_stats": _handle_stats,
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

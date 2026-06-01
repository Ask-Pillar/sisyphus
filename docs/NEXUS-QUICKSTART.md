# Nexus 快速搭建方案 — 基于现有系统

## 原则

- 不动 sisyphus 一行代码
- 就用现有组件组装
- 今天开始，本周能跑

## 第一步：创建 nexus 项目结构

```bash
mkdir nexus && cd nexus
git init
git submodule add git@github.com:Ask-Pillar/sisyphus.git
```

```
nexus/
├── sisyphus/              ← git submodule（不动）
├── nexus/
│   ├── __init__.py
│   ├── core.py            ← 调度层（~100行）
│   └── protocol.py        ← 模块协议（~30行）
├── server/
│   └── mcp.py             ← 新 MCP Server（复制+扩展）
├── web/
│   └── ingest.py          ← Web Ingest 端点（~50行）
├── pyproject.toml
├── config/
│   └── nexus.yaml
└── README.md
```

## 第二步：调度层（nexus/core.py）

直接复用 sisyphus 的 UnifiedRetriever，不改它，只加一个薄包装：

```python
# nexus/core.py
import sys
sys.path.insert(0, "sisyphus/src")

from sisyphus.memory.unified import UnifiedRetriever
from sisyphus.memory.pools import PoolRegistry

class NexusCore:
    def __init__(self):
        self.registry = PoolRegistry()
        self.registry.init_structure()
        self.retriever = UnifiedRetriever()

    def search(self, query, scope=None, top_k=10):
        return self.retriever.retrieve(query, scope, top_k)

    def get_context(self, query, max_chars=3000):
        # 复用 sisyphus AgentMemory.build 逻辑
        from sisyphus.memory.context import AgentMemory
        from sisyphus.memory.store import MemoryStore
        store = self.registry.get_store("personal")
        mem = AgentMemory(store)
        return mem.before_turn(query, max_chars)
```

零新代码——全是现成的。调度层就是 `sisyphus.*` 的方法别名。

## 第三步：MCP Server（server/mcp.py）

复制 `sisyphus/src/sisyphus/server/mcp.py`，加三个新工具：

```python
TOOLS = {
    # sisyphus 原有的 14 个不变
    "search_memory": {...},
    "write_memory": {...},
    # ...

    # Nexus 新增
    "get_context": {
        "description": "获取编译后的记忆上下文（Agent 直接使用）",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "max_chars": {"type": "integer", "default": 3000},
            },
            "required": ["query"],
        },
    },
    "ingest_text": {
        "description": "接收外部文本，自动提取并存储",
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {"type": "string"},
                "source": {"type": "string"},
            },
            "required": ["text"],
        },
    },
}
```

HANDLERS 加对应的处理函数，每个 ~5 行。

## 第四步：Web Ingest（web/ingest.py）

```python
# web/ingest.py
from aiohttp import web
from nexus.core import NexusCore

core = NexusCore()

async def handle_ingest(request):
    data = await request.json()
    text = data.get("text", "")
    source = data.get("source", "web")
    # 调 sisyphus Extractor 自动提取
    core.ingest(text, source)
    return web.json_response({"status": "ok"})

app = web.Application()
app.router.add_post("/ingest", handle_ingest)
web.run_app(app, port=8765)
```

## 第五步：配置（config/nexus.yaml）

```yaml
modules:
  sisyphus:
    enabled: true
    weight: 1.0
    submodule_path: sisyphus/

server:
  mcp_port: 0        # stdio
  ingest_port: 8765   # HTTP

pools:
  personal: {enabled: true, weight: 0.5}
  project: {enabled: true, weight: 0.3}
  knowledge: {enabled: true, weight: 0.2}
  shared: {enabled: true, weight: 0.1}
```

## 第六步：pyproject.toml

```toml
[project]
name = "nexus"
version = "0.1.0"
dependencies = ["sisyphus @ file://./sisyphus", "aiohttp", "pyyaml"]

[project.scripts]
nexus-serve = "nexus.server.mcp:main"
```

## 总体时间线

| 步骤 | 工作量 | 说明 |
|------|--------|------|
| 项目骨架 | 10 分钟 | mkdir + git submodule + pyproject.toml |
| nexus/core.py | 20 分钟 | ~100 行，全是 sisyphus 方法别名 |
| server/mcp.py | 30 分钟 | 复制 sisyphus MCP + 加 2 个工具 |
| web/ingest.py | 15 分钟 | ~50 行 aiohttp |
| config + 测试 | 30 分钟 | 验证 sisyphus 408 测试不变 |
| Docker | 15 分钟 | Dockerfile + docker-compose.yml |
| **总计** | **2 小时** | 从零到能跑 |

## 不做的

- 不改 sisyphus 代码 —— submodule 只读
- 不创建新的存储引擎 —— 底层全是 sisyphus SQLiteMemoryStore
- 不实现 semantic / procedural —— 先跑通核心调度，后面慢慢加
- 不写新测试框架 —— 复用 sisyphus pytest，加 5 个核心测试

## 验证

```bash
cd nexus
python3 -c "from nexus.core import NexusCore; c = NexusCore(); c.search('test')"  # 不报错
python3 -m pytest sisyphus/tests/ --ignore=sisyphus/tests/test_bge_reranker.py   # 408 全过
curl -X POST localhost:8765/ingest -d '{"text":"test memory","source":"test"}'    # 200 OK
```

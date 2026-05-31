# Sisyphus 使用手册

## CLI 命令

```bash
# 记录记忆
python3 -m sisyphus.memory.cli record lesson "Python typing" --content "用 Optional 替代 |" --tags python

# 搜索记忆
python3 -m sisyphus.memory.cli search "Python typing"

# 查看最近 10 条
python3 -m sisyphus.memory.cli recent --limit 10

# 查看详情
python3 -m sisyphus.memory.cli show mem_xxxx

# 软删除
python3 -m sisyphus.memory.cli forget mem_xxxx

# 恢复
python3 -m sisyphus.memory.cli restore mem_xxxx

# 统计
python3 -m sisyphus.memory.cli stats

# 生成 Dashboard
python3 -m sisyphus.memory.cli dashboard --output ~/Desktop/sisyphus.html

# 导入历史记忆
python3 -m sisyphus.memory.cli import --path ~/notes/memories.md

# 刷新索引
python3 -m sisyphus.memory.cli rebuild

# 分析记忆日志
python3 -m sisyphus.memory.cli audit --days 7
```

## Python API

```python
from pathlib import Path
from sisyphus.memory.store import MemoryStore

store = MemoryStore(Path.home() / ".omo" / "memory")
# 创建
mem = store.create(title="数据库连接池配置", type="decision", content="最大20，超时30s", importance=8)
# 查询
mem = store.get(mem.id)
# 列表
lessons = store.list(type_filter="lesson")
# 去重创建
mem = store.create_if_new(title="数据库连接池配置", type="decision")
# 评分
store.rate(mem.id, 4)
# 屏蔽
store.dismiss(mem.id)
```

## 跨池检索

```python
from sisyphus.memory.unified import UnifiedRetriever
r = UnifiedRetriever()
results = r.retrieve("mysql 连接池", top_k=5)
for mem, score, pool in results:
    print(f"[{pool}] {mem.title} score={score:.2f}")
```

## 知识库

```python
from sisyphus.memory.knowledge import KnowledgeBase
kb = KnowledgeBase(domain="backend")
kb.import_directory("/path/to/docs/")
results = kb.search("proxy_pass timeout")
```

## 命名空间

```python
from sisyphus.memory.pools import PoolRegistry
reg = PoolRegistry()
reg.init_structure()  # 创建 ~/.omo/{personal,projects,knowledge,shared}
store = reg.get_store("personal")
project_store = reg.project_store()  # 自动检测 git remote
```

## MCP 工具（Agent 对话中自动调用）

| 工具 | 功能 |
|------|------|
| search_memory | 检索记忆 |
| write_memory | 记录记忆 |
| rate_memory | 评分 1-5 |
| dismiss_memory | 永久屏蔽 |
| memory_stats | 统计概览 |
| import_memories | 导入 md/jsonl |
| import_knowledge | 导入文档到知识库 |
| switch_scope | 切换检索范围 |
| list_pools | 池状态 |
| run_pipeline | 离线巩固 |

## 触发机制

| 你说的话 | 触发 |
|----------|------|
| "记住/记下/备忘" | 写入 MemoryStore |
| "上次/之前/前面提到" | 检索 MemoryStore |
| "根据记忆/记录里" | 检索 MemoryStore |
| 无触发词 | 不检索 |

## 存储结构

```
~/.omo/
├── personal/memory/store.db        # 主记忆池
├── projects/{hash}/memory/store.db # 项目池
├── knowledge/{domain}/chunks.db    # 知识库
├── shared/memory/store.db          # 共享池
├── sessions/2026-05-30.md          # 会话日志
└── config.yaml                     # 配置
```

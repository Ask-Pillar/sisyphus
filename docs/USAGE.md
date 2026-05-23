# Sisyphus 使用文档

## 安装

```bash
git clone https://github.com/Ask-Pillar/sisyphus.git
cd sisyphus
pip install -r requirements.txt  # transformers torch jieba
```

## MCP Server

启动 MCP Server（stdio 协议）：

```bash
PYTHONPATH=src python3 -m sisyphus.server.mcp
```

在任何支持 MCP 的客户端配置中引用：

```json
{
  "mcpServers": {
    "sisyphus": {
      "command": "python3",
      "args": ["-m", "sisyphus.server.mcp"],
      "env": {"PYTHONPATH": "src"}
    }
  }
}
```

支持的客户端：opencode、Claude Code、Cursor 等。

## MCP 工具

### remember — 创建记忆

```json
{"name": "remember", "arguments": {
  "title": "Python类型标注",
  "type": "lesson",
  "content": "使用Optional和List语法，不用|管道",
  "tags": ["python", "typing"],
  "importance": 7
}}
```

### recall — 搜索记忆

```json
{"name": "recall", "arguments": {
  "query": "Python类型标注语法",
  "top_k": 5
}}
```

返回 ContextRetriever 双路径检索结果（Path A 树浏览 / Path B 精确检索自动路由）。

### forget — 删除记忆

```json
{"name": "forget", "arguments": {"id": "mem_a1b2c3d4"}}
```

### list — 列出记忆

```json
{"name": "list", "arguments": {"type": "lesson"}}
```

### import — 一键导入

```json
{"name": "import", "arguments": {"path": "/path/to/memories/"}}
```

支持的格式：
- **Markdown 文件**：带 frontmatter（`---\ntitle: xxx\ntype: lesson\n---\n内容`）或纯文本
- **JSONL 文件**：每行一个 JSON 对象 `{"title":"xxx", "type":"lesson", "content":"..."}`
- **目录**：递归扫描 `.md` 和 `.jsonl` 文件

去重：相同 title 自动跳过，不覆盖已有记忆。

### run_pipeline — 离线巩固

```json
{"name": "run_pipeline", "arguments": {"force": true, "use_llm": false}}
```

执行 Sleep Pipeline：LoopDetect → Compress → Dream → TreeBuild → MOC → LinkClean。

- `force: true`：即使 RAW < 20 条也强制运行
- `use_llm: true`：启用 Dream + Compress（需要 LLM API key）

## CLI 操作

```bash
# 记录记忆
PYTHONPATH=src python3 -m sisyphus.memory.cli record lesson "Python type hints"
PYTHONPATH=src python3 -m sisyphus.memory.cli record pattern "TDD优先: 先写测试再实现"

# 搜索
PYTHONPATH=src python3 -m sisyphus.memory.cli search "type hints"

# 列出
PYTHONPATH=src python3 -m sisyphus.memory.cli recent

# 重建 Memory Tree
PYTHONPATH=src python3 -c "
from sisyphus.cli.tree_cmd import cmd_tree_rebuild
from pathlib import Path
cmd_tree_rebuild(Path.home() / '.omo' / 'memory')
"
```

## 生长测试

按数据增长阶段验证检索质量：

```bash
PYTHONPATH=src python3 docs/p5_gate.py      # Gate 测试 (30 queries)
PYTHONPATH=src python3 docs/p5_growth.py    # 生长测试 (4 stages)
```

## 文件结构

```
~/.omo/memory/            ← 记忆存储根目录
├── INDEX.md              ← MOC 主题地图入口
├── lesson/               ← RAW: 教训类记忆
├── pattern/              ← RAW: 模式类记忆
├── note/                 ← RAW: 笔记类记忆
├── refined/              ← REFINED: LLM 精炼产物
│   ├── reflection/
│   ├── summary/
│   └── loop/
├── tree/                 ← Memory Tree
│   ├── _meta.json
│   ├── l0.json           ← 全局摘要
│   ├── l1/               ← type 聚类节点
│   └── l2/               ← 单条记忆叶子
└── logs/                 ← 操作审计日志
```

## Reranker 激活条件

BCE-Reranker (279M) 在以下条件自动激活：
- 同类型下记忆数 ≥ 8 条
- 实际场景（非测试）：预期 +13% @1

不需要手动配置，`ContextRetriever._auto_reranker()` 自动检测并加载。

## 环境要求

- Python 3.9+
- 磁盘：~3GB (BCE 模型 ~1GB + 记忆文件)
- CPU 即可（BCE 279M 无需 GPU）
- jieba (中文分词)、transformers、torch

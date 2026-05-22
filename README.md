# Sisyphus — Self-Evolving AI Agent with Persistent Memory

A layered memory system for LLM agents with file-native storage, local-only retrieval (BM25 + Embedding + Reranker), hippocampus cognitive architecture, and MCP server — zero API keys required.

```
.omo/memory/
├── INDEX.md            ← MOC 全局索引入口
├── <type>/<id>.md      ← RAW 层（append-only）
├── refined/
│   ├── reflection/     ← LLM 反射洞察
│   ├── summary/        ← 退火压缩摘要
│   └── loop/           ← 回路阻断记录
├── agents/
│   └── <name>/         ← 子 agent 独立沙箱
└── logs/               ← 结构化操作日志
```

## 架构

### 四层存储

| 层级 | 目录 | 特点 |
|------|------|------|
| **RAW** | `memory/<type>/` | 原始记忆，append-only，永不删除 |
| **REFINED** | `memory/refined/` | LLM 加工产物，可重新生成 |
| **MOC** | `memory/INDEX.md` | 多维主题地图，Obsidian 兼容 |
| **AGENT** | `memory/agents/<name>/` | 子 agent 独立记忆沙箱 |

核心原则：

- **文件即 SSOT** — 所有记忆是 Markdown 文件，数据库（SQLite）只是可重建的缓存
- **痕迹只增不删** — RAW 层永远不覆盖或删除原始记忆
- **LLM 可缺失** — 所有涉及 LLM 的操作在无 API key 时自动跳过，不崩溃
- **管道驱动** — 所有加工通过 Pipeline 自动触发

### 海马体认知架构

检索系统模拟人脑海马体分层结构：

| 脑区 | 对应实现 | 功能 |
|------|----------|------|
| **DG** (齿状回) | Qwen3-Embedding 0.6B | 语义编码，区分相似记忆 |
| **CA3** (CA3区) | BM25 + TFIDF 余弦 | 模式补全，关键词匹配 |
| **CA1** (CA1区) | Qwen3-Reranker 0.6B | 精排重打分，提升准确率 |
| **EC** (内嗅皮层) | Memory Tree (层级摘要树) | 多粒度记忆索引 (Phase 1-4) |

## 检索系统

三层分层召回 + 混合检索：

```
用户 query
    │
    ▼
L1: 类型分类 ──→ MOC 关键词匹配，限定检索范围
    │
    ▼
L2: REFINED 优先 ──→ 从 reflection/summary 中召回
    │
    ▼
L3: RAW 补缺 ──→ 高重要性/高关联度的原始记忆补充
    │
    ▼
decay_score 排序截断 ──→ 指数衰减（半衰期 30 天）
```

### 检索算法

| 方法 | 速度 | top-1 准确率 | 适用场景 |
|------|------|-------------|----------|
| **BM25** | ~0.03s | 56% (小数据) ~ 70% (大数据) | 关键词精准匹配，零依赖 |
| **TFIDF + 余弦** | ~0.02s | — | 纯 Python，零依赖兜底 |
| **Qwen3-Embedding 0.6B** | ~0.3s | 50% ~ 96% | 跨语言/语义扩展，大数据优势明显 |
| **Qwen3-Reranker 0.6B** | ~20s (CPU) | +5~10% | 精排，建议 GPU 使用 |
| **FlashRank (ONNX)** | ~0.2s | 46% | 轻量级 (4MB)，英文场景 |

**最佳策略**：BM25 主检索（小数据） + Embedding 语义兜底（大数据），Reranker 仅在 GPU 环境启用。

### 测试结果

| 测试集 | 数据量 | BM25 | Embedding | Reranker |
|--------|--------|------|-----------|----------|
| 旧数据(英文技术笔记, 中文查英文) | 30条 | 46% | **96%** | — |
| Sisyphus 含重复 | 265条 | 70% | **87%** | 83% |
| Sisyphus 去重 | 58条 | **56%** | 50% | 50% |

**核心发现**：Embedding 在大而杂数据上碾压，在小而同质数据上不如 BM25。Recall@5 两种方法均达 90%。

详细报告见 `abc-test-report.html`。

## 快速开始

```bash
git clone https://github.com/Ask-Pillar/sisyphus.git
cd sisyphus

# 启动 MCP server（供 AI agent 连接）
PYTHONPATH=src python3 -m sisyphus.server.mcp

# 或通过 CLI 操作记忆
PYTHONPATH=src python3 -m sisyphus.memory.cli record lesson "Python type hints"
PYTHONPATH=src python3 -m sisyphus.memory.cli recent
PYTHONPATH=src python3 -m sisyphus.memory.cli search "type hints"
```

## MCP Server

通过 Model Context Protocol (stdio) 为 AI agent 提供持久记忆：

```
[agent] ←── MCP stdio ──→ [sisyphus]
                             │
                             ├── search(query, top_k=5)    检索记忆
                             ├── record(title, type, content)  记录新记忆
                             ├── recent(limit=10)   最近记忆
                             └── stats()   系统概览
```

启动：`PYTHONPATH=src python3 -m sisyphus.server.mcp`

## 子进程 LLM 调度 (Subagent)

所有 LLM 加工通过 **SubagentLauncher** 在独立子进程中执行：

| Handler | 功能 |
|---------|------|
| `dream` | 对未加工记忆生成反射洞察 |
| `compress` | 多记忆退火压缩合并 |
| `recall_search` | 全文搜索+嵌入排序 |
| `recall_relevant` | 根据 query 筛选最相关的 top-N |
| `classify_types` | 类型分类（MOC L1） |

**离线验证**：`--fixture` 模式使用 fixture JSON 模拟 LLM 响应，零 API key 全链路测试。

```
python3 -m sisyphus.memory.subagent --handler dream --fixture
```

## Pipeline 自动流水线

每次触发按顺序运行：

1. **回路检测** — 同标题 ≥3 次自动标记
2. **压缩** — RAW 数量超阈值时退火合并
3. **反射** — 未加工的记忆 ≥3 条时自动触发 DreamEngine
4. **MOC 索引** — 每次增量更新
5. **断链清理** — 移除无效/重复/自引用链接

## 自动上下文 (MemoryContext)

**MemoryContext** 为每轮对话自动构建上下文，支持三种模式：

| 模式 | 说明 |
|------|------|
| **全量 (full)** | 每 `refresh_interval` 轮一次完整三层召回 |
| **增量 (incremental)** | 中间轮次只检索 REFINED 层 |
| **脏刷新 (dirty)** | `_dirty` 标记触发按需更新 |

```python
from sisyphus.memory.context import MemoryContext
from sisyphus.memory.store import MemoryStore

store = MemoryStore()
ctx = MemoryContext(store, refresh_interval=3)
context = ctx.build(query="Python type hints")
```

## 开发

```bash
git clone https://github.com/Ask-Pillar/sisyphus.git
cd sisyphus

PYTHONPATH=src pytest tests/ -v
```

- Python 3.9+
- 文件系统驱动，零外部依赖（LLM 调用仅通过 `LLMClient`，无 key 静默跳过）
- TDD：先写测试再实现

## 测试

```
============================= 196 passed in 10s ==============================
```

| 文件 | 说明 |
|------|------|
| `test_store.py` / `test_store_v2.py` | 文件 CRUD + 持久化 |
| `test_refined.py` | 三层加工存储 |
| `test_log.py` | 结构化日志 |
| `test_moc.py` | MOC 索引生成 |
| `test_pipeline.py` | 自动触发流水线 |
| `test_dream.py` | 反射引擎 |
| `test_link.py` | 断链清理 |
| `test_loop.py` | 回路检测 |
| `test_agent.py` | 子 agent 沙箱隔离 |
| `test_cache.py` | SQLite 缓存重建与搜索 |
| `test_extraction.py` / `test_compression.py` | 提取与压缩 |
| `test_recall.py` / `test_search.py` / `test_snapshot.py` | 检索与快照 |
| `test_retrieval.py` | 三层召回 + 衰减权重 |
| `test_context.py` | 自动上下文构建 |

## 环境要求

- **CPU**：Intel/AMD，BM25 零依赖，Embedding 建议 8GB+ 内存
- **GPU**：可选，用于 Reranker（Qwen3-Reranker 0.6B 约 2GB 显存）
- **网络**：模型首次下载需 huggingface 访问（或配置 `HF_ENDPOINT=https://hf-mirror.com`）
- **磁盘**：模型缓存约 2.5GB（Embedding 0.6B + Reranker 0.6B）

# Sisyphus 记忆系统 — 项目现状

## 核心定位

从存储到排序，从单池到多池，从被动检索到主动触发。为 AI Agent 构建个性化检索推荐系统。

## 技术栈

Python 3.14+ / SQLite + FTS5 / Markdown（兼容旧格式）/ MCP JSON-RPC / jieba

## 架构

```
用户查询
  → 触发系统 (L0 信号词 / L1 周期 / L2 退避)
    → UnifiedRetriever 跨池检索
      → FTS5 召回 → Decay 粗排 → BCE 精排 → Diversity 重排
        → 返回 Top-K

记忆写入
  → 触发词命中 → MemoryStore / SQLiteMemoryStore
  → 全部消息 → ~/.omo/sessions/{date}.md
```

## 组件清单

### 存储层

| 组件 | 文件 | 功能 |
|------|------|------|
| SQLiteMemoryStore | sqlite_store.py | 主存储，SQLite+FTS5，自动从 Markdown 迁移 |
| MemoryStore | store.py | 旧版文件存储，兼容读取 |
| KnowledgeBase | knowledge.py | 知识库，SQLite FTS5 分块(500词/chunk) |
| PoolRegistry | pools.py | 四池管理：personal/projects/knowledge/shared |
| Memory 类 | store.py | 数据类，30 个字段（含反馈、软删除、多分类） |

### 检索层

| 组件 | 文件 | 功能 |
|------|------|------|
| UnifiedRetriever | unified.py | 跨池加权检索入口 |
| ContextRetriever | retrieval.py | BM25/BCE/TF-IDF/Decay 排序 |
| DiversityReranker | diversity.py | MMR 去冗余 + 类型配额 |
| Decay Score | retrieval.py | 半衰期 180 天，recall_count 加权，feedback 衰减 |
| TreeRetriever | tree_retriever.py | 树形浏览路径 |
| FtsIndex | fts_index.py | FTS5 全文索引 |

### 触发系统

| 组件 | 文件 | 功能 |
|------|------|------|
| L0 信号词 | trigger.py | 正则匹配 20+ 中英文触发词 |
| L1 周期+话题 | trigger.py | 每 5 轮触发 + Jaccard 话题切换 < 0.3 |
| L2 指数退避 | context.py | 连续无命中跳 2^n 轮 |

### 反馈系统

| 组件 | 文件 | 功能 |
|------|------|------|
| rate_memory | store.py + mcp.py | MCP 工具，评分 1-5 |
| dismiss_memory | store.py + mcp.py | MCP 工具，永久屏蔽 |
| 反馈衰减 | retrieval.py | 半衰期 90 天，负反馈降权 |
| 反茧房 | unified.py | Forgotten Gems 10% + 多样性保底 + 对立观点 |

### 流水线

| 组件 | 文件 | 功能 |
|------|------|------|
| SleepPipeline | pipeline/sleep.py | DirLock + 6 步：loop/compress/dream/tree/moc/link |
| DreamEngine | dream.py | LLM 反思引擎 |
| Compressor | compression.py | 旧记忆压缩 |
| LoopDetector | loop.py | 重复模式检测 |

### 边界层

| 组件 | 文件 | 功能 |
|------|------|------|
| hooks.py | agent/hooks.py | OpenCode before/after 钩子 |
| MCP Server | server/mcp.py | 14 个工具 |
| Session Log | hooks.py | `~/.omo/sessions/{date}.md` 双向记录 |

## MCP 工具 (14 个)

| 工具 | 功能 |
|------|------|
| search_memory | 检索记忆 |
| get_context | 获取上下文 |
| write_memory | 记录记忆 |
| rate_memory | 评分 1-5 |
| dismiss_memory | 永久屏蔽 |
| delete_memory | 软删除 |
| restore_memory | 恢复 |
| list_memories | 列出记忆 |
| memory_stats | 统计概览 |
| import_memories | 导入 md/jsonl |
| import_knowledge | 导入文档到知识库 |
| switch_scope | 切换检索范围 |
| list_pools | 列出池状态 |
| run_pipeline | 离线巩固 |

## 存储结构

```
~/.omo/
├── personal/memory/store.db        # 主记忆池 (SQLite + FTS5)
├── projects/{hash}/memory/store.db # 项目记忆池
├── knowledge/{domain}/chunks.db    # 知识库 (FTS5)
├── shared/memory/store.db          # 共享池
├── sessions/2026-05-30.md          # 会话日志
└── config.yaml                     # 池权重 + 白名单
```

## 关键数据字段

Memory 类 30 个字段：id, types(多分类), title, content, tags, links, importance, status, deleted, dismissed, feedback_score, feedback_at, recall_count, last_recalled_at, refined_by, evidence, compressed_from, created_at, updated_at, ...

## 已有数据

78 条原始记忆 + 12 条精炼记忆，覆盖 decision/lesson/pattern/note 等类型。

## 触发系统

| 级别 | 方式 | 延迟 |
|------|------|------|
| L0 | 正则匹配"记住/上次/recall"等 20+ 词 | < 1ms |
| L1 | 每 5 轮触发 + 话题切换 Jaccard < 0.3 | < 5ms |
| L2 | 连续无命中指数退避 2^n 轮 | 0ms |

## 验证

408/408 测试全通过。覆盖 35 个测试文件。

## 测试覆盖

| 模块 | 测试数 | 覆盖内容 |
|------|--------|----------|
| store | 17 | CRUD/软删除/migration |
| sqlite_store | 12 | SQLite 存储 |
| trigger | 25 | 信号词匹配 |
| trigger_accuracy | 60 | 标注样本准确率(60/61) |
| retrieval | 22 | 衰减/排序 |
| knowledge | 10 | 导入/搜索 |
| unified | 6 | 跨池检索 |
| pipeline | 20 | 流水线 |
| diversity | 6 | MMR 重排 |
| refined | 13 | 精炼记忆 |
| pools | 7 | 池隔离 |
| 其他 24 模块 | 231 | 完整覆盖 |

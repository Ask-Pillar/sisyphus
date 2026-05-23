# Sisyphus — 持久记忆 AI Agent

海马体认知架构 + Memory Tree + MCP Server。为 AI agent 提供跨 session 持久记忆，纯文件存储，零外部依赖。

```
.omo/memory/
├── INDEX.md            ← MOC 主题地图
├── <type>/<id>.md      ← RAW 层 (append-only)
├── refined/            ← LLM 精炼记忆
├── tree/               ← Memory Tree 层级索引
│   ├── _meta.json
│   ├── l0.json
│   ├── l1/
│   └── l2/
└── logs/               ← 操作日志
```

## 架构 v3.0 (当前)

| 脑区 | 实现 | 状态 |
|------|------|------|
| 🧠 新皮层 | MemoryStore (RAW + REFINED) | ✅ |
| 🗂️ 海马旁回 | MOC 关键词路由 (jieba 分词) | ✅ |
| 🌳 内嗅皮层 | Memory Tree + TreeRetriever | ✅ |
| 🔀 齿状回 | ~~Qwen3-Embedding 0.6B~~ → 已裁 | ❌ |
| 🔗 CA3 | BM25 (jieba + EN regex + CJK 单字) | ✅ 83% @1 |
| ✅ CA1 | BCE-Reranker 279M CPU / 同 topic 8+ 自动激活 | ✅ |
| 🌙 睡眠 | Sleep Pipeline (6 步) | ✅ |
| ❤️ 杏仁核 | decay_score = importance × 0.5^(days/30) | ✅ |
| 🌐 MCP | stdio JSON-RPC 跨 Agent 共享 | ✅ |
| 🔒 沙箱 | ~~SubagentLauncher~~ → MCP 替代 | ❌ |

## 检索系统

双路径 + 四级降级链：

```
Path A (树浏览):   Query → 子树叶 max-score 匹配 L1 → 子树 BM25 精排 → 返回
Path B (精确检索): Query → MOC 类型匹配 → BM25 全量 → BCE 精排 → 返回

降级: Path A 失败 → Path B → raw BM25 → 空
```

## 性能

| 指标 | 值 |
|------|-----|
| Gate @1 | 83% (30 queries × 21 docs) |
| 单 query 耗时 | 0.001s (BM25) / 5s (BCE) |
| 规模稳定性 | 9-508 docs @1 不变 |
| 测试 | 292 passed |

## MCP Tools

| 工具 | 功能 |
|------|------|
| `remember` | 创建新记忆 |
| `recall` | ContextRetriever 双路径检索 |
| `forget` | 删除记忆 |
| `list` | 列出记忆 (支持 type 过滤) |
| `import` | 一键导入 .md/.jsonl/目录 |
| `run_pipeline` | Sleep Pipeline 离线巩固 |

## Phase

```
P0 ✅ P1 ✅ P2 ✅ P3 ✅ P4 ✅ P5 ✅ → P6 📋 (自我学习)
```

## 文档

| 文档 | 内容 |
|------|------|
| `docs/ARCH-COMPARISON.md` | 海马体架构 vs 实际实现对比 |
| `docs/ARCHITECTURE-v3.html` | 当前架构全景图 |
| `docs/TESTING-STRATEGY.md` | 生长测试策略 |
| `docs/P3-GATE-REPORT.md` | P3 Gate 验收 (83% PASS) |
| `docs/P4-GROWTH-RESULTS.md` | P4 生长 + BCE 测试 |
| `docs/P5-GATE-REPORT.md` | P5 Gate (83%, 无倒退) |
| `docs/USAGE.md` | 使用文档 |

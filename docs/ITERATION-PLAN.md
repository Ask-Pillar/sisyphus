# Sisyphus 迭代规划（定稿）

> 日期: 2026-05-27 凌晨
> 原则: 能用现成的就用现成的，修地基优先，每步可验证
> 状态: Phase 1 待启动

---

## Phase 1: 修基底

| 顺序 | 编号 | 内容 | 工作量 | 工具 |
|------|------|------|--------|------|
| 1 | P0-2 | store/moc 写冲突 → MOC.md | ~10行 | — |
| 2 | P2-1 | 清 Test 数据 | ~15行 | — |
| 3 | P0-3 | L2 操作日志 operations.jsonl | ~30行 | json stdlib |
| 4 | P0-1 | REFINED 激活 | ~50行 | — |

## Phase 2: 补架构

| 顺序 | 编号 | 内容 | 工作量 | 工具 |
|------|------|------|--------|------|
| 5 | L3-fts5 | SQLite FTS5 索引 | ~100行 | sqlite3(stdlib) |
| 6 | P1-5 | PERSIST 层 | ~30行 | — |
| 7 | P1-8 | 初始感知 | ~15行 | — |
| 8 | P1-4 | 冷热分层 | ~20行 | — |

## Phase 3: 自动化

| 顺序 | 编号 | 内容 | 工作量 | 工具 |
|------|------|------|--------|------|
| 9 | P1-3 | MCP 工具注入 | ~10行 | — |
| 10 | P1-1 | Pipeline 自动触发 | ~60行 | opencode task() |
| 11 | P1-2 | Extractor 自动提取 | ~150行 | — |
| 12 | P1-audit | 审计层 | ~60行 | L2+L3 |

## Phase 4: 扩展

| 顺序 | 内容 | 工具 |
|------|------|------|
| 13 | CodeGraphContext 集成 | pip install |
| 14 | 可视化仪表盘 | Cytoscape.js + Chart.js CDN |
| 15 | 去重 | hash + LLM |

## 用现成的清单

| 组件 | 工具 | 安装 |
|------|------|------|
| FTS5 全文搜索 | Python sqlite3 | stdlib 自带 |
| 中文分词 | jieba | 已有 |
| 代码索引 | CodeGraphContext | pip install |
| 操作日志 | json stdlib | 自带 |
| 后台子 agent | opencode task() | 已有 |
| 知识图谱 | Cytoscape.js | CDN |
| 统计图表 | Chart.js | CDN |

**外部依赖: 1 个 pip 包**

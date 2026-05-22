# Phase 验收标准 — Sisyphus Memory System

## P0 — 基础设施验收

### 功能门槛（全部通过才算完成）

| 验收项 | 验证命令/方式 |
|---|---|
| `atomic_write` crash-safe | 测试：写到一半 kill 进程，原文件完整无损 |
| `DirLock` 无死锁 | 测试：两进程并发写，最终数据一致不丢行 |
| `DirLock` stale pid 自愈 | 测试：写入死进程 PID，下次 acquire 自动清锁 |
| SQLite WAL 已开启 | `PRAGMA journal_mode;` 返回 `wal` |
| `wal_autocheckpoint` 生效 | `PRAGMA wal_autocheckpoint;` 返回 `1000` |
| MCP 8 工具全部可调用 | `echo '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}' \| python -m sisyphus.server.mcp` 返回 8 个 tool |
| `search_memory` 走 ContextRetriever | 同一 query，MCP search 结果与 `agent.before_turn()` 结果一致 |
| `_setup()` 单例 | 连续调用 2 次 `_setup()`，返回同一对象 `id()` |

### 测试门槛

```bash
pytest tests/ -q
# 要求：≥ 195 passed（原 187 + 新增 ~8），0 新增失败
```

### 命中率验证

```bash
python tests/abc_recall.py   # 跑 165 题
# 要求：top-1 在 58-62%（允许 ±2%，不能比改前低）
```

---

## P1 — TreeStore 验收

### 功能门槛

| 验收项 | 验证方式 |
|---|---|
| `_meta.json` 格式正确 | 新增叶子后，`_meta.json` 包含该节点的 `parent_id`/`level` |
| 叶子新增只写一个文件 | `strace`/跟踪：`add_leaf()` 只创建 `l2/<id>.json`，不改其他文件 |
| `get/subtree/path` 正确 | 单元测试：给定 id，返回正确祖先链 |
| `_meta` rename 原子 | 测试：并发两个写，`_meta.json` 不损坏 |
| 向后兼容：RAW store 可读 | 已有 `~/.omo/memory/` 数据不受影响 |

### 测试门槛

```bash
pytest tests/ -q
# 要求：≥ 202 passed（原 195 + 新增 ~7）
```

---

## P2 — TreeBuilder 验收

### 功能门槛

| 验收项 | 验证方式 |
|---|---|
| 无 LLM 时不崩 | `unset SISYPHUS_LLM_API_KEY && python -c "from sisyphus.memory.tree.tree_builder import TreeBuilder; TreeBuilder(...).build()"` 正常返回 |
| title 拼接降级产出合理摘要 | l1 节点 `summary` 非空，内容为该簇 title 拼接 |
| 粗聚类按 type/tag 分组正确 | 5 条 lesson + 3 条 idea → 两个 l1 节点各自对应 |
| 细聚类相似度阈值 0.3 生效 | 注入 2 条相似记忆 + 1 条无关，相似的进同一簇 |
| l0 全局摘要存在 | `tree/l0.json` 文件存在，`summary` 非空 |

### 测试门槛

```bash
pytest tests/ -q
# 要求：≥ 208 passed（原 202 + 新增 ~6）
```

---

## P3 — 双路径检索验收（含 Gate）

### 功能门槛

| 验收项 | 验证方式 |
|---|---|
| 短/模糊 query 走 Path A | `query="关于记忆"` → log 显示 `path=A` |
| 精确 query 走 Path B | `query="SubagentLauncher 的 fixture_path 参数"` → log 显示 `path=B` |
| Embedding 缓存命中 | 同一内容第二次 embed 不调模型（SQLite 有记录） |
| 四级降级链不崩 | 逐级禁用（Reranker→Embedding→BM25→TF-IDF），每级仍返回结果 |
| 向量存于 SQLite | `sqlite3 ~/.omo/memory/cache/embeddings.db ".tables"` 显示 `embedding` 表 |

### 命中率 Gate（硬性，不通过不进 P4）

```bash
python tests/abc_recall.py
# 要求：top-1 ≥ 80%，否则排查双路径选择逻辑再跑
```

### 测试门槛

```bash
pytest tests/ -q
# 要求：≥ 214 passed（原 208 + 新增 ~6）
```

---

## P4 — Sleep Pipeline 验收

### 功能门槛

| 验收项 | 验证方式 |
|---|---|
| 触发条件生效 | 写入第 20 条 RAW 记忆后，`sleep.py` 自动启动 |
| 无 LLM 跳过 Dream+Compress | `unset SISYPHUS_LLM_API_KEY`，pipeline 跑完，日志显示 `skip dream` `skip compress` |
| 无 LLM 时 TreeBuilder 降级运行 | 第 4 步 TreeBuilder 正常完成，`l0.json` 更新时间戳更新 |
| 全流程 7 步有日志 | 每步开始/结束均有结构化日志，无 LLM 时 step 3/4 标记 `skipped` |
| 增量运行幂等 | 连续跑两次 Sleep，第二次无变化时各步快速跳过 |
| CLI 命令可用 | `python -m sisyphus tree rebuild` 触发同等流水线 |

### 命中率验证

```bash
python tests/abc_recall.py
# 要求：top-1 ≥ 85%（Sleep 后 Reranker 精排提升）
```

### 测试门槛

```bash
pytest tests/ -q
# 要求：≥ 220 passed（原 214 + 新增 ~6），全套 0 失败
```

---

## 通用原则

1. **不得退化**：每个 Phase 的 abc 命中率不能比上一 Phase 低超过 2%
2. **失败阻断**：任意 Gate 未达标，停止推进下一 Phase，先分析再调整
3. **回归覆盖**：每次提交前必须跑完整 `pytest tests/`，不允许带新失败合入
4. **可观测**：每个检索决策（path 选择、降级触发）必须有日志，方便 abc 失败后排查

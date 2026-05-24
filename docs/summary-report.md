# Sisyphus 记忆系统综合评估报告

> 日期: 2026-05-24  
> 来源: Sisyphus 主 session + WeChat agent 四层架构审查  
> 缺陷: 8 项 | 方案: 3 项 | 代码索引: 已调研

---

## 一、记忆系统缺陷（8项）

### P0 — 阻塞核心功能

| # | 缺陷 | 影响 | 工作量 |
|---|------|------|--------|
| P0-1 | REFINED 层为空（90 RAW → 1 REFINED） | Dream/Compress 没实际产出 | 中 |
| P0-2 | MemoryStore 和 MOC 写同一个 INDEX.md | MOC 结构永远不生效 | 小 |

**P0-1 详情**: Dream Engine 存在但从未运行出结果。`_gather_memories()` 全量拉 90 条（含 69 条 Test），Dream prompt 被垃圾数据稀释。

**P0-2 详情**: `store.py._rebuild_index()` 和 `moc.py.generate()` 都写 `INDEX.md`，后来者覆盖前者。

### P1 — 自进化断链

| # | 缺陷 | 影响 | 工作量 |
|---|------|------|--------|
| P1-1 | Pipeline 完全手动触发 | 每次人工触发，不可持续 | 中 |
| P1-2 | 会话不自动提取到记忆 | 对话结果流失 | 大 |
| P1-3 | MCP 工具无系统提示注入 | agent 不知道有 MCP 可用 | 小 |
| P1-4 | 记忆检索无冷热分层 | 每次扫 90 条全量，Test 数据干扰 | 中 |

**P1-1 详情**: 需要 `after_turn()` 钩子 + `task(run_in_background=true)` 异步触发。LLM 后端矩阵：opencode subagent（默认零成本）/ DeepSeek Flash（~2分/次）/ Ollama 本地 / one-api 代理。Dream 只取未加工记忆（created_at > last_dream AND NOT refined_by AND NOT test）。

**P1-3 详情**: 需要两层注入——Layer 1 `before_turn()` 已有（注入 `<sisyphus_context>`），Layer 2 MCP 工具指令缺失。方案: 创建 `sisyphus-memory` skill 内含工具列表，或动态生成注入。

**P1-4 详情**: 检索时 hot（7天内, ~20条）优先 → 不足 top_k 再扫全量。实现: store.py 写入时自动维护 `HOT.md`，ContextRetriever 先搜 hot，Dream 只扫 hot。

### P2 — 质量/降级

| # | 缺陷 | 影响 | 状态 |
|---|------|------|------|
| P2-1 | 测试数据污染（69/90 Test） | 检索精度下降 | 待处理 |
| P2-2 | 半衰期过短（原30天） | 记忆过早衰减 | ✅ 已改为180天 |

---

## 二、微信端讨论要点

### 本期讨论（00:32-00:37 CST）

1. **Auto-trigger** — "每次都要手动触发，主动触发做不到呀" → 需要 after_turn 自动化
2. **半衰期** — "30天过短" → 已确认改为 180 天
3. **会话提取** — "会话会被汇总到记忆系统里面吗？" → 目前不会，需要 Extractor
4. **近期记忆定义** — 确认 7 天窗口
5. **冷热分层** — "近期记忆放最快访问的分区里" → P1-4 方案

### 前期讨论（压缩记忆）

- A/B 测试: 有记忆 1.1 vs 无记忆 0.6
- BM25 @1 从 56% 提升到 83%（jieba 分词优化）
- Qwen3-Embedding 负收益，已移除
- Reranker 有条件收益（同 topic ≥8 条时 +13%）
- 砍掉 Subagent 沙箱（MCP Server 替代）

---

## 三、代码索引方案分析

### 需求

代码知识（函数签名、调用关系、模块依赖、类继承）需要独立索引，与记忆系统（存对话经验/偏好）数据结构完全不同。通过统一 MCP 接口暴露，agent 不感知背后有几个索引。

### 方案对比

| 维度 | CodeGraphContext（现成） | 自研 |
|------|--------------------------|------|
| 语言支持 | Python/TS/JS/Go/Rust/C++等 20 种 | 需逐个实现 AST parser |
| 核心技术 | tree-sitter + KùzuDB 图数据库 | 需自选栈 |
| MCP Server | ✅ 内置，开箱即用 | 需手动实现 |
| CLI 工具 | ✅ 完整（callers/callees/complexity/dead-code） | 需从头开发 |
| 增量更新 | ✅ `cgc watch` 文件监控 | 需自行实现 |
| 成熟度 | 3K+ GitHub Stars, MIT 许可, v0.3.9 | 零 |
| 部署成本 | `pip install codegraphcontext` | 数周～数月开发 |
| 维护成本 | 社区维护 | 全自担 |

### 推荐

**直接用 CodeGraphContext**。自研不是功能不行，而是时间不对——当前 P0-P2 已经有 8 个缺陷需要修，再加一个代码索引基建会严重摊薄精力。CodeGraphContext 已经完美覆盖需求：

- 树解析 → 图存储 → MCP Server 输出
- 命令行: `cgc index .` → `cgc analyze callers my_func`
- MCP Server: agent 拿到 `mcp__codegraphcontext__analyze_calls` 等工具

集成方式：在 sisyphus 的 MCP Server 旁边加一个 codegraphcontext 实例，agent 通过统一 MCP 协议同时访问记忆和代码两个索引。

---

## 四、实施路线

```
P0-2 (写冲突) → P0-1 (REFINED) → P2-1 (清理 Test)
    ↓
P1-4 (冷热分层) → P1-3 (MCP tool 注入) → P1-1 (自动触发)
    ↓
P1-2 (自动提取) → CodeGraphContext 集成
```

---

## 五、相关文件

- `docs/memory-defects-plan.md` / `.html` — 详细改进计划
- `docs/mcp-wechat-debug.md` / `.html` — MCP 接入调试记录
- `src/sisyphus/server/mcp.py` — MCP Server（已修复语法）
- `src/sisyphus/memory/context.py` — AgentMemory + before_turn
- `src/sisyphus/memory/dream.py` — Dream 引擎
- `src/sisyphus/memory/store.py` — MemoryStore（需改热索引 + MOC 分离）

---

## 六、记忆记录

以下记忆已同步到系统：

- `mem_6e0bb92e04b0` — 改进方案讨论结论
- `mem_231c391bb72b` — 四层架构现状评估（RAW:91, REFINED:1, MOC:0）
- `mem_df53218df5f2` — REFINED 层为空
- `mem_a7469e311c54` — store/moc 写冲突
- `mem_97d963afe918` — 代码索引方案（CodeGraphContext）
- `mem_2f8c0d2a76aa` — WeChat bridge MCP 调试全链路
- `mem_e9b792530625` — [compressed] 整体开发状态

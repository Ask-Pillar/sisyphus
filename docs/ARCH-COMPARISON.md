# 海马体架构 vs 实际实现 — 差异记录

## 完整对比

| 海马体组件 | 架构图设计 | 实际实现 | 差异 | 原因 |
|-----------|-----------|---------|------|------|
| 🧠 新皮层 Neocortex | LLM 编码 → RAW/REFINED 双层存储 | ✅ 一致 | — | — |
| 🗂️ 海马旁回 PHR | MOC 关键词路由 | ✅ 一致 | — | — |
| 🌳 内嗅皮层 EC | Memory Tree 层级摘要树（LLM 生成语义摘要） | ⚠️ TreeStore 已做，摘要降级 | 无 LLM 时退化为 title 拼接 | LLM 不可用时需降级 |
| 🔀 齿状回 DG | Qwen3-Embedding-0.6B 向量化 | ❌ 已移除 | 砍掉了整个 embedding 路径 | 0.6B 模型中文语义匹配太弱，cosine 相似度几乎随机。混合权重 75cos+25bm25 把 BM25 的 76% 拉低到 43% |
| 🔗 CA3 | BM25 + Embedding 混合检索 | ⚠️ 纯 BM25 替代 | 砍 DG 后混合无意义 | 纯 BM25（jieba+单字 fallback）= 76%，优于混合 |
| ✅ CA1 | Cross-encoder Reranker 精排 | ✅ 一致（BCE 替代 Qwen3-Reranker） | 模型换小 | Qwen3-Reranker 需 GPU；BCE 279M CPU 可跑，同 topic 8+ docs 时 +13% |
| 🌙 睡眠 | DreamEngine + Compressor + TreeBuilder | ✅ 一致（Sleep Pipeline） | — | — |
| ❤️ 杏仁核 | importance + decay_score 衰减 | ✅ 一致 | — | — |
| 🌲 双路径 | Path A 树浏览 + Path B 精确检索 | ✅ 一致（TreeRetriever + _choose_path） | — | — |
| 🔒 子 Agent 沙箱 | AGENT 层隔离子进程 | ❌ 已移除 | 沙箱层砍掉 | MCP Server 替代子 agent 隔离，所有客户端共享同一份记忆 |
| 🌐 跨 Agent 共享 | 未涉及 | ✅ 已实现（MCP stdio 协议） | 架构图没这个维度 | MCP 是标准协议，任何支持 MCP 的客户端都能接入 |

## 关键决策记录

### 1. 移除 Qwen3-Embedding (2026-05-23)

**原因**: 30 条 query × 21 条文档基准测试：
- 纯 BM25: 76% @1
- 混合 (0.75 × cosine + 0.25 × BM25): **43%** @1

0.6B 参数量的模型无法有效理解中文技术文档的语义，cosine 相似度接近随机分布。保留只会拉低纯 BM25 已实现的 76%。

### 2. 替换 Qwen3-Reranker 为 BCE (2026-05-23)

**原因**: Qwen3-Reranker-0.6B 需要 GPU 推理。BCE-Reranker-base_v1（网易有道，279M）CPU 可跑，benchmark 比 BGE 高（61.29 vs 59.04）。同 topic ≥ 8 docs 时 +13% @1。

### 3. 砍掉子 Agent 沙箱 (2026-05-23)

**原因**: MCP Server 本身就是跨 agent 共享的标准协议。子 agent 不需要独立沙箱——通过 MCP 的 recall/remember 工具读写同一份记忆即可。架构从"agent 沙箱隔离"变成"MCP 客户端共享"。

### 4. EC 摘要降级 (2026-05-21)

**原因**: TreeBuilder.build() 在无 LLM 环境下用 title 拼接代替语义摘要。路径 A 的子树 max-score 匹配逻辑仍然正确（基于叶子内容打分），摘要质量只影响 L1 匹配速度，不影响准确率。

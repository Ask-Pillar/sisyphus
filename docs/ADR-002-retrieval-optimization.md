# ADR-002: 记忆检索优化（Tokenization + Ranking）

Date: 2026-05-23

## 背景

Sisyphus 记忆检索使用 `ContextRetriever` 三层管道：MOC 类型分类 → BM25 粗召 → Embedding/Reranker 精排。初始实现在 30 条中文查询上 Top-1 仅为 43%。

## 已完成的变更

### 1. 分词替换（`_tokenize` 函数）

| 变更前 | 变更后 |
|--------|--------|
| CJK → overlapping bigrams | CJK → jieba 分词 + 单字 fallback |
| EN → word split | EN/数字 → 正则提取保留原样 |
| 混合文本全量 bigram | 先提取 EN 再 jieba 切 CJK |

**效果**：BM25 Top-1 从 43% → 76%（30 queries × 21 docs）

**示例**：
```
"BM25参数: k1=1.2" 
  旧: ["BM","M2","25","k1","1=","=1","1.",".2"]  — 全是噪音
  新: ["bm25","k1","1.2","参数"]                   — 精确命中
```

### 2. 移除 Qwen3Embedding 路径

`ContextRetriever` 默认 `embedder=None`，不再加载 Qwen3-Embedding-0.6B。

**原因**：70% cosine + 30% BM25 混合后反而降到 43%。0.6B 模型对中文技术文档语义匹配太弱，cosine 相似度基本随机。

### 3. Reranker 评估

| 模型 | @1 (19 docs) | @1 (98 docs) | 耗时 |
|------|-------------|-------------|------|
| 纯 BM25 | 100% | 100% | 0.001s |
| BM25 + BGE-reranker-v2-m3 (2.2G) | 90% | 60% | 158s |
| BM25 + BCE-reranker-base_v1 (279M) | 30% | 30% | 4.4s |

**结论**：Cross-encoder reranker 在知识库场景下帮倒忙。干扰文档与正解共享大量文字时，reranker 将"更新版"排到"原版"前面。

**BCE 适用场景**：同主题下存在 3+ 条语义不同的文档时（如"存储架构有几层" vs "存储架构怎么初始化"），BCE 可补位。当前每个 topic 仅 1-2 条文档，不需要。

### 4. 单字 fallback（Unigram）

jieba 分词后追加 CJK 单字字符。解决查询和文档词面不同但语义相同的问题：

```
"有几层设计" vs "四层结构"
  jieba: ["几层","设计"] vs ["四层","结构"]  → 0 overlap
  +c1:   +["层"] vs +["层"]                  → 命中
```

当前测试集全部为精确关键词查询，无此类 case，前后无差异。已保留在 `_tokenize` 中。

## 当前最优配置

```python
retriever = ContextRetriever(store, refined, subagent)
# embedder=None (default) — 纯 BM25，无额外模型开销
# reranker=None (default) — 小规模不需要
```

## 规模扩展指南

| 条件 | 方案 |
|------|------|
| 单 topic < 3 docs | 纯 BM25 |
| 单 topic 3+ docs 且内容不同 | BM25 + BCE-reranker |
| 查询使用自然问法（非关键词） | BCEmbedding 的 `RerankerModel` / LLM query expansion |
| 500+ 总文档 | 加单字 fallback 已 cover |

## 相关文件

- `src/sisyphus/memory/retrieval.py` — `_tokenize`, `ContextRetriever`
- `.omo/test_bm25_vs_bge.py` — BGE 对比测试
- `.omo/test_bce_vs_bm25.py` — BCE 对比测试
- `.omo/test_scale.py` — BM25 规模测试（41/120/320 docs）
- `.cache/modelscope/maidalun/bce-reranker-base_v1` — 已下载的 BCE 模型

## 后续

- 补充自然问法测试 query（"有几层设计"而非"存储架构有几层"）
- 单 topic 3+ docs 时测 BCE 实际效果
- 探索 LLM query expansion 作为单字 fallback 的升级方案

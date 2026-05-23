# P4 计划调整记录

**日期**: 2026-05-23  
**原因**: P3 实测结果与原始假设不符，需要根据实测数据调整 P4 计划  
**原计划**: `plan-merged.html` → 已存档为 `plan-merged-v1-original.html`

---

## 原始 P4 计划 (v1)

| 组件 | 文件 | 状态 |
|------|------|------|
| Sleep Pipeline | `pipeline/sleep.py` | 待实现 |
| CLI tree rebuild | `cli/tree.py` | 待实现 |
| Qwen3-Reranker-0.6B | 需要 GPU | 不可能（无 GPU） |
| Qwen3-Embedding 前提 | — | 已砍 |
| Gate: 85%+ | — | — |

## 实测发现 (P3 中期)

1. **Qwen3-Embedding 拖后腿**：0.75cos + 0.25bm25 混合后 @1 从 76% 降到 43%。移除后纯 BM25 = 76%
2. **BGE-reranker 无收益**：2.2G 模型，@1 不增反降（稠密同 topic 下 87% → 60%）
3. **BCE-reranker 有条件收益**：279M CPU 可跑，同 topic ≥ 8 docs 时 +13%（87% → 100%）
4. **P3 有延期项**：四级降级链、TF-IDF O(N²)、list_nodes O(N²) 未完成

## 调整后 P4 计划 (v2)

### 新增

| 组件 | 文件 | 说明 |
|------|------|------|
| Sleep Pipeline | `pipeline/sleep.py` | 6 步编排，无 LLM 降级 |
| CLI tree rebuild | `cli/tree.py` | 手动重建 Memory Tree |
| BCE 自动激活 | `retrieval.py` | 同 topic ≥ 8 docs 时路由到 BCE |
| tests | `tests/test_sleep.py` | ~6 个测试 |

### 从 P3 延期

| 组件 | 文件 | 说明 |
|------|------|------|
| 四级降级链 | `retrieval.py` | Path A fail → Path B → raw fallback → empty |
| TF-IDF O(N²) fix | `retrieval.py` | `list.index()` 改 dict 查找 |
| list_nodes O(N²) fix | `tree.py` | 缓存 meta scan |

### 已砍掉

| 组件 | 原因 |
|------|------|
| Qwen3-Reranker | 需要 GPU，不可用 |
| Qwen3-Embedding | 实测负收益 |
| EmbeddingCache | 依赖 embedding |

### Gate

- 目标: 85%+ top-1
- 当前: 83% (ContextRetriever)
- 差距: 2%，依赖 BCE 同 topic 激活 + 降级链补位

---

## P4 文件清单

```
P4 新增:
  src/sisyphus/pipeline/sleep.py        ← Sleep 编排器
  src/sisyphus/cli/tree.py              ← CLI tree rebuild
  tests/test_sleep.py                   ← ~6 个测试

P4 修改 (P3 延期):
  src/sisyphus/memory/retrieval.py      ← 降级链 + BCE 激活 + TF-IDF fix
  src/sisyphus/memory/tree.py           ← list_nodes O(N²) fix
```

## 全 Phase 命中率演进 (修正后)

| Phase | 预期 | 实际 | 关键改动 |
|-------|------|------|----------|
| P0 | 58-62% | 56% | atomic_write + 锁 |
| P1-2 | ~70% | 56% | TreeStore + Builder |
| P3 | ≥80% | **83%** ✅ | jieba 分词 + TreeRetriever + 双路径 |
| P4 | 85%+ | — | Sleep + BCE + 降级链 |

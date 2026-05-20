# ADR-004: Memory Retrieval 2.0 — Context-Aware Layered Recall with Weight Decay

## Status

Draft (2026-05-20)

## Context

v1.4 解决了记忆存储的全链路——分层文件系统、反射、压缩、回路检测、子 agent 沙箱、缓存加速。但**读取能力仍停留在 v0 水平**：

1. **FrozenSnapshot** — 会话启动时建一次静态 Markdown，之后不再更新，长会话新鲜度断层
2. **Recall.search** — 需要 agent 主动调用工具才能搜记忆，如果 agent 忘了搜，记忆等于不存在
3. **搜索平铺** — 只有一层 flat LLM 调用，没有"先看模式 → 再看证据"的分层策略
4. **无遗忘机制** — 所有记忆权重相等，长周期下上下文窗口被低价值记忆占据

用户确认需要同时解决这四个问题。

## Decision

### 1. 记忆衰减字段

在 `Memory` dataclass 中新增两个字段，追踪每条记忆被召回的历史：

```python
@dataclass
class Memory:
    # ... 现有 25 个字段 ...
    recall_count: int = 0        # 已 +1 替换 repeat_count? 重名冲突说明见下
    last_recalled_at: str = ""   # ISO 格式时间戳
```

**注意**：现有 `recall_count`（见 `loop.py`）是`repeat_count`的别名用于回路检测。为避免混淆，新字段命名为 `recall_count` 但含义不同——"被召回次数" vs "重复出现次数"。回路检测的 `repeat_count` 保留不动。

衰减函数（无外部依赖）：

```python
def _decay_score(importance: int, days_since_recall: float) -> float:
    """指数衰减：30 天后重要性降一半，90 天剩 1/8。"""
    if days_since_recall < 0:
        days_since_recall = 0
    half_life_days = 30.0
    decay = 0.5 ** (days_since_recall / half_life_days)
    return importance * decay
```

- 从未被 recall 过的记忆：days_since_recall 按创建时间算
- 衰减后的分数仅在排序时用，不持久化（避免衰减的不可逆性）

### 2. 三层检索器 — ContextRetriever

取代现有的单层 `Recall.search()`，改为分三层逐步缩小范围：

```
ContextRetriever.retrieve(query, top_k=8)
    │
    ├── L1: MOC 层
    │   问 LLM：query 涉及哪些记忆类型？
    │   输出：["lesson", "pattern", "user_preference"]
    │   约束：不搜所有类型，只搜相关的
    │
    ├── L2: Refined 层（默认召回目标）
    │   在 L1 类型的 refined 记忆里搜
    │   问 LLM：哪些 reflections / summaries 和 query 相关？
    │   输出：refined memory IDs
    │   加分：refined 记忆有 evidence 链可追溯到 RAW
    │
    └── L3: RAW 层（按需）
       如果 refined 结果不够 top_k，补 RAW 的：
       问 LLM：query 在哪些记忆里
       输出：raw memory IDs
       └── 衰减排序：按 decay_score 排序取 top
```

L1 可省略：如果 query 很短或无类型信号，跳过 L1 直接做 L2+L3。

### 3. MemoryContext — 自动上下文构建

每轮对话前调用，取代目前的 `FrozenSnapshot.build()`。

```python
class MemoryContext:
    """记忆上下文构建器。在每轮对话前自动调用。

    每次调用：
    1. 通过 ContextRetriever 检索当前 query 相关记忆
    2. 如果不新鲜（超过 N 轮），刷新完整 snapshot
    3. 返回 Markdown 上下文块
    """

    def __init__(self, store, refined, subagent, refresh_interval: int = 5):
        ...

    def build(self, query: str, turn_count: int) -> str:
        """构建本轮上下文。

        - 如果 turn_count - last_build_turn >= refresh_interval：
          做完整三层检索，重建完整 snapshot
        - 否则：
          只做轻量 L2+L3 增量检索，追加到当前 snapshot 顶部
        - 更新 衰减分数 并排序
        - 截断到 max_chars
        """
```

输出示例：

```markdown
<sisyphus_context>
--- 持续记忆 ---
[reflection] 项目使用 Python 3.9 + TDD | importance=8
  Three key conventions: type annotations, TDD, SSOT.
[lesson] DeepSeek 缓存命中率 91.5% | importance=7
  磁盘缓存 + append-only 即可享受高命中率
--- 增量记忆 (本回合) ---
[project_context] 当前工作在 sisyphus repo | importance=5
  PYTHONPATH=src，148 tests green
</sisyphus_context>
```

### 4. 衰减排序与上下文压缩

当构建的上下文超过 `max_chars` 时：

1. 按 `decay_score` 降序排列所有候选记忆
2. 从高分到低分依次填入，直到满 `max_chars`
3. 被裁剪的低分记忆不丢弃——只在下次 recall_count 更新的循环中自然降权
4. 每次 `retrieve()` 命中某条记忆时，`recall_count += 1`，`last_recalled_at = now`

### 5. 与现有组件的集成

```
每轮对话前
    │
    ├── MemoryContext.build(query, turn_count)
    │       │
    │       ├── ContextRetriever.retrieve(query)
    │       │       │
    │       │       ├── [L1] Subagent: type filter (mockable)
    │       │       ├── [L2] Subagent: refined recall (mockable)
    │       │       └── [L3] Subagent: raw recall + decay sort
    │       │
    │       ├── 更新 MemoryStore 中召回统计
    │       └── 返回 Markdown 上下文
    │
    └── (上下文注入 system prompt)
```

SubagentLauncher 复用已有的 `recall_search` / `recall_relevant` 任务类型。

### 6. 文件变更清单

#### 新文件

| 文件 | 职责 |
|------|------|
| `retrieval.py` | `ContextRetriever` — 三层检索 + 衰减打分 |
| `context.py` | `MemoryContext` — agent 调用的自动上下文构建 |

#### 改文件

| 文件 | 改动 |
|------|------|
| `store.py` | `Memory` 加 `recall_count: int` 和 `last_recalled_at: str` |
| `store_v2.py` 对应测试 | 验证新字段默认值 |
| `subagent.py` | 加 `recall_search_refined` / `recall_type_classify` handler |
| `snapshot.py` | 可选 refresh 机制（向后兼容） |

### 7. 测试策略

| 层级 | 测试内容 | 方式 |
|------|----------|------|
| 衰减函数 | `_decay_score` 数学正确性 | 纯函数单元测试 |
| ContextRetriever | 三层流程 | MockSubagent 验证调用顺序 |
| MemoryContext | 刷新间隔、增量 vs 完整 | MockRetriever 验证 build |
| store_v2 | 新字段默认值 | 直接断言 |

### 8. 边界情况

- **query 为空** → 跳过 L1/L2，直接取最近衰减分最高的 top_k 条
- **单层 MOC 无匹配** → 跳过该层，不报错
- **衰减后全部低于阈值** → 至少返回 1 条（保证上下文不空）
- **多条记忆 recall_count 同时更新** → 批量更新 store（单次 flush）
- **和现有回路检测的 repeat_count 不冲突** → 两个字段不同含义，互不干扰

## 后果

### 正面

- 每轮自动注入相关记忆，不需要 agent 主动搜
- 分层检索减少 LLM 调用量（L1 确定类型后 L2 只需要在局部搜）
- 衰减确保上下文窗口被高价值记忆占据
- 增量模式减少长会话中的上下文波动

### 负面

- 每轮多一次 subprocess 调用（毫秒级延迟）
- Memory 文件增加两个字段，所有现有文件不向后兼容（新字段有默认值，读旧文件不报错但 `last_recalled_at` 为空）
- 衰减排序增加复杂度，需要验证排序正确性

### 缓解

- Subprocess 平均耗时 < 200ms（纯 LLM 推理无 IO），可接受
- 新字段默认值=0/""，读旧文件自动补全，无需迁移
- 衰减函数纯计算，无副作用，可单独测试

## 参考

- Generative Agents (Park et al.) — 每日 Reflection + 检索
- Mem0 — entity-linking 分层召回
- A-Mem — 动态记忆架构，权重衰减 + 时间衰减
- Anthropic 的 "memory as context" 模式

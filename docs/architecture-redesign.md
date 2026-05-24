# Sisyphus 架构重设计：从 MemoryRetriever 到 ContextAssembler

> 日期: 2026-05-24  
> 基础: "一切记忆都是上下文组装"  
> 对比: 当前实现 vs 目标设计

---

## 一、当前架构

```
AgentMemory.before_turn(query)
  │
  ├─ MemoryContext.build(query, turn_count, max_chars=4000)
  │     ├─ dirty? → retriever.retrieve()  // 全量检索
  │     └─ !dirty → retriever.retrieve_refined_only()  // 轻量刷新
  │
  └─ ContextRetriever.retrieve(query, top_k=8)
        ├─ L1: MOC type 分类 → 缩小范围
        ├─ L2: Refined 检索 → 反思层优先
        ├─ L3: RAW 检索 → BM25 / TF-IDF / Qwen3-Embedding
        ├─ Reranker (条件激活)
        └─ decay_score 排序 → top_k
              ↓
        _format_context(memories, max_chars) → "<sisyphus_context>..."
```

**问题**：

| 问题 | 说明 |
|------|------|
| 单 pipeline，无分层组装 | 所有来源混在同一个 retriever 里，无法独立控制配额和优先级 |
| 无 PERSIST 层 | 项目上下文和普通记忆混在一起，可能被裁切掉 |
| 无 scene 感知 | 编码/规划/调试用同一套检索策略 |
| 无 source 抽象 | 加 CodeGraphContext 只能硬改 retriever 内部 |
| 前缀缓存不友好 | PERSIST 应该在 session 开始时 frozen，当前每次 build 都重新检索 |

---

## 二、目标架构

```
ContextAssembler.assemble(query, scene="coding")
  │
  ├─ Budget.allocate(total=8000)
  │
  ├─ Source[0]: PERSIST (frozen, 无条件) 
  │     └─ 返回: 项目上下文、架构决策、核心模式
  │     配额: 2000 chars, frozen after first build
  │
  ├─ Source[1]: HOT (7 天内，按相关性)
  │     └─ 返回: 近期教训、决策、模式
  │     配额: budget.allocate(0.3) = 1800 chars
  │
  ├─ Source[2]: SKILL (条件触发)
  │     └─ 返回: 匹配的 skill 指令
  │     配额: 按需、有上限
  │
  ├─ Source[3]: CODE (按需, scene=coding 时激活)
  │     └─ 返回: 函数签名、调用链、模块依赖
  │     配额: budget.allocate(0.2) = 1200 chars (coding)
  │
  ├─ Source[4]: COLD (兜底)
  │     └─ 返回: 其余衰减记忆
  │     配额: budget.remaining()
  │
  └─ trim_to_budget(ctx) → 返回拼接文本
```

---

## 三、Source 接口

```python
class Source(ABC):
    """上下文来源的抽象接口"""
    
    name: str              # "PERSIST" | "HOT" | "SKILL" | "CODE" | "COLD"
    priority: int           # 组装顺序（0 最高）
    
    @abstractmethod
    def assemble(self, query: str, budget: int) -> list[TextBlock]:
        """组装上下文块，不超过 budget 字符"""
        ...

class TextBlock:
    text: str               # 上下文文本
    source: str             # 来源标记
    tokens: int             # token 估算
    frozen: bool            # 是否可在 session 内缓存
```

---

## 四、ContextAssembler

```python
class ContextAssembler:
    def __init__(self, sources: list[Source], plan: AssemblyPlan):
        self.sources = sorted(sources, key=lambda s: s.priority)
        self.plan = plan
    
    def assemble(self, query: str, scene: str = "coding") -> str:
        total_budget = self.plan.total_budget  # 8000 chars
        quota = self.plan.quotas.get(scene, DEFAULT_QUOTAS)
        
        ctx = []
        remaining = total_budget
        
        for source in self.sources:
            budget = min(quota.get(source.name, 0), remaining)
            if budget <= 0:
                break
            blocks = source.assemble(query, budget)
            for block in blocks:
                ctx.append(block.text)
                remaining -= len(block.text)
        
        return "\n".join(ctx)

class AssemblyPlan:
    total_budget: int = 8000
    
    quotas: dict[str, dict[str, int]] = {
        "coding": {
            "PERSIST": 2000,
            "HOT": 2400,
            "SKILL": 800,
            "CODE": 1200,
            "COLD": 1600,     # remainder
        },
        "planning": {
            "PERSIST": 2000,
            "HOT": 2400,
            "SKILL": 600,
            "CODE": 0,        # 不装代码
            "COLD": 3000,
        },
        "debugging": {
            "PERSIST": 2000,
            "HOT": 3000,
            "SKILL": 600,
            "CODE": 1200,
            "COLD": 0,        # 调试时不用冷记忆
        },
    }
```

---

## 五、每个 Source 的实现

### PERSIST Source

```python
class PersistSource(Source):
    name = "PERSIST"
    priority = 0
    
    def __init__(self, store: MemoryStore):
        self.store = store
        self._frozen: str | None = None  # session 级缓存
    
    def assemble(self, query: str, budget: int) -> list[TextBlock]:
        if self._frozen is not None:
            return [TextBlock(self._frozen, "PERSIST", frozen=True)]
        
        # 首次组装：加载 pinned=True 或 importance>=8 的 project_context/decision
        mems = [m for m in self.store.list()
                if m.pinned or (m.importance >= 8 and m.type in ("project_context", "decision"))]
        
        formatted = _format_entries(mems, budget, header="## PERSIST\n")
        self._frozen = formatted
        return [TextBlock(formatted, "PERSIST", frozen=True)]
```

### HOT Source

```python
class HotSource(Source):
    name = "HOT"
    priority = 1
    
    def __init__(self, store: MemoryStore, days: int = 7):
        self.store = store
        self.days = days
    
    def assemble(self, query: str, budget: int) -> list[TextBlock]:
        cutoff = datetime.now(timezone.utc) - timedelta(days=self.days)
        recent = [m for m in self.store.list()
                  if m.created_at and datetime.fromisoformat(m.created_at) > cutoff]
        scored = [(m, _keyword_score(m, query)) for m in recent]
        scored.sort(key=lambda x: -x[1])
        formatted = _format_entries([m for m, _ in scored], budget, header="## Recent\n")
        return [TextBlock(formatted, "HOT")]
```

### CODE Source (新增)

```python
class CodeSource(Source):
    name = "CODE"
    priority = 3
    
    def __init__(self, cgc_client=None):
        self.cgc = cgc_client  # CodeGraphContext client
    
    def assemble(self, query: str, budget: int) -> list[TextBlock]:
        if self.cgc is None:
            return []
        # 调用 CodeGraphContext: analyze_callers / find_name 等
        func_name = _extract_function_name(query)
        if func_name:
            callers = self.cgc.analyze_callers(func_name)
            text = f"## Code Context\n{_format_callers(callers)}"
            return [TextBlock(text[:budget], "CODE")]
        return []
```

---

## 六、改前 vs 改后对比

| 维度 | 改前 (ContextRetriever) | 改后 (ContextAssembler) |
|------|------------------------|------------------------|
| 入口 | `AgentMemory.before_turn(query)` | `ContextAssembler.assemble(query, scene)` |
| 来源 | 单一 retriever，内部 3 层 | 多个独立 Source，优先级排队 |
| PERSIST | ❌ 无 | ✅ frozen，session 级缓存，无条件注入 |
| HOT | ❌ 无独立概念 | ✅ 7 天内优先检索 |
| CODE | ❌ 无 | ✅ CodeGraphContext 作为 Source |
| 配额 | 全局 max_chars | 分层配额 + 场景切换 |
| 场景感知 | ❌ 无 | ✅ coding/planning/debugging 切换配额 |
| 前缀缓存 | ❌ 每次重新检索 | ✅ PERSIST frozen，其余按需 |
| 扩展性 | 改 retriever 内部 | 加一个 Source 类 |

---

## 七、迁移路径（向后兼容）

不需要一次全改。可以逐步迁移：

```
Step 1: 加 Source 接口 + PERSIST Source
        → 先让项目上下文无条件注入，其余仍然走旧 retriever

Step 2: 加 HOT Source + ContextAssembler
        → PERSIST + HOT + 旧 retriever 作为 COLD fallback

Step 3: 加 CODE Source
        → 引入 CodeGraphContext

Step 4: 加 SKILL Source + scene 切换
        → 完整组装管线
```

每一步都不破坏现有功能。`AgentMemory.before_turn()` 保持接口不变，内部切到 `ContextAssembler`。

---

## 八、文件结构

```
src/sisyphus/memory/
├── context.py         → 保留 AgentMemory, 内部切到 assembler
├── assembler.py       → 新增: ContextAssembler + AssemblyPlan
├── source/
│   ├── __init__.py
│   ├── base.py        → Source ABC + TextBlock
│   ├── persist.py     → PersistSource
│   ├── hot.py         → HotSource
│   ├── skill.py       → SkillSource (后续)
│   ├── code_source.py → CodeSource (CodeGraphContext bridge)
│   └── cold.py        → ColdSource (包装旧 ContextRetriever)
├── retrieval.py       → 保留 ContextRetriever 作为 ColdSource 内部引擎
```

---

## 九、一句话

```
改前: "把所有记忆搜一遍，挑最相关的 10 条塞进 prompt"
改后: "每个来源有配额，按场景优先级拼装上下文"
```

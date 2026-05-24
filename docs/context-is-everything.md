# Sisyphus 重构：一切记忆都是上下文组装

> 日期: 2026-05-24  
> 核心洞察: "所有的数据对于模型来说不过是提示词和上下文罢了"

---

## 一、本质

所有记忆系统做的事完全相同：

```
Mem0:    向量相似度 → top-k → 拼接 → 塞进 prompt
Letta:   pinned block + 向量搜索 → 拼接 → 塞进 prompt
Hermes:  frozen MEMORY.md → 直接塞进 prompt
Claude:  MEMORY.md索引 + 后台提取 → 塞进 prompt
Sisyphus: BM25 + LLM recall → <sisyphus_context> → 塞进 prompt
```

差异只在**组装规则**——先装什么、装多少、什么时候刷新、装不下了怎么裁。

---

## 二、概念统一

| 传统叫法 | 实质 |
|----------|------|
| PERSIST 层 | 每 turn 无条件 prepend 固定文本，配额 ≤2000 chars |
| HOT 索引 | 按时间+相关性排序，挑 top-k |
| Dream | 离线预计算"将来可能用得上的好文本" |
| Compress | 离线把旧文本压缩成更短的等效文本 |
| Skill | 按触发条件动态 append 指令 |
| 代码索引 | 函数签名/调用链翻译成文本 |
| before_turn | 上述所有规则的调度器 |
| after_turn | 异步写回，填充下次的候选池 |
| 半衰期 | 排序分数的时间权重 |
| 冷热分层 | 先搜小池子快，不够再搜大池子 |

**没有"记忆"这种东西，只有"上下文窗口的组装策略"。**

---

## 三、简化后的架构

```
before_turn(query):
    ctx = []
    budget = REMAINING_BUDGET
    
    // L0: 无条件（frozen，prefix-cacheable）
    ctx += SYSTEM_PROMPT           // 身份、工具、基本规则，不变
    ctx += PERSIST.load()          // 项目上下文，≤ 2000 chars
    
    // L1: 条件匹配（按优先级填充）
    ctx += HOT.search(query, budget=budget*0.4)    // 7天内相关
    ctx += SKILL.match(query, budget=budget*0.2)   // 触发式加载
    
    // L2: 按需（剩余配额）
    if context_needs_code(query):
        ctx += CODE.search(query, budget=remaining)
    if context_needs_history(query):
        ctx += COLD.search(query, budget=remaining)
    
    // 硬上限裁切
    return trim_to_budget(ctx)
```

**四个设计原则**：

1. **配额制，不是类型制** — 不是"PERSIST 存什么类型"，而是"PERSIST 占多少 token 预算"。写太多就裁底部。
2. **排序优先级场景化** — 编码优先 CODE + 最近 debug 记录，规划优先决策 + 架构图，调试优先错误模式 + 调用链。
3. **上下文窗口就是可视化** — 显示每层占多少、裁了什么、上次组装时间。
4. **Dream/Compress 就是离线预填缓存** — 提前算好下次可能用得上的好文本，省实时检索开销。

---

## 四、这个视角的好处

**之前纠结的问题直接消失**：

| 纠结 | 消除 |
|------|------|
| "PERSIST 该存多少条？" | → 配额说了算，存到 2000 chars 为止 |
| "热记忆和冷记忆怎么分？" | → 同一条记忆，只是两个搜索池子，hot 查得快 |
| "Dream 什么时候触发？" | → 配额有富余就触发，预填缓存 |
| "为什么要可视化？" | → 就是看上下文窗口的占用量和内容 |
| "半衰期应该是几天？" | → 只是一个排序权重，不是"强制遗忘" |
| "需要几个 MCP server？" | → 只是上下文来源的多样性，统一调度 |

---

## 五、实施影响

### 当前架构不需要大改

```
现有:  before_turn() → ContextRetriever → <sisyphus_context>
改为:  before_turn() → ContextAssembler(sources=[PERSIST, HOT, SKILL, CODE, COLD]) → ctx

ContextRetriever 变成 ContextAssembler 的一个 source。
```

### 新增概念

| 新增 | 含义 |
|------|------|
| `ContextAssembler` | 替代 `MemoryContext`，调度所有 source |
| `Source` | 抽象接口: `.search(query, budget) → [text_block]` |
| `Budget` | token 配额管理器: `.allocate(n)` `.remaining()` |
| `AssemblyPlan` | 场景化组装策略: `{layers: [...], ratios: [...]}` |

### Memory dataclass 不变

`pinned` / `project` / `scope` 这些字段只是帮助 source 做排序和过滤的元数据，不影响组装逻辑。

---

## 六、已有文档映射

本视角下，之前所有文档仍然有效，只是视角换了：

| 旧文档 | 新视角下的含义 |
|--------|---------------|
| `memory-defects-plan.md` | 当前 source 的实现缺陷 |
| `memory-architecture-v2.md` | PERSIST/HOT/CODE/COLD 作为 source 的实现方案 |
| `market-comparison-v2.md` | 各系统的 source 组装策略对比 |
| `mcp-wechat-debug.md` | MCP 作为一个 source 接入失败的原因 |

---

## 七、一句话总结

> Sisyphus 不存储记忆。它组装上下文。Dream 是缓存预填，HOT 是快速池子，PERSIST 是永不裁切的页眉，半衰期是时间权重——全都在做同一件事：把最有用的文本，塞进模型前置的几千个 token 里。

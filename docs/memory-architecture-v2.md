# Sisyphus 记忆系统深度分析：分层架构与代码索引

> 日期: 2026-05-24  
> 版本: v2 — 增加长时效记忆 + 项目记忆 + 代码索引架构设计

---

## 一、当前架构诊断

### 现有四层结构

```
RAW (file-based .md)        → 91 条 (69 Test)
  ↓
REFINED (Dream + Compress)  → 1 条 (几乎为空)
  ↓
MOC (type-grouped index)    → 0 条 (被 store.py 覆盖)
  ↓
AGENT (before_turn 注入)    → <sisyphus_context> 块
```

### TreeStore 层级

```
tree/l0.json    → 根节点（全局摘要）
tree/l1/        → 类型/簇摘要
tree/l2/        → 叶子（单条记忆）
```

### 核心缺陷：时间维度 vs 重要性维度混淆

当前所有记忆只区分 **hot（7天）vs cold（其余）**，基于创建时间。但**项目级知识没有"过期"概念**。

```
当前: 所有记忆 → decay_score(180天) → 按分数排序
问题: project_context 写于 6 个月前，跟一条 Test 垃圾衰减到同分
```

---

## 二、新增：记忆耐久度分层

### 按生命周期区分，而非仅按时间

| 层级 | 名称 | 生命周期 | 包含内容 | 检索优先级 | 示例 |
|------|------|----------|----------|-----------|------|
| **L-PERSIST** | 持久层 | 永不过期 | 项目上下文、架构决策、核心模式 | 每次 turn 必加载 | "sisyphus 是四层记忆系统，路径 ~/.omo/memory/" |
| **L-HOT** | 热层 | 7 天窗口 | 近期决策、教训、模式 | 优先检索 | "刚刚发现 store.py 和 moc.py 写冲突" |
| **L-CODE** | 代码索引 | 随代码更新 | 函数签名、调用链、模块依赖 | 按需查询 | "retrieve() 被哪些函数调用" |
| **L-COLD** | 冷层 | 长期衰减 | 其他所有历史记忆 | fallback 检索 | "3 个月前那个 BM25 调优记录" |

### L-PERSIST（新增）

不参与 decay，不参与 time-based 淘汰。`before_turn()` **无条件注入**，不占 top_k 配额。

**入选标准**：
- `importance >= 8` 且 `type in (project_context, decision, pattern)`
- 或者手动标记 `pinned: true`

**存储**：`PERSIST.md` 独立索引，与 `HOT.md` / `INDEX.md` 并列。

```python
# before_turn() 改为
pinned = self._load_persist()           # 必加载，不占配额
hot = self.retriever.retrieve_hot(...)   # 7天内优先
cold = self.retriever.retrieve(...)      # fallback 全量
context = self._merge(pinned, hot, cold)
```

---

## 三、项目记忆（Project Memory）专门化

### 它与 L-PERSIST 的关系

L-PERSIST 是**机制**（如何标记+存储+加载），项目记忆是**内容**（存什么）。

项目记忆 = 属于当前项目的 L-PERSIST 条目：

```
项目记忆清单:
  ├── 项目概述: 这是什么项目、技术栈、目录结构
  ├── 架构决策: 为什么选 X 不选 Y（ADRs）
  ├── 核心模式: 项目级的编码约定
  ├── 关键教训: 重大 bug 和解决方案
  └── 当前状态: 活跃分支、未完成特性
```

### 实现方式

在 `Memory` dataclass 加字段：

```python
@dataclass
class Memory:
    # ... existing fields ...
    pinned: bool = False          # PERSIST 层标记
    project: str = ""             # 所属项目（sisyphus/opencode/disk-demo）
    scope: str = "global"         # global | project | session
```

### 加载优先级

```
before_turn("如何改进检索？")
  │
  ├─ 1. PERSIST: pinned=True 或 importance≥8 的 project_context/decision
  │     → "sisyphus 路径 ~/.omo/memory/, 四层架构, P5已完成MCP升级"
  │
  ├─ 2. HOT: 7天内, 按 decay 排序
  │     → "昨天发现 store/moc 写冲突"
  │
  └─ 3. COLD: 其余, 按 decay 排序
        → "3个月前 BM25 @1 56%→83%"
```

---

## 四、代码索引集成方案

### 两层索引

| | 记忆索引 | 代码索引 |
|---|---|---|
| **存什么** | 对话经验、决策、教训 | 函数签名、调用关系、类继承 |
| **怎么存** | File-based .md | KùzuDB 图数据库 |
| **检索方式** | BM25 + decay + LLM recall | 图查询：callers/callees/chain |
| **MCP Server** | sisyphus (stdio Python) | codegraphcontext (stdio Python) |
| **更新时机** | 每次 turn 后 | `cgc watch` 文件变更 |

### 统一入口

agent 通过 MCP 协议同时访问两个 server，不感知后端：

```
agent 问: "retrieval.py 的 retrieve() 被哪些地方调用了？"
  │
  ├─ codegraphcontext MCP:
  │     cgc analyze callers retrieve --file retrieval.py
  │     → [context.py:87, context.py:93, mcp.py:67, mcp.py:74]
  │
  └─ sisyphus MCP:
        search_memory("retrieval 调用链")
        → "决策: retrieve() 需加 Reranker 路由，已在 P4 实现"
```

### 部署方式

```bash
# 两个 MCP Server 并列运行
openocode mcp add sisyphus -- python3 -m sisyphus.server.mcp
openocode mcp add codegraph -- cgc mcp start
```

agent 拿到 `mcp__sisyphus__search_memory` 和 `mcp__codegraphcontext__analyze_callers`，统一工具列表。

---

## 五、对比：改前 vs 改后

| 维度 | 改前 | 改后 |
|------|------|------|
| 记忆耐久 | 全部参与 180 天衰减 | L-PERSIST 永久 / L-HOT 7天 / L-COLD 衰减 |
| 项目上下文 | 混在 90 条里，检索概率低 | PERSIST 层无条件注入 |
| 代码知识 | 零 | codegraphcontext 图索引 |
| before_turn | 一次检索 | 三层合并：PERSIST + HOT + COLD |
| 记忆作用域 | 无区分 | global / project / session |
| MCP Server | 1 个 (sisyphus) | 2 个 (sisyphus + codegraphcontext) |

---

## 六、实施路线（更新）

```
P0-2 (写冲突) → P0-1 (REFINED) → P2-1 (清理 Test)
    ↓
P1-5 (L-PERSIST 持久层 + pinned/project/scope 字段)
    ↓
P1-4 (HOT.md 7天热索引) → P1-3 (MCP tool 注入)
    ↓
P1-1 (自动触发) → P1-2 (自动提取)
    ↓
P1-6 (CodeGraphContext 集成)
```

新增了两项：
- **P1-5**: L-PERSIST 持久层（pinned 标记 + project/scope 字段 + PERSIST.md）
- **P1-6**: CodeGraphContext MCP Server 集成

---

## 七、Memory 字段扩展方案

```python
@dataclass
class Memory:
    # 现有字段
    id: str
    type: str          # lesson/decision/pattern/project_context/note/user_preference/compressed/reflection
    title: str
    content: str
    tags: list[str]
    created_at: str
    importance: int    # 1-10
    
    # 新增 — 耐久度分层
    pinned: bool = False       # True → PERSIST 层，无条件注入
    scope: str = "global"      # global | project | session
    project: str = ""          # 所属项目名
    
    # 新增 — 代码关联（可选）
    code_refs: list[str] = []  # 关联的代码路径: ["retrieval.py:87", "store.py:104"]
```

---

## 八、相关记忆

- `mem_8d4225c935d7` — 综合评估 v1
- `mem_231c391bb72b` — 四层架构现状
- `mem_97d963afe918` — 代码索引方案
- `mem_6e0bb92e04b0` — 改进方案讨论结论

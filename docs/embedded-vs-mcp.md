# Sisyphus 应该是 agent 内嵌，不是 MCP Server

> 日期: 2026-05-24  
> 核心: before_turn 是预处理，不是工具调用

---

## 一、根本问题

MCP 协议的设计意图是**工具调用**——agent 主动决定"我要用这个工具"。但 `before_turn()` 的本质是**上下文预处理**——在 agent 开始思考之前，先把相关记忆注入 prompt。

把上下文预处理包装成 MCP 工具，等同于把操作系统的内核改成网络服务——每次要读内存，先走 TCP 协议发请求。

---

## 二、拆开看：9 个 MCP 工具，两类操作

```
被动（预处理，不该是 MCP）：
  get_context         → 应该在 before_turn 里自动跑，agent 不需要"调用"它
  memory_stats        → agent 偶尔主动查，适合 MCP

主动（工具操作，适合 MCP / Skill）：
  write_memory        → agent 决定记录一条记忆
  search_memory       → agent 主动搜索特定内容
  get_memory          → agent 按 ID 查详情
  list_memories       → agent 浏览所有记忆
  delete_memory       → agent 决定删除
  run_pipeline        → agent 触发后台任务
  import_memories     → agent 导入历史数据
```

**9 个工具中，只有 1 个真正不该是 MCP：`get_context`。** 但就这一个，恰恰是最核心的——它是整个记忆系统价值的入口。

---

## 三、为什么不该是 MCP

### 作为 MCP 工具的问题

```
Agent 流程:
  1. 收到用户消息
  2. 需要决定"要不要调用 get_context"  ← 它怎么知道？
  3. 如果不知道，就不会调
  4. 不调 → 无记忆注入 → 无上下文 → 失忆

结果: WeChat bridge 的 agent 从来不用 get_context，因为没有 system prompt 告诉它
```

### 作为内嵌模块

```
Agent 流程:
  1. 收到用户消息
  2. before_turn(query) 自动跑
  3. PERSIST + HOT 上下文已注入 prompt
  4. agent 开始思考 → 天然有记忆

结果: 无需 agent 知道记忆系统的存在，上下文自然到位
```

---

## 四、推荐架构：混合

```
┌──────────────────────────────────────────┐
│  Agent 内嵌（Python import）              │
│                                          │
│  AgentMemory.before_turn(query)          │
│    ├─ PERSIST.load()                    │
│    ├─ HOT.search()                      │
│    ├─ CODE.search()                     │
│    └─ COLD.search()                     │
│         ↓                                │
│    上下文注入 prompt                      │
│                                          │
│  AgentMemory.after_turn()               │
│    └─ Extractor → 自动写 RAW             │
│         ↓                                │
│    后台 Dream / Compress                 │
└──────────────────────────────────────────┘
                    │
      主动操作走 MCP / Skill
                    │
┌──────────────────────────────────────────┐
│  MCP Server（保留，精简）                  │
│                                          │
│  write_memory      → 手动记录            │
│  search_memory     → 主动搜索            │
│  memory_stats      → 仪表盘              │
│  get_memory        → 查看详情            │
│  list_memories     → 浏览               │
│  delete_memory     → 删除               │
│  run_pipeline      → 触发后台            │
│  import_memories   → 导入               │
└──────────────────────────────────────────┘
```

**`get_context` 从 MCP 工具列表移除**。它的功能由内嵌的 `before_turn()` 完成。

---

## 五、对 WeChat Bridge 的影响

当前 WeChat bridge 的问题根因现在很清楚了：

```
Bridge agent 不知道 sisyphus MCP 存在
  → 不会调用 get_context
  → 无记忆注入
  → 失忆

如果 before_turn 是内嵌的:
  → Bridge agent 启动时自动加载 sisyphus 模块
  → 每 turn 自动注入上下文
  → 不需要 agent 知道 MCP 存在
```

WeChat bridge 现在是通过 bash + Python 直接调 sisyphus 绕过 MCP 的——这说明**内嵌路已经走通了**，MCP 反而成了多余的那层。

---

## 六、实施

```
Step 1: 把 before_turn/after_turn 从 mcp.py 剥离到独立的 agent 集成层
        → sisyphus 作为 Python package import，不是 MCP subprocess

Step 2: MCP Server 只保留 8 个主动工具
        → 去掉 get_context

Step 3: opencode 集成:
        → from sisyphus.memory.context import AgentMemory
        → memory = AgentMemory(...)
        → context = memory.before_turn(query)  # 自动跑

Step 4: 如果其他 agent 需要 MCP 工具（write/search/stats）
        → python3 -m sisyphus.server.mcp  ← 仍然可用，但只提供主动工具
```

---

## 七、一句话

> `before_turn` 不应该是一个工具调用，就像 `import` 不应该是一个 HTTP 请求。内嵌是它本该在的地方，MCP 是主动操作的通道。

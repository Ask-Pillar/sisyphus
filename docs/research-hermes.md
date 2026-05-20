# Hermes Agent 分析报告：Sisyphus 进化参考

**分析日期**: 2026-05-20
**来源**: github.com/NousResearch/hermes-agent (15.8 万星)

## 概述

Hermes Agent 是 Nous Research 构建的自进化 AI agent。
Python 实现，MIT 许可。核心差异化：**learning loop**。

## 值得学习的

### 1. 记忆系统（Memory System）

Hermes 有两级记忆：

**持久记忆（Persistent Memory）**:
- `MEMORY.md` — agent 的个人笔记，2200 字符限制
- `USER.md` — 用户画像，1375 字符限制
- 两者在 session 开始时以冻结快照注入 system prompt
- 中间不变 → 保持 prefix cache
- Agent 用 `memory` 工具（add/replace/remove）管理

**Session Search**:
- SQLite FTS5 存储所有历史会话
- 支持全文搜索（~20ms 查询）
- 搜索时自动分组、截断、LLM 摘要

### 2. Learning Loop（核心差异）

- 完成复杂任务后自动创建 skill 文档
- skill 在使用中自我改进
- 跨 session 用户建模（Honcho dialectic）
- "The agent that grows with you"

### 3. 子代理委托（Delegation）

```
User → Hermes (brain, planning, memory)
  ├── delegate_task (basic subagent)
  ├── code_execution (Python RPC)
  └── opencode (OMO meta-subagent via plugin)
```

### 4. 工具设计

- `AIAgent` 类有 ~60 个初始化参数
- 工具集（toolsets）可插拔
- 工具调用迭代上限默认 90 轮
- 内置 browser、shell、file I/O 等

### 5. Cron 调度

自然语言调度："每天发报告"、"每周审计"
systemd 服务化运行。

## 不适用于 Sisyphus 的

- SQLite 存所有 session 消息——Sisyphus 不是 full runtime
- 60 参数 AIAgent 类太臃肿
- Cron 调度是第四期的事

## 关键收获

> **Memory as frozen snapshot** 是最有价值的模式——在 session 开始时锁定记忆快照，
> 既保持 prefix cache，又保证记忆一致性。
> Learning loop 是终极目标，但 memory 是前提。

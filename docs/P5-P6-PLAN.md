# P5-P6 规划草案

## P5: 多客户端 + 跨 Agent 共享 + Gate 收官

### 背景
P4 完成了单客户端下的完整检索管道。但系统定位是 MCP Server——需要支持多个 AI 客户端（opencode、Claude Code、Cursor 等）同时连接，共享同一份记忆。当前 stdio 1:1 模式不支持并发。

### 交付物

| 组件 | 文件 | 说明 |
|------|------|------|
| 读写锁 | `memory/utils.py` | 文件级锁防并发写冲突 |
| Session 隔离 | `server/mcp.py` | 每个客户端独立 session，共享底层 MemoryStore |
| 多客户端验证 | — | 同时启动 2 个 opencode session 读写同一目录 |
| Gate 85% | — | 补文档内容或等 BCE 触发 |

### Gate 目标

- 补 3 条不可答 query 对应的文档内容
- 或等数据涨到 8+/topic 触发 BCE 自然过
- 两者任一达成即过 P5 gate

## P6: 自我学习循环

### 背景
Hermes Agent 的核心差异化是 learning loop——完成复杂任务后自动创建 skill。Sisyphus 已经积累了足够的记忆基础设施，可以跨出这一步。

### 交付物

| 组件 | 说明 |
|------|------|
| 模式识别 | 从 recall_count 和 decay 中识别高频使用模式 |
| Skill 生成 | 同类型记忆 ≥ 5 条时自动生成总结/最佳实践 |
| Skill 注入 | 生成的 skill 自动作为系统 prompt 的一部分 |

### 灵感来源

- Hermes Agent: "The agent that grows with you"
- OpenHuman: tool-scoped memory with priority pinning
- 你自己的 Memory Tree: 层级摘要已经做了，skill 是它的自然延伸

---

## 里程碑

| Phase | 核心交付 | Gate | 预计新增测试 |
|-------|----------|------|-------------|
| P5 | 多客户端 + 读写锁 | 85% @1 | ~8 |
| P6 | 自我学习循环 | 新生 skill 准确率 | ~6 |

当前状态:

```
P0 ✅ → P1 ✅ → P2 ✅ → P3 ✅ → P4 ✅ → P5 📋 → P6 📋
```

# Sisyphus 全局集成：AGENTS.md 就是全局指令

> 日期: 2026-05-24  
> 问题: 每个项目配 AGENTS.md 太麻烦，能不能全局？

---

## 一、业界全局方案

| 项目 | 全局文件 | 位置 | 作用域 |
|------|----------|------|--------|
| **Claude Code** | `~/.claude/CLAUDE.md` | 用户 home | 所有项目 |
| **Hermes** | `~/.hermes/SOUL.md` | 用户 home | 全局身份 |
| **Cursor** | User Rules (Settings) | Cursor 设置 | 所有项目 |
| **Sisyphus** | `workspace/AGENTS.md` | 工作区根 | **所有子项目** |

**Sisyphus 已经有全局 AGENTS.md 了**——就在工作区根目录，覆盖 `opencode`、`disk-demo`、`sisyphus` 和将来的所有项目。只要把这个文件写好，所有 agent session 自动加载。

---

## 二、全局 vs 项目级

```
~/.config/opencode/        ← 用户级（所有 workspace 的所有项目）
    opencode.json
    mcp.json

workspace/AGENTS.md        ← 工作区级（当前 workspace 的所有项目）✅ 已更新
    ├── opencode/
    │   └── AGENTS.md      ← 项目级（opencode 专属规则）
    ├── disk-demo/
    │   └── AGENTS.md      ← 项目级
    └── sisyphus/
        └── AGENTS.md      ← 项目级（Sisyphus 项目自己的规则）
```

**优先级**：项目 AGENTS.md 覆盖全局 AGENTS.md。项目级可以补项目专属规则。

---

## 三、AGENTS.md 已更新的内容

`workspace/AGENTS.md` 新增了强制指令节：

```markdown
### Before EVERY response (MANDATORY):

1. Load relevant memory context (before_turn):
   PYTHONPATH=src python3 -c "
   from sisyphus.memory.context import AgentMemory
   from sisyphus.memory.store import MemoryStore
   store = MemoryStore(Path.home() / '.omo' / 'memory')
   mem = AgentMemory(store)
   print(mem.before_turn(CURRENT_QUERY, max_chars=4000))
   "

2. The <sisyphus_context> block is past lessons/decisions/patterns.
   Read it. Reference relevant items.

### After significant work:

3. Record to memory:
   python3 .omo/scripts/memory.py record lesson "title" --content "..."
```

**效果**：Sisyphus 在任何项目下启动时，都会：
1. 先跑 `memory.py recent + search`（启动时）
2. 每 turn 前跑 `before_turn()`（自动注入上下文）
3. 重大决策后跑 `memory.py record`（写记忆）

---

## 四、对比

| | Claude Code | Sisyphus |
|---|---|---|
| 全局文件 | `~/.claude/CLAUDE.md` | `workspace/AGENTS.md` |
| 自动加载 | ✅ session 启动 | ✅ session 启动（OpenCode 自动加载） |
| 内容 | 编码风格、工作流、项目架构 | 记忆系统规则 + 项目上下文 |
| agent 自写 | auto memory `MEMORY.md` | `memory.py record` |

---

## 五、一句话

> 全局就是工作区 AGENTS.md。Claude Code 的 `~/.claude/CLAUDE.md` 用什么，Sisyphus 的 `workspace/AGENTS.md` 就写什么。已经改好了。

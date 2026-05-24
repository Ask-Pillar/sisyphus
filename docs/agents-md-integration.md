# Sisyphus 集成方案：写入 CLAUDE.md / AGENTS.md

> 日期: 2026-05-24  
> 方案: 像 Hermes/Cursor/Claude Code 一样，通过文件级指令自动加载记忆

---

## 一、业界怎么做

| 项目 | 文件 | 何时加载 | 内容 |
|------|------|----------|------|
| **Claude Code** | `CLAUDE.md` + `MEMORY.md` | 每 session 启动时 | 规则 + agent 自写记忆。首 200 行 / 25KB 上限 |
| **Hermes** | `SOUL.md` + `MEMORY.md` | 每 session frozen | 身份 + 持久记忆。硬上限 2200/1375 字符 |
| **Cursor** | `.cursor/rules/*.mdc` + `AGENTS.md` | 启动 / 文件匹配 / 手动 | 规则 + 路径作用域 + alwaysApply |
| **OpenCode** | `AGENTS.md` | 自动加载 | 项目上下文 + 编码规范 |

**共同模式**：
- **文件即指令** — 不需要改 agent 代码，写文件就够了
- **冻结快照** — session 开始时捕获，中途不变，节省 prefix cache
- **优先级覆盖** — 项目级 > 用户级，目录级 > 根级

---

## 二、Sisyphus 的 AGENTS.md 集成方案

### 文件: `disk-demo/AGENTS.md`（或任意项目根目录）

```markdown
# AGENTS.md — Sisyphus Memory Integration

## Memory System

This project uses Sisyphus for persistent, self-evolving memory.
Before EVERY response, you MUST inject relevant context.

### Before each turn (REQUIRED):

1. Run before_turn() to get relevant memories:
   ```bash
   cd /Users/landon/PycharmProjects/workspace/sisyphus
   PYTHONPATH=src python3 -c "
   from sisyphus.memory.context import AgentMemory
   from sisyphus.memory.store import MemoryStore
   from pathlib import Path

   store = MemoryStore(Path.home() / '.omo' / 'memory')
   mem = AgentMemory(store)
   ctx = mem.before_turn('${CURRENT_USER_QUERY}', max_chars=4000)
   print(ctx)
   "
   ```

2. The output is a `<sisyphus_context>...</sisyphus_context>` block.
   Read it — it contains lessons, decisions, and patterns from past sessions.

3. If the context mentions something relevant to the user's question,
   reference it in your response.

### After each turn (when significant):

4. If you made a decision, learned a pattern, or found a bug:
   ```bash
   python3 ~/PycharmProjects/workspace/.omo/scripts/memory.py record lesson "Short title" \
     --tags "relevant,tags" \
     --content "What happened and what was learned"
   ```

### Available MCP tools (when connected):

- `memory_stats` — check memory counts by type
- `search_memory` — find specific memories
- `write_memory` — record structured memory
- `run_pipeline` — trigger Dream/Compress

### Memory layers (auto-loaded):

| Layer | What | When |
|-------|------|------|
| PERSIST | Project context, key decisions | Always, frozen |
| HOT | Last 7 days, recent lessons | Per-turn, relevance-scored |
| CODE | Function signatures, call chains | When query mentions code |
| COLD | Archive, decayed | Fallback when HOT is thin |
```

---

## 三、开箱即用：init-agent.sh

一次性初始化脚本，给项目的 AGENTS.md 注入 sisyphus 集成：

```bash
#!/bin/bash
# sisyphus/scripts/init-agent.sh
# Usage: ./scripts/init-agent.sh /path/to/project

PROJECT_DIR="$1"
AGENTS_FILE="$PROJECT_DIR/AGENTS.md"

cat >> "$AGENTS_FILE" << 'EOF'

## Sisyphus Memory (auto-injected)

This agent has persistent memory via Sisyphus.
Before each response, context from past sessions is loaded automatically.
Memory layers: PERSIST (always) → HOT (7d) → CODE (on demand) → COLD (archive).

To record a lesson: `python3 .omo/scripts/memory.py record lesson "title" --content "..."`
To search memories: `python3 .omo/scripts/memory.py search "query"`
To see stats: `python3 .omo/scripts/memory.py stats`
EOF

echo "✅ Sisyphus memory rules appended to $AGENTS_FILE"
```

---

## 四、跟 Hermes/Claude Code 对比

| | Hermes | Claude Code | Sisyphus (本方案) |
|---|---|---|---|
| 指令文件 | SOUL.md + AGENTS.md | CLAUDE.md + MEMORY.md | AGENTS.md + sisyphus skill |
| 自动加载 | ✅ frozen at start | ✅ first 200 lines | ✅ AGENTS.md auto-load |
| 主动记忆 | MEMORY.md (agent 写) | auto memory (agent 写) | memory.py record (agent 写) |
| 上下文注入 | 系统 prompt 冻结 | 系统 prompt + 用户消息 | before_turn() 注入 |
| 触发方式 | 每次 turn | 每次 session | 每次 turn |

---

## 五、一句话

> 不需要改 opencode 源码。写到 AGENTS.md 里，agent 自己读、自己调、自己记。Hermes/Cursor/Claude Code 都是这么干的。

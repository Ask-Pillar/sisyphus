# WeChat Bridge → Sisyphus MCP 接入调试全记录

> 日期: 2026-05-23 ~ 2026-05-24  
> 状态: 部分完成（WeChat 通道已通，MCP 工具未在 agent 中显示）  
> 相关: [sisyphus](..) · [wechat-bridge-opencode v0.3.2](.)

---

## 背景

Sisyphus 记忆系统通过 MCP Server（`sisyphus.server.mcp`）对外提供 9 个工具（write_memory / search_memory / get_context / memory_stats / get_memory / list_memories / delete_memory / run_pipeline / import_memories）。期望微信端用户通过 WeChat Bridge → opencode ACP agent → MCP Server 调用这些工具。

用户反馈：微信那边接入 MCP 有问题。

---

## 调试链路

### 1. 问题定位：MCP Server 启动失败

**现象**：bridge 日志中有 schema 校验错误

```
Expected { readonly "type": "local", ... } | { readonly "type": "remote", ... }, got {"command":"python3"...}
Missing key mcp.sisyphus.enabled
```

**根因 #1 — `mcp.py` 语法错误**

文件 `sisyphus/src/sisyphus/server/mcp.py` 78-93 行存在重复定义 + 孤儿代码：

```python
# 72-76: _handle_context v1 ✅
# 79-90: _handle_stats v1 (只统计 all_mems)
# 91-93: 孤儿代码 —— for m, s in results / ] / }  ← 语法错误！
# 96-100: _handle_context v2 (重复)
# 103-114: _handle_stats v2 (改进了，含 refined_mems)
```

这段垃圾代码是 P5 重构时遗留的合并冲突残骸，导致 `python3 -m sisyphus.server.mcp` 直接 `IndentationError`，MCP Server 从未成功启动。

**修复**：删除重复 handler + 孤儿代码，保留改进版 `_handle_stats`（含 refined_mems 计数）。24 行删除，292 tests 全部通过。

```
git: sisyphus 0e3439b — fix: remove duplicate handlers and orphaned syntax error
```

---

### 2. 问题定位：Bridge 固定传空 mcpServers

MCP Server 修好后，WeChat 端 agent 仍然不使用 MCP 工具。日志中 `[available_commands_update]` 只显示 16 个内置命令，没有任何 `mcp__` 前缀的工具。

对比 WeChat agent 和 Sisyphus 主 session：

| | Sisyphus 主 session | WeChat agent (ACP) |
|---|---|---|
| skill_mcp | ✅（仅 playwright） | ✅（工具列表中可见） |
| mcp__sisyphus__* | ❌ | ❌ |

**根因 #2 — Bridge 硬编码 `mcpServers: []`**

查看 bridge 源码 `wechat-bridge-opencode@0.3.2`：

```
dist/src/acp/session.js:      5 处 mcpServers: []
dist/src/acp/agent-manager.js: 3 处 mcpServers: []
```

共 8 处全部硬编码为空数组。Bridge 从不读取 opencode 配置文件，因此 ACP agent 收不到任何 MCP Server 信息。

**修复**：在两个文件中增加 `getMcpServers(cwd)` 函数，依次检查：

1. `{cwd}/.opencode/opencode.json`
2. `{cwd}/.opencode/opencode.jsonc`
3. `~/.config/opencode/opencode.json`

将 MCP 配置转换为 ACP 协议所需的 `{name, command, args, env}` 格式。

同时在 `disk-demo/` 下创建 `.opencode/opencode.json` 和 `.opencode/opencode.jsonc`，包含完整的 sisyphus MCP 配置。

```
git: disk-demo ff9e8aa — feat: add MCP config for sisyphus memory server
```

**验证**：debug log 确认配置加载成功

```
LOADED 1 servers: [{"name":"sisyphus","command":"python3",
  "args":["-m","sisyphus.server.mcp"],
  "env":[{"name":"PYTHONPATH","value":".../sisyphus/src"}]}]
```

---

### 3. 问题定位：ACP Agent 不显示 MCP 工具 ⚠️ 未解决

MCP Server 配置已成功传给 ACP agent，但 `[available_commands_update]` 仍然只有 16 个内置命令。

Agent 的 thought log 显示它意识到了问题：

```
The user is repeatedly asking to call the same MCP tool.
I'm wondering if there's a way to just show the result
without running a new subprocess each time.

I should also try using the Playwright MCP... no, that's unrelated.
Let me just do it quickly. [tool] bash (pending)
```

**推测根因 #3 — `sdk.mcp.add` 静默失败**

opencode 源码 `packages/opencode/src/acp/agent.ts` 1147-1185 行：

```typescript
const mcpServers: Record<string, ConfigMCP.Info> = {}
for (const server of params.mcpServers) {
  // ... 转换为 ConfigMCP.Info 格式
}
await Promise.all(
  Object.entries(mcpServers).map(async ([key, mcp]) => {
    await this.sdk.mcp.add({ directory, name: key, config: mcp }, { throwOnError: true })
      .catch((error) => {
        log.error("failed to add mcp server", { name: key, error })
      })
  }),
)
```

`mcp.add` 调用后 tools 不出现，可能原因：

1. **ACP session 复用**：每次 resume `ses_1c24fc596ffe962zwQMnxEOxIR`，这个旧 session 可能缓存了"无 MCP"状态
2. **stdio 启动失败**：MCP Server 子进程 spawn 失败但错误被吞
3. **ACP 协议版本**：`sdk.mcp.add` 端点可能不被连接的协议版本支持
4. **权限/沙箱**：ACP 进程无法访问 disk-demo 目录

---

## 当前状态

| 组件 | 状态 |
|---|---|
| mcp.py 语法 | ✅ 已修复，292 tests 通过 |
| MCP Server 功能 | ✅ 直接调用正常（90 raw / 1 refined） |
| Bridge 配置读取 | ✅ 已打补丁，能加载 MCP 配置 |
| WeChat 通道 | ✅ 消息收发正常 |
| Agent bash 调用 | ✅ 能通过 bash + Python 访问 sisyphus |
| Agent MCP 工具 | ❌ 未出现（下一步攻关） |

---

## 涉及的补丁文件

### Sisyphus（已提交）
- `sisyphus/src/sisyphus/server/mcp.py` — 删除重复 handler + 孤儿代码

### disk-demo（已提交）
- `.opencode/opencode.json` — 项目级 MCP 配置
- `.opencode/opencode.jsonc` — 同上

### wechat-bridge-opencode（本地补丁，未提交）
- `~/.local/share/fnm/.../wechat-bridge-opencode/dist/src/acp/session.js` — `getMcpServers()` + 5 处替换
- `~/.local/share/fnm/.../wechat-bridge-opencode/dist/src/acp/agent-manager.js` — `getMcpServers()` + 3 处替换

---

## 下一步

1. 查 opencode ACP agent 的 `sdk.mcp.add` 实现（`packages/opencode/src/acp/agent.ts`）
2. 尝试新建 session 而非复用旧 session
3. 检查 stdout/stderr 中是否有 `"failed to add mcp server"` 错误
4. 考虑直接升级 wechat-bridge-opencode 版本（当前 0.3.2）

---

## 附录：关键配置

### opencode MCP 配置 `~/.config/opencode/opencode.json`

```json
{
  "mcp": {
    "sisyphus": {
      "type": "local",
      "enabled": true,
      "command": "python3",
      "args": ["-m", "sisyphus.server.mcp"],
      "env": {
        "PYTHONPATH": "/Users/landon/PycharmProjects/workspace/sisyphus/src"
      }
    }
  }
}
```

### MCP Server 工具列表

```
write_memory · search_memory · get_context · memory_stats
get_memory · list_memories · delete_memory
run_pipeline · import_memories
```

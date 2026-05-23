# P5 计划 — MCP Server 完善 + 一键导入

## 背景

P4 完成了完整的检索管道（双路径 + BCE + Sleep Pipeline），Gate 80%（排除不可答 query 为 89%）。
当前 MCP Server 是旧版实现，仍引用已移除的 BGEReranker 和 SubagentLauncher。

用户确认：
- **不需要多客户端并发** — MCP stdio 协议本身就是单客户端模型，一个进程服务一个 client
- **不需要子 Agent 沙箱** — MCP 已替代子 agent 隔离，所有客户端共享同一份记忆存储
- **需要一键导入** — 新用户首次使用时有历史记忆（.md / .jsonl），需要批量导入功能

## 交付物

### 1. 升级 MCP Server

| 改动 | 文件 | 说明 |
|------|------|------|
| 替换 BGEReranker → ContextRetriever | `server/mcp.py` | 使用 P3/P4 完成的双路径管道 |
| 移除 SubagentLauncher | `server/mcp.py` | MCP 协议自身解决跨 agent 问题 |
| 添加 TreeRetriever 集成 | `server/mcp.py` | Path A 树浏览可用 |
| 添加 `import` 工具 | `server/mcp.py` | 批量导入历史记忆 |

### 2. 一键导入功能

| 功能 | 说明 |
|------|------|
| 输入格式 | `.md` 文件（frontmatter + 正文）/ `.jsonl` 文件 / 目录扫描 |
| 导入逻辑 | 逐文件解析 → 提取 title/type/content/tags → MemoryStore.create() |
| 去重保护 | title 已存在时跳过（不覆盖） |
| 进度反馈 | 返回 `{imported: N, skipped: M, errors: [...]}` |

### 3. 测试

| 测试 | 说明 |
|------|------|
| `test_mcp_import.py` | markdown 批量导入 |
| `test_mcp_import_jsonl.py` | jsonl 导入 |
| `test_mcp_import_dup.py` | 重复 title 跳过 |
| `test_mcp_recall_new.py` | 使用新 ContextRetriever 的 recall |

## Gate

- MCP recall @1 ≥ 80%（使用 Gate 测试集验证）
- 导入 100 条 .md 文件不报错
- 去重逻辑正确（相同 title 不覆盖）

## 文件清单

```
P5 修改:
  src/sisyphus/server/mcp.py          ← 升级 ContextRetriever + import 工具
  src/sisyphus/server/importer.py     ← 新建，批量导入逻辑

P5 测试:
  tests/test_mcp_import.py            ← ~4 个测试

P5 不涉及:
  src/sisyphus/memory/retrieval.py    ← 不需要改
  src/sisyphus/memory/tree.py         ← 不需要改
  tests/test_retrieval.py             ← 不需要改（Gate 测试已覆盖）
```

## 与其他 Phase 的关系

```
P0 ✅ → P1 ✅ → P2 ✅ → P3 ✅ → P4 ✅ → P5 📋
                                            ├── MCP 升级
                                            ├── 一键导入
                                            └── Gate 验证
```

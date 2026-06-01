# Sisyphus v4.0 — Agent 中枢记忆系统

## 这是什么

Sisyphus 是一个为 AI Agent 构建的持久记忆系统。不是"存一段文本以后搜"，而是**自己能判断什么时候该记、该记什么、该不该想起来、该不该忘**。

## 为什么需要它

普通 Agent 每次对话都是从头开始。上一轮讨论的架构决策、踩过的坑、学到的教训，换个 session 全丢了。

Sisyphus 解决的就是这个——让 Agent 像一个真正的团队成员，能记住项目历史、个人偏好、过去的决策。

## 跟 OpenCode 的关系

Sisyphus 通过 MCP Server 暴露 14 个工具，OpenCode 直接调用：

```
OpenCode Agent
  → MCP
    → search_memory("数据库连接池怎么配")
      → Sisyphus 检索 → 返回: "MySQL 连接池最大 20，超时 30s，重要性 8"
```

OpenCode 不需要知道 Sisyphus 怎么工作，只需要调 `search_memory` / `write_memory`。

## 当前能力（v4.0）

### 记忆存储
- SQLite + FTS5 全文索引，支持 Markdown 自动迁移
- 四池命名空间：personal / projects / knowledge / shared
- 跨池加权检索 + MMR 多样性重排

### 智能触发
- 你说"记住"→ 自动写入，你说"上次"→ 自动检索
- 无触发词 → 不检索，节省开销
- 连续无命中 → 指数退避

### 反馈闭环
- `rate_memory(id, 1-5)` 评分
- `dismiss_memory(id)` 屏蔽
- 半衰期衰减（90天）

### 知识库
- FTS5 分块存储，支持 `.md/.txt/.jsonl/.csv` 批量导入
- 自动分批，50GB+ 不 OOM

### 测试
- 408/408 全部通过

## 架构

基于 IBM/普林斯顿 CoALA 四层记忆框架：

| 层 | 做什么 | 状态 |
|----|--------|------|
| Episodic | 决策/教训/偏好 | ✅ |
| Semantic | 知识库/文档 | ⏳ Phase 5 |
| Procedural | 技能/Agent路由 | ⏳ Phase 6 |

## 安装

```bash
git clone git@github.com:Ask-Pillar/sisyphus.git
cd sisyphus
pip install -e .

# 记录第一条记忆
PYTHONPATH=src python3 -m sisyphus.memory.cli record lesson "第一条记忆" --content "Sisyphus 已就绪"

# 查看统计
PYTHONPATH=src python3 -m sisyphus.memory.cli stats
```

## MCP 配置

在 opencode.json 中添加：

```json
{
  "mcpServers": {
    "sisyphus": {
      "command": "python3",
      "args": ["-m", "sisyphus.server.mcp"],
      "cwd": "/path/to/sisyphus"
    }
  }
}
```

## 后续计划

- Phase 5: Semantic 层（URL 索引 + 50GB 知识库）
- Phase 6: Procedural 层（技能系统 + Agent 路由）
- 独立 MCP Server 部署

## 链接

- 仓库: github.com/Ask-Pillar/sisyphus
- 文档: docs/PROJECT-STATUS.md / docs/USAGE.md
- 路线图: docs/ROADMAP-v3.md

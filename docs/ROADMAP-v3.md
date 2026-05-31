# Sisyphus 最终规划 — Agent 中枢记忆系统

## 定位

不只是记忆系统，是所有 Agent 的中枢神经。任何 Agent 的记忆、知识、技能、路由都走 Sisyphus。

## CoALA 四层记忆映射

基于 IBM/普林斯顿 CoALA 框架（Working / Semantic / Procedural / Episodic）：

| IBM 分类 | 是什么 | Sisyphus | 状态 |
|----------|--------|----------|------|
| Working | 上下文窗口，volatile | 不做（LLM 自己的事） | — |
| Episodic | 过去的决策、教训、对话 | MemoryStore + Session Log | ✅ |
| Semantic | 知识、规则、文档 | KnowledgeBase + URL 索引 | ⏳ Phase 5 |
| Procedural | 技能、工作流、行为规则 | SkillStore + Agent 路由 | ⏳ Phase 6 |

## 当前能力（v4.0）

| 模块 | 功能 |
|------|------|
| SQLiteMemoryStore | SQLite + FTS5 存储，Markdown 自动迁移 |
| PoolRegistry | personal / projects / knowledge / shared 四池 |
| UnifiedRetriever | 跨池加权检索 + MMR 重排 + 多样性 |
| 触发系统 | L0 信号词 / L1 周期+话题 / L2 指数退避 |
| 反馈闭环 | rate(1-5) / dismiss / 半衰期 90 天 |
| Forgotten Gems | 10% 概率注入被遗忘的高重要记忆 |
| 对立观点 | Top-3 同类型时搜索 counterpoint |
| Session Log | sessions/{date}.md 双向记录 |
| KnowledgeBase | FTS5 分块 500词/chunk，导入 md/txt/jsonl/csv |
| MCP Server | 14 个工具 |
| 测试 | 408/408 全过 |

## 最终架构

```
任何 Agent (通过 MCP)
  → Sisyphus Server (独立进程)
    ├── Episodic 层 (MemoryStore)
    │   └── 决策、教训、偏好、对话历史
    ├── Semantic 层 (KnowledgeBase)
    │   ├── URL 索引 (官方文档地址 + 描述)
    │   ├── 内容缓存 (FTS5 自动刷新)
    │   └── 领域分库 (security/backend/hardware/...)
    ├── Procedural 层 (SkillStore)
    │   ├── 技能库 (条件→动作规则)
    │   ├── Agent 路由 (谁擅长什么调谁)
    │   └── 工作流 (多步骤编排)
    └── config.yaml (池权重 + 开关)
```

## 下一步

### Phase 5: Semantic 层

| 步骤 | 做什么 |
|------|--------|
| 5.1 | URL 索引 → urls.db，FTS5 搜描述 |
| 5.2 | 内容缓存 → fetch + 自动刷新 |
| 5.3 | 分批导入 → 支持 50GB+ 不 OOM |
| 5.4 | 多格式解析 → PDF/DOCX/图片→文本 |
| 5.5 | 白名单 + 包源验证 |
| 5.6 | 安全审计 → AST 检测危险调用 |

### Phase 6: Procedural 层

| 步骤 | 做什么 |
|------|--------|
| 6.1 | 技能格式 → YAML frontmatter + Markdown body |
| 6.2 | 条件匹配 → "遇到 X → 调 Y 方法" |
| 6.3 | Agent 画像 → 每个 Agent 擅长什么 |
| 6.4 | Agent 路由 → 择最优 Agent 执行 |
| 6.5 | 借 Hermes 技能创建逻辑 |

### 独立部署

| 步骤 | 做什么 |
|------|--------|
| 部署 | pip install sisyphus → `sisyphus serve` |
| MCP | 标准 JSON-RPC，任何 Agent 都能接 |
| 配置 | config.yaml 控制模块开关 |

## 对比 Hermes

| | Hermes | Sisyphus |
|---|--------|----------|
| 定位 | 通用 Agent 框架 | Agent 中枢记忆系统 |
| 模块化 | 内置，不可插拔 | 池模块，可插拔 |
| 命名空间 | 扁平（MEMORY.md + USER.md） | 四池 + 领域分库 |
| 触发机制 | 无条件 | L0/L1/L2 三级 |
| 反馈闭环 | 无 | rate/dismiss + 半衰期 |
| 重排 | 无 | MMR + 类型配额 |
| 技能系统 | ✅ 自动创建 | ❌ Phase 6 |
| 多平台 | ✅ 5 个平台 | ❌ 仅 MCP |
| 生产加固 | ✅ 文件锁+注入扫描 | ❌ |

## 技术栈

Python 3.14+ / SQLite + FTS5 / MCP JSON-RPC / jieba / llama.cpp (可选)

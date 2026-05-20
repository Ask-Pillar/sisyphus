# ADR-001: 记忆系统架构

**状态**: Accepted
**日期**: 2026-05-20
**决策者**: Ask-Pillar

## 背景

Sisyphus 需要一个持久记忆系统，使其能够跨 session 保留知识。
在第一期，我们只需要一个简单可靠的实现。

## 方案调研

| 方案 | 优点 | 缺点 |
|------|------|------|
| **SQLite + FTS5** (Hermes 方式) | 查询快，结构清晰 | Schema 迁移麻烦，数据不透明 |
| **向量数据库** (Mem0 方式) | 语义搜索强 | 基础设施重，不适合 v0.1 |
| **Markdown 文件** (Claude Code 方式) | 零依赖，人类可读，可 git | 检索效率低，需 LLM 辅助 |

## 决策

**采用 Claude Code 的文件式记忆 + Hermes 的冻结快照模式。**

### 理由

1. **零依赖**：只用标准库，无需数据库、无需向量引擎
2. **人类可读**：Markdown 文件可用任何编辑器查看和修改
3. **透明**：记忆内容一目了然，没有黑盒
4. **可演化**：以后可以在下层加索引，不改上层接口

### 架构

```
~/.omo/memory/
├── INDEX.md              ← 入口索引（始终在上下文中）
├── project-context.md    ← 主题文件（按需加载）
├── decisions.md          ← 主题文件
├── patterns.md           ← 主题文件
└── lessons.md            ← 主题文件
```

### 关键设计决策

1. **INDEX.md 是索引，不是记忆**：前 50 行在 session 开始时加载
2. **主题文件按需加载**：不全部塞进上下文
3. **Agent 写记忆**：同 Claude Code——用文件工具写
4. **冻结快照**（v0.4）：session 开始时冻结，中间不变，保持 prefix cache

## 影响

- 正面：推土机模式开发，马上能用
- 正面：用户可以直接编辑记忆文件
- 负面：需要 LLM 辅助召回（无原生语义搜索）
- 缓解：v0.2 加 LLM 侧路召回，v0.5 加轻量向量

## 替代方案

- **Mem0**：拒绝，太重，56K star 的项目是产品不是库
- **Hermes SQLite**：保留给 v0.5 的 session search
- **LangMem**：拒绝，绑定 LangGraph + 18s 延迟

## 后续

- ADR-002: LLM-powered recall（v0.2）
- ADR-003: 背景提取 agent（v0.3）

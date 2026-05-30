# Sisyphus — 个性化检索推荐系统

为 AI Agent 构建的持久记忆系统。从存储到排序，从单池到多池，从被动检索到主动触发。

## 架构

```
推荐视角:  用户画像 → 物料池 → 召回 → 粗排 → 精排 → 重排 → 反馈
Sisyphus:  Personal  → 4池    → BM25  → Decay → BCE  → MMR  → rate/dismiss
```

| 层级 | 实现 |
|------|------|
| 用户画像 | Personal Memory (偏好/习惯/反馈) |
| 物料池 | personal / project / knowledge / shared 四池 |
| 召回 | BM25 + FTS5 + Tree Browse |
| 粗排 | Decay Score (半衰期 180 天) + recall_count 加权 |
| 精排 | BCE Reranker (同 topic 8+ 自动激活) |
| 重排 | DiversityReranker (类型配额 + MMR) |
| 反馈 | rate_memory(1-5) + dismiss_memory |
| 反茧房 | Forgotten Gems (10% 轮转) + 多样性保底 + 对立观点 |

## 触发系统

三级触发，平衡准确率与性能：

| 级别 | 方式 | 延迟 |
|------|------|------|
| L0 | 信号词正则（记住/之前/recall） | < 1ms |
| L1 | 周期性触发 + 话题切换检测 | < 5ms |
| L2 | 指数退避（连续无命中跳过） | 0ms |

## MCP 工具

| 工具 | 功能 |
|------|------|
| search_memory | 检索记忆 |
| write_memory | 记录记忆 |
| rate_memory | 评分 1-5 |
| dismiss_memory | 屏蔽记忆 |
| import_memories | 导入 md/jsonl |
| import_knowledge | 导入文档到知识库 |
| switch_scope | 切换检索范围 |
| list_pools | 列出所有池 |
| run_pipeline | 离线巩固流水线 |

## 存储

- **MemoryStore**: SQLite + FTS5（自动从 Markdown 文件迁移）
- **KnowledgeBase**: SQLite FTS5 分块（500 词/chunk）
- **Session 日志**: `~/.omo/sessions/{date}.md`
- **目录结构**: `~/.omo/{personal,projects,knowledge,shared}/`

## 测试

408 测试全通过。模块覆盖：

| 模块 | 测试 |
|------|------|
| store | CRUD + 软删除 + 迁移 |
| trigger | 60 样本准确率 |
| retrieval | 衰减 + 排序 + 路径路由 |
| knowledge | 导入 + 搜索 + 批处理 |
| unified | 跨池检索 + 多样性 |
| pipeline | 流水线 + 睡眠 |

## 文档

| 文档 | 内容 |
|------|------|
| `docs/ROADMAP-v2.md` | 项目规划 + 4 阶段路线图 |
| `docs/ADDR-*.md` | 架构决策记录 |
| `AGENTS.md` | AI Agent 使用规范 |

# ADR-003: Memory 2.0 — Layered, Linked, Observable Memory System

## Status

Draft (2026-05-20)

## Context

v0.1–v0.6 built a working memory system: file storage, LLM recall, extraction,
snapshot, compression, and search. But with usage and the envisioned expansion
to sub-agents, several limitations surfaced:

1. Compression deletes originals — irreversible if compression is wrong
2. No structured way to trace "why did the agent do that" — zero observability
3. No multi-agent memory isolation or sharing
4. No dimensional layering (project vs global, fact vs principle)
5. No record of repeated mistakes / infinite loops — agent learns nothing from
   its own failures
6. The knowledge lives in files but can't be browsed like a wiki

This ADR redesigns the memory system around four principles:

- **Raw never deleted** — all processing is additive
- **Every action is logged** — full audit trail
- **Files are the source of truth** — databases are rebuildable caches
- **Obsidian-compatible** — browse, link, graph out of the box

## Decision

### 1. Memory Layering

```
┌─────────────────────────────────────────────────────────────┐
│                    RAW 层（原始记忆）                        │
│  append-only，永不删除                                       │
│  来源：自动提取 / 主动记录 / 子 agent 汇报                  │
│  格式：frontmatter + markdown                                │
│                                                              │
│  .omo/memory/raw/                                            │
│  ├── <type>/<id>.md                                          │
│  └── <type>/<id>.md                                          │
├─────────────────────────────────────────────────────────────┤
│                  REFINED 层（加工记忆）                       │
│  可重新生成，原始数据不变即可重跑                             │
│  来源：反射 / 压缩 / 回路阻断 / 关联分析                    │
│  使用：默认召回目标                                           │
│                                                              │
│  .omo/memory/refined/                                        │
│  ├── reflection/<id>.md      ← LLM 洞察 + 证据引用           │
│  ├── summary/<id>.md         ← 退火压缩摘要                  │
│  └── loop/<id>.md            ← 回路阻断记录                  │
├─────────────────────────────────────────────────────────────┤
│                  MOC 层（主题地图）                            │
│  多维度索引页，Obsidian 打开直接做看板                        │
│                                                              │
│  .omo/memory/                                                │
│  ├── INDEX.md                 ← 全局索引入口                  │
│  ├── MOC-project.md           ← 项目维度看板                  │
│  ├── MOC-preference.md        ← 用户偏好看板                  │
│  └── MOC-<dimension>.md       ← 其他维度                     │
├─────────────────────────────────────────────────────────────┤
│                  AGENT 层（子 agent 记忆沙箱）                │
│  每个持久子 agent 有自己的记忆目录                             │
│                                                              │
│  .omo/memory/agents/                                         │
│  └── <agent_name>/                                           │
│      ├── INDEX.md                                             │
│      ├── raw/                                                 │
│      └── refined/                                             │
└─────────────────────────────────────────────────────────────┘
```

### 2. RAW 记忆格式

每条记忆是带 frontmatter 的 Markdown 文件，兼容 Obsidian：

```markdown
---
id: mem_a1b2c3d4e5f6
type: lesson                # lesson | pattern | preference | project_context
importance: 7               # LLM 评分 1-10
tags:
  - python
  - typing
  - project:sisyphus
links:                      # wikilink 关联
  - mem_x1y2z3
  - mem_p9q8r7
refined_by:                 # 反向引用（哪些加工产用了这条）
  - ref_001
created: 2026-05-20T14:00:00+08:00
status: active              # active | archived | deprecated
source: extraction          # extraction | manual | agent_report
session_id: ses_abc123      # 来源 session
---

# Python 3.9 类型注解规范

Use `Optional[X]` not `X | None`. Use `List` not `list`.

这条规则来自项目初期对 Python 3.9 兼容性的评估。
相关讨论参见 [[mem_x1y2z3|Python 版本选择]]。
```

**frontmatter 字段说明：**

| 字段 | 用途 | 是否必需 |
|------|------|---------|
| `id` | 唯一标识，引用基准 | ✅ |
| `type` | 分类 | ✅ |
| `importance` | LLM 原始评分，影响召回权重 | ✅ |
| `tags` | 标签，支持 `project:` 前缀做项目级过滤 | ✅ |
| `links` | 双向 wikilink 到其他记忆 | 推荐 |
| `refined_by` | 反向引用，自动维护 | 推荐 |
| `status` | 状态 | ✅ |
| `source` | 来源 | 推荐 |
| `session_id` | 来源 session 追溯 | 推荐 |

### 3. REFINED 记忆格式

#### 3a. 反射（Reflection）

```markdown
---
id: ref_015
type: reflection
importance: 8
tags: [project:sisyphus, convention]
evidence:
  - mem_a1b2c3              # Python 类型规范
  - mem_d4e5f6              # TDD 流程
  - mem_g7h8i9              # 文件式存储
created: 2026-05-20T14:30:00+08:00
trigger: importance_sum=65  # 触发原因
input_count: 5              # 输入记忆数
llm_calls: 2                # LLM 调用次数（问题生成 + 洞察提炼）
duration_ms: 2300           # 耗时
---

# 项目核心规范总结

本项目遵循 [[mem_a1b2c3|Python 3.9 类型注解规范]]，
采用 [[mem_g7h8i9|文件式存储]] 而非数据库，
开发流程遵循 [[mem_d4e5f6|TDD 红绿循环]]。
```

#### 3b. 退火压缩摘要

```markdown
---
id: sum_001
type: summary
importance: 6
tags: [project:sisyphus, memory]
compressed_from:
  - mem_old1
  - mem_old2
  - mem_old3
created: 2026-05-20T14:35:00+08:00
---

# 旧 lesson 汇总（2026-05-19 ~ 2026-05-20）

关于记忆系统的经验教训汇总：
- 文件式存储优于数据库（简单、可读、可 Git）
- A: 退火——近的留细节，远的浓缩
- 重要性评分让 recall 更精准
```

**注意：压缩不删除原始记忆。** `compressed_from` 只是引用，原始 RAW 文件完好。

#### 3c. 回路阻断记录

```markdown
---
id: loop_d4e5f6
type: loop_record
importance: 9
tags: [debug, pytest]
detected_at: 2026-05-20T15:00:00+08:00
repeat_count: 5
repeat_pattern: "pytest: call pytest 5 times with same args"
resolved: true
---

# 循环记录：pytest 反复失败

**场景**: 运行 pytest 测试失败后反复重跑
**重复行为**: 连续 5 次调用 `pytest test_xxx.py`，参数几乎相同
**根因**: 忘记先 `pip install -e .`
**正确方案**: 跑测试前检查依赖是否已安装
**后续**: 检测到 pytest 调用前先执行 pip list 确认
```

**回路阻断的触发检测：**

```
每轮对话后检查：
  1. 同一工具连续调用 ≥ N 次（默认 5）且参数相似度 > 80%？
     → 记录回路阻断
  2. 连续输出完全相同 ≥ 3 次？
     → 记录回路阻断
  3. 生成→执行→报错→重试 循环 > 3 轮且方案不变？
     → 记录回路阻断

下次类似场景，recall 会召回这条 → 提前知道应对方案。
```

### 4. MOC（Map of Content）

每个 MOC 是一个 Obsidian-兼容的索引页：

```markdown
# 项目记忆 — sisyphus

## 架构决策
- [[ref_001|项目核心规范总结]]
- [[mem_a1b2|文件式存储选型]]
- [[mem_x1y2|ADR-001 设计原因]]

## 技术栈
- [[mem_c3d4|Python 3.9 兼容性]]
- [[mem_e5f6|pytest 配置]]

## 经验教训
- [[loop_d4e5f6|pytest 循环记录]]
- [[sum_001|旧 lesson 汇总]]
```

MOC 由 `sisyphus memory index` 命令自动维护，也可以手动编辑。

### 5. 子 Agent 记忆沙箱

```markdown
.omo/memory/agents/
├── reviewer/                ← 审查子 agent
│   ├── INDEX.md             ← 自己的 MOC
│   ├── raw/
│   │   └── pattern/
│   │       └── mem_xxx.md   ← 它发现的审查模式
│   └── refined/
│       └── reflection/
│           └── ref_xxx.md   ← 它自己提炼的洞察
│
└── tester/                  ← 测试子 agent
    ├── INDEX.md
    ...

互相引用：
  [[agents/reviewer/mem_xxx|审查模式]]  ← 跨 agent 引用
```

子 agent 记忆规则：
- 读：主记忆 refined（共享上下文）+ 自己的记忆
- 写：只能写自己目录下的 raw/ 和 refined/
- 权限：不能改主记忆和其他 agent 的记忆

### 6. 自动化加工流水线

所有加工走 CLI，CLI 统一写日志。但触发是自动事件：

```
事件循环（每轮对话的 stop hook 阶段触发，不阻塞）
  │
  ├─ 1. extractMemories ─────────── [每轮]
  │    查看本轮对话，提取新记忆写入 raw/
  │    去重：type + title + 前 100 字一致则不写
  │    调用: sisyphus memory extract
  │
  ├─ 2. 循环检测 ────────────────── [每轮]
  │    检测到循环行为？写入 refined/loop/
  │    调用: sisyphus memory detect-loop
  │
  ├─ 3. 触发检测 ────────────────── [每轮]
  │    raw 计数 > threshold？
  │      → sisyphus memory compress    [退火压缩]
  │
  │    自上次 autoDream > 24h + 新 session >= 5？
  │      → sisyphus memory dream       [反射 + 关联分析]
  │
  │    refined 变更了？
  │      → sisyphus memory index       [更新 MOC + 索引]
  │
  └─ 4. 日志 ────────────────────── [每步]
        所有 CLI 命令自动输出结构化日志到 .omo/logs/
```

**CLI 命令一览：**

| 命令 | 功能 | 触发方式 | 产日志 |
|------|------|---------|-------|
| `extract` | 从对话提取记忆 | 每轮自动 | ✅ |
| `detect-loop` | 检测循环行为 | 每轮自动 | ✅ |
| `compress` | 退火压缩 | 超过阈值自动 | ✅ |
| `dream` | 反射 + 关联分析 | 24h+5session 自动 | ✅ |
| `index` | 更新 MOC | refined 变更后自动 | ✅ |
| `link` | 建立/更新关联 | 手动 | ✅ |
| `rebuild` | 重建数据库缓存 | 手动 | ✅ |

### 7. 日志系统

每条 CLI 命令自动产日志：

```markdown
# .omo/logs/dream-2026-05-20-143000.log

---
command: dream
started: 2026-05-20T14:30:00+08:00
trigger: auto (importance_sum=65, 间隔=26h, 新session=7)
---

## 输入
- 原始记忆 5 条: mem_a1b2, mem_c3d4, mem_e5f6, mem_g7h8, mem_i9j0

## 阶段 1: 问题生成
LLM 调用 1: "根据最近记忆，生成 3 个高价值问题"
→ "项目核心规范有哪些？"
→ "用户偏好的沟通方式？"
→ "常用工具链？"

## 阶段 2: 检索
问题 1 匹配：mem_a1b2, mem_c3d4
问题 2 匹配：mem_e5f6
问题 3 匹配：mem_g7h8, mem_i9j0

## 阶段 3: 洞察提炼
LLM 调用 2: "根据以上证据，生成洞察"
→ ref_015（详情见 refined/reflection/ref_015.md）

## 输出
- 创建 ref_015
- 更新 mem_a1b2.refined_by → [ref_015]
- 更新 mem_c3d4.refined_by → [ref_015]

## 耗时
- 总时长: 2.3s
- LLM 调用: 2 次（1.8s + 0.5s）
```

### 8. 数据库策略

| 场景 | 存储 | 原因 |
|------|------|------|
| 真相源头 | Markdown 文件 | 可读、可 Git、可 Obsidian 浏览 |
| 加速索引 | SQLite（`.omo/cache/`） | 快速查引用关系、跨类型筛选 |
| 加工日志 | Markdown 文件 | 可读、可 Obsidian 查看 |

**文件永远是真理源，数据库随时可重建：**

```bash
sisyphus memory rebuild    # 扫描所有记忆文件，重建 SQLite 缓存
```

数据库丢失不影响功能，只是召回变慢（变回文件扫描）。

### 9. Obsidian 兼容

直接设 `.omo/` 为 Obsidian vault：

```
.omo/                          ← Obsidian vault 根目录
├── memory/
│   ├── raw/<type>/<id>.md     ← 每条记忆是一个笔记页
│   ├── refined/reflection/    ← 反射结果是笔记
│   ├── refined/summary/       ← 压缩摘要是笔记
│   ├── refined/loop/          ← 回路阻断是笔记
│   ├── INDEX.md               ← 全局看板
│   └── MOC-*.md               ← 维度看板（1 个文件 = 1 个 MOC）
├── logs/                      ← 日志也可以打开看
└── cache/                     ← 忽略（.gitignore）
```

功能：
- **图谱视图**：`[[wikilink]]` 自动生成记忆关联图
- **标签浏览**：`tags:` frontmatter 按标签筛选
- **全文搜索**：Obsidian 内置搜索
- **看板**：MOC 文件就是看板页
- **手动编辑**：直接改 frontmatter 或内容

## 进化路线

```
v1.0 ─ RAW + frontmatter + MOC + 日志体系              ← 现在做
v1.1 ─ 反射系统（dream）+ 关联分析
v1.2 ─ 回路阻断 + 自动触发流水线
v1.3 ─ 子 agent 记忆沙箱
v1.4 ─ SQLite 加速缓存
```

## Consequences

### Positive

- 原始数据永不丢失，所有加工可追溯
- 每一步加工都有日志，AI 行为可审计
- 记忆可浏览、可编辑、可图谱查看（Obsidian）
- 子 agent 扩展不污染主记忆
- 数据库可有可无，文件保底

### Negative

- 写入变多（每条记忆 + 每次加工都产文件）
- 文件数随使用线性增长（但原始层 append-only 是设计的取舍）
- 需要两步 setup：项目内装 CLI + Obsidian 设 vault

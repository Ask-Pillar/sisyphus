# Sisyphus: 面向 LLM 智能体的情景-语义记忆架构设计

**架构设计文档 · 2026 年 5 月**

**作者：Landon · Sisyphus 项目**

> ⚠️ 本文为架构设计文档，所描述的部分功能为设计目标，当前代码实现可能不完整。实现在 `github.com/landon/Sisyphus` 持续进行中。

---

## 摘要

本文介绍 Sisyphus，一个面向 LLM 驱动智能体的记忆系统架构设计。核心原则是：**Git 是最好的备份系统，索引不是存储，情景证据永远不应被销毁**。Sisyphus 受 Andrej Karpathy 的 LLM Wiki 概念启发，于 2026 年 5 月启动架构设计与原型开发。在调研过程中，我们发现智能体记忆领域在 2025-2026 年间爆发式增长，arXiv 上涌现了 40 余篇相关论文，开源社区出现了 OpenHuman（2026 年 2 月发布，26.6K⭐）、OpenMemory（2025 年 10 月发布，4.1K⭐）、TencentDB Agent Memory（2026 年 3 月首发）等项目。Sisyphus 的若干关键设计决策——情景证据优先、可重建索引、来源追踪、门控整合——与多篇独立学术论文的发现高度一致。本文记录了架构设计思路、与学术发现的对照、当前实现状态及后续路线图。

---

## 一、背景与动机

### 1.1 设计灵感

Sisyphus 的设计始于 2026 年 5 月。最初的灵感来自 Andrej Karpathy 提出的 LLM Wiki 概念：利用 LLM 增量构建和维护一个可持久化的 Markdown 知识库，原始源文件不可变，LLM 负责摘要、交叉引用和编目。这一模式不仅适用于个人知识管理，更可以直接映射到 AI 智能体的**持久记忆**问题。

### 1.2 设计针对的根本问题

现有智能体记忆系统的主流方案存在我们认为值得重新审视的设计选择：

1. **索引即存储**：丢失向量数据库相当于丢失数据
2. **摘要覆盖证据**：LLM 生成的摘要覆盖原始交互记录，摘要出错时原始证据已丢失
3. **不可审计**：缺乏完整的操作历史，无法追溯"谁在什么时候说了什么"
4. **二进制锁定**：记忆存储在二进制格式中，无法 diff、无法 blame、无法用 Git 管理

### 1.3 生态调研

2026 年 5 月，我们系统性地调研了 arXiv 上关于智能体记忆的论文和开源项目：

- **2026 年 2 月 18 日**：OpenHuman（GitHub 26.6K⭐）发布，同样受 Karpathy 的 LLM Wiki 启发，采用 SQLite 存储 + Markdown 文件导出 + Obsidian Wiki 混合方案
- **2025 年 10 月**：OpenMemory（4.1K⭐）发布，自称"认知记忆引擎"
- **2026 年 3 月 25 日**：腾讯云发布 TencentDB Agent Memory，采用 L0-L3 分层记忆架构
- **2026 年 1-5 月**：arXiv 上出现了 40+ 篇关于智能体记忆的学术论文

这些项目和论文表明，智能体记忆正在成为一个快速发展的领域。

---

## 二、Sisyphus 架构设计

### 2.1 设计原则

Sisyphus 的设计围绕四个核心原则展开：

1. **场景证据不可销毁**：原始 .md 文件永远保留，所有抽象（摘要、反思、压缩）为衍生品
2. **索引可重建**：检索索引可以从操作日志完整重建，索引丢失不导致数据丢失
3. **Git 原生**：所有数据为纯文本，支持 diff、blame、checkout
4. **分层解耦**：REST 存储、操作日志、语义索引各司其职

### 2.2 三层架构（设计）

**L1：情景存储（Markdown 文件）**
- 每条记忆存储为一个纯文本 `.md` 文件，带 YAML 前置元数据
- 文件按类型存储于 `~/.omo/memory/` 目录
- 由 Git 追踪

**L2：操作日志（operations.jsonl，设计阶段）**
- 每次写入操作追加为一行 JSON 到不可变日志
- 每个条目包含序列号、时间戳、操作类型、记忆 ID
- 支持完整审计追踪
- L3 从 L2 重建

**L3：语义索引（设计阶段）**
- 通过回放 L2 操作重建的查询索引
- FTS5 全文搜索 + 中文分词（jieba + CJK 单字回退）
- 四层耐久度分区：PERSIST（永久注入）/ HOT（7 天优先）/ CODE（代码索引）/ COLD（衰减兜底）
- 衰减评分：`importance × 0.5^(days/180)`

### 2.3 记忆模式

| 字段 | 类型 | 说明 |
|------|------|------|
| id | string | mem_xxx 唯一标识 |
| type | enum | lesson/decision/pattern/project_context/user_preference/note/reflection 等 |
| title | string | 标题 |
| content | string | 正文 |
| tags | list[string] | 标签 |
| importance | int 1-10 | 重要性 |
| created_at | ISO 8601 | 创建时间 |
| pinned | bool | PERSIST 层级标记（设计阶段） |
| scope | string | global/project/session（设计阶段） |
| project | string | 所属项目名（设计阶段） |

### 2.4 检索流程（设计）

`before_turn` 过程实现分层注入：

1. **PERSIST**：按 importance≥8 或 pinned=True 筛选，无条件加载
2. **HOT**：7 天内创建的记忆按衰减评分排序，优先检索
3. **COLD**：其余活跃记忆作为 fallback
4. **CODE**：当查询涉及代码时，通过 CodeGraphContext 提供函数签名/调用链

### 2.5 当前实现状态

截至 2026 年 5 月 24 日，Sisyphus 原型包含约 35 个 Python 源文件、30 个测试文件、292 个测试用例（全部通过）。已实现：

- ✅ **MemoryStore**：文件级 CRUD，YAML 前置元数据 Markdown 格式
- ✅ **BM25 全文检索**：中文 jieba 分词 + 英文正则 + CJK 单字回退
- ✅ **ContextRetriever**：三层检索（MOC 类型分类 → Refined 反思层 → RAW 原始层）
- ✅ **MCP Server**：stdio JSON-RPC，9 个工具（write/search/stats/pipeline/import 等）
- ✅ **Sleep Pipeline 框架**：Dream（LLM 反思）/ Compress（压缩）/ TreeBuild
- ✅ **Subagent 系统**：独立子进程执行 LLM 任务，支持 --fixture 离线模式
- ✅ **Memory Tree**：L0（根节点）/ L1（类型簇）/ L2（叶子）三层树结构
- ✅ **AgentMemory.before_turn()**：每 turn 自动注入 `<sisyphus_context>` 块
- ✅ **Reranker**：BGE Reranker v2-m3，同 topic ≥8 条时自动激活
- ⏳ **L2 operations.jsonl / L3 SQLite FTS5**：设计完成，待实现
- ⏳ **四层耐久度分区（PERSIST/HOT/CODE/COLD）**：设计完成，待迁移 ContextRetriever
- ⏳ **Dream 自动触发（after_turn 钩子）**：设计完成，待实现
- ⏳ **会话自动提取（Extractor）**：框架就绪，待接入 LLM 判断链路
- ⏳ **初始感知（项目嗅觉：git log + 目录树）**：设计完成，待实现

已完成的架构演进讨论（2026-05-24）：从单一 `ContextRetriever` 向多 Source 的 `ContextAssembler` 迁移、MCP 工具的被动/主动分离（`before_turn` 应内嵌而非作为 MCP 工具）、全局 `AGENTS.md` 指令机制、以及市场对比分析。详见项目文档目录。

---

## 三、学术论文调研（2025-2026）

2026 年 5 月，我们系统性地调研了 arXiv 上关于智能体记忆的论文。以下为已核实存在的真实论文（附 arXiv ID 可查证）。

### 3.1 记忆有害机制

#### Useful Memories Become Faulty When Continuously Updated by LLMs

**arXiv:2605.12978** · 2026-05-13 提交 · UIUC + 清华大学

系统性地研究了 LLM 持续整合记忆时的退化问题。核心发现：将正确答案信息流式输入给 GPT-5.4 进行整合后，GPT-5.4 在之前零记忆时 100% 解决的 ARC-AGI 题上失败率高达 54%；同样的轨迹在不同更新计划下产生质量完全不同的记忆；"仅情景"模式（保留原始轨迹，禁用抽象）优于或持平所有整合方案。

**与 Sisyphus 的关联**：Sisyphus 设计为保留原始 .md 文件、所有抽象为衍生品。该论文从实验角度验证了"情景证据不可销毁"的设计原则。

#### ProMem: Proactive Memory Extraction

**arXiv:2601.04463** · 2026-01-08

指出摘要方法的两个局限：摘要是"提前的"（不知道未来查询需要什么）和"一次性的"（缺乏反馈回路）。提出通过自我提问的循环反馈来恢复丢失信息和纠正错误。

### 3.2 分层记忆架构

#### TiMem: Temporal-Hierarchical Memory

**arXiv:2601.02845** · 2026-01-06

提出时间记忆树（TMT），将时间连续性作为长程对话记忆的首要组织原则。LoCoMo 75.30%，LongMemEval-S 76.88%，召回记忆长度减少 52.20%。

#### All-Mem: Agentic Lifelong Memory via Dynamic Topology Evolution

**arXiv:2603.19595** · 2026-03-20

提出非破坏性拓扑编辑（SPLIT/MERGE/UPDATE 三算子），保留版本化可追溯性到不可变证据。在 LoCoMo 和 LongMemEval 上提升检索和 QA 表现。

### 3.3 门控整合

#### RecMem: Recurrence-based Memory Consolidation

**arXiv:2605.16045** · ACL 2026 Findings

将交互存储在嵌入层，仅当语义相似内容重复出现时才触发 LLM 整合。Token 消耗减少高达 87%。

#### GAM: Hierarchical Graph-based Agentic Memory

**arXiv:2604.12285** · ICLR 2026 Workshop

提出语义-事件触发机制，将编码与整合解耦：对话在事件推进图中隔离，仅在语义边界完整时整合到主题关联网络。

### 3.4 认知架构

#### Synapse: Episodic-Semantic via Spreading Activation

**arXiv:2601.02744** · 2026-01

将记忆建模为动态图，通过扩散激活和侧向抑制实现关联检索。

#### HeLa-Mem: Hebbian Learning Associative Memory

**arXiv:2604.16839** · 2026-04

赫布学习动力学构建动态图，双路径检索（情景 + 语义）。

### 3.5 安全与污染

#### State Contamination in Memory-Augmented LLM Agents

**arXiv:2605.16746** · 2026-05-16

发现"记忆洗钱"：有毒上下文被压缩成摘要后通过毒性检测器，但仍影响下游行为。压缩前消毒效果远好于事后消毒。

#### Hidden in Memory: Sleeper Memory Poisoning

**arXiv:2605.15338** · 2026-05

注入虚假记忆可长期潜伏，跨会话影响行为。注入率高达 99.8%，检索后利用率为 60-89%。

### 3.6 已验证的其他论文

以下论文均已通过 arXiv 搜索确认存在：

- **MemTier** (arXiv:2605.03675)：三部分记忆架构 + 五信号加权检索
- **AtomMem** (arXiv:2601.08323)：CRUD 原子操作 + GRPO 学习记忆策略
- **MemRL** (arXiv:2601.03192)：基于值函数的检索决策
- **TierMem** (arXiv:2602.17913)：双层摘要+原始日志，溯源指针
- **Mem-T** (arXiv:2601.23014)：MoT-GRPO 树引导强化学习

完整调研列表见参考文献。

---

## 四、与学术发现的对照

### 4.1 情景证据优先

*Useful Memories Become Faulty*、*TiMem*、*ProMem* 一致发现最小化抽象、保留原始轨迹的效果等于或优于持续整合。Sisyphus 的 L1 .md 文件不可变设计与这些发现一致。

### 4.2 分层架构

*TiMem*（时间层次树）、*All-Mem*（可见表面+归档证据）都采用分层策略。Sisyphus 的三层架构（文件→操作日志→索引）与这些工作一致，但更强调 Git 原生存储。

### 4.3 来源追踪

*TierMem* 的溯源指针、*All-Mem* 的版本化可追溯性、*MemoRepair* 的级联修复都依赖来源追踪。Sisyphus 的 L2 操作日志设计天然支持完整来源追溯。

### 4.4 差距

学术文献揭示了当前设计中未覆盖的方向：

1. **决策中心价值**（*DeMem*）：检索应针对下游决策效用，而非语义相似性
2. **端到端学习**（*MemRL*、*AtomMem*）：管线基于规则，而非 RL 学习
3. **非破坏性编辑**（*All-Mem*）：不支持 SPLIT/MERGE/UPDATE 算子
4. **记忆安全**：缺乏注入扫描和内容消毒

---

## 五、结论

Sisyphus 是一个面向 LLM 智能体的记忆系统架构设计，于 2026 年 5 月启动。其设计受 Karpathy 的 LLM Wiki 概念启发，核心原则是"情景证据优先、索引可重建、Git 原生"。在调研过程中，我们发现其关键设计决策——情景证据优先、分层解耦、来源追踪——与 2025-2026 年间多篇独立学术论文的发现高度一致，说明这些原则不只是实现偏好，而是可靠智能体记忆的基本架构要求。

项目当前处于早期原型阶段，核心存储和检索机制已实现并通过 292 个测试，三层架构的 L2 操作日志和 L3 语义索引、四层耐久度分区、以及自动触发机制仍在设计向实现的过渡中。我们计划完成三层架构的代码落地，然后逐步引入学术研究中的改进方向。

**本报告中的所有论文引用均可在 arXiv 上通过提供的 ID 查证。**

---

## 参考文献

1. arXiv:2605.12978 - Useful Memories Become Faulty When Continuously Updated by LLMs
2. arXiv:2601.02845 - TiMem: Temporal-Hierarchical Memory
3. arXiv:2603.19595 - All-Mem: Agentic Lifelong Memory via Dynamic Topology Evolution
4. arXiv:2601.04463 - ProMem: Proactive Memory Extraction
5. arXiv:2605.16045 - RecMem: Recurrence-based Memory Consolidation
6. arXiv:2604.12285 - GAM: Hierarchical Graph-based Agentic Memory
7. arXiv:2601.02744 - Synapse: Episodic-Semantic Memory via Spreading Activation
8. arXiv:2604.16839 - HeLa-Mem: Hebbian Learning Associative Memory
9. arXiv:2605.16746 - State Contamination in Memory-Augmented LLM Agents
10. arXiv:2605.15338 - Hidden in Memory: Sleeper Memory Poisoning
11. arXiv:2605.03675 - MemTier: Tiered Memory Architecture
12. arXiv:2601.08323 - AtomMem: Learnable Dynamic Agentic Memory
13. arXiv:2601.03192 - MemRL: Self-Evolving Agents via Runtime RL
14. arXiv:2602.17913 - TierMem: From Lossy to Verified
15. arXiv:2601.23014 - Mem-T: Densifying Rewards
16. arXiv:2511.01448 - LiCoMemory: CogniGraph
17. arXiv:2605.08563 - Context Contamination (CCRM)
18. arXiv:2604.07877 - MemReader: Active Extraction
19. arXiv:2602.01869 - ProcMEM: Reusable Procedural Memory
20. arXiv:2601.02553 - SimpleMem: Efficient Lifelong Memory
21. arXiv:2605.10870 - DeMem: Decision-Centric Rate-Distortion
22. arXiv:2512.21567 - DAM: Decision-theoretic Agent Memory
23. arXiv:2602.05665 - Graph-based Agent Memory Survey
24. arXiv:2604.16548 - Survey on Security of Long-Term Memory

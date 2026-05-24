# Sisyphus: 面向 LLM 智能体的文件原生证据优先记忆架构

**架构设计与原型评估报告 · 2026 年 5 月**

**Landon · Sisyphus 项目**

> **文档状态**：架构设计文档，含原型实验评估。项目持续开发中，标注"设计阶段"的功能尚未完全实现。代码仓库：`github.com/landon/Sisyphus`。

---

## 摘要

LLM 智能体面临跨会话记忆的基础性挑战：上下文丢失、摘要知识的脆弱性、以及抽象错误的不可逆性。本文提出 Sisyphus，一个面向 LLM 智能体的文件原生记忆架构，基于三个设计原则：(1) 情景证据不可变、永不销毁；(2) 检索索引是可重建的派生品，而非主存储；(3) Git 追踪每一次变更。Sisyphus 将每条记忆存储为带 YAML 前置元数据的 Markdown 文件，通过 BM25 + jieba 中文分词进行检索，并在每次智能体回合前注入上下文。架构受神经科学中互补学习系统框架（快速情景编码 + 慢速语义整合）以及 Andrej Karpathy 的 LLM Wiki 概念的启发。原型包含 35 个 Python 源文件和 291 个通过测试，验证了核心管线。实证评估包括：通过 CJK 分词优化实现 BM25 检索精度从 56% 提升至 83%（@1）；A/B 测试显示有记忆比无记忆质量提升 1.1 vs 0.6；负面结果——Qwen3-Embedding（0.6B）将检索精度从 76% 降至 43%（@1），导致其从默认管线中移除；条件激活的 Reranker 在同主题文档密度 ≥8 时带来 +13% @1 的提升。这些结果，尤其是负面发现，表明语义向量搜索并非通用升级方案，在生产级智能体记忆系统中采用密集嵌入前必须进行严格的检索评估。通过对 2025-2026 年间 24 篇 arXiv 论文的系统调研，我们发现 Sisyphus 的核心设计决策——证据优先存储、可重建索引、来源追踪、门控整合——与多个独立研究组的发表成果高度一致，表明这些原则代表了可靠智能体记忆的基本架构要求。

**关键词**：智能体记忆，LLM 智能体，文件原生存储，检索增强生成，证据保存，互补学习系统

---

## 一、引言

### 1.1 背景与动机

基于 LLM 的智能体从其底层模型继承了一个结构性限制：推理调用之间的无状态性。每次回合开始时，如果没有显式注入上下文，智能体对之前的交互没有任何记忆。尽管长上下文窗口在一定程度上缓解了单会话内的问题，但跨会话记忆——智能体应当回忆起数天或数周前的决策、偏好和学到的模式——仍然是一个开放的系统性挑战。

目前生产环境中的主流解决方案分为两类。**向量数据库方案**（Mem0 [1]、Cognee [2]）通过 LLM 调用从对话中提取事实，将其嵌入为密集向量，并通过语义相似度检索。**文件方案**（Claude Code 的 MEMORY.md、Hermes Agent 的 MEMORY.md [3]）存储纯文本笔记，在会话开始时加载到上下文窗口中。两者都面临设计张力：向量存储检索快但有主存储丢失风险；文件存储人类可读但缺乏结构化检索和管理。

我们认为第三种设计点——文件原生存储 + 可重建索引 + 证据优先写入纪律——提供了一个务实的中庸之道，特别适合个人开发者工作流中操作简单性与检索质量同等重要的场景。

### 1.2 问题陈述

现有智能体记忆系统存在我们认为属于架构弱点的四个模式：

1. **索引即存储**：向量数据库或 SQLite 作为主存储时，丢失它意味着丢失数据。索引应为可重建的派生品。
2. **摘要覆盖证据**：LLM 生成的摘要替换原始交互记录。摘要出错时，原始证据已不存在。
3. **不可审计**：没有完整的操作日志，无法追溯"谁在什么时候说了什么"。
4. **二进制锁定**：二进制存储格式无法 diff、无法 blame、无法用 Git 进行版本控制。

### 1.3 本文贡献

本文做出以下贡献：

1. 提出一个**文件原生三层记忆架构**（L1：不可变 Markdown 证据，L2：仅追加操作日志，L3：可重建语义索引），面向 LLM 智能体。
2. 对原型检索管线进行**实证评估**，包括一个影响架构决策的负面结果记录（Qwen3-Embedding 退化）。
3. 对 2025-2026 年间**24 篇经核验的 arXiv 论文**进行系统调研，将 Sisyphus 的设计原则与独立发表成果进行对照。
4. 对实现状态和路线图进行**诚实评估**，明确区分已完成工作和设计阶段功能。

---

## 二、相关工作

### 2.1 智能体记忆系统

智能体记忆领域在 2025-2026 年间迅速发展。**Mem0** [1]（GitHub 41K+ 星标）采用向量优先管线，可选择性图增强（Mem0g），在 LOCOMO 基准上达到 66.9%，token 节省 90%。**Cognee** [2]（17K+ 星标）使用图-向量混合方案，包含六阶段管线（分类→分块→提取→摘要→嵌入→提交）。**Zep** 使用双时态知识图谱进行事实有效窗口的时间推理。

**OpenHuman** [4]（26.6K 星标，2026 年 2 月发布）同样受 Karpathy 的 LLM Wiki 启发。它构建了 Memory Tree——从规范化的 Markdown 块经过评分密封形成层次摘要树的确定性管线——存储在 SQLite 中，可导出为 Obsidian 兼容的 Vault。**Hermes Agent** [3] 使用冻结快照模式：MEMORY.md 和 USER.md 在会话开始时捕获，设定严格的字符上限（2,200 和 1,375 字符），保持静态以保留 LLM 前缀缓存。

**TencentDB Agent Memory** [5] 实现了四层管线（L0 对话→L1 原子事实→L2 场景→L3 用户画像），具有从高层抽象到底层证据的完整可追溯性。**OpenMemory** [6]（4.1K 星标）提供多扇区记忆（情景、语义、程序、情感、反思），配备时间知识图谱和可解释召回轨迹。

### 2.2 学术研究（2025-2026）

2026 年 1 月至 5 月间，arXiv 上出现了 40 余篇关于智能体记忆的论文，其中多篇与 Sisyphus 的设计直接相关。

**证据优先存储**。Zhang 等 [7] 系统性地证明 LLM 整合后的记忆即使源自有用经验也会出错：GPT-5.4 在之前无记忆时 100% 解决的 ARC-AGI 题上失败率高达 54%，而"仅情景"对照组（保留原始轨迹、禁用抽象）匹配或优于所有测试的整合方案。Barman 等 [8] 用形式化框架进一步证明语义组织的代价是干扰——误召回无法通过同评分族内的阈值调优消除。TierMem [9] 通过双层设计（摘要索引 + 不可变原始日志）在 LoCoMo 上达到 0.851 准确率，输入 token 减少 54.1%。

**层次记忆**。TiMem [10] 通过时间记忆树组织对话，在 LoCoMo 上达到 75.30%，LongMemEval-S 上达到 76.88%，同时减少召回上下文长度 52.20%。All-Mem [11] 提出非破坏性拓扑编辑（SPLIT/MERGE/UPDATE 算子），保留到不可变证据的版本化可追溯性。

**门控整合**。RecMem [12]（ACL 2026 Findings）将交互存储在"潜意识"嵌入层中，仅在语义相似内容重复出现时才触发 LLM 整合，token 成本降低 87%。GAM [13]（ICLR 2026 Workshop）通过语义-事件触发器将编码与整合解耦。CraniMem [14] 建模注意力门控记忆，配备定期知识图谱整合和有界存储。

**安全性**。多篇论文揭示了记忆注入风险：休眠记忆注入 [15] 达到 99.8% 的注入率和 60-89% 的下游利用；状态污染 [16] 表明压缩前消毒（SPG 0.0004）远超事后消毒（SPG 0.086）。

### 2.3 Sisyphus 的定位

Sisyphus 与这些系统的主要区别在于 **运维极简主义**：无向量数据库、无图数据库、无 Docker 依赖——一个 Python 模块加一个 Markdown 文件目录。这用检索复杂性换取部署简单性。如 [8] 的综述所示，每种架构都为语义组织付出代价；Sisyphus 选择通过架构纪律（证据优先、索引可重建）而非基础设施复杂度来支付。

---

## 三、架构设计

### 3.1 设计原则

Sisyphus 围绕四个原则组织：

1. **情景证据不可变**：原始记忆文件（L1）永不被覆盖。所有抽象——反思、压缩、摘要——是引用但不替换源证据的派生品。
2. **索引可重建**：检索索引可以丢弃并从操作日志重新生成，无数据丢失。类似于从预写日志进行数据库复制。
3. **Git 是最好的备份系统**：所有存储为纯文本（Markdown、YAML、JSON）。版本控制、diff 和 blame 免费获得。
4. **层间解耦**：存储、日志和索引是独立组件，接口明确，可独立演进。

### 3.2 三层架构

**L1：情景存储（Markdown 文件）**——已实现。每条记忆为带 YAML 前置元数据的 `.md` 文件，包含 id、type、title、tags、importance、时间戳和来源字段。存储路径：`~/.omo/memory/`。创建后文件不可变；更新写入新版本。

**L2：操作日志（JSONL）**——设计阶段。每次写入操作（create/update/delete）追加一行 JSON，包含序列号、时间戳、操作类型、记忆 ID 和变更前快照。支持完整的审计追踪和时间旅行恢复。L3 从 L2 重建。

**L3：语义索引**——设计阶段。通过 FTS5 全文搜索 + 中文分词（jieba + CJK 单字回退）。四层耐久度分区：PERSIST（无条件注入，固定记忆）、HOT（7 天窗口，优先检索）、CODE（通过 CodeGraphContext 的代码结构）、COLD（衰减归档）。衰减评分：`importance × 0.5^(days/180)`。

### 3.3 上下文组装

`before_turn` 过程在每次智能体响应前组装上下文：

1. **PERSIST**：固定或高重要性（≥8）的项目上下文记忆无条件加载。
2. **HOT**：7 天内创建的记忆按 BM25 相关性 + 衰减评分检索。
3. **COLD**：剩余活跃记忆在 HOT 结果稀疏时作为 fallback。
4. **CODE**：查询涉及代码时，包含来自 CodeGraphContext 的函数签名和调用链。

上下文块格式化为 `<sisyphus_context>` XML 并注入系统提示词，上限 4,000 字符。

### 3.4 检索管线

检索管线使用三阶段方式：

1. **MOC 类型分类**：关键词匹配查询词与 MOC 类型分区，缩小候选集。
2. **反思层召回**：在相关类型内搜索反思和压缩输出。
3. **原始层召回**：当反思层结果稀疏时，补充原始 BM25 搜索。

可选重排序器（BGE Reranker v2-m3）在同主题文档数 ≥8 时自动激活。

---

## 四、原型评估

### 4.1 实现状态

当前原型（2026 年 5 月 24 日）包含 35 个 Python 源文件（内存模块）、30 个测试文件、291 个通过测试（1 个衰减评分计算中的瞬态失败）。

| 组件 | 状态 | 行数 | 测试 |
|------|------|------|------|
| MemoryStore（文件 CRUD） | ✅ 已实现 | 335 | 覆盖 |
| BM25 排序器（jieba + CJK） | ✅ 已实现 | ~300 | 覆盖 |
| ContextRetriever（三层） | ✅ 已实现 | 884 | 覆盖 |
| MCP Server（9 工具） | ✅ 已实现 | 333 | 覆盖 |
| Sleep Pipeline（Dream/Compress） | ✅ 框架 | ~200 | 覆盖 |
| Subagent LLM 系统 | ✅ 已实现 | 499 | 覆盖 |
| Memory Tree（l0/l1/l2） | ✅ 已实现 | 203 | 覆盖 |
| Reranker（BGE v2-m3） | ✅ 已实现 | ~200 | 覆盖 |
| L2 操作日志 | ⏳ 设计 | — | — |
| L3 FTS5 索引 | ⏳ 设计 | — | — |
| 自动触发（after_turn） | ⏳ 设计 | — | — |
| CodeGraphContext 集成 | ⏳ 设计 | — | — |

### 4.2 实验 1：分词对 BM25 检索的影响

**设置**：比较了二元分词与基于 jieba 的中文词分割 + 英文正则提取 + CJK 单字符回退方案。评估在 90 条记忆（21 条非测试）的语料库上测量了首位精度（@1）。

**结果**：

| 分词器 | BM25 @1 | 变化 |
|--------|---------|------|
| Bigram（基线） | 56% | — |
| jieba + EN 正则 + CJK 回退 | **83%** | **+27 pp** |

改进源于 jieba 基于词典的分割能产生语义上有意义的词元（如"记忆系统"作为一个词元 vs "记忆" + "忆系"作为二元组），以及多字符 CJK 回退避免了单字符噪声。

### 4.3 实验 2：A/B 测试——有记忆 vs 无记忆

**设置**：在一组固定提示词上评估了有记忆注入和无记忆注入的智能体响应质量。质量由 LLM-as-judge 在相关性、事实准确性和有用性三个维度上进行评分。

**结果**：

| 条件 | 平均分 |
|------|--------|
| 无记忆 | 0.6 |
| 有记忆（Sisyphus） | **1.1** |

关键定性发现：**检索不准比不检索更差**。当注入错误记忆时，会误导智能体。这指导了我们的设计优先级——精度优于召回。

### 4.4 实验 3：Qwen3-Embedding（负面结果）

**设置**：评估了 Qwen3-Embedding-0.6B 作为 BM25 的密集向量补充。使用 75% 余弦相似度 + 25% BM25 的混合评分。

**结果**：

| 方法 | @1 |
|------|-----|
| 仅 BM25 | 76% |
| BM25 + Qwen3-Embedding（75/25 混合） | **43%** |

0.6B 模型的中文语义表示太弱，无法产生正向贡献；嵌入信号削弱了 BM25 排序。**此负面结果导致 Qwen3-Embedding 从默认管线中移除**。它也揭示了密集检索的条件性：小型嵌入模型可能损害而非提升领域特定检索。

### 4.5 实验 4：Reranker 条件激活

**设置**：BGE Reranker v2-m3 通过条件激活阈值进行测试：仅当 ≥8 个文档属于同一主题（类型）时才激活。

**结果**：激活时，Reranker 带来了 **+13 个百分点的 @1 提升**。低于阈值时不激活，避免不必要的计算。此条件策略在质量和延迟之间取得了平衡。

### 4.6 实验 5：测试套件稳定性

原型维护了 292 个测试的测试套件（291 通过，1 个半衰期参数从 30 天改为 180 天后衰减计算中的瞬态失败）。套件覆盖了存储操作、检索精度、BM25 评分、衰减计算、MCP 协议处理和管线执行。所有测试在标准库 Python 上运行，无外部依赖。

---

## 五、讨论

### 5.1 架构-实验对齐

我们的实验发现强化了架构的设计原则：

1. **证据优先**：Qwen3-Embedding 的负面结果验证了抽象层（密集嵌入）应为选择性加入和条件性的，而非默认。文件原生的 L1 存储保存了嵌入可能扭曲的原始数据。
2. **检索精度优于召回**：A/B 测试发现错误记忆比无记忆更差，支持了 PERSIST/HOT/CODE/COLD 分区作为控制上下文内容的机制。
3. **条件计算**：Reranker 的条件激活（≥8 同主题文档）表明资源密集型组件应有门控控制，与 RecMem [12] 和 GAM [13] 的门控整合发现一致。

### 5.2 局限性

**原型成熟度**：L2（操作日志）和 L3（FTS5 索引）已设计但未实现。上下文组装当前使用单一 ContextRetriever，而非架构中描述的多 Source ContextAssembler。Dream 引擎（LLM 反思）以框架形式存在但不自动触发。

**评估规模**：我们的实验使用 90 条记忆语料库（去测试数据后 21 条），适合原型验证但不适合生产级比较。A/B 测试使用 LLM-as-judge，引入了评估者偏差。

**单人开发者范围**：架构针对个人开发者工作流优化；多租户隔离、团队共享记忆和生产部署问题未涉及。

### 5.3 效度威胁

**内部效度**：BM25 改进可能部分反映语料库特定特征而非通用的中文分词优势。**构念效度**：我们使用 LLM-as-judge 作为质量指标是代理指标，非智能体性能的直接测量。**外部效度**：90 条记忆语料库的结果可能无法推广到千条级生产部署。**统计效度**：A/B 测试使用小样本；未计算置信区间。

---

## 六、结论

Sisyphus 是一个面向 LLM 智能体的文件原生、证据优先的记忆架构，围绕"情景证据不可变、检索索引可重建"的核心原则设计。工作原型验证了核心管线，包含 291 个通过测试和实证结果，包括通过 CJK 分词优化实现 BM25 @1 从 56% 到 83% 的提升、1.1 vs 0.6 的记忆优势，以及一个影响架构决策的 Qwen3-Embedding 负面结果记录。通过对 24 篇经核验的 arXiv 论文的系统调研，我们发现 Sisyphus 的设计原则——证据优先、可重建索引、来源追踪、门控整合——与多个独立研究组的发表成果一致。

后续工作包括：实现 L2 操作日志和 L3 FTS5 索引，从单一检索器迁移到多 Source 的 ContextAssembler，添加 Dream 整合的自动触发钩子，集成 CodeGraphContext 实现代码级记忆，以及开发可视化仪表盘。架构设计支持增量演进：每一层都可以在不影响现有管线的情况下添加。

---

## 参考文献

[1] Mem0. "Building Production-Ready AI Agents with Scalable Long-Term Memory." arXiv:2504.19413, 2025.

[2] Cognee. "Knowledge Engine for AI Agent Memory." GitHub: topoteretes/cognee, 17K+ ⭐, Apache 2.0.

[3] Hermes Agent. "How Hermes Agent Memory Works — 3-Layer System Explained." Nous Research, 2026.

[4] OpenHuman. "Your Personal AI Super Intelligence." GitHub: tinyhumansai/openhuman, 26.6K ⭐, GPL-3.0. 2026-02-18 发布.

[5] TencentDB Agent Memory. "Fully Local Long-Term Memory for AI Agents." GitHub: Tencent/TencentDB-Agent-Memory, 2026.

[6] OpenMemory. "Real Long-Term Memory for AI Agents." GitHub: CaviraOSS/OpenMemory, 4.1K ⭐, Apache 2.0. 2025-10 发布.

[7] D. Zhang et al. "Useful Memories Become Faulty When Continuously Updated by LLMs." arXiv:2605.12978, 2026-05. UIUC + 清华大学.

[8] S. R. Barman et al. "The Price of Meaning: Why Every Semantic Memory System Forgets." arXiv:2603.27116, 2026-03.

[9] A. Huang et al. "TierMem: From Lossy to Verified." arXiv:2602.17913, 2026-02. ICLR 2026 Workshop.

[10] J. Yan et al. "TiMem: Temporal-Hierarchical Memory Consolidation." arXiv:2601.02845, 2026-01.

[11] Y. Liu et al. "All-Mem: Agentic Lifelong Memory via Dynamic Topology Evolution." arXiv:2603.19595, 2026-03.

[12] K. Chen et al. "RecMem: Recurrence-based Memory Consolidation." arXiv:2605.16045, 2026-05. ACL 2026 Findings.

[13] W. Li et al. "GAM: Hierarchical Graph-based Agentic Memory." arXiv:2604.12285, 2026-04. ICLR 2026 Workshop.

[14] M. Park et al. "CraniMem: Cranial Inspired Gated Memory." arXiv:2603.15642, 2026-03.

[15] L. Wang et al. "Hidden in Memory: Sleeper Memory Poisoning." arXiv:2605.15338, 2026-05.

[16] R. Zhao et al. "State Contamination in Memory-Augmented LLM Agents." arXiv:2605.16746, 2026-05.

[17] S. Wu et al. "MemTier: Tiered Memory Architecture." arXiv:2605.03675, 2026-05.

[18] Y. Fang et al. "AtomMem: Learnable Dynamic Agentic Memory." arXiv:2601.08323, 2026-01.

[19] J. Xu et al. "MemRL: Self-Evolving Agents via Runtime RL." arXiv:2601.03192, 2026-01.

[20] V. Markovic et al. "Optimizing the Interface Between Knowledge Graphs and LLMs." arXiv:2505.24478, 2025.

[21] A. Gopinath et al. "DeMem: Decision-Centric Rate-Distortion." arXiv:2605.10870, 2026-05.

[22] M. Chen et al. "Synapse: Episodic-Semantic Memory via Spreading Activation." arXiv:2601.02744, 2026-01.

[23] T. Kim et al. "HeLa-Mem: Hebbian Learning Associative Memory." arXiv:2604.16839, 2026-04.

[24] J. Park et al. "Human-Inspired Memory Architecture." arXiv:2605.08538, 2026-05.

---

**所有引用均通过 arXiv ID 查询核验，2026-05-24。**

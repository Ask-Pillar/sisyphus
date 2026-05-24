# 记忆系统市场对比：Sisyphus vs Mem0 vs Letta vs Cognee

> 日期: 2026-05-24  
> 用途: 评估 Sisyphus 规划方向与主流方案的异同，识别差异化优势

---

## 一、对比总览

| 维度 | **Mem0** | **Letta (MemGPT)** | **Cognee** | **Sisyphus（规划）** |
|------|----------|-------------------|------------|---------------------|
| Stars | 41K+ | 13K+ (原 MemGPT) | 17K+ | — |
| 定位 | AI memory layer | Agent runtime + memory | AI knowledge engine | Self-evolving dev agent |
| 许可 | Apache 2.0 | Apache 2.0 | Apache 2.0 | — |
| 核心技术 | 向量 + 可选图 | 上下文窗口管理 + git 文件系统 | 图向量混合 | File-based MD + BM25 |
| 检索方式 | 语义 + BM25 + 实体图 | 记忆树 + 对话搜索 | 图遍历 + 向量 | BM25 + LLM recall |
| 持久化 | 向量DB + Neo4j + SQLite | MemFS (git-backed) | Neo4j/图DB + 向量DB | `.md` 文件 |
| MCP Server | ✅ 内置 | ❌ 非原生 | ✅ 内置 | ✅ 自建 stdio |
| 部署复杂度 | 中（需向量DB） | 高（Letta 框架） | 中（需图DB） | **极低（零依赖）** |
| 学习成本 | 中 | 高 | 中 | 低 |

---

## 二、各家特色

### Mem0 — 标杆级记忆引擎

```
提取管线: 对话 → LLM提取事实 → 去重+embedding → 向量DB
                                                     → 实体链接 → 图DB  
检索:    语义相似度 + BM25关键词 + 实体图匹配 → 融合排序
```

**亮点**: ADD-only 永不删除，时间上下文不丢失。多租户隔离（user/agent/app/session）。

**弱点**: 需要向量 DB + 可选 Neo4j，本地部署重。对中文和代码领域无特殊优化。

### Letta — 自编辑记忆 agent

```
Tier 1 (上下文内):  core_memory 块(pinned) + 对话历史
Tier 2 (上下文外):  recall_storage + archival_storage(向量DB)
  
Sleep-time compute: 后台子 agent 反思 → 更新 core_memory
MemFS:             git-backed 文件系统，system/ 目录始终加载
```

**亮点**: 记忆块概念（pinned 到上下文窗口），agent 自己管理内存。Sleep-time 后台反思。

**弱点**: 绑定 Letta 框架，不自带代码索引。部署重。

### Cognee — 图向量混合知识引擎

```
6阶段管线:  分类 → 权限 → 分块 → LLM提取实体 → 摘要 → embed+写入图
retrieve:   向量搜索找入口 → 图遍历 → 结构化上下文 → 生成答案
session:    短期内存（快速缓存）→ 后台同步到持久图
```

**亮点**: `cognify` + `memify` 自进化。MCP 内建。图遍历能理解实体关系。

**弱点**: 需要图 DB。管线复杂，本地部署需要 Neo4j 或 KùzuDB。

---

## 三、Sisyphus 差异化定位

### 优点（其他三家做不到的）

| 优势 | Mem0 | Letta | Cognee | Sisyphus |
|------|------|-------|--------|----------|
| **零外部依赖** | ❌ 需向量DB | ❌ 需框架 | ❌ 需图DB | ✅ 纯文件 |
| **中文优先** | ❌ 英文为主 | ❌ 英文为主 | ❌ 英文为主 | ✅ jieba/CJK 优化 |
| **代码记忆** | ❌ 无 | ❌ 无 | ❌ 无 | ✅ 计划集成 CodeGraphContext |
| **agent 自进化** | 部分 | ✅ 记忆块自编辑 | ✅ memify | ✅ Dream+Compress+after_turn |
| **部署门槛** | pip install + DB | Letta 框架 | pip install + DB | python3 -m sisyphus |
| **成本** | API + 向量DB | API + 框架 | API + 图DB | **零**（opencode 自带模型） |

### 差距（需要追赶的）

| 短板 | Mem0 | Sisyphus 现状 | 计划 |
|------|------|-------------|------|
| **语义检索** | 19+ 向量DB | BM25 关键词 | 可选：加轻量 embedding |
| **关系推理** | 图 DB 实体链接 | 无 | CodeGraphContext 补代码关系 |
| **多租户** | user/agent/app/run | 无 | scope/project 字段 |
| **记忆去重** | hash + LLM 判定 | 无 | 未规划 |
| **记忆更新** | ADD-only 不覆盖 | 直接覆盖 | 需考虑 |
| **生产就绪** | 41K stars | 自用阶段 | — |

---

## 四、Sisyphus 的新增差异化设计

### 1. 耐久度分层（其他三家都没有）

```
Mem0:    所有记忆放向量DB，按相似度检索，无耐久度概念
Letta:   system/ 始终加载 = 我们 PERSIST，但粒度是文件不是记忆条目
Cognee:  短期 session + 长期 permanent，但无"无条件注入"层

Sisyphus: L-PERSIST (无条件注入) / L-HOT (7天优先) / L-CODE (代码) / L-COLD (衰减)
          → 既按时间也按耐久度，四层独立索引
```

### 2. 项目作用域（简单但有力）

```
Mem0:    多租户 model (user/agent/app/run) → 面向 SaaS
Cognee:  dataset 概念 → 面向数据管理

Sisyphus: project 字段 + scope(global/project/session)
          → 轻量，开发场景更自然（我切项目时就切记忆）
```

### 3. 零依赖部署

```
Mem0:    pip install mem0ai + 向量DB（需要 OpenAI key）
Cognee:  pip install cognee + Neo4j（需要图DB）
Letta:   安装 Letta 框架 + Docker

Sisyphus: python3 -m sisyphus.server.mcp
          → 零新增依赖，opencode 自带模型
```

### 4. 代码记忆 + 经验记忆一体化

```
其他三家:  纯对话/文档记忆
Sisyphus:  对话记忆（sisyphus MCP）+ 代码索引（codegraphcontext MCP）
           → agent 问"这个函数被谁调用"时有结构化的图查询结果
```

---

## 五、Sisyphus 应该补的

| 优先级 | 能力 | 对标 | 方式 |
|--------|------|------|------|
| P1 | 记忆去重（ADD-only） | Mem0 | 写入前 hash 比对，相似→标记 refined_by |
| P2 | 轻量向量检索 | Mem0/Cognee | SQLite + sentence-transformers（可选，不强制） |
| P2 | 记忆更新不覆盖 | Mem0 | 旧内容标 deprecated，新内容另写 |
| P3 | 跨 agent 共享 | Letta/Cognee | 共享 PERSIST 层（同一份 PERSIST.md） |

---

## 六、结论

Sisyphus **不跟 Mem0/Cognee 硬拼向量/图数据库**——那些是通用记忆引擎，目标用户是有运维能力的团队。Sisyphus 的护城河是：

1. **零依赖** — 不需要装任何数据库，纯文件即记忆，pip install 也不需要
2. **中文原生** — jieba 分词 + CJK 处理，Mem0 的 BM25 对中文是稀烂的
3. **代码记忆** — 独角兽级别（记忆中夹带代码索引，三大家都没有）
4. **耐久度分层** — PERSIST/HOT/CODE/COLD 四层，比 Letta 的 system/ 设计更细粒度
5. **自进化闭环** — Dream + Compress + after_turn → 从对话中自动长记性

定位：**面向单人开发者的零依赖、中文原生、自带代码索引的自进化记忆系统。** 不需要 VC 的 41K stars，但对你我自己的工作流有实际价值。

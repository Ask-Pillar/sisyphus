# Sisyphus 项目规划：从记忆存储到个性化检索推荐系统

## 一、项目愿景与目标

**一句话目标**：为 AI Agent 构建一个个性化知识检索推荐系统，使 Agent 在多轮对话、跨会话、跨项目场景下，能够精准、多样、可控地召回用户相关记忆与知识。

**核心度量（北极星指标）**：

- **NDCG@5 ≥ 0.85** — 用户实际需要的记忆出现在 Top-5 推荐中
- **触发准确率 ≥ 90%** — 该调用时调用，不该调用时不打扰
- **端到端延迟 < 500ms** — 记忆注入不拖慢 Agent 响应

### 项目定位重构

| 传统视角 | 推荐视角 | Sisyphus 对应 | 当前状态 |
|----------|----------|---------------|----------|
| 存储 | 用户画像 | Personal Memory (偏好/习惯/反馈) | ✅ 基础存在 |
| 索引 | 物料池 | Memory + Knowledge + Project 多池 | ⚠️ 仅单池 |
| 检索 | 召回 | BM25 / FTS5 / Tree Browse | ✅ 已实现 |
| - | 粗排 | TF-IDF + Decay Score | ✅ 已实现 |
| - | 精排 | BCE / BGE Reranker | ✅ 已实现 |
| - | 重排 | 多样性 / 反茧房 / 对立观点 | ❌ 未实现 |
| - | 反馈 | recall_count (隐式) | ⚠️ 仅隐式 |
| - | 触发机制 | 无 (每次都调用) | ❌ 未实现 |
| - | 知识库导入 | importer (小规模 md/jsonl) | ⚠️ 不支持大规模 |

## 二、架构演进：从单池到命名空间

### 2.1 目标架构

```
~/.omo/
├── personal/          # 个人记忆池 (偏好、习惯、反馈历史)
│   ├── memory/        # MemoryStore (SQLite)
│   └── cache/         # FTS5 索引
├── projects/          # 项目记忆池 (按 git remote 隔离)
│   ├── {project-hash}/
│   │   ├── memory/
│   │   ├── sessions/  # 对话日志
│   │   └── cache/
│   └── ...
├── knowledge/         # 知识库池 (大规模导入)
│   ├── {domain}/      # 按领域分区
│   │   └── chunks.db  # SQLite FTS5 分块存储
│   └── ...
├── shared/            # 跨项目共享池
│   └── memory/
└── config.yaml        # 全局配置 + 池权重
```

### 2.2 UnifiedRetriever（统一检索器）

```python
class UnifiedRetriever:
    """跨池检索，scope 控制激活哪些池，weight 控制混合权重。"""
    
    def retrieve(self, query, scope=None, top_k=10):
        # 1. 根据 scope 确定激活池 (默认: personal + current_project)
        # 2. 各池独立召回 candidate_lists
        # 3. 归一化分数 + 加权混合
        # 4. 全局精排 (Reranker)
        # 5. 重排 (多样性 + 反茧房)
        # 6. 返回 top_k
```

## 三、操作规划：四个阶段

### Phase 1：基础修复 + 排序质量（2 周）

**主题**：别再造存储了，开始做排序

| # | 任务 | 优先级 | 说明 |
|---|------|--------|------|
| 1.1 | store.create() 去重逻辑移至应用层 | P0 | 移到 importer / hooks，修复 LoopDetector 4 个测试 |
| 1.2 | Pipeline 统一 | P0 | 合并 memory/pipeline.py 与 pipeline/sleep.py，保留 SleepPipeline 的 DirLock + 6步流程 |
| 1.3 | 修复剩余 5 个测试失败 | P0 | BGE torch mock × 4, path routing CJK × 1 |
| 1.4 | 重排层实现 | P1 | 在 Reranker 之后增加 DiversityReranker：类型配额 + MMR 去冗余 |
| 1.5 | Decay 公式调优 | P1 | 修正 docstring (180→实际值)，增加 recall_count 加权：`score *= (1 + log(1 + recall_count))` |
| 1.6 | SQLite 存储合并 | P1 | 用户已实现但未 push，合并后替换文件系统 MemoryStore |

**验证标准**：

- 全部测试通过 (0 failures)
- 重排后 Top-5 中类型多样性 ≥ 2 种 (在 10 条以上记忆场景)
- NDCG@5 在现有 Gate 测试集上不低于 P5 水平 (≥ 83%)

### Phase 2：触发机制 + 对话日志（3 周）

**主题**：知道什么时候该记、什么时候该忆

| # | 任务 | 优先级 | 说明 |
|---|------|--------|------|
| 2.1 | L0 信号词触发 | P0 | 正则匹配关键词 ("记住", "之前", "上次", "remember", "recall" 等)，命中则调用检索 |
| 2.2 | L1 轻量规则触发 | P1 | 每 N 轮检查一次 + 话题切换检测（余弦相似度 < 阈值） |
| 2.3 | L2 跳过 + 缓存 | P1 | 连续无命中时指数退避，避免无效调用 |
| 2.4 | 对话日志分层存储 | P0 | sessions/{date}.md 主对话, sessions/{date}_sub_{NNN}.jsonl 子 Agent 日志 |
| 2.5 | hooks.py after_turn 重构 | P1 | 停止将每条回复存入 MemoryStore，改写入 session 日志；仅"值得记住"的内容才 create memory |
| 2.6 | 触发准确率测试集构建 | P1 | 50+ 标注样本：(user_message, should_trigger: bool, expected_pool: str) |

**验证标准**：

- 触发准确率 ≥ 85% (在标注集上)
- 无触发场景平均延迟 < 5ms (纯正则 + 规则)
- 对话日志不污染 memory.search() 结果
- 子 Agent 日志可追溯但不参与检索

### Phase 3：命名空间 + 知识库导入（3 周）

**主题**：从单用户单项目到多池多域

| # | 任务 | 优先级 | 说明 |
|---|------|--------|------|
| 3.1 | 命名空间目录结构实现 | P0 | ~/.omo/ 多池目录，config.yaml 池注册 |
| 3.2 | UnifiedRetriever 实现 | P0 | 跨池召回 + 归一化 + 加权混合 |
| 3.3 | 项目池自动切换 | P1 | 根据 git remote / cwd 自动激活对应 project 池 |
| 3.4 | KnowledgeBase 大规模导入 | P1 | SQLite FTS5 分块存储，支持 .md / .txt / .pdf / .jsonl / .csv |
| 3.5 | 导入管道 | P1 | 分块策略 (固定/语义)，进度条，增量更新，1GB+ 测试 |
| 3.6 | MCP 工具扩展 | P2 | 新增 import_knowledge, switch_scope, list_pools |

**验证标准**：

- 3 个池 (personal + project + knowledge) 同时激活时检索延迟 < 800ms
- 1GB 知识库导入完成时间 < 10 分钟
- 跨池检索结果来源标注正确 (pool_id 字段)
- 项目切换后自动加载正确的 project 池

### Phase 4：反馈闭环 + 反茧房（2 周）

**主题**：让系统越用越准，但不让用户越走越窄

| # | 任务 | 优先级 | 说明 |
|---|------|--------|------|
| 4.1 | 显式反馈机制 | P0 | MCP 新增 rate_memory(id, score: 1-5) + dismiss_memory(id)，反馈存入 personal 池 |
| 4.2 | 反馈信号融入排序 | P0 | feedback_score 权重衰减 (半衰期 90 天)，负反馈直接降权 |
| 4.3 | 多样性保底 | P1 | Top-K 结果中强制至少 1 条来自非主池 / 非高频类型 |
| 4.4 | Forgotten Gems 轮转 | P1 | 每次检索有 10% 概率注入 1 条"被遗忘的高重要性记忆" (recall_count=0, importance≥7) |
| 4.5 | 对立观点检查 | P2 | 如果 Top-3 结论一致，检索是否存在相反观点的记忆，有则附加标注 |
| 4.6 | 反馈效果 A/B 测试框架 | P2 | 记录 with-feedback vs without-feedback 的检索点击率差异 |

**验证标准**：

- 持续使用 7 天后，用户评分 ≥ 4 的记忆在 Top-5 中出现概率提升 ≥ 20%
- dismiss 的记忆在后续 10 次检索中不再出现
- Forgotten Gems 命中率 ≥ 5% (用户对轮转记忆的正反馈率)
- NDCG@5 ≥ 0.85 (最终北极星指标)

## 四、阶段验证计划总览

```
Phase 1 (W1-W2)          Phase 2 (W3-W5)          Phase 3 (W6-W8)          Phase 4 (W9-W10)
┌─────────────────┐    ┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐
│ 修复 + 排序质量   │ →  │ 触发 + 对话日志   │ →  │ 命名空间 + 知识库  │ →  │ 反馈 + 反茧房     │
├─────────────────┤    ├──────────────────┤    ├──────────────────┤    ├──────────────────┤
│ ✓ 0 test fail   │    │ ✓ 触发准确 ≥85%  │    │ ✓ 多池延迟 <800ms │    │ ✓ NDCG@5 ≥0.85  │
│ ✓ 类型多样 ≥2   │    │ ✓ 无触发 <5ms    │    │ ✓ 1GB导入 <10min │    │ ✓ dismiss 生效   │
│ ✓ NDCG@5 ≥83%  │    │ ✓ 日志不污染搜索  │    │ ✓ 来源标注正确    │    │ ✓ 评分提升 ≥20%  │
└─────────────────┘    └──────────────────┘    └──────────────────┘    └──────────────────┘
```

## 五、当前技术债清单（Phase 1 前置）

| 问题 | 影响 | 修复方案 |
|------|------|----------|
| store.create() SHA256 去重在 Store 层 | LoopDetector 失效 (4 test fail) | 移至 importer/hooks 应用层 |
| 两个 Pipeline 类并存 | 维护混乱，行为不一致 | 合并为 SleepPipeline，Pipeline 类降级为 alias |
| hooks.py after_turn 写入 MemoryStore | 污染搜索、触发 Reranker | 改写 session 日志，分离关注点 |
| BGE Reranker 测试缺 torch mock | 4 test fail | 添加 _make_torch_mock() |
| CJK path routing 无 jieba 回退 | 1 test fail | CJK 字符计数 + fuzzy 子串预检 |
| `_fine_cluster()` 死代码 | tree_builder.py 噪声 | 删除或标记 TODO |
| test_mcp_import.py 覆盖盲区 | 不测 mcp.py 的 import handler | 补充集成测试 |
| Decay docstring 不匹配 (30 vs 180) | 文档误导 | 修正 docstring |

## 六、关键设计决策记录

| 决策 | 选择 | 理由 |
|------|------|------|
| 存储引擎 | SQLite (用户已实现) | 零依赖、支持 FTS5、比文件系统快 10x+ |
| 去重层级 | 应用层 (importer/hooks) | Store 层去重破坏 LoopDetector 语义 |
| 对话日志 | 独立 sessions/ 目录 | 不污染记忆检索，保留完整对话用于回溯 |
| 子 Agent 日志 | {date}_sub_{NNN}.jsonl | 链接到主对话，按需查看，不参与检索 |
| 知识库格式 | SQLite FTS5 分块 | 支持 GB 级别，增量更新，与记忆池隔离 |
| 触发机制 | 三级 (信号词→规则→退避) | 平衡准确率与性能开销 |
| 反茧房 | 多样性配额 + Gems 轮转 + 对立检查 | 项目作用域天然收窄，需主动拓展 |
| 反馈衰减 | 半衰期 90 天 | 用户偏好会变，反馈不应永久生效 |

---

*这个计划以 10 周为周期，优先级明确：Phase 1 扫清债务 → Phase 2 建立触发智能 → Phase 3 扩展数据池 → Phase 4 闭环反馈。每个阶段都有可量化的验证标准，避免"做了但不知道做得好不好"。核心思路始终是——存储够了，排序为王。*

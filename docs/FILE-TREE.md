# Sisyphus 项目文件结构

> 更新日期: 2026-05-24 · 292 tests passing

```
sisyphus/
│
├── AGENTS.md                    # 项目级 AI agent 指令（编码规范、TDD要求、提交规范）
├── README.md                    # 项目概述与架构说明
├── pyproject.toml               # Python 项目配置
├── .gitignore
│
├── src/sisyphus/                # 核心源码（不要改动）
│   ├── __init__.py
│   ├── cli/                     # CLI 命令行工具
│   │   └── tree_cmd.py          #   树结构查看命令
│   ├── memory/                  # 记忆系统核心（28 个文件）
│   │   ├── store.py             #   文件级 CRUD（Memory + MemoryStore）
│   │   ├── retrieval.py         #   三层检索器（884行，含 BM25+TFIDF+Reranker+Cache）
│   │   ├── context.py           #   AgentMemory + before_turn 上下文注入
│   │   ├── refined.py           #   REFINED 层存储
│   │   ├── tree.py              #   Memory Tree（l0/l1/l2 三层树结构）
│   │   ├── tree_builder.py      #   Tree 构建器
│   │   ├── tree_retriever.py    #   Tree 检索器
│   │   ├── moc.py               #   MOC 索引生成
│   │   ├── subagent.py          #   LLM 子进程执行系统（499行）
│   │   ├── llm.py               #   OpenAI 兼容 LLM 客户端
│   │   ├── dream.py             #   Dream 反思引擎
│   │   ├── compression.py       #   Compress 压缩引擎
│   │   ├── extraction.py        #   Extractor 会话提取框架
│   │   ├── pipeline.py          #   Sleep Pipeline 编排器
│   │   ├── recall.py            #   LLM 语义召回
│   │   ├── reranker_bce.py      #   BCE Reranker
│   │   ├── search.py            #   搜索接口
│   │   ├── snapshot.py          #   快照管理
│   │   ├── link.py              #   记忆关联
│   │   ├── log.py               #   操作日志
│   │   ├── loop.py              #   循环检测
│   │   ├── cache.py             #   Embedding 缓存
│   │   ├── sandbox.py           #   沙箱（已废弃）
│   │   ├── agent.py             #   Agent 集成
│   │   ├── cli.py               #   记忆 CLI 工具
│   │   └── utils.py             #   工具函数
│   ├── pipeline/                # Pipeline 子模块
│   │   └── sleep.py             #   Sleep Pipeline 实现
│   └── server/                  # MCP Server
│       ├── mcp.py               #   MCP stdio JSON-RPC Server（9 工具）
│       └── importer.py          #   一键导入工具
│
├── tests/                       # 测试目录（30 个文件，292 tests）
│   ├── conftest.py              #   pytest 配置
│   ├── test_store.py            #   存储层测试
│   ├── test_retrieval.py        #   检索测试（含衰减评分修复）
│   ├── test_context.py          #   上下文注入测试
│   └── ...                      #   其他测试文件
│
├── scripts/                     # 基准测试/分析脚本（从根目录搬入）
│   ├── ab_test.py               #   A/B 测试（有记忆 vs 无记忆）
│   ├── ab_test_v2.py            #   A/B 测试 v2
│   ├── abc_clean.py             #   测试数据清理
│   ├── abc_flashrank.py         #   FlashRANK 基准
│   ├── abc_local.py             #   本地模型基准
│   ├── abc_recall.py            #   召回基准
│   ├── abc_sisyphus.py          #   Sisyphus 检索基准
│   ├── bm25_analysis.py         #   BM25 分词分析
│   └── scale_test.py            #   规模测试
│
├── reports/                     # HTML/MD 测试报告（从根目录搬入）
│   ├── abc-test-report.html     #   ABC 测试报告
│   ├── full-test-report.html    #   全量测试报告
│   ├── recall_benchmark_report.html  # 召回基准报告
│   ├── test-report.html         #   测试报告
│   ├── p0-verification-report.* #   P0 验证报告
│   ├── p1-verification-report.html   # P1 验证报告
│   ├── p2-verification-report.html   # P2 验证报告
│   ├── p3-verification-report.html   # P3 验证报告
│   └── p3_upgrade_report.html   #   P3 升级报告
│
└── docs/                        # 设计文档与论文（仅设计文档提交，论文不提交）
    ├── final-dev-plan.*         #   最终开发计划
    ├── final-comparison.*       #   市场对比（8 系统）
    ├── memory-defects-plan.*    #   缺陷改进计划
    ├── context-is-everything.*  #   架构洞察：上下文组装
    ├── architecture-redesign.*  #   ContextRetriever→ContextAssembler
    ├── embedded-vs-mcp.*        #   before_turn 内嵌 vs MCP
    ├── agents-md-integration.*  #   项目级 AGENTS.md 集成
    ├── global-agents-md.*       #   全局 AGENTS.md 集成
    ├── summary-report.*         #   综合评估报告
    ├── market-comparison.*      #   市场对比 v1
    ├── market-comparison-v2.*   #   市场对比 v2（可视化规划）
    ├── memory-architecture-v2.* #   耐久度分层架构
    ├── mcp-wechat-debug.*       #   WeChat Bridge MCP 调试
    ├── sisyphus-paper-v4.md     #   论文 v4（英文 IMRaD）← 不提交
    ├── sisyphus-paper-zh-v4.md  #   论文 v4（中文版）← 不提交
    ├── sisyphus-paper-zh-v2.md  #   论文 v2（微信生成原始版）← 不提交
    ├── sisyphus-paper-v3.md     #   论文 v3（时间修正版）← 不提交
    └── sisyphus-paper-*.md      #   其他论文版本 ← 均不提交
```

### 文件分类说明

| 类别 | 位置 | 可否提交 | 说明 |
|------|------|---------|------|
| 核心源码 | `src/sisyphus/` | ✅ | 核心代码，不可改动（本次整理中） |
| 测试代码 | `tests/` | ✅ | pytest 测试套件 |
| 辅助脚本 | `scripts/` | ✅ | 基准测试、分析脚本 |
| 测试报告 | `reports/` | ✅ | 历史测试和验证报告 |
| 设计文档 | `docs/*`（除论文外） | ✅ | 架构设计、计划、对比 |
| 论文文档 | `docs/sisyphus-paper-*.md` | ❌ | 论文各版本，仅供本地参考 |

### 论文文档说明

以下论文文件在 `docs/` 中，但**不加入版本控制**（仅在 `.gitignore` 中）：

- `sisyphus-paper-v4.md` — 最终版英文 IMRaD 论文
- `sisyphus-paper-zh-v4.md` — 最终版中文论文
- `sisyphus-paper-v3.md` — 时间修正版
- `sisyphus-paper-zh-v2.md` — 微信 agent 生成原始版
- `sisyphus-paper-draft.md` — 早期草稿

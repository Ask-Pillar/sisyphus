# Nexus 整体规划

## 定位

Agent 中枢记忆系统。所有 Agent 的记忆、知识、技能都走 Nexus。MCP 是水管，Nexus 是调度阀门。

## 架构

```
任何 Agent (OpenCode / Claude Code / Hermes / Claw)
  → MCP JSON-RPC
    → Nexus Core (调度层)
      ├── 路由: 请求该查哪些模块
      ├── 合并: 多模块结果加权排序
      └── 开关: config.yaml 控制模块启停
        ├── sisyphus/    (Episodic 层)
        ├── semantic/    (Semantic 层)
        ├── procedural/  (Procedural 层)
        └── external/    (第三方模块)
```

## 目录结构

```
nexus/
├── nexus/
│   ├── __init__.py
│   ├── core.py          # 调度层 (路由+合并+开关)
│   ├── protocol.py      # 模块协议 (search/import/stats)
│   ├── config.py        # 配置加载
│   ├── sisyphus/        # Episodic 层 (现有代码挪过来)
│   │   ├── memory/      # store / retrieval / context / extraction / ...
│   │   ├── agent/       # hooks
│   │   ├── pipeline/    # SleepPipeline
│   │   └── server/      # dashboard / mcp
│   ├── semantic/        # Semantic 层 (Phase 5)
│   │   ├── url_index.py
│   │   ├── fetcher.py
│   │   ├── sandbox.py
│   │   └── knowledge.py # 已有，挪过来
│   ├── procedural/      # Procedural 层 (Phase 6)
│   │   ├── skill_store.py
│   │   ├── agent_router.py
│   │   └── persona.py
│   └── external/        # 第三方模块桥接
│       └── hermes_skills.py
├── config/
│   └── nexus.yaml
├── tests/
│   ├── sisyphus/        # 现有测试挪过来
│   ├── semantic/
│   └── procedural/
├── docs/
├── pyproject.toml
├── README.md
└── setup.py
```

## 模块协议

任何模块只需实现三个方法，就能接入 Nexus 调度：

```python
class ModuleProtocol:
    name: str                          # 模块名，如 "sisyphus"
    search(query: str, top_k: int) -> list[(result, score, source)]
    import(source: str) -> int
    stats() -> dict
```

外部模块（如 Hermes 技能系统）只需包装成这个协议，就能注册进 Nexus。

## 配置

`nexus/config/nexus.yaml`：

```yaml
modules:
  sisyphus:
    enabled: true
    weight: 0.4
    package: nexus.sisyphus
  semantic:
    enabled: true
    weight: 0.3
    package: nexus.semantic
  procedural:
    enabled: false
    weight: 0.2
    package: nexus.procedural
  hermes-skills:
    enabled: false
    weight: 0.1
    package: nexus.external.hermes_skills

default_scope:
  - sisyphus
  - semantic
```

## 实施计划

### 第一步：项目改名 + 目录重组

| 步骤 | 做什么 | 风险 |
|------|--------|------|
| 1.1 | `sisyphus/` → `nexus/`，更新 `pyproject.toml` | 低 |
| 1.2 | 现有代码移到 `nexus/nexus/sisyphus/` | 中，import 路径全改 |
| 1.3 | 更新所有 import 路径 (`sisyphus.memory` → `nexus.sisyphus.memory`) | 高，机械但量大 |
| 1.4 | 更新所有测试 import | 中 |
| 1.5 | `git remote set-url` 更新仓库（如果要改名） | 低 |
| 1.6 | 408 测试全过 | — |

### 第二步：调度层实现

| 步骤 | 做什么 |
|------|--------|
| 2.1 | 实现 `core.py`：模块注册、路由、合并 |
| 2.2 | 实现 `protocol.py`：ModuleProtocol 基类 |
| 2.3 | 实现 `config.py`：加载 nexus.yaml |
| 2.4 | sisyphus 模块注册为第一个协议实现 |
| 2.5 | 测试：多模块检索 + 权重验证 |

### 第三步：Semantic 层

| 步骤 | 做什么 |
|------|--------|
| 3.1 | URL 索引 + FTS5 |
| 3.2 | 内容缓存 + 自动刷新 |
| 3.3 | 分批导入 50GB |
| 3.4 | 白名单 + 包源验证 |
| 3.5 | 注册为 Nexus 模块 |
| 3.6 | 测试：URL 搜索 + 缓存刷新 |

### 第四步：Procedural 层

| 步骤 | 做什么 |
|------|--------|
| 4.1 | 技能格式定义 |
| 4.2 | 条件匹配引擎 |
| 4.3 | Agent 画像 + 路由规则 |
| 4.4 | 注册为 Nexus 模块 |
| 4.5 | 借 Hermes 技能创建逻辑 |
| 4.6 | Agent 画像注册 (`agent_registry.yaml`) |
| 4.7 | 模型路由：本地模型 / API 自动匹配 |

### 模型路由

**原理**：跟 Agent 路由同一套引擎。条件→动作规则，匹配后自动选择最优模型。

```yaml
# 模型路由表
model_routing:
  rules:
    - pattern: "代码生成|补全|写函数"
      model: qwen3-coder-14b (本地 GPU,16GB)
    - pattern: "复杂推理|架构设计"
      model: qwen3-32b (本地 CPU,64GB)
    - pattern: "图片识别|OCR|截图"
      model: llama-vision (本地 GPU,7GB,临时切换)
    - pattern: "翻译|闲聊|简单问答"
      model: qwen-turbo (API, 省钱)
    - default: qwen3-14b (本地 GPU)
```

与 Agent 路由共用 Procedural 层匹配引擎，不单独建模块。

## 关于 RAG

**不需要传统 RAG**。原因：

| 我们已有的 | RAG 提供的 | 结论 |
|-----------|-----------|------|
| FTS5 关键词召回 | 同 | 覆盖 |
| URL 索引 + 缓存 | 文档检索 | 覆盖 |
| Decay + feedback + MMR 排序 | 同 | 覆盖 |
| LLM 查詢理解 + 答案生成 | 同 | 覆盖 |
| 向量嵌入 + 语义搜索 | 向量相似度 | **不需要，LLM 替代** |
| 无 | 多轮对话上下文管理 | 不需要，LLM 自己管 |

**核心理由**：CS 领域 80% 查询是精准关键词。剩下 20% 模糊查询用 LLM 直接理解+生成，不需要 embedding 中间层。LLM API 极便宜且效果更好，省去维护向量数据库和 GPU 推理成本。

## 记忆系统加强

| 方向 | 当前 | 加强后 |
|------|------|--------|
| Agent 调用记忆 | 被动，Agent 调 MCP | Nexus 主动推送：检测到相关话题自动注入上下文 |
| 去重 | 无 | title+content 语义去重，避免"同一次故障学了 3 次" |
| 过期清理 | 无 | 超过 6 个月无访问 + 低 importance → 自动压缩 |
| 调度自学习 | 无 | Dream 分析调度日志 → 优化路由规则 |
| 多 Agent 会话关联 | 无 | 同一任务链（你问 A→A 调 B→B 调 C）自动串联 |

## 第七步：Docker 部署

| 步骤 | 做什么 |
|------|--------|
| 7.1 | `Dockerfile`：Python 3.14 + SQLite + Nexus |
| 7.2 | `docker-compose.yml`：nexus-core + 可选 agent 容器 |
| 7.3 | Volumes：`~/.omo` 持久化所有记忆 |
| 7.4 | `nexus serve` 单命令启动 MCP + HTTP |
| 7.5 | GPU Agent 容器：nvidia-docker 挂载 5060Ti

### 第五步：独立部署 + 社区发布

| 步骤 | 做什么 |
|------|--------|
| 5.1 | `nexus serve` 命令 |
| 5.2 | MCP Server 独立进程 |
| 5.3 | 发布到 OpenCode 社区 |

## 迁移影响

| 改什么 | 影响范围 |
|--------|----------|
| import 路径 | 所有 `.py` 文件 |
| 测试 import | 所有 `test_*.py` |
| CLI 入口 | `cli.py` + `tree_cmd.py` |
| MCP 路径 | opencode.json 配置 |
| git remote | 如果仓库改名 |
| 文档 | README + 所有 docs |

## 风险控制

- 第一步是最大风险。拆成多个小 commit，每步可回滚
- 先改目录结构，不改代码逻辑
- 每个小步跑测试确认
- 不改功能只改路径，测试能过就说明迁移成功

## 第六步：Web Ingest — 免操作知识采集

**目标**：用户在任何网页 AI（豆包/通义/ChatGPT）聊天后，内容自动进入 Nexus，零操作。

**架构**：

```
豆包网页 ──→ 浏览器插件 ──→ localhost:8765/ingest ──→ Nexus 自动提取 → sisyphus
通义网页 ──→ 浏览器插件 ──→ localhost:8765/ingest ──→ Nexus 自动提取 → sisyphus
ChatGPT  ──→ 浏览器插件 ──→ localhost:8765/ingest ──→ Nexus 自动提取 → sisyphus
```

**实施**：

| 步骤 | 做什么 |
|------|--------|
| 6.1 | Nexus 加 `/ingest` HTTP POST 端点，接收纯文本 |
| 6.2 | 对接现有 Extractor：自动提取 lesson/decision/pattern |
| 6.3 | 浏览器插件：检测 `doubao.com` / `tongyi.aliyun.com` / `chat.openai.com` |
| 6.4 | 对话结束后自动抓取内容，POST 到 `localhost:8765/ingest` |
| 6.5 | 支持手动触发：点插件图标 → 立即抓取当前对话 |

**用户操作**：零。装一次插件，后面所有对话自动采集。

**存储策略**：Nexus 只存精华索引，不存全文：

```
豆包对话 "Python 3.14 改了什么"
  → 浏览器插件提取
    → Nexus 只存: "Python 3.14 Optional 废弃，用 | 替代 (来源: 豆包)"，   ← 一条索引
    → 对话原文留在豆包，不回传
    → 以后需要看全文 → 回豆包搜索，不占 Nexus token
```

- token 节省：一次对话 5000 token → 一条索引 30 token，压缩 99%+
- 原文归属：对话内容属于原平台，Nexus 不缓存全文
- 可追溯：每条索引标注 `source: doubao`，知道去哪找回原文

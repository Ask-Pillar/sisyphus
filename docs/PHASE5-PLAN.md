# Phase 5: 智能知识库 + 零信任执行层

## 目标

知识库从被动存储升级为自治系统：自动维护新鲜度、三层知识架构、零信任 Agent 操作。

## 5.1 URL 索引层

**原理**：知识库以 URL 为主键，不存储文档全文。CS 领域 90% 的查询 LLM 预训练已覆盖，URL 索引是兜底。

**执行**：

| 步骤 | 操作 |
|------|------|
| 5.1.1 | 创建 `~/.omo/knowledge/{domain}/urls.db`，SQLite 表含 `url, title, description, domain, last_fetched, content_hash` |
| 5.1.2 | 导入种子 URL：pandas 文档、react 文档、nginx 文档等，手动录入 `title + description` |
| 5.1.3 | FTS5 对 `title + description` 建索引，搜 `pandas read_csv` 返回 URL 列表 |

**验证**：导入 50 个种子 URL，搜 `pandas read_csv chunksize`，Top-1 返回 `pandas.pydata.org/docs/reference/api/pandas.read_csv.html`

## 5.2 内容缓存层

**原理**：URL 索引只存地址，需要时抓取页面内容并缓存。缓存有过期时间，过期自动重抓。

**执行**：

| 步骤 | 操作 |
|------|------|
| 5.2.1 | 扩展 urls.db 加 `content TEXT` 列，存页面正文（去 HTML 标签） |
| 5.2.2 | `fetcher.py`：`fetch(url)` → 检查缓存 → 过期则 HTTP GET → 提取正文 → 更新缓存 |
| 5.2.3 | FTS5 索引 `content` 列，作为全文检索兜底 |
| 5.2.4 | 过期策略：官方文档 30 天，个人博客 90 天，永不超期的手动标记 |

**验证**：手动标记一个 URL 过期，调用 `fetch(url)`，验证内容已更新，`last_fetched` 刷新。

## 5.3 代码感知索引

**原理**：CS 文档中英文术语 + 代码块混合。代码块不参与分词索引，走精准子串匹配。

**执行**：

| 步骤 | 操作 |
|------|------|
| 5.3.1 | 内容解析器：检测 ``` 标记，代码段分离到 `code` 列，正文进 `prose` 列 |
| 5.3.2 | 英文术语拆分：CamelCase → 'camel case'，snake_case → 'snake case'，`::` → 空格 |
| 5.3.3 | jieba 预处理中文，写入时完成分词（不是查询时） |
| 5.3.4 | 代码子串索引：对高频 API 名建立倒排（`pandas.read_csv` → 出现的所有文档 ID） |

**验证**：导入 Django 文档，搜 `class-based view dispatch`，返回 View 类的 dispatch 方法的文档页。

## 5.4 PersonaStore — 人物认知模型

**原理**：你想学习的人的决策模式和思维规则，作为独立的知识层。

**执行**：

| 步骤 | 操作 |
|------|------|
| 5.4.1 | 定义 Persona 数据结构：`{name, rule_type: decision|pattern|heuristic, condition, action, confidence}` |
| 5.4.2 | 存储：`~/.omo/personas/{name}.json`，每条规则一个 JSON 对象 |
| 5.4.3 | 检索：`search_persona(name, query)` → 匹配 condition → 返回 action |
| 5.4.4 | 来源：从邮件、演讲、commit log 中提取，人工标注 confidence |

**验证**：录入 Linus 的 10 条决策规则，搜 `subsystem conflict`，返回 `"Linus: 用 config 开关，不用 #ifdef" (confidence: 0.9)`

## 5.5 URL 白名单 + 包源配置

**原理**：Agent 不能访问任意 URL，只能在白名单内操作。包下载走用户配置的源列表。

**执行**：

| 步骤 | 操作 |
|------|------|
| 5.5.1 | 扩展 `config.yaml` 加 `sources.allowed_domains` 白名单 |
| 5.5.2 | 加 `sources.pypi_mirrors` 配置项，默认 `['pypi.org', 'pypi.tuna.tsinghua.edu.cn']` |
| 5.5.3 | `sandbox.py` 新增 `validate_url(url)`：不在白名单 → 拒绝 |
| 5.5.4 | `sandbox.py` 新增 `validate_package(name, version)`：查 PyPI 官方 JSON API 验证存在性 + 版本号 |

**验证**：
- 请求 `pandas-docs.io`（不在白名单）→ 被拦截
- 请求 `pandas.pydata.org`（在白名单）→ 通过
- `pip install fake-package-999` → 包名验证失败，拒绝

## 5.6 代码安全审计

**原理**：Agent 安装任何包前，必须审计 `setup.py`/`pyproject.toml` 中的危险调用。

**执行**：

| 步骤 | 操作 |
|------|------|
| 5.6.1 | `auditor.py`：解析 `setup.py` AST，检测 `subprocess`、`os.system`、`eval`、`exec`、`__import__` |
| 5.6.2 | 检测到危险调用 → 标记 `risk: high`，拒绝安装 |
| 5.6.3 | 检测到网络调用（`requests`、`urllib`）→ 标记 `risk: medium`，需用户确认 |
| 5.6.4 | 仅允许纯数据/纯工具库（无网络、无系统调用）自动安装 |

**验证**：给一个包含 `os.system('curl evil.com')` 的 `setup.py` → 审计标记 `risk: high` → 拒绝。

## 5.7 运行时沙箱

**原理**：所有 Agent 操作在 Docker 容器内执行，不触碰宿主机。

**执行**：

| 步骤 | 操作 |
|------|------|
| 5.7.1 | Dockerfile：Python 3.12 + pip + 只读挂载 `/usr`，可写挂载 `.omo/` |
| 5.7.2 | 网络隔离：容器只允许访问 PyPI 镜像源和白名单域名 |
| 5.7.3 | `sandbox.py` 封装 `docker run` 命令，所有 pip/apt 操作通过沙箱 |

**验证**：在沙箱内 `pip install` 正常完成。尝试 `curl evil.com` → 网络拒绝。

## 5.8 知识新鲜度自治

**原理**：不依赖人工检查过期。系统自动检测、抓取、标记差异。

**执行**：

| 步骤 | 操作 |
|------|------|
| 5.8.1 | 定时任务（每周）：遍历 urls.db，`last_fetched > 30天` 的 URL 自动重抓 |
| 5.8.2 | 内容对比：`content_hash` 变化 → 标记 `stale=True`，通知用户 |
| 5.8.3 | 差异高亮：用 difflib 对比旧/新内容，输出变更摘要 |

**验证**：修改一个已缓存页面的内容（模拟官方文档更新），运行刷新任务，验证 `stale=True` 标记已更新。

## 验证总览

| 任务 | 验证指标 |
|------|----------|
| URL 索引 | 50 种子 URL，关键词搜索 Top-1 准确 |
| 内容缓存 | 缓存命中 < 50ms，过期自动刷新 |
| 代码索引 | 代码搜索不返回散文，散文搜索不返回代码 |
| PersonaStore | 10 条规则，条件匹配准确 |
| URL 白名单 | 非白名单域名 100% 拦截 |
| 包源验证 | 不存在包名 100% 拦截 |
| 安全审计 | 危险调用 100% 检测 |
| 沙箱隔离 | 宿主机文件系统不可写 |
| 新鲜度自治 | 过期 URL 24h 内自动检测 |

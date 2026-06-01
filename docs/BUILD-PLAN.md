# Nexus 搭建总览 — 复用清单 & 时间估算

## 已有组件（零开发）

| 组件 | 来源 | 状态 |
|------|------|------|
| SQLiteMemoryStore | sisyphus | ✅ 408 测试 |
| UnifiedRetriever | sisyphus | ✅ 跨池检索 |
| 触发系统 | sisyphus | ✅ L0/L1/L2 |
| 反馈闭环 | sisyphus | ✅ rate/dismiss |
| MCP Server | sisyphus | ✅ 14 工具 |
| Decay + MMR 排序 | sisyphus | ✅ |
| Forgotten Gems | sisyphus | ✅ |
| 对立观点 | sisyphus | ✅ |
| DiversityReranker | sisyphus | ✅ |
| KnowledgeBase | sisyphus | ✅ FTS5 分块 |
| Session Log | sisyphus | ✅ |
| Obsidian 编辑 | Obsidian 官方 | ✅ 不需要我们管 |
| OCR | tesseract | ✅ pip install |
| PDF 解析 | pymupdf | ✅ pip install |
| 容器部署 | Docker + Docker Compose | ✅ |

## 需要新写的代码

| 文件 | 行数 | 做什么 | 时间 |
|------|------|--------|------|
| `nexus/core.py` | ~80 行 | 调度层：路由 + 合并 + 配置加载 | 30 分钟 |
| `nexus/protocol.py` | ~20 行 | `ModuleProtocol` 基类 | 10 分钟 |
| `server/mcp.py` | 复制 + 加 2 工具 | MCP Server（基于 sisyphus 的复制） | 30 分钟 |
| `web/ingest.py` | ~50 行 | Web Ingest HTTP 端点 | 15 分钟 |
| `config/nexus.yaml` | ~30 行 | 配置文件 | 5 分钟 |
| `pyproject.toml` | ~20 行 | 项目依赖 | 5 分钟 |
| `README.md` | ~50 行 | 文档 | 15 分钟 |
| `knowledge/obsidian.py` | ~30 行 | 扫描 Obsidian vault → FTS5 | 20 分钟 |
| `knowledge/importer.py` | ~100 行 | 分批导入 + 中断续传 | 1 小时 |
| `tests/test_core.py` | ~50 行 | 核心测试 | 30 分钟 |
| **总计** | **~430 行** | | **~4 小时** |

## 不需要新写的

| 功能 | 为什么 |
|------|--------|
| 存储引擎 | sisyphus SQLiteMemoryStore 完全够用 |
| 检索排序 | sisyphus UnifiedRetriever 覆盖 |
| 触发系统 | sisyphus trigger.py 覆盖 |
| 反馈系统 | sisyphus store.rate/dismiss 覆盖 |
| Dashboard | sisyphus dashboard.py 已有 |
| 测试框架 | sisyphus pytest 覆盖，加 5 个新测试 |

## 需要照抄的外部方案

| 来源 | 抄什么 | 原因 |
|------|--------|------|
| Hermes | skill 文件格式 | 成熟、社区认可 |
| Hermes | 文件锁 + 注入扫描 | 生产加固直接复用 |
| OpenClaw | 消息路由逻辑 | 以后用于多平台 |
| Claude Code | `.remember/now.md` 模式 | 工作记忆参考 |

照抄不是抄代码——是抄设计模式。用 Python 重新实现。

## 总时间线

| 步骤 | 时间 | 产出 |
|------|------|------|
| 项目骨架 | 30 分钟 | git init + submodule + pyproject.toml |
| nexus/core.py | 30 分钟 | 调度层跑通 |
| MCP Server | 30 分钟 | Agent 可调 |
| Web Ingest | 15 分钟 | 浏览器插件对接 |
| Obsidian 接入 | 20 分钟 | 知识层打通 |
| 分批导入器 | 1 小时 | 50GB 可导入 |
| 配置 + 文档 | 20 分钟 | 可用 |
| 测试 | 30 分钟 | 验证 |
| **总计** | **~4 小时** | **最小可用 Nexus** |

## 启动命令

```bash
# 创建项目
mkdir nexus && cd nexus
git init
git submodule add https://github.com/Ask-Pillar/sisyphus.git
pip install sisyphus/ pymupdf tesseract aiohttp pyyaml

# 写代码（~4 小时，按上表）

# 启动
python3 -m nexus.server.mcp           # MCP Server
python3 web/ingest.py                 # Web Ingest (8765 端口)

# 测试
python3 -m pytest sisyphus/tests/     # 408 不发生倒退
python3 -m pytest tests/              # 5 个新测试
```

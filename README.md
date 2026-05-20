# Sisyphus — Self-Evolving AI Agent with Persistent Memory

A layered memory system for LLM agents with Obsidian-compatible file storage, LLM-powered reflection, loop detection, and rebuildable SQLite caching.

```
.omo/memory/
├── INDEX.md            ← MOC 全局索引入口
├── <type>/<id>.md      ← RAW 层（append-only）
├── refined/
│   ├── reflection/     ← LLM 反射洞察
│   ├── summary/        ← 退火压缩摘要
│   └── loop/           ← 回路阻断记录
├── agents/
│   └── <name>/         ← 子 agent 独立沙箱
└── logs/               ← 结构化操作日志
```

## 架构

### 四层存储

| 层级 | 目录 | 特点 |
|------|------|------|
| **RAW** | `memory/<type>/` | 原始记忆，append-only，永不删除 |
| **REFINED** | `memory/refined/` | LLM 加工产物，可重新生成 |
| **MOC** | `memory/INDEX.md` | 多维主题地图，Obsidian 兼容 |
| **AGENT** | `memory/agents/<name>/` | 子 agent 独立记忆沙箱 |

核心原则：

- **文件即 SSOT** — 所有记忆是 Markdown 文件，数据库（SQLite）只是可重建的缓存
- **痕迹只增不删** — RAW 层永远不覆盖或删除原始记忆
- **LLM 可缺失** — 所有涉及 LLM 的操作在无 API key 时自动跳过，不崩溃
- **管道驱动** — 所有加工通过 Pipeline 自动触发，CLI 统一入口

## 快速开始

```bash
pip install sisyphus

# 记录一条记忆
sisyphus-memory record lesson "Python type hints" --content "Use Optional[X] for 3.9" --tags python,typing

# 查看
sisyphus-memory recent
sisyphus-memory show <id>
sisyphus-memory stats

# 加工
sisyphus-memory dream              # LLM 反射
sisyphus-memory link                # 清理断链
sisyphus-memory detect-loop         # 检测重复模式
sisyphus-memory index               # 重建 MOC 索引

# 子 agent 沙箱
sisyphus-memory agent create worker-1
sisyphus-memory agent list
sisyphus-memory agent show worker-1

# 加速缓存（文件是 SSOT，可随时重建）
sisyphus-memory cache rebuild
sisyphus-memory cache status
sisyphus-memory cache search "type hints"
```

## 命令行参考

| 命令 | 说明 |
|------|------|
| `record <type> <title>` | 记录新记忆 |
| `search <query>` | 搜索记忆 |
| `recent` | 最近记忆 |
| `show <id>` | 显示单条详情 |
| `stats` | 统计概览 |
| `snapshot` | 生成冻结快照 |
| `dream` | LLM 反射引擎 |
| `link` | 清理断链/去重/自引用 |
| `detect-loop` | 检测重复模式（≥3 次同标题标记为回路） |
| `index` | 重建 MOC 索引 |
| `log` | 操作日志 |
| `refined` | 列出加工记忆 |
| `agent list/create/show` | 子 agent 沙箱管理 |
| `cache rebuild/status/search` | SQLite 缓存管理 |

## Pipeline 自动流水线

每次触发按顺序运行：

1. **回路检测** — 扫描 RAW 层，同标题 ≥3 次自动标记
2. **压缩** — RAW 数量超阈值时退火合并
3. **反射** — 未加工的记忆 ≥3 条时自动触发 DreamEngine
4. **MOC 索引** — 每次增量更新
5. **断链清理** — 移除无效/重复/自引用链接

可在无 LLM API key 环境下安全运行（跳过 LLM 步骤）。

## 开发

```bash
git clone https://github.com/Ask-Pillar/sisyphus.git
cd sisyphus

pip install -e ".[dev]"
pytest tests/ -v
```

- Python 3.9+
- 文件系统驱动，零外部依赖（LLM 调用仅通过 `LLMClient`，无 key 静默跳过）
- TDD：先写测试再实现

## 测试

```
============================= 146 passed in 10s ==============================
```

- `tests/test_store.py` — 文件 CRUD + 持久化
- `tests/test_store_v2.py` — frontmatter 格式 + 向后兼容
- `tests/test_refined.py` — 三层加工存储
- `tests/test_log.py` — 结构化日志
- `tests/test_moc.py` — MOC 索引生成
- `tests/test_pipeline.py` — 自动触发流水线
- `tests/test_dream.py` — 反射引擎
- `tests/test_link.py` — 断链清理
- `tests/test_loop.py` — 回路检测
- `tests/test_agent.py` — 子 agent 沙箱隔离
- `tests/test_cache.py` — SQLite 缓存重建与搜索
- `tests/test_extraction.py` — 记忆提取
- `tests/test_compression.py` — 退火压缩
- `tests/test_recall.py` / `test_search.py` / `test_snapshot.py` — 检索与快照

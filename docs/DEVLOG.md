# 开发日志 — Sisyphus Memory

## v1.1 — 反射系统（进行中）

### 2026-05-20

| 步 | 内容 | 状态 |
|----|------|------|
| step1 | DreamEngine 反射引擎 + refined_by 字段 | ✅ |
| step2 | CLI dream 命令 + Pipeline 自动触发 | ✅ |
| step3 | 关联分析（link 命令） | 🔴 待实现 |

**当前测试**: 115 全绿
**备注**: 无 LLM 环境时 compress/dream 自动跳过不崩

---

## v1.0 — Memory 2.0 分层架构 ✅

### 2026-05-20

| 步 | 内容 | 新增测试 | 关键文件 |
|----|------|----------|----------|
| ADR | 四层架构设计文档 | — | `docs/ADR-003-memory-2.0.md` |
| step1 | Store 升级 frontmatter 格式 + Memory 25 字段 | 7 | `store.py` |
| step2 | Refined 存储层（reflection/summary/loop_record） | 13 | `refined.py` |
| step3 | 结构化日志系统（LogStore） | 10 | `log.py` |
| step4 | MOC 生成器（wikilink 分组索引） | 8 | `moc.py` |
| step5 | CLI 新命令（index/log/refined） | 5 | `cli.py` |
| step6 | 自动触发流水线（Pipeline 框架） | 9 | `pipeline.py` |

**改动要点**:
- RAW 层 append-only，永不删原始记忆
- 所有加工走 CLI，CLI 统一产日志
- 文件是 SSOT，数据库只是可重建缓存
- YAML frontmatter 兼容 Obsidian
- 旧格式文件自动降级兼容

---

## v0.x — 基础功能

| 版本 | 日期 | 内容 | 测试数 |
|------|------|------|--------|
| v0.1 | — | 项目骨架 + 文件式 CRUD 存储 | 14 |
| v0.2 | — | LLM 语义召回 | 7 |
| v0.3 | — | 对话自动提取记忆 | 9 |
| v0.4 | — | CLI + 冻结快照 | 8 |
| v0.5 | — | 退火压缩 (annealing) | 5 |
| v0.6 | — | n-gram 向量语义搜索 | 7 |

---

## 架构约定

- Python 3.9, `Optional[X]` / `List` 语法
- TDD: 先写 RED 测试 → 实现 → GREEN
- 每步一个可验证功能，小步迭代
- 全中文注释 + 提交信息

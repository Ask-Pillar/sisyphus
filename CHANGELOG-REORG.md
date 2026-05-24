# 项目结构整理记录

> 日期: 2026-05-24  
> 状态: 完成 · 292 tests passing  
> 原则: 核心代码不动，只动文档/辅助代码/测试代码

---

## 变更摘要

| 类别 | 变更 | 文件数 |
|------|------|--------|
| 新增 `scripts/` | 从根目录搬入基准测试和分析脚本 | 9 |
| 新增 `reports/` | 从根目录搬入 HTML/MD 测试报告 | 14 |
| 修复测试 | 半衰期 30→180 天导致测试失败 | 1 fix |
| 新增文档 | 文件树说明 + 改动记录 | 2 |

---

## 详细变更

### 1. 创建 `scripts/` 目录

**原因**: 根目录有 9 个 `.py` 分析/基准脚本，与源码、文档混在一起。

**搬入文件**:
- `ab_test.py` → `scripts/ab_test.py`
- `ab_test_v2.py` → `scripts/ab_test_v2.py`
- `abc_clean.py` → `scripts/abc_clean.py`
- `abc_flashrank.py` → `scripts/abc_flashrank.py`
- `abc_local.py` → `scripts/abc_local.py`
- `abc_recall.py` → `scripts/abc_recall.py`
- `abc_sisyphus.py` → `scripts/abc_sisyphus.py`
- `bm25_analysis.py` → `scripts/bm25_analysis.py`
- `scale_test.py` → `scripts/scale_test.py`

**代码改动**: 零。所有脚本使用 `PYTHONPATH=src` 导入 sisyphus，路径不变。

**Git**: `9797d9c`

### 2. 创建 `reports/` 目录

**原因**: 根目录有 14 个 HTML/MD 报告文件，与源码混在一起。

**搬入文件**:
- `abc-test-report.html`
- `full-test-report.html`
- `hippocampus-arch.html`
- `p0-verification-report.{html,md}`
- `p1-verification-report.html`
- `p2-verification-report.html`
- `p3-verification-report.html`
- `p3_upgrade_report.html`
- `plan-compare.html`
- `plan-merged*.html`
- `recall_benchmark_report.html`
- `test-report.html`

**Git**: `482060b`

### 3. 修复测试

**原因**: 半衰期从 30 天改为 180 天（`retrieval.py:29 DECAY_HALF_LIFE_DAYS = 180`），但 `test_half_life_reduces_score` 仍用 30 天间隔计算期望值，导致 `assert abs(score - 4.0) < 0.01` 失败（实际值 ~7.13）。

**修复**: 将测试日期调整为 180 天间隔。292/292 全部通过。

**Git**: `54b8955`

### 4. 新增 FILE-TREE.md

`docs/FILE-TREE.md` — 完整文件树，包含每个文件的作用说明和论文文档不提交的提示。

### 5. 论文文档处理

以下文件在 `docs/` 中，**不加入版本控制**：

- `sisyphus-paper-v4.md` — 英文 IMRaD 最终版
- `sisyphus-paper-zh-v4.md` — 中文最终版
- `sisyphus-paper-v3.md` — 时间修正版
- `sisyphus-paper-zh-v2.md` — 微信生成原始版
- `sisyphus-paper-draft.md` — 早期草稿

---

## 整理后的根目录

```
sisyphus/
├── AGENTS.md
├── README.md
├── pyproject.toml
├── .gitignore
├── src/          # 核心代码（未改动）
├── tests/        # 测试代码
├── scripts/      # 基准测试/分析脚本（新增）
├── reports/      # 测试报告（新增）
└── docs/         # 设计文档
```

## 未改动的部分

- `src/sisyphus/` 全部文件：不动
- `tests/` 测试文件：只修复了一行日期，其余不动

## 后续计划

- `src/sisyphus/memory/retrieval.py` (884 行) 建议拆分为子模块（`retrieval/bm25.py`, `retrieval/reranker.py` 等）
- `src/sisyphus/memory/source/` 新建 ContextAssembler 模块（`persist.py`, `hot.py`, `cold.py`）
- 论文 v4 最终版可以考虑转换为 LaTeX 格式投稿

# P0 基础设施验收报告

## 测试结果

```
pytest tests/ -q
199 passed, 9 failed (all pre-existing)
```

### 新增测试：12/12 通过

新建 `tests/test_atomic_write.py`：

| 测试 | 结果 |
|---|---|
| `TestAtomicWrite::test_writes_content` | ✅ |
| `TestAtomicWrite::test_overwrites_existing` | ✅ |
| `TestAtomicWrite::test_original_intact_after_crash` | ✅ |
| `TestAtomicWrite::test_no_tmp_left_behind` | ✅ |
| `TestAtomicWrite::test_unicode_content` | ✅ |
| `TestAtomicWrite::test_empty_content` | ✅ |
| `TestDirLock::test_acquire_release` | ✅ |
| `TestDirLock::test_context_manager` | ✅ |
| `TestDirLock::test_mutual_exclusion` | ✅ |
| `TestDirLock::test_stale_pid_cleaned` | ✅ |
| `TestDirLock::test_double_acquire_noop` | ✅ |
| `TestDirLock::test_concurrent_write_via_lock` | ✅ |

## ABC 命中率验证

```
BM25 @1 = 56%  (baseline: 56%, 无退化)
BM25 @3 = 80%
BM25 @5 = 90%
```

## 改动清单

| 文件 | 改动类型 | 说明 |
|---|---|---|
| `src/sisyphus/memory/utils.py` | 新建 | `atomic_write()` + `DirLock` 类 |
| `src/sisyphus/memory/store.py` | 修改 | 3 处 `write_text` → `atomic_write()` |
| `src/sisyphus/memory/moc.py` | 修改 | 2 处 `write_text` → `atomic_write()` |
| `src/sisyphus/memory/cache.py` | 修改 | 添加 `PRAGMA journal_mode=WAL` + `wal_autocheckpoint=1000` |
| `src/sisyphus/server/mcp.py` | 修改 | 模块级单例 + `ContextRetriever.retrieve()` + 4 新工具（共 8 工具） |
| `pyproject.toml` | 修改 | `dependencies` 添加 `pyyaml>=6.0` |
| `tests/test_atomic_write.py` | 新建 | 12 个测试用例 |

## Gate 判定

- ✅ 测试门槛：199 ≥ 195
- ✅ 无新增失败：0 new failures
- ✅ 命中率：56%，与基线一致，在 58-62% ±2% 范围内
- **P0 通过，可进入 P1**

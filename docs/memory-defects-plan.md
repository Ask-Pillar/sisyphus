# 记忆系统缺陷改进计划

> 日期: 2026-05-24
> 来源: WeChat agent 对记忆系统四层架构的全面审查
> 缺陷总数: 6 | P0: 2 | P1: 2 | P2: 2

---

## 优先级总览

| 优先级 | 缺陷 | 影响 | 工作量 |
|--------|------|------|--------|
| **P0** | REFINED 层为空 | Dream/Compress 没实际产出 | 中 |
| **P0** | store.py / moc.py 写冲突 | MOC 结构永远不生效 | 小 |
| **P1** | Pipeline 无自动触发 | 每次手动调，不可持续 | 中 |
| **P1** | 会话不自动提取 | 对话结果流失，自进化断链 | 大 |
| **P2** | 测试数据污染 | 检索精度下降 | 小 |
| **P2** | 半衰期过短 | 记忆过早衰减 | 已修复 |

---

## P0-1: REFINED 层为空

**当前状态**

```
RAW:     90 条 (69 条 Test 垃圾)
REFINED: 1 条 (loop_record)
MOC:     0 (被覆盖)
```

Dream Engine 和 Compressor 代码存在但从未在实际场景中运行出结果。

**目标状态**

- Dream Engine 在 RAW ≥ 阈值时自动运行，产出反思记忆
- Compressor 对同 topic 多条记忆自动压缩
- REFINED 层有持续增长的 output

**方案**

1. 写一个集成测试：构造 5 条同 topic 记忆 → 触发 Dream → 验证 REFINED 产出
2. 检查 Dream/Compress handler 的 LLM 调用链路是否完整
3. 确保 Pipeline.run() 中的 Dream/Compress 步骤实际执行（不是 skip）

**验证标准**: 构造场景跑 Pipeline → REFINED 层新增 ≥1 条记录

---

## P0-2: MemoryStore 和 MOC 写同一文件冲突

**当前状态**

```
store.py:  _rebuild_index() → 写 INDEX.md（扁平格式）
moc.py:    generate()      → 写 INDEX.md（wikilink 分组格式）
```

后来者覆盖前者。`moc.py` 的输出永远不生效。

**目标状态**

- INDEX.md 和 MOC 写入不同文件，互不覆盖
- agent 同时能访问两种索引

**方案**

1. `moc.py` 输出到 `MOC.md`（而非 `INDEX.md`）
2. `store.py` 只维护 `INDEX.md`（扁平索引）
3. `ContextRetriever` 或 `recall` 同时查询两个索引

**验证标准**: 运行 store 写入 + moc 生成 → 两个文件都存在，内容各自独立

---

## P1-1: Pipeline 无自动触发

**当前状态**

Dream / Compress / TreeBuild 全部需要手动调用 `run_pipeline`，没有自动触发机制。

**目标状态**

- 每次 agent turn 结束后自动检查条件
- 满足条件时自动触发 Dream（后台执行，不阻塞）
- 用户无感知，agent 自行决定何时反思

**方案**

### 1. after_turn() 钩子

```python
# 伪代码 - 每次 agent 回复完自动执行
def after_turn():
    new_count = count_new_since_last_dream()
    if new_count >= THRESHOLD and not in_cooldown():
        trigger_dream_async()   # fork 出后台子 agent
```

### 2. 异步子 agent 触发

不走同步（会卡住主 agent 回复微信），而是 `task(run_in_background=true)` ：

```
主 agent after_turn()
  ├─ should_trigger() → 5 条新 RAW？冷却期过了？
  ├─ 是 → task(category="deep", run_in_background=true, prompt="跑 Dream")
  │         ↑ fork 出独立子 agent
  └─ 立即 return，主 agent 继续工作

后台子 agent
  ├─ 读取最新未加工的 RAW
  ├─ 调 LLM 生成反思 → 写入 REFINED
  └─ 下次 turn Sisyphus 自动检索到新 REFINED
```

### 3. LLM 后端灵活切换

Dream 本身只是"收集记忆 → 调 LLM → 写结果"的编排层，不绑定具体后端。`LLMClient` 接口不变：

| 后端 | 配置 | 成本 |
|------|------|------|
| opencode subagent（默认） | `task(category="deep")` | 零额外（走 opencode 自带模型） |
| Claude Code | `task(subagent_type="oracle")` | 高 |
| DeepSeek Flash | `SISYPHUS_LLM_BASE_URL=...` | 几分/次 |
| Ollama 本地 | `SISYPHUS_LLM_BASE_URL=http://localhost:11434/v1` | 免费 |
| one-api 代理 | `SISYPHUS_LLM_BASE_URL=http://127.0.0.1:3000/v1` | 已有 |
| github models | `base_url=https://models.inference.ai.azure.com` | 免费额度 |

优先级：opencode subagent 优先（零成本、同环境），API 作为 fallback。

### 4. Dream 只处理未加工记忆

当前 `_gather_memories()` 简单调 `self.store.list()`，全量 90 条（含 69 条 Test）都塞进 prompt。

改为：只取**上次 Dream 之后新增、未被 refined_by 过的有效记忆**——过滤掉旧数据、测试数据和已加工过的。

```python
def _gather_memories(self) -> List[Memory]:
    all_mems = self.store.list()
    return [
        m for m in all_mems
        if m.created_at > self._last_dream_time     # 新增的
        and not m.refined_by                         # 没被加工过
        and "test" not in m.tags                     # 不是测试数据
    ]
```

**验证标准**: 连续写入 5 条新记忆 → 下次 turn 自动触发 Dream → 后台子 agent 完成 → REFINED 层新增 ≥1 条

---

## P1-2: 会话不自动提取到记忆

**当前状态**

对话结束后，关键决策、教训、模式完全依赖手动 `record`。Agent session 关闭后上下文丢失，无法从对话中提取结构化记忆。

**目标状态**

- 每个 agent turn 结束后自动运行 Extractor
- Extractor 分析对话内容，提取决策/模式/教训
- 自动写入 RAW 层（标记 `source: auto-extract`）

**方案**

1. 实现 `after_turn()` 钩子
2. `Extractor` 接收当前 turn 的 prompt + response
3. 用 LLM 判断是否包含可提取的记忆（decision/pattern/lesson）
4. 有则自动调用 `write_memory`
5. 使用轻量模型（避免每次 turn 都消耗大量 token）

**验证标准**: 对话中做出一个明确决策 → 下一次 turn 前 RAW 层出现对应记忆

---

## P2-1: 测试数据污染

**当前状态**

90 条 RAW 中 69 条标题为 "Test"，检索时被召回，降低精度。

**目标状态**

- 测试数据与生产数据隔离
- 检索时自动过滤测试记忆

**方案**

1. 给 `delete_memory` 加批量能力（按 tag 过滤删除）
2. 或者给测试记忆打 `test` tag → 检索时默认排除
3. 添加 `memory.py clean --tag test` CLI

**验证标准**: 清理后 RAW 数量 ≈21（91-69-1），搜索不含 Test 结果

---

## P2-2: 半衰期过短

**当前状态**

默认 30 天。用户决策改为 180 天。

**状态**: ✅ 已修复（`decay_score` 改为 180 天）

---

## 实施建议顺序

```
P0-2 (写冲突) → P0-1 (REFINED) → P2-1 (清理测试数据)
    ↓
P1-1 (自动触发) → P1-2 (自动提取)
```

P0-2 改动最小、影响最大（解耦两个 writer 后整个索引层才能正常工作）。P1-2 工作量大，放在最后。

---

## 相关记忆

- `mem_231c391bb72b` — 四层架构现状评估
- `mem_df53218df5f2` — REFINED 层为空
- `mem_a7469e311c54` — store/moc 写冲突
- `mem_6e0bb92e04b0` — 改进方案讨论结论

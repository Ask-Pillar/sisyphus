# Sisyphus 开发计划（最终版）

> 日期: 2026-05-24  
> 基于: 上下文组装视角 + 全局 AGENTS.md + 初始感知  
> 缺陷: **9 项** | P0: 2 | P1: 5 | P2: 2

---

## 一、架构结论汇总

| 决策 | 结论 | 文档 |
|------|------|------|
| 记忆 = 上下文组装 | 所有记忆系统本质相同，差异在组装规则 | `context-is-everything.*` |
| PERSIST 内嵌 vs MCP | `before_turn` 内嵌，8 个主动工具保留 MCP | `embedded-vs-mcp.*` |
| 全局指令 | `workspace/AGENTS.md` = Sisyphus 版 `CLAUDE.md` | `global-agents-md.*` |
| Source 分层 | ContextAssembler 调度 5 个 Source，场景化配额 | `architecture-redesign.*` |
| 代码索引 | CodeGraphContext，独立 MCP Server 并列 | `summary-report.*` |
| 可视化 | Cytoscape.js + Chart.js 静态 HTML | `market-comparison-v2.*` |

---

## 二、缺陷总览

### P0 — 阻塞核心功能

| # | 缺陷 | 方案 | 工作量 |
|---|------|------|--------|
| P0-1 | REFINED 为空 (90→1) | Dream 只取 HOT 未加工记忆，加集成测试 | 中 |
| P0-2 | store/moc 写冲突 | moc.py 输出到 MOC.md，INDEX.md 独立维护 | 小 |

### P1 — 自进化断链

| # | 缺陷 | 方案 | 工作量 |
|---|------|------|--------|
| P1-1 | Pipeline 手动触发 | after_turn + task(background) + 冷却期 | 中 |
| P1-2 | 会话不自动提取 | Extractor + LLM 判断 → 自动 write_memory | 大 |
| P1-3 | MCP 工具无注入 | Layer 2: 工具列表注入 skill 或动态生成 | 小 |
| P1-4 | 检索无冷热 | HOT.md 7天索引，先搜 hot → fallback | 中 |
| P1-5 | 无 PERSIST 层 | pinned + importance≥8 → PERSIST.md 无条件注入 | 中 |
| P1-8 | **无初始感知（新）** | before_turn 加项目嗅觉：git log + 目录树 + 上次会话摘要 | 小 |

### P2 — 质量

| # | 缺陷 | 方案 | 状态 |
|---|------|------|------|
| P2-1 | 测试数据污染 (69/90) | 检索排除 test tag | 待处理 |
| P2-2 | 半衰期 30→180 天 | ✅ 已修复 | ✅ |
| P2-3 | 无可视化 | Cytoscape.js + Chart.js 静态 HTML dashboard | 规划中 |
| P2-4 | 无去重清扫 | hash 比对 + 相似→标记 refined_by + hourly sweep | 规划中 |

---

## 三、P1-8: 初始感知（新增）

### 现状

`before_turn` 不感知"我在哪个项目"，只看全局记忆。

### 方案

```
before_turn(query, cwd):
    project = detect_project(cwd)   // AGENTS.md 存在？属于已知项目？
    
    // L0-PERSIST: 全局 + 项目
    ctx += PERSIST.load(scope="global")
    ctx += PERSIST.load(project=project)
    
    // L0-嗅觉: 项目启动时一次性感知（新）
    if first_turn_in_session:
        ctx += recent_commits(cwd)         // git log -10
        ctx += project_structure(cwd)      // tree -L 2
        ctx += last_session_summary(cwd)   // 上次会话摘要
    
    // L1-HOT: 按 query + project 过滤
    ctx += HOT.search(query, project=project)
    
    // L2-CODE: coding 场景激活
    // L3-COLD: 兜底
```

### 工作量

| 组件 | 实现 | 时间 |
|------|------|------|
| `detect_project(cwd)` | 找最近的 AGENTS.md / `.git` | 10 行 |
| `recent_commits(cwd)` | `subprocess.run(["git", "log", "-10", "--oneline"])` | 5 行 |
| `project_structure(cwd)` | 扫描目录生成摘要 | 已可用 |
| `last_session_summary(cwd)` | 从 session 日志取最后摘要 | 需加存储 |

---

## 四、实施路线

```
P0-2 (写冲突) ──→ P0-1 (REFINED) ──→ P2-1 (清理 Test)
    │
    ├─ P1-5 (PERSIST)
    │     └─ P1-8 (初始感知)  ← 新
    │
    ├─ P1-4 (HOT)
    │     └─ P1-3 (MCP 注入)
    │           └─ P1-1 (自动触发)
    │                 └─ P1-2 (自动提取)
    │
    └─ P1-6 (CodeGraph) ──→ P1-7 (去重) ──→ P2-3 (可视化)
```

---

## 五、阶段划分

| 阶段 | 内容 | 里程碑 |
|------|------|--------|
| **Phase 1: 修基底** | P0-2 + P0-1 + P2-1 | REFINED 能产出，MOC 可工作，Test 清理 |
| **Phase 2: 分层** | P1-5 + P1-8 + P1-4 | PERSIST 注入 + 初始感知 + HOT 7天索引 |
| **Phase 3: 自进化** | P1-3 + P1-1 + P1-2 | MCP 注入 + 自动触发 + 自动提取 |
| **Phase 4: 扩展** | P1-6 + P1-7 + P2-3 | CodeGraph + 去重 + 可视化 |

---

## 六、Memory 字段（最终版）

```python
@dataclass
class Memory:
    # 现有
    id, type, title, content, tags, created_at, importance
    
    # P1-5: 耐久度
    pinned: bool = False       # PERSIST 层标记
    scope: str = "global"      # global | project | session
    project: str = ""          # 所属项目名
    
    # P1-8: 会话关联
    session_id: str = ""       # 产生此记忆的 session
    cwd: str = ""              # 产生时的目录
    
    # P1-6: 代码关联
    code_refs: list[str] = []  # ["retrieval.py:87", "store.py:104"]
```

---

## 七、文档索引

| 文档 | 内容 |
|------|------|
| `memory-defects-plan.*` | 原始 6 缺陷 + 方案 |
| `context-is-everything.*` | 一切记忆 = 上下文组装 |
| `architecture-redesign.*` | ContextRetriever → ContextAssembler |
| `embedded-vs-mcp.*` | before_turn 内嵌 vs MCP |
| `agents-md-integration.*` | 项目级 AGENTS.md 方案 |
| `global-agents-md.*` | 全局 AGENTS.md 方案 |
| `market-comparison-v2.*` | 8 系统对比 + 可视化规划 |
| **本文档** | 最终开发计划 |

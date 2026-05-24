# 记忆系统全市场对比（扩展版）：Hermes · OpenHuman · agentmemory · Claude Code

> 日期: 2026-05-24  
> 新增: Hermes Agent · OpenHuman · agentmemory · Claude Code memory · 可视化模块规划

---

## 一、扩展对比矩阵

| 维度 | **Mem0** | **Letta** | **Cognee** | **Hermes** | **OpenHuman** | **agentmemory** | **Claude Code** | **Sisyphus** |
|------|----------|-----------|------------|------------|---------------|-----------------|-----------------|--------------|
| Stars | 41K | 13K | 17K | — | — | — | 闭源 | — |
| 定位 | AI memory layer | Agent framework | Knowledge engine | Self-improving agent | AI desktop companion | Coding agent memory | AI coding agent | Dev memory system |
| 核心存储 | 向量+可选图 | MemFS(git) | 图向量混合 | 文件MD | SQLite+MD树 | 向量+图+BM25 | 文件MD | 文件MD |
| 记忆分层 | 3-tier存储 | 2-tier(内/外) | session+perm | **3层(耐久/技能/搜索)** | **3树(源/主题/全局)** | 流+语义+图 | index+topic | **4层(PERSIST/HOT/CODE/COLD)** |
| 始终加载 | ❌ | ✅ system/ | ❌ | ✅ MEMORY.md+USER.md | ❌ | ❌ | ✅ MEMORY.md | ✅ PERSIST层 |
| 容量上限 | 无 | 有(char) | 无 | **硬上限2200/1375字符** | 3K-token chunk | 无 | **硬上限200行/25KB** | 无 |
| 记忆类型 | 自由fact | 自由 | 自由 | 2文件 | 自由chunk | 自由 | **4型分类** | **7型+自定义** |
| 自我编辑 | ✅ LLM提取 | ✅ 工具调用 | ✅ cognify | ✅ memory工具 | ❌ 只读 | ✅ hooks | ✅ 后台agent | 📋 P1-2规划 |
| 后台反思 | ❌ | ✅ sleep-time | ✅ memify | ✅ nudge | ❌ | ✅ hourly sweep | ✅ auto-dream | 📋 P1-1规划 |
| 跨session | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| 去重 | ✅ hash+LLM | ❌ | ❌ | ❌ | ✅ 定id | ✅ merge | ✅ 后台合并 | 📋 需补 |
| 注入安全 | ❌ | ❌ | ❌ | **✅ 双扫描** | ❌ | ❌ | ❌ | ❌ |
| 代码索引 | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ 只有文件级 | ✅ CodeGraph |
| MCP | ✅ 内置 | ❌ | ✅ 内置 | ✅ 内置 | ❌ | ✅ 内置 | ❌ | ✅ 自建 |
| 可视化 | ❌ | ❌ | ❌ | ❌ | ❌ | **✅ 3113端口dashboard** | ❌ | 📋 规划中 |
| 部署 | 中 | 高 | 中 | 低 | 中 | 低 | 中 | **极低(零依赖)** |
| 中文 | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | **✅ jieba+CJK** |

---

## 二、深挖：各家值得借鉴的设计

### Hermes — 最接近 Sisyphus 理念的产品

```
3层记忆:
  L1 Durable:  MEMORY.md + USER.md → frozen-snapshot, 始终在 prompt
  L2 Skills:   过程性记忆 → 按需加载, agent 自己创建
  L3 Search:   FTS5全文搜索 + LLM摘要 → 跨 session 回溯
```

**直接可借鉴**：
1. **Frozen-snapshot + prefix cache** — 记忆在 session 开始时捕获，中途不变，保留 LLM 的 prefix cache。Sisyphus 的 PERSIST 层可以做同样的事。
2. **硬上限** — MEMORY.md 2,200 字符 / USER.md 1,375 字符。防止记忆膨胀吃掉 context。
3. **At-most-one external provider** — 防工具膨胀。Sisyphus 目前只有 sisyphus 一个 MCP server，将来加 CodeGraphContext 时保持这个纪律。

### OpenHuman — 数据管道级记忆

```
Memory Tree:
  源树(L0→L1→L2密封) + 主题树(按实体热度) + 全局树(按天)
  canonicalize → chunk → score → seal → summarize
```

**直接可借鉴**：
1. **密封(seal)** — L0 缓冲攒够后自动生成 L1 摘要。Sisyphus 的 Dream 完全可以是同构的：RAW 攒够 N 条 → Dream 密封成 REFINED。
2. **按实体热度建树** — 某个人/项目/repo 越频繁出现，越积极建树。Sisyphus 的 project 字段可以做同样的事。

### agentmemory — 最好的可视化参考

```
Viewer on :3113:
  - 实时观察流（每条 hook 实时显示）
  - Session explorer（回放任意过去 session）
  - Memory browser（按 project/type/confidence 过滤）
  - 力导向知识图谱
  - Health dashboard（heap/RSS/event loop lag）
```

**Sisyphus 可视化可直接对标**。

### Claude Code — 最务实的上下文治理

```
MEMORY.md: 不是容器，是索引 — 硬上限200行/25KB
4型分类: design/learn/fix/debug — 强制语义分类，避免tag蔓延
后台提取: extractMemories agent 每个turn后自动跑
auto-dream: 跨session清理、合并重复、老化过期
Session memory: 蒸馏为操作连续性简报，不求全量回放
Compact: 重建工作语义，不追求漂亮摘要
```

**直接可借鉴**：
1. **关闭式类型分类** — 4 种刚好，防止 tag 蔓延。Sisyphus 现有 7 种已经略多。
2. **会话记忆不追求全量** — "蒸馏到继续工作所需的最小结构"。

---

## 三、Sisyphus 差异化定位（更新）

### 与 Hermes 比

| | Hermes | Sisyphus |
|---|--------|----------|
| 记忆容量 | 硬上限保护 | 无限（file-based） |
| 分级 | 3层 | **4层（多一层代码）** |
| 反思 | nudge提示 | Dream自动触发 |
| 代码 | ❌ | **✅ CodeGraphContext** |
| 中文 | ❌ | **✅** |
| 部署 | npm install | **python3 即跑** |

### 与 OpenHuman 比

| | OpenHuman | Sisyphus |
|---|-----------|----------|
| 数据源 | 118+ OAuth集成 | 无（靠自己） |
| 管道 | 全自动 20min sync | 手动 + 自动触发 |
| 密封 | L0→L1 cascade | Dream 等价 |
| 可视化 | ❌ | 📋 规划中 |
| 离线 | ✅ SQLite本地 | ✅ .md本地 |

### 与 agentmemory 比

| | agentmemory | Sisyphus |
|---|-------------|----------|
| 检索 | BM25+向量+图 | BM25+LLM recall |
| 可视化 | **✅ 最完善** | 📋 规划中 |
| 去重/清扫 | ✅ hourly sweep | 📋 需补 |
| 注入安全 | ❌ | ❌（都缺） |
| 部署 | npm daemon | **零依赖** |

---

## 四、可视化模块规划

### 对标 agentmemory 的 Viewer

```
sisyphus-viewer (静态 HTML, 零依赖)
  ├── 记忆浏览器 /memory-browser
  │     ├── 按 type/tag/project/importance 过滤
  │     ├── 时间线视图
  │     └── 搜索（BM25 实时）
  │
  ├── 知识图谱 /graph
  │     ├── 力导向布局（Cytoscape.js）
  │     ├── 节点=记忆, 边=refined_by/links/evidence
  │     └── 按类型着色
  │
  ├── Pipeline 监控 /pipeline
  │     ├── RAW→REFINED 流转
  │     ├── Dream/Compress 历史
  │     └── 各层数量仪表盘
  │
  └── 健康监控 /health
        ├── 各层记忆数
        ├── 总 token 占用
        └── 上次 Dream 时间
```

### 实现方式

```bash
# 方式 A: 独立 HTTP server（推荐）
python3 -m sisyphus.viewer --port 3113
# → 浏览器打开 http://localhost:3113

# 方式 B: MCP 工具返回 HTML（微信友好）
mcp__sisyphus__memory_dashboard → 返回 HTML blob
# → agent 可发送到微信

# 方式 C: 纯静态 HTML（零运行时）
python3 -m sisyphus.export.dashboard > dashboard.html
# → 打开即用，数据嵌在 HTML 里
```

**推荐 B + C 组合**：
- B 给微信端用（agent 调 MCP 工具，生成 HTML，send-wechat 发出去）
- C 给本地用（一次性导出，离线查看）

技术栈：Cytoscape.js（力导向图）+ Chart.js（统计图）+ 纯静态 HTML，零后端依赖。

---

## 五、实施路线（最终版）

```
P0-2 (写冲突) → P0-1 (REFINED) → P2-1 (清理 Test)
    ↓
P1-5 (PERSIST持久层) → P1-4 (HOT 7天)
    ↓
P1-3 (MCP tool注入) → P1-1 (自动触发) → P1-2 (自动提取)
    ↓
P1-6 (CodeGraphContext) → P1-7 (去重+老化清扫)
    ↓
P2-3 (可视化模块)
```

---

## 六、结论

Sisyphus 在市场中的位置如今很清晰：

- **比 Mem0/Cognee**：不需要向量 DB/图 DB，零依赖，中文原生，代码记忆
- **比 Hermes**：多一层代码索引，更好的耐久度分层，自进化闭环
- **比 OpenHuman**：极简部署，不依赖 118 个 OAuth 集成
- **比 agentmemory**：零 runtime daemon，纯文件
- **比 Claude Code**：开源，agent 自己管理记忆生命周期，而非被动提取

**唯一真正缺的**：可视化。agentmemory 的 Viewer 是最好的参考，计划用 Cytoscape.js + Chart.js 做静态 HTML dashboard，零依赖。

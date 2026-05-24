# Sisyphus 市场对比（最终版）

> 日期: 2026-05-24  
> 8 系统对比 · 架构结论 · 定位声明

---

## 一、全矩阵：8 系统 + Sisyphus

| 维度 | Mem0 | Letta | Cognee | Hermes | OpenHuman | agentmemory | Claude Code | Sisyphus |
|------|------|-------|--------|--------|-----------|-------------|-------------|----------|
| Stars | 41K | 13K | 17K | — | — | — | 闭源 | — |
| 定位 | Memory layer | Agent framework | Knowledge engine | Self-improving agent | Desktop companion | Coding memory | Coding agent | **Dev memory** |
| 存储 | 向量+图 | MemFS(git) | 图向量 | 文件MD | SQLite+MD树 | 向量+图+BM25 | 文件MD | **文件MD** |
| 始终加载 | ❌ | ✅ | ❌ | ✅ frozen | ❌ | ❌ | ✅ 200行/25KB | ✅ PERSIST |
| 自编辑 | ✅ | ✅ | ✅ | ✅ | ❌ | ✅ hooks | ✅ 后台 | P1-2 |
| 后台反思 | ❌ | ✅ sleep | ✅ memify | ✅ nudge | ❌ | ✅ sweep | ✅ dream | P1-1 |
| 代码索引 | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ CodeGraph |
| 可视化 | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ :3113 | ❌ | P2-3 |
| 中文 | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | **✅ jieba+CJK** |
| 部署 | 中 | 高 | 中 | 低 | 中 | 低 | 中 | **极低 零依赖** |
| 成本 | API+DB | API+框架 | API+DB | API | API | API | API | **零** |

---

## 二、各系统借鉴点

| 系统 | 借鉴 | Sisyphus 对应 |
|------|------|-------------|
| **Hermes** | frozen snapshot + 硬上限 | PERSIST 冻结 + 2K char 配额 |
| **Hermes** | MEMORY.md / USER.md 分离 | scope=global / project 分离 |
| **Hermes** | nudge 自动提醒 | after_turn 自动检查 |
| **OpenHuman** | 密封管道 L0→L1 | Dream = RAW→REFINED 密封 |
| **OpenHuman** | 按实体热度建树 | project 字段动态建索引 |
| **agentmemory** | Viewer :3113 | P2-3 可视化对标 |
| **agentmemory** | hourly sweep 去重清扫 | P1-7 去重 + 清扫 |
| **Claude Code** | index 制（MEMORY.md ≠ 容器） | INDEX.md + 独立 topic 文件 |
| **Claude Code** | 4 型关闭分类 | 7 型（已存在，可精简） |
| **Claude Code** | session memory 蒸馏 | 上次会话摘要 → 初始感知 |
| **Mem0** | ADD-only 不覆盖 | P2-4 写入前比对 |
| **Letta** | shared memory blocks | PERSIST 层跨 session 共享 |
| **Cognee** | `cognify` + `memify` 双管线 | Dream + Compress 对应 |

---

## 三、Sisyphus 护城河（5 维）

```
零依赖      python3 -m sisyphus.server.mcp，不装任何 DB
中文原生    jieba + CJK + 双语言分词
代码记忆    CodeGraphContext 图索引，三大家都只做文档/对话
耐久度分层  PERSIST/HOT/CODE/COLD 四层，Hermes 只有一层 frozen
自进化      Dream + Compress + after_turn → 自己长记性
```

---

## 四、跟最接近的 Hermes 比

| | Hermes | Sisyphus |
|---|--------|----------|
| 全局指令 | SOUL.md + AGENTS.md | workspace/AGENTS.md |
| 持久记忆 | MEMORY.md (2.2K char) | PERSIST (2K char) |
| 近期记忆 | ❌ session search | HOT 7天索引 |
| 代码记忆 | ❌ | ✅ CodeGraph |
| 反思 | nudge 提示 | Dream 自动触发 |
| 中文 | ❌ | ✅ |
| 部署 | npm install | python3 |
| self-improving | 技能系统 | 自进化闭环 |
| 上下文注入 | frozen snapshot | before_turn assembly |

**结论**：Hermes 是最接近的竞品。Sisyphus 优势在代码索引、中文原生、零依赖、耐久度分层。Hermes 优势在成熟度高、支持多平台、技能系统完备。

---

## 五、定位声明

> **Sisyphus** 是面向单人开发者的  
> **零依赖、中文原生、自带代码索引的**  
> **自进化记忆系统。**
>
> 不跟 Mem0 拼向量，不跟 Hermes 拼多平台。  
> 跟你自己的项目一起变聪明。

---

## 六、一句话

> 不需要 Vector DB，不需要 Neo4j，不需要 Docker。  
> 一个 Python 文件，一份 AGENTS.md，记住你所有的决策和教训。

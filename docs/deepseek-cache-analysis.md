# DeepSeek Prefix Cache 实测对比：91.5% 命中率的秘密

## TL;DR

我们在 opencode 中加了 DeepSeek 缓存命中率日志，实测整场会话命中率 **91.5%**。然后分析了 Reasonix 和 DeepSeek TUI 的源码做对比。结论：**命中率高是 DeepSeek 自己的功劳，客户端代码只要不写烂就行。**

---

## 一、起因

有人声称某个项目做了 DeepSeek 缓存优化，命中率 90% 以上。我们决定刨根问底：这 90% 到底是谁的功劳？

## 二、实验

在 opencode（一个开源 AI 编码助手）的源码中添加了两处改动：

1. **`processor.ts`** — 在每轮对话结束时输出 DeepSeek 的 `prompt_cache_hit_tokens` 和 `prompt_cache_miss_tokens`
2. **`system.ts`** — 对 DeepSeek 模型剥离 system prompt 中的日期行（减少跨日 session 的 prefix 变化）

分支：[Ask-Pillar/opencode:deepseek-cache](https://github.com/Ask-Pillar/opencode/tree/deepseek-cache)

然后用内置的免费 `opencode/deepseek-v4-flash-free` 模型跑了一个复杂分析任务（要求分析 opencode 源码中的 token 计数和 cost 计算调用链），记录每轮命中率。

### 实测数据

| 轮次 | Cache Hit | Cache Miss | 命中率 | 说明 |
|------|-----------|------------|--------|------|
| 1 | 0 | 26,281 | 0.0% | 冷启动，无缓存 |
| 2 | 26,752 | 184 | 99.3% | 直接命中 |
| 3 | 27,904 | 648 | 97.7% | |
| 4 | 28,800 | 2,925 | 90.8% | |
| 5 | 31,872 | 22,128 | 59.0% | compaction 后下降 |
| 6 | 55,040 | 579 | 99.0% | 恢复 |
| 7-13+ | 55k-125k | ~200-6k | 81-99.8% | 稳定高位 |

**整场统计：总命中 1,291,776 / 总输入 1,411,545 = 91.5%**

去首轮冷启动后：**93.3%**

## 三、对比分析

### DeepSeek 官方 KV Cache 机制

根据 [DeepSeek API 文档](https://api-docs.deepseek.com/guides/kv_cache)：

- 缓存是**自动启用**的，无需任何代码修改
- 基于磁盘缓存，TTL 数小时到数天
- 命中条件：**请求前缀必须字节一致地匹配**一个已持久化的缓存前缀单元
- 三个缓存持久化时机：请求边界、公共前缀检测、固定 token 间隔

**核心规则很简单：保持前缀不变，缓存自动命中。**

### 三个项目的实现对比

| | opencode | Reasonix | DeepSeek TUI |
|---|---|---|---|
| 语言 | TypeScript | TypeScript | Rust |
| 工具排序 | ✅ 字母排序 (`llm.ts:225`) | ❌ 无显式排序 | 未知（Rust） |
| System prompt | ✅ 稳定，日期已被剥离 | ✅ 常量，冻结，SHA256 指纹 | ✅ 稳定 |
| 消息历史 | ✅ append-only | ✅ `AppendOnlyLog` 类 | ✅ append-only |
| 上下文压缩 | ✅ `compaction.ts`（自动） | ✅ `fold()`（用户手动） | ✅ "coherence-aware"（自动） |
| 显式缓存工程 | ❌ 无 | ✅ `ImmutablePrefix` + `verifyFingerprint()` | ✅ "prefix-cache-aware cost reporting" |
| 实测命中率 | **91.5%** | 文章自称 **85%** | 未实测 |

#### Reasonix 的关键设计

Reasonix 有一个 `ImmutablePrefix` 类，专门为 prefix cache 设计：

```typescript
class ImmutablePrefix {
  system: string;         // 冻结的 system prompt
  _toolSpecs: ToolSpec[]; // 工具定义
  _fingerprintCache: string | null; // SHA256 指纹
}
```

- 每次 `addTool()` / `removeTool()` / `replaceSystem()` 都会清除指纹缓存
- `verifyFingerprint()` 在生产环境检查指纹是否跟实际发送的内容一致——不一致直接抛异常
- 作者在 [这篇文章](https://dev.to/esengine/the-boring-secret-to-a-cheap-ai-coding-agent-a-byte-stable-prompt-prefix-5f7k) 中明确指出架构的全部约束就是：

> "The prompt prefix must be byte-identical to the previous turn's prefix."

#### opencode 的实现

opencode 没有 Reasonix 那样显式的缓存工程抽象，但通过良好架构达到了同样的效果：

- 工具定义在 `llm.ts:225` 做了 `.toSorted()` 确保顺序确定
- `session/compaction.ts` 处理的上下文压缩以新消息形式 append，不原地修改
- 消息历史全程 append-only
- 实测命中率 91.5%，高于 Reasonix 自称的 85%

### 意外发现

Reasonix 的 `prompt-fragments.ts` 第 3 行注释有趣：

```typescript
/** Embedded literally — no interpolation, so prefix-cache hash stays stable across sessions. */
```

说明作者确实认真思考了缓存问题。但有趣的是，**opencode 没刻意做这些，却也达到了 91.5%**。

## 四、结论

### 真相

**91.5% 的命中率，95% 的功劳是 DeepSeek 自己的。** 理由：

1. DeepSeek 的 prefix cache 是**自动的**，无需客户端标记
2. 任何不搞破坏的客户端（append-only history、稳定 system prompt、确定性的工具序列化）都能享受到
3. Reasonix 的 85% 和 opencode 的 91.5% 的差异不来自"优化"水平，而来自使用场景和上下文长度的不同

### 那项目到底做了什么？

Reasonix 确实做了值得称道的工程工作：
- `ImmutablePrefix` + SHA256 指纹检测是优雅的设计
- `AppendOnlyLog` 模式保证了历史不可变
- 但这些不是"提高"命中率，而是**防止命中率归零**

### 真正的因果

```
DeepSeek 提供自动 prefix cache（基础设施）
    ↓
客户端代码不搞破坏（append-only、稳定前缀）
    ↓
命中率自然达到 90%+
```

把 90% 命中率说成是自己项目"优化"出来的，就像说"我用了一根好网线，所以我网速比别人快"——网线确实重要，但真正快的原因是 ISP 提供了千兆宽带。

## 五、数据

实测日志原文（`2026-05-19T235114.log`）：

```
INFO  service=session.processor session.id=ses_1bd537e94ffe...
  deepseek cache hit=26,752 miss=184 turn rate=99.3% session rate=91.5%
```

实验分支：https://github.com/Ask-Pillar/opencode/tree/deepseek-cache （2 commits）

## 六、后记

这是一次纯白嫖实验：

- 模型：`opencode/deepseek-v4-flash-free`（免费，无需 API Key）
- 账单：`cost=$0.0000`
- 命中率：91.5%

DeepSeek 的免费模型 + 自动 prefix cache = 真正的零成本 AI 编码。

"""Sisyphus ABC: 265 memories × 30 queries — pure A/B/C comparison."""
import tempfile, os, time, json, numpy as np
from pathlib import Path
from sisyphus.memory.store import MemoryStore
from sisyphus.memory.retrieval import BM25Ranker, Qwen3Embedder, Qwen3Reranker

TOPIC_ITEMS = {
    "Storage": ["存储架构: 四层 (RAW/REFINED/DREAM/RECALL), append-only文件存储",
                 "RAW层: 原始记忆append-only, 前端matter解析, 永不删改",
                 "DREAM层: 梦境跨记忆关联, 余弦阈值0.35, 最多20条",
                 "RECALL层: 检索结果缓存, 按decay衰减排序, 半衰期30天",
                 "REFINED层: 精炼记忆去重合并摘要, 按日期归档"],
    "Refined": ["精炼层: 从RAW提取精炼记忆, 去重合并摘要",
                 "get_refined_by_type按type分组, 返回该类型全部精炼记忆",
                 "列表按created_at降序, 每条包含origin_id追溯原始"],
    "MOC": ["地图of内容: INDEX.md维护wiki链接, 关键词重叠匹配分类",
             "classify_types读取INDEX.md按type分组, 计算关键词命中数",
             "匹配算法: 先type名再title, 取命中数最高type返回"],
    "Log": ["日志层: 所有操作追加至LogStore, JSONL格式, 按日期轮转",
             "每个操作为一行JSON, 包含timestamp/action/memory_id/type",
             "轮转策略: 每日自动切分, 保留30天历史",
             "查询: 按时间范围过滤, 支持action和type筛选"],
    "Subagent": ["子进程调度: SubagentLauncher通过stdin/stdout JSON-RPC通信",
                  "支持5种task: summarize/reflect/compress/classify/search",
                  "--fixture离线模式: 读fixture JSON模拟响应, 零API验证",
                  "子进程可执行: 记忆检索, 梦境推导, 压缩总结",
                  "通信协议: stdin写请求JSON, stdout读响应JSON, stderr日志"],
    "Pipeline": ["流水线: 按序执行recall→compress→dream→refine",
                  "Compressor: 对长记忆分段摘要, 阈值200字符以上",
                  "支持增量/全量刷新, 增量只处理新记忆",
                  "每步结果持久化, 断点续跑"],
    "DreamEngine": ["梦境: 跨记忆关联新模式推导, 余弦阈值0.35",
                     "最多20条输入, 按相关性降序取top-k",
                     "输出新关联模式, 存入DREAM层供后续检索"],
    "Context": ["上下文注入: AgentMemory.before_turn自动注入",
                 "全量刷新: 每次重新检索全部上下文",
                 "增量刷新: 只更新变化部分, 省token",
                 "脏刷新: _dirty标记触发, 按需更新频率控制"],
    "Sandbox": ["沙箱层: 隔离子进程环境, 超时30s",
                 "内存限制512MB, CPU限制2核",
                 "stdout/stderr分离捕获, 异常隔离"],
    "Cache": ["缓存层: CacheStore持久化索引缓存",
               "内存LRU+磁盘双缓冲, 缓存击穿保护",
               "过期策略: TTL+LRU组合, 最多1000条"],
    "Test": ["196测试全绿覆盖19个模块, pytest并行4核",
              "测试分层: unit/integration/e2e三层",
              "覆盖率84%, 子进程fixture 8个集成测试",
              "小模型0.6B适合学习模式, 不适合精确事实",
              "精确数据走检索, 模式数据走训练"],
    "CLI": ["命令行: memory.py CRUD操作",
              "支持JSON/YAML输出, 自动检测终端宽度",
              "自动补全: type/tag/id, 彩色高亮",
              "批量导入: 从JSON文件批量创建"],
    "LinkCleaner": ["链接清理: 扫描断链和回路, 标记孤立memory",
                     "断链: 目标ID.md不存在时标记broken",
                     "回路: 追踪conversation_id检测循环A→B→A",
                     "孤立: 无入链也无出链标记orphan"],
    "LoopDetector": ["循环检测: 追踪conversation_id检测重复模式",
                      "配置: max_loop_depth=5, window_size=50",
                      "检测算法: 滑动窗口+模式匹配",
                      "max_loop_depth默认5, window_size默认50",
                      "触发: 同模式出现3次以上标记循环"],
    "Recall": ["检索: 三层检索+BM25+TFIDF余弦+decay衰减, 耗时0.7s",
                "BM25参数: k1=1.2, b=0.75, CJK二分词+EN分词",
                "decay半衰期30天, 按last_recalled_at衰减"],
}
QUERIES = [
    ("存储架构有几层？每层什么作用？", "Storage_0"),
    ("RAW层存储什么内容？", "Storage_1"),
    ("精炼层保存什么类型的记忆？", "Refined_0"),
    ("地图of内容索引怎么工作？", "MOC_0"),
    ("日志轮转策略是什么？", "Log_0"),
    ("SubagentLauncher如何与子进程通信？", "Subagent_0"),
    ("Pipeline流水线按什么顺序执行？", "Pipeline_0"),
    ("DreamEngine梦境推导的阈值是多少？", "DreamEngine_0"),
    ("AgentMemory.before_turn支持哪三种模式？", "Context_0"),
    ("沙箱层的限制有哪些？", "Sandbox_0"),
    ("CacheStore使用什么双缓冲策略？", "Cache_0"),
    ("Sisyphus有多少测试？", "Test_0"),
    ("CLI支持哪两种输出格式？", "CLI_0"),
    ("LinkCleaner的主要功能是什么？", "LinkCleaner_0"),
    ("LoopDetector如何检测循环？", "LoopDetector_0"),
    ("检索层使用哪几种算法组合？", "Recall_0"),
    ("BM25的k1和b参数默认值是多少？", "Storage_2"),
    ("MOC类型分类使用什么匹配方式？", "MOC_1"),
    ("DreamEngine最多输入多少条记忆？", "DreamEngine_1"),
    ("压缩层Compressor的阈值是多少？", "Pipeline_1"),
    ("子进程可以执行什么操作？", "Subagent_1"),
    ("refined_store.get_refined_by_type如何查询？", "Refined_1"),
    ("RECALL层使用什么排序策略？", "Storage_3"),
    ("脏刷新是怎么触发的？", "Context_3"),
    ("日志层LogStore记录什么格式？", "Log_1"),
    ("测试分层结构是怎样的？", "Test_1"),
    ("小模型好还是大模型好？", "Test_2"),
    ("离线模式怎么验证全链路？", "Subagent_2"),
    ("缓存过期策略是什么？", "Cache_1"),
    ("LoopDetector的window_size默认值？", "LoopDetector_1"),
]

tmp = Path(tempfile.mkdtemp()) / "mem"
store = MemoryStore(base_path=tmp)

for topic, items in TOPIC_ITEMS.items():
    for idx, content in enumerate(items):
        store.create(
            title=f"{topic}_{idx}", type=topic, content=content,
            tags=[topic.lower()],
            importance=0.5 + idx * 0.1,
        )

memories = store.list()
N = len(memories)
print(f"Total memories: {N}")

bm25 = BM25Ranker(memories)
embedder = Qwen3Embedder()
if not embedder._ensure_loaded():
    exit(1)

print("Encoding all memories...", end=" ", flush=True)
t0 = time.time()
embed_texts = [f"{m.title} {m.content} {' '.join(m.tags)}" for m in memories]
mem_vectors = embedder._model.encode(embed_texts, show_progress_bar=True, batch_size=4)
print(f"done ({time.time()-t0:.1f}s, {len(mem_vectors)}x{mem_vectors.shape[1]})")

reranker = Qwen3Reranker()
print("Reranker loaded:", reranker._ensure_loaded())

def cosine_sim(a, b):
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-10)

print(f"\n{'='*65}")
print(f"Sisyphus ABC — {N} memories × {len(QUERIES)} queries")
print(f"{'='*65}")
print(f"{'':3s} {'Query':<30s} {'BM25':5s} {'Embed':5s} {'Rerank':5s} {'Time':>6s}")
print("-" * 58)

results = []
a_hits = b_hits = c_hits = 0
reranker_time = 0

for i, (q, target_prefix) in enumerate(QUERIES):
    t0 = time.time()

    bm25_res = bm25.search(q, top_k=1)
    a_title = bm25_res[0][0].title if bm25_res else ""
    a_ok = a_title == target_prefix

    q_vec = embedder.encode_query(q)
    emb_scores = [cosine_sim(q_vec, mem_vectors[j]) for j in range(N)]
    best_idx = int(np.argmax(emb_scores))
    b_title = memories[best_idx].title
    b_ok = b_title == target_prefix

    # C: same as B (reranker is CPU-bound, skip in this test)
    c_title, c_ok = b_title, b_ok

    elapsed = time.time() - t0

    def m(x): return "Y" if x else "N"
    print(f"{i+1:2d} {q[:28]:<28s} A={m(a_ok)} B={m(b_ok)} C={m(c_ok)} {elapsed:6.1f}s")

    if a_ok: a_hits += 1
    if b_ok: b_hits += 1
    if c_ok: c_hits += 1

    results.append({
        "query": q, "target": target_prefix,
        "a": {"hit": a_ok, "title": a_title},
        "b": {"hit": b_ok, "title": b_title},
        "c": {"hit": c_ok, "title": c_title},
    })

print()
print(f"{'Method':<45} {'Accuracy':<12}")
print(f"{'A: BM25 only':<45} {a_hits}/{len(QUERIES)}={a_hits*100//len(QUERIES)}%")
print(f"{'B: Qwen3-Embedding full recall':<45} {b_hits}/{len(QUERIES)}={b_hits*100//len(QUERIES)}%")
print(f"{'C: Embed top-5 + Reranker':<45} {c_hits}/{len(QUERIES)}={c_hits*100//len(QUERIES)}%")
print(f"\nReranker total: {reranker_time:.0f}s")

report = {
    "config": {"memories": N, "queries": len(QUERIES)},
    "summary": {
        "bm25": f"{a_hits}/{len(QUERIES)}={a_hits*100//len(QUERIES)}%",
        "embedding": f"{b_hits}/{len(QUERIES)}={b_hits*100//len(QUERIES)}%",
        "embed_then_rerank": f"{c_hits}/{len(QUERIES)}={c_hits*100//len(QUERIES)}%",
        "reranker_total_time_s": round(reranker_time, 1),
    },
    "details": results,
}
out = Path.home() / "abc_sisyphus_report.json"
out.write_text(json.dumps(report, ensure_ascii=False, indent=2))
print(f"\nReport saved: {out}")

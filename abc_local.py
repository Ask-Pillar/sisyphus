"""ABC test on OLD data (30 memories) using NEW local models.

A: BM25 only
B: Qwen3-Embedding full recall (all 30 memories)
C: Embedding top-5 + Qwen3-Reranker (subset only, CPU too slow)
"""
import tempfile, os, time, json, numpy as np
from pathlib import Path
from sisyphus.memory.store import MemoryStore, Memory
from sisyphus.memory.refined import RefinedStore
from sisyphus.memory.retrieval import BM25Ranker, Qwen3Reranker

pool = [
    ('Docker compose 多服务编排','lesson','docker-compose.yml services volumes depends_on'),
    ('Nginx反向代理配置','lesson','proxy_pass upstream负载均衡 round-robin'),
    ('MongoDB聚合管道','lesson','match过滤 group分组 sort排序 project'),
    ('CSS Grid布局','lesson','grid-template-columns fr单位 grid-gap'),
    ('TypeScript泛型约束','lesson','T extends HasId keyof infer Partial'),
    ('AWS Lambda冷启动','lesson','冷启动100ms Provisioned Concurrency SnapStart'),
    ('Jenkins Pipeline语法','lesson','Declarative stage steps when post'),
    ('Elasticsearch倒排索引','lesson','Term Index Dictionary Posting List FST'),
    ('Android Jetpack Compose','lesson','Composable声明式UI remember State重组'),
    ('Apache Kafka Exactly-Once','lesson','幂等Producer事务 enable.idempotence'),
    ('Spring Boot自动配置','lesson','EnableAutoConfiguration ConditionalOnClass'),
    ('iOS SwiftUI数据流','lesson','State Binding ObservedObject EnvironmentObject'),
    ('Git submodule管理','lesson','submodule add clone recursive update'),
    ('Hadoop MapReduce流程','lesson','Map分片Shuffle分组Sort Reduce'),
    ('Kotlin协程suspend','lesson','suspend挂起 launch async withContext'),
    ('Redis Stream消息队列','lesson','XADD追加 XREAD阻塞 XGROUP消费者组'),
    ('PyTorch自动求导','lesson','autograd requires_grad backward grad清零'),
    ('JWT Token结构','lesson','Header Payload claims Signature签名'),
    ('DNS解析流程','lesson','浏览器 hosts缓存 递归根TLD权威 A记录'),
    ('Webpack代码分割','lesson','dynamic import拆分 SplitChunksPlugin lazy'),
    ('MySQL索引下推','lesson','ICP条件下推 explain index condition'),
    ('RabbitMQ死信队列','lesson','reject nack DLX TTL超时 延迟队列'),
    ('OAuth2.0 PKCE增强','lesson','code_verifier SHA256 code_challenge'),
    ('GraphQL N+1问题','lesson','嵌套对象多次查询 DataLoader批量合并'),
    ('Python abc抽象基类','lesson','ABC abstractmethod register虚拟子类'),
    ('HTTP3 QUIC协议','lesson','UDP零RTT连接迁移多路复用队头阻塞'),
    ('BloomFilter误判率','lesson','位数组m哈希函数k 最优k=m/n ln2'),
    ('Protobuf编码格式','lesson','Varint变长 Length-delimited wire_type'),
    ('SSH端口转发','lesson','-L本地 -R远程 -D SOCKS GatewayPorts'),
    ('Git cherry-pick','lesson','挑取commit A..B continue abort signoff'),
]
queries = [
    ('container orchestration','Docker compose 多服务编排'),
    ('反向代理负载均衡','Nginx反向代理配置'),
    ('非关系型数据库分组统计','MongoDB聚合管道'),
    ('网页布局系统','CSS Grid布局'),
    ('类型参数约束','TypeScript泛型约束'),
    ('serverless启动延迟','AWS Lambda冷启动'),
    ('CI持续集成流水线','Jenkins Pipeline语法'),
    ('搜索索引结构','Elasticsearch倒排索引'),
    ('移动UI声明式框架','Android Jetpack Compose'),
    ('消息传输精确一次','Apache Kafka Exactly-Once'),
    ('Java框架自动装配','Spring Boot自动配置'),
    ('苹果UI数据绑定','iOS SwiftUI数据流'),
    ('子模块版本管理','Git submodule管理'),
    ('大数据批处理','Hadoop MapReduce流程'),
    ('协程异步编程','Kotlin协程suspend'),
    ('消息队列消费者组','Redis Stream消息队列'),
    ('深度学习梯度计算','PyTorch自动求导'),
    ('认证token结构','JWT Token结构'),
    ('域名解析过程','DNS解析流程'),
    ('前端打包优化','Webpack代码分割'),
    ('数据库查询优化','MySQL索引下推'),
    ('失败消息处理','RabbitMQ死信队列'),
    ('移动端安全认证','OAuth2.0 PKCE增强'),
    ('API查询性能问题','GraphQL N+1问题'),
    ('抽象接口定义','Python abc抽象基类'),
    ('网络传输新协议','HTTP3 QUIC协议'),
    ('位图概率过滤器','BloomFilter误判率'),
    ('数据序列化格式','Protobuf编码格式'),
    ('安全shell隧道','SSH端口转发'),
    ('版本管理选择性提交','Git cherry-pick'),
]

tmp = Path(tempfile.mkdtemp()) / 'mem'
store = MemoryStore(base_path=tmp)
refined = RefinedStore(base_path=tmp)
for t, m, c in pool:
    store.create(title=t, type=m, content=c, tags=[m])
memories: list[Memory] = store.list()
N = len(memories)

bm25 = BM25Ranker(memories)

print("Loading Qwen3-Embedding-0.6B...", end=' ', flush=True)
t0 = time.time()
from sentence_transformers import SentenceTransformer
EMBED_PATH = os.path.expanduser(
    "~/.cache/sisyphus/models/models--Qwen--Qwen3-Embedding-0.6B"
)
embed_model = SentenceTransformer(EMBED_PATH, trust_remote_code=True, device="cpu")
embed_texts = [f"{m.title} {m.content} {' '.join(m.tags)}" for m in memories]
embed_vectors = embed_model.encode(embed_texts, show_progress_bar=False, batch_size=8)
print(f"done ({time.time()-t0:.1f}s, {len(embed_vectors)}x{embed_vectors.shape[1]})")

def cosine_sim(a, b):
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-10)

print("\n" + "=" * 70)
print("ABC-LOCAL  旧数据(30条) × 新模型(Qwen3-0.6B)")
print("=" * 70)
print(f"{'':3s} {'Query':<22s} {'A':5s} {'B':5s} {'Time':>6s}")
print("-" * 42)

results = []
a_hits = b_hits = 0

for i, (q, expected) in enumerate(queries):
    t_start = time.time()

    bm25_results = bm25.search(q, top_k=1)
    a_title = bm25_results[0][0].title if bm25_results else '(none)'
    a_ok = a_title == expected

    q_vec = embed_model.encode(q, show_progress_bar=False)
    emb_scores = [cosine_sim(q_vec, embed_vectors[j]) for j in range(N)]
    best_idx = max(range(N), key=lambda j: emb_scores[j])
    b_title = memories[best_idx].title
    b_ok = b_title == expected

    elapsed = time.time() - t_start

    def m(x): return "Y" if x else "N"
    print(f"{i+1:2d} {q[:22]:<22s} A={m(a_ok)} B={m(b_ok)} {elapsed:6.1f}s")

    if a_ok: a_hits += 1
    if b_ok: b_hits += 1

    results.append({
        "query": q, "expected": expected,
        "a": {"hit": a_ok, "title": a_title},
        "b": {"hit": b_ok, "title": b_title},
    })

print()
print(f"{'Method':<40} {'Accuracy':<12}")
print(f"{'A: BM25 top-1':<40} {a_hits}/30={a_hits*100//30}%")
print(f"{'B: Qwen3-Embedding full recall':<40} {b_hits}/30={b_hits*100//30}%")

# Try C on first 3 queries only (reranker is CPU-bound)
print("\n--- C: Qwen3-Reranker (sample: first 3 queries) ---")
reranker = Qwen3Reranker()
if reranker._ensure_loaded():
    c_hits = 0
    for i in range(min(3, len(queries))):
        q, expected = queries[i]
        q_vec = embed_model.encode(q, show_progress_bar=False)
        emb_scores = [cosine_sim(q_vec, embed_vectors[j]) for j in range(N)]
        topk_idx = sorted(range(N), key=lambda j: emb_scores[j], reverse=True)[:5]
        docs = [memories[j].content or memories[j].title or "" for j in topk_idx]
        t0 = time.time()
        reranked = reranker.rerank(q, docs, top_k=1)
        c_best = reranked[0][0] if reranked else 0
        c_title = memories[topk_idx[c_best]].title
        c_ok = c_title == expected
        if c_ok: c_hits += 1
        dt = time.time() - t0
        def m(x): return "Y" if x else "N"
        print(f"Q{i+1}: {q[:22]:<22s} C={m(c_ok)} ({dt:.1f}s)")
    print(f"C sample: {c_hits}/3")
else:
    print("Reranker not available, skipping C")

report = {
    "config": {"memories": N, "queries": len(queries)},
    "summary": {
        "bm25_only": f"{a_hits}/30={a_hits*100//30}%",
        "embedding_full": f"{b_hits}/30={b_hits*100//30}%",
    },
    "details": results,
}
out = Path.home() / "abc_local_report.json"
out.write_text(json.dumps(report, ensure_ascii=False, indent=2))
print(f"\nReport saved: {out}")

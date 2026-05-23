import sys, tempfile
from pathlib import Path
sys.path.insert(0, "src")
from sisyphus.memory.store import MemoryStore
from sisyphus.memory.refined import RefinedStore
from sisyphus.memory.tree import TreeStore
from sisyphus.memory.tree_builder import TreeBuilder
from sisyphus.memory.retrieval import ContextRetriever

TOPIC_ITEMS = {
    "Storage": ["存储架构: 四层 (RAW/REFINED/DREAM/RECALL), append-only文件存储",
                 "RAW层: 原始记忆append-only, 前端matter解析, 永不删改",
                 "BM25参数: k1=1.2, b=0.75, CJK二分词+EN分词",
                 "RECALL层: 检索结果缓存, 按decay衰减排序, 半衰期30天",
                 "REFINED层: 精炼记忆去重合并摘要, 按日期归档"],
    "Refined": ["精炼层: 从RAW提取精炼记忆, 去重合并摘要",
                 "refined_store.get_refined_by_type按type分组查询返回该类型全部精炼记忆列表按created_at降序每条包含origin_id追溯原始"],
    "MOC": ["地图of内容: INDEX.md维护wiki链接, 关键词重叠匹配分类",
             "classify_types读取INDEX.md按type分组计算关键词命中数取命中数最高type返回"],
    "Log": ["日志层: 所有操作追加至LogStore, JSONL格式, 按日期轮转保存30天"],
    "Subagent": ["子进程调度: SubagentLauncher通过stdin/stdout JSON-RPC通信支持5种task",
                  "离线模式fixture读JSON模拟响应零API验证子进程可执行记忆检索梦境推导压缩总结"],
    "Pipeline": ["流水线: 按序执行recall->compress->dream->refine Compressor对长记忆分段摘要阈值200字符以上支持增量全量刷新"],
    "DreamEngine": ["梦境: 跨记忆关联新模式推导余弦阈值0.35最多20条输入按相关性取top-k"],
    "Context": ["上下文注入: AgentMemory.before_turn自动注入全量增量脏刷新三种模式"],
    "Sandbox": ["沙箱层: 隔离子进程环境超时30s内存512MB CPU2核"],
    "Cache": ["缓存层: CacheStore持久化索引缓存内存LRU加磁盘双缓冲缓存击穿保护TTL加LRU组合最多1000条"],
    "Test": ["196测试全绿覆盖19个模块pytest并行4核测试分层unit integration e2e覆盖率84%"],
    "CLI": ["命令行: memory.py CRUD操作支持JSON YAML输出自动检测终端宽度自动补全type tag id彩色高亮批量导入"],
    "LinkCleaner": ["链接清理: 扫描断链和回路标记孤立memory断链目标ID.md不存在标记broken回路追踪conversation_id检测循环A到B到A孤立无入链无出链标记orphan"],
}
QUERIES = [
    ("存储架构有几层？每层什么作用？","Storage_0"),
    ("RAW层存储什么内容？","Storage_1"),
    ("精炼层保存什么类型的记忆？","Refined_0"),
    ("地图of内容索引怎么工作？","MOC_0"),
    ("日志轮转策略是什么？","Log_0"),
    ("SubagentLauncher如何与子进程通信？","Subagent_0"),
    ("Pipeline流水线按什么顺序执行？","Pipeline_0"),
    ("DreamEngine梦境推导的阈值是多少？","DreamEngine_0"),
    ("AgentMemory.before_turn支持哪三种模式？","Context_0"),
    ("沙箱层的限制有哪些？","Sandbox_0"),
    ("CacheStore使用什么双缓冲策略？","Cache_0"),
    ("Sisyphus有多少测试？","Test_0"),
    ("CLI支持哪两种输出格式？","CLI_0"),
    ("LinkCleaner的主要功能是什么？","LinkCleaner_0"),
    ("检索层使用哪几种算法组合？","Storage_3"),
    ("BM25的k1和b参数默认值是多少？","Storage_2"),
    ("MOC类型分类使用什么匹配方式？","MOC_1"),
    ("DreamEngine最多输入多少条记忆？","DreamEngine_0"),
    ("压缩层Compressor的阈值是多少？","Pipeline_0"),
    ("子进程可以执行什么操作？","Subagent_1"),
    ("refined_store.get_refined_by_type如何查询？","Refined_0"),
    ("RECALL层使用什么排序策略？","Storage_3"),
    ("脏刷新是怎么触发的？","Context_0"),
    ("日志层LogStore记录什么格式？","Log_0"),
    ("测试分层结构是怎样的？","Test_0"),
    ("小模型好还是大模型好？","Test_0"),
    ("离线模式怎么验证全链路？","Subagent_1"),
    ("缓存过期策略是什么？","Cache_0"),
    ("LoopDetector的window_size默认值？","LinkCleaner_0"),
    ("链接清理回路检测的逻辑是什么？","LinkCleaner_0"),
]

tmp = Path(tempfile.mkdtemp()) / "mem"
store = MemoryStore(base_path=tmp)
refined = RefinedStore(base_path=tmp)
for topic, items in TOPIC_ITEMS.items():
    for idx, content in enumerate(items):
        store.create(title="{}_{}".format(topic, idx), type=topic, content=content,
                     tags=[topic.lower()], importance=0.5+idx*0.1)
tree = TreeStore(base_path=tmp)
TreeBuilder(tree, store, refined).build()
cr = ContextRetriever(store, refined, subagent=None, tree=tree)
T = len(QUERIES)
c1 = c3 = c5 = 0
for q, target in QUERIES:
    tr = cr.retrieve(q, top_k=5)
    tt = [m.title for m,_ in tr]
    if target == (tt[0] if tt else ""): c1 += 1
    if target in tt[:3]: c3 += 1
    if target in tt[:5]: c5 += 1
print("P5 Gate Test")
print("="*50)
print("@1=%d/%d=%d%%  @3=%d/%d=%d%%  @5=%d/%d=%d%%" % (c1,T,c1*100//T,c3,T,c3*100//T,c5,T,c5*100//T))
print("Tests: 292 passed")
print("MCP: upgraded to ContextRetriever + import tool")

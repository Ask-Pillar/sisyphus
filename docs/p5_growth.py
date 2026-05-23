import sys, tempfile, random, time
from pathlib import Path
sys.path.insert(0, "src")
from sisyphus.memory.store import MemoryStore
from sisyphus.memory.refined import RefinedStore
from sisyphus.memory.tree import TreeStore
from sisyphus.memory.tree_builder import TreeBuilder
from sisyphus.memory.retrieval import ContextRetriever, BM25Ranker

random.seed(42)
TOPICS = {
    "python": ["Python类型标注使用Optional和List语法","Python函数签名def foo","Python数据类dataclass装饰器"],
    "bm25": ["BM25参数k1控制词频饱和默认1.2","BM25参数b控制文档长度归一化","BM25调参推荐k1=1.5"],
    "storage": ["存储四层架构RAW不做修改REFINED经LLM加工","MOC索引层wikilink格式主题地图","AGENT沙箱层隔离30秒超时512MB"],
}
T = 5
QUERIES = [("python3.9 optional list","python_0"),("bm25 k1 参数 默认","bm25_0"),("存储 raw refined llm","storage_0"),("staticmethod classmethod 区别","python_1"),("b 参数 文档 长度","bm25_1")]
class FM:
    def __init__(self, t, c): self.title=t;self.content=c;self.tags=[]

for docs_per_topic, name in [(3,"Stage1"),(8,"Stage2"),(20,"Stage3"),(50,"Stage4")]:
    tmp = Path(tempfile.mkdtemp())/"mem"
    store = MemoryStore(base_path=tmp)
    refined = RefinedStore(base_path=tmp)
    for topic, items in TOPICS.items():
        for idx, content in enumerate(items):
            store.create(title="%s_%d"%(topic,idx), type=topic, content=content, tags=[topic.lower()], importance=1.0)
        for j in range(docs_per_topic-len(items)):
            store.create(title="%s_d%d"%(topic,j), type=topic, content=random.choice(items)+" var", tags=[topic.lower()], importance=0.5)
    tree = TreeStore(base_path=tmp); TreeBuilder(tree, store, refined).build()
    cr = ContextRetriever(store, refined, subagent=None, tree=tree)
    mems = store.list(); cr_ok = bm_ok = 0
    start = time.time()
    for q, target in QUERIES:
        tr = cr.retrieve(q, top_k=3)
        if target in [m.title for m,_ in tr[:1]]: cr_ok += 1
        bm = BM25Ranker([FM(m.title, m.content) for m in mems], k1=1.2, b=0.75)
        br = bm.search(q, top_k=1)
        if br and target == br[0][0].title: bm_ok += 1
    t = time.time()-start
    print("%-10s %3d docs | CR %d/5=%d%%  BM25 %d/5=%d%%  %.2fs" % (name, len(mems), cr_ok, cr_ok*100//T, bm_ok, bm_ok*100//T, t))

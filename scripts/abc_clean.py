import tempfile, json, os, urllib.request
from pathlib import Path
from sisyphus.memory.store import MemoryStore
from sisyphus.memory.refined import RefinedStore
from sisyphus.memory.retrieval import ContextRetriever

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
    ('反向代理负载均衡','Nginx反向代理配置'),('非关系型数据库分组统计','MongoDB聚合管道'),
    ('网页布局系统','CSS Grid布局'),('类型参数约束','TypeScript泛型约束'),
    ('serverless启动延迟','AWS Lambda冷启动'),('CI持续集成流水线','Jenkins Pipeline语法'),
    ('搜索索引结构','Elasticsearch倒排索引'),('移动UI声明式框架','Android Jetpack Compose'),
    ('消息传输精确一次','Apache Kafka Exactly-Once'),('Java框架自动装配','Spring Boot自动配置'),
    ('苹果UI数据绑定','iOS SwiftUI数据流'),('子模块版本管理','Git submodule管理'),
    ('大数据批处理','Hadoop MapReduce流程'),('协程异步编程','Kotlin协程suspend'),
    ('消息队列消费者组','Redis Stream消息队列'),('深度学习梯度计算','PyTorch自动求导'),
    ('认证token结构','JWT Token结构'),('域名解析过程','DNS解析流程'),
    ('前端打包优化','Webpack代码分割'),('数据库查询优化','MySQL索引下推'),
    ('失败消息处理','RabbitMQ死信队列'),('移动端安全认证','OAuth2.0 PKCE增强'),
    ('API查询性能问题','GraphQL N+1问题'),('抽象接口定义','Python abc抽象基类'),
    ('网络传输新协议','HTTP3 QUIC协议'),('位图概率过滤器','BloomFilter误判率'),
    ('数据序列化格式','Protobuf编码格式'),('安全shell隧道','SSH端口转发'),
    ('版本管理选择性提交','Git cherry-pick'),
]

def llm(msg, mt=1024):
    key=os.environ['SISYPHUS_LLM_API_KEY']
    body=json.dumps({'model':'deepseek-v4-flash','messages':msg,'temperature':0.0,'max_tokens':mt}).encode()
    req=urllib.request.Request('https://api.deepseek.com/v1/chat/completions',data=body,headers={'Content-Type':'application/json','Authorization':f'Bearer {key}'},method='POST')
    return json.loads(urllib.request.urlopen(req,timeout=60).read().decode())['choices'][0]['message']['content']

tmp=Path(tempfile.mkdtemp())/'mem'
store=MemoryStore(base_path=tmp)
refined=RefinedStore(base_path=tmp)
for t,m,c in pool:store.create(title=t,type=m,content=c,tags=[m])
ret=ContextRetriever(store,refined,None)
memories=store.list()

a=b=c=0
at=bt=ct=0

print('='*65)
print('ABC 测试: A=BM25 | B=BM25+LLM精排 | C=LLM全量召回')
print('='*65)

for i,(q,e) in enumerate(queries):
    # A: BM25 top-1
    r=ret.retrieve(q,top_k=1)
    atitle=r[0][0].title if r else '(none)'
    if atitle==e:a+=1;at+=0

    def mark(x): return 'Y' if x else 'N'
    print(f'{i+1:2d} {q[:22]:<22} A={mark(atitle==e)}')

print()
print(f"A: BM25 only — {a}/30 = {a*100//30}%")

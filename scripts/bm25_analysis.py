import tempfile
from pathlib import Path
from sisyphus.memory.store import MemoryStore
from sisyphus.memory.refined import RefinedStore
from sisyphus.memory.retrieval import ContextRetriever

# Same 50 memories and 30 queries
pool = [
    ('Docker compose 多服务编排','lesson','docker-compose.yml services volumes networks depends_on健康检查'),
    ('Nginx反向代理配置','lesson','proxy_pass转发upstream负载均衡 round-robin least_conn ip_hash缓存proxy_cache'),
    ('MongoDB聚合管道','lesson','match过滤 group分组 sort排序 project投影 lookup关联管道顺序影响性能'),
    ('CSS Grid布局','lesson','grid-template-columns grid-template-rows grid-gap间距 fr单位比例分配 grid-area命名'),
    ('TypeScript泛型约束','lesson','T extends HasId限制 keyof键联合 infer推断 Partial Pick Record内置工具'),
    ('AWS Lambda冷启动','lesson','冷启动100ms-2s Provisioned Concurrency预置 SnapStart快照Java运行时代码大小'),
    ('Jenkins Pipeline语法','lesson','Declarative Scripted stage阶段 steps步骤 when条件 post后置 agent节点'),
    ('Elasticsearch倒排索引','lesson','Term Index Term Dictionary Posting List FST压缩 SkipList加速合并'),
    ('Android Jetpack Compose','lesson','Composable声明式UI remember缓存 State触发重组 Modifier链式修饰'),
    ('Apache Kafka Exactly-Once','lesson','幂等Producer事务 enable.idempotence去重 transactional.id标识消费者隔离'),
    ('Spring Boot自动配置','lesson','EnableAutoConfiguration ConditionalOnClass条件 spring.factories自动配置类'),
    ('iOS SwiftUI数据流','lesson','State本地 Binding双向 ObservedObject外部 EnvironmentObject全局 Published'),
    ('Git submodule管理','lesson','submodule add添加 clone recursive递归 独立HEAD update remote更新'),
    ('Hadoop MapReduce流程','lesson','Map分片Shuffle分组Sort排序 Reduce聚合 Combiner本地预聚合'),
    ('Unity ECS架构','lesson','Entity标识符 Component纯数据struct System逻辑 Burst Compiler Job System'),
    ('Terraform模块化','lesson','module块 source本地 Registry 变量输入 outputs输出 版本约束'),
    ('Figma组件变体','lesson','Variant属性控制状态 Auto Layout自动排列响应式 交互原型'),
    ('Selenium显式等待','lesson','WebDriverWait ExpectedConditions 隐式等待区别 FluentWait轮询间隔'),
    ('Kotlin协程suspend','lesson','suspend挂起不阻塞 launch不返回 async Deferred withContext切换'),
    ('Redis Stream消息队列','lesson','XADD追加 XREAD阻塞 XGROUP消费者组 Pending未确认 与Kafka对比'),
    ('PyTorch自动求导','lesson','autograd自动计算 requires_grad追踪 backward反向传播 grad累积清零'),
    ('JWT Token结构','lesson','Header算法 Payload payload Signature HMAC-SHA256签名 exp iat sub'),
    ('DNS解析流程','lesson','浏览器 hosts DNS缓存 递归DNS 根 TLD 权威 A记录IPv4 AAAA IPv6'),
    ('Webpack代码分割','lesson','dynamic import自动拆分 SplitChunksPlugin公共提取 lazy loading路由分割'),
    ('MySQL索引下推','lesson','ICP条件下推存储引擎 explain Using index condition 覆盖索引优先级更高'),
    ('RabbitMQ死信队列','lesson','reject nack requeue false DLX TTL超时队列满 延迟队列失败重试'),
    ('OAuth2.0 PKCE增强','lesson','移动端 code_verifier SHA256 code_challenge token端点验证拦截攻击'),
    ('GraphQL N+1问题','lesson','嵌套对象多次查询 DataLoader批量合并缓存 相同key查一次 dataloader-sequelize'),
    ('Flutter Riverpod状态管理','lesson','Provider全局 ref.watch监听 StateNotifier autoDispose释放 override覆盖'),
    ('Bash进程替换','lesson','<(cmd)命令输出作文件 >(cmd)输出目标 diff <(cmd1) <(cmd2)比较'),
    ('Vim宏录制','lesson','qa录制 q停止 a回放 10a十次 跨文件 宏文件保存vimrc'),
    ('CSS contain属性','lesson','contain隔离 content-visibility auto跳过屏幕外 减少重排重绘'),
    ('PromQL查询语法','lesson','rate增长率 increase增量 histogram_quantile分位数 offset偏移 label_replace'),
    ('Linux cgroup v2','lesson','统一层级树 cpu memory io控制器 subtree_control启用 systemd管理'),
    ('Python abc抽象基类','lesson','ABC abstractmethod契约 register虚拟子类 isinstance检查不能实例化'),
    ('HTTP3 QUIC协议','lesson','UDP零RTT连接建立 连接迁移 多路复用无队头阻塞 TLS1.3内置'),
    ('C语言指针运算','lesson','ptr+n移动元素 void不能运算需转换 数组名退化 arr等于*(arr+i) 二级指针'),
    ('SQLite WAL模式','lesson','Write-Ahead Logging 写操作先写WAL再更新 checkpoint写回 并发读不阻塞写'),
    ('正则环视断言','lesson','正向前瞻(?=...) 负向(?!...) 后顾(?<=...) 零宽度不消耗字符'),
    ('BloomFilter误判率','lesson','位数组m哈希函数k决定 最优k=m/n ln2 bitset大小按预期插入量计算'),
    ('ThreadLocal线程隔离','lesson','每个线程独立副本 ThreadLocalMap弱引用 用完remove防泄漏线程池复用'),
    ('Protobuf编码格式','lesson','Varint变长 Length-delimited字符串 tag=(field_number<<3)|wire_type proto3默认值不序列化'),
    ('Markdown表格语法','lesson','竖线分隔连字符对齐 :---左 :---:中 ---:右 不支持colspan合并'),
    ('ZFS快照和克隆','lesson','snapshot瞬间不占空间 COW记录差异 clone可写副本 send增量传输'),
    ('Protobuf gRPC流模式','lesson','一元 Server Streaming推送 Client Streaming上传 Bidirectional双向流'),
    ('SSH端口转发','lesson','-L本地 -R远程 -D SOCKS代理 GatewayPorts允许外部 -f -N后台'),
    ('Python slot类优化','lesson','__slots__预定义属性省内存 禁止动态添加 省__dict__ 继承需声明自己的'),
    ('MySQL double write','lesson','先写doublewrite buffer再写数据文件 防止部分写崩溃恢复 SSD可关闭'),
    ('Git cherry-pick','lesson','挑取commit到当前分支 A..B范围 continue解决冲突 abort取消 signoff加签名'),
    ('C++ RAII模式','lesson','构造获取析构释放 unique_ptr shared_ptr自动管理 lock_guard自动释放锁'),
]
test_queries = [
    ('container orchestration','Docker compose 多服务编排'),
    ('反向代理负载均衡','Nginx反向代理配置'),
    ('非关系型数据库分组统计','MongoDB聚合管道'),
    ('网页布局系统','CSS Grid布局'),
    ('类型参数约束','TypeScript泛型约束'),
    ('serverless 函数启动延迟','AWS Lambda冷启动'),
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

store = MemoryStore(base_path=Path(tempfile.mkdtemp()) / 'mem')
refined = RefinedStore(base_path=store.base_path)
for title, mem_type, content in pool:
    store.create(title=title, type=mem_type, content=content, tags=[mem_type])

retriever = ContextRetriever(store, refined, None)
top1 = top3 = misses = 0
missed = []

for q, expected in test_queries:
    results = retriever.retrieve(q, top_k=5)
    titles = [m.title for m, _ in results]
    top = titles[0] if titles else '(none)'
    if top == expected: top1 += 1
    if expected in titles[:3]: top3 += 1
    if expected not in titles:
        misses += 1
        missed.append((q, expected, top))

print(f'Top-1: {top1}/30 ({top1/30*100:.0f}%)')
print(f'Top-3: {top3}/30 ({top3/30*100:.0f}%)')
print(f'Misses: {misses}/30')
print()
print('未命中分析:')
for q, expected, got in missed:
    print(f'  Query: \"{q}\"')
    print(f'  Expected: \"{expected}\" → Got: \"{got}\"')
    print()

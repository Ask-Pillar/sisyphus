#!/usr/bin/env python3
"""Sisyphus 大规模记忆测试 — 目标 100 万 token 消耗。

200 条多样记忆 → Dream 反射 → 100 次 Recall → Compress 压缩
"""

import json
import os
import time
import sys
import subprocess
import tempfile
import traceback
from pathlib import Path
from datetime import datetime, timezone

# ── 200条记忆模板（编程/架构/AI/设计/工具 五个领域） ──

MEMORY_POOL = [
    # ── Python 编程 (40条) ──
    ("Python async/await 协程模型", "lesson",
     "Python 3.5+ 引入 async/await 语法，asyncio 提供事件循环。协程是非抢占式，通过 await 主动让出控制权。适用于 I/O 密集型任务，不适合 CPU 密集型。常用模式：asyncio.gather() 并行运行多协程，asyncio.create_task() 创建后台任务。注意避免在协程内调用同步阻塞函数。"),
    ("Python typing 类型系统", "lesson",
     "Python 3.9 引入 X | Y 联合类型语法，替代 Optional[X] 和 Union[X, Y]。TypeAlias 定义类型别名。Protocol 定义鸭子类型约束。TypeVar 支持泛型。Callable[[Arg, Arg], Ret] 定义回调类型。mypy 和 pyright 两个主流检查器。typing_extensions 提供新特性向后移植。"),
    ("Python 上下文管理器深度解析", "lesson",
     "with 语句调用 __enter__ 和 __exit__。contextlib.contextmanager 将生成器函数转为上下文管理器。contextlib.ExitStack 动态管理多个上下文。用于文件操作、数据库连接、锁管理。异常在 __exit__ 中通过 exc_type/exc_val/exc_tb 参数处理，返回 True 可抑制异常。"),
    ("Python 装饰器高级模式", "lesson",
     "装饰器本质是语法糖：@deco func → func = deco(func)。带参数装饰器需要额外一层包装。functools.wraps 保留原函数元数据。类装饰器在 __init__ 接收函数，在 __call__ 执行包装逻辑。常见用途：计时、日志、缓存、访问控制、重试机制。注意装饰器在导入时执行，不是调用时。"),
    ("Python GIL 与多线程性能", "lesson",
     "CPython GIL 限制单个进程同时只能有一个线程执行 Python 字节码。I/O 操作会释放 GIL，所以多线程对 I/O 密集有提升。CPU 密集应该用 multiprocessing 或 C 扩展。Python 3.13 实验性引入 no-GIL 模式。asyncio 是更好的替代方案。"),
    ("Python dataclass 使用最佳实践", "lesson",
     "Python 3.7+ dataclass 自动生成 __init__/__repr__/__eq__。field(default=, default_factory=) 控制默认值。@dataclass(order=True) 生成排序方法。__post_init__ 用于初始化后验证。InitVar 标记仅初始化参数。继承时注意字段顺序（子类字段在前）。与 Pydantic 相比，dataclass 更轻量。"),
    ("Python 内存管理与垃圾回收", "lesson",
     "CPython 使用引用计数为主、分代回收为辅。del 只减少引用计数不保证立即释放。循环引用由 GC 模块处理 gc.collect()。sys.getrefcount() 查看引用数。weakref 创建弱引用避免循环。__slots__ 减少实例内存开销。tracemalloc 追踪内存分配。"),
    ("Python 正则表达式性能优化", "lesson",
     "预编译 re.compile() 避免重复解析。使用非捕获组 (?:...) 减少开销。re.finditer() 流式处理大文本。注意回溯陷阱 (catastrophic backtracking)，原子组 (>...) 防止回溯。re.DOTALL 让 . 匹配换行。html/xml 解析不要用正则，用 lxml/BeautifulSoup。"),
    ("Python 日志系统最佳实践", "lesson",
     "logging 模块层级：Logger → Handler → Formatter。loggers 按模块名组织，子 logger 继承父配置。RotatingFileHandler 按大小轮转，TimedRotatingFileHandler 按时间。structlog 提供结构化日志。不要用 root logger 直接 log，创建具名 logger。敏感信息不要记录。"),
    ("Python 包管理和虚拟环境", "lesson",
     "venv 创建隔离环境。pip install -e . 开发模式安装。pyproject.toml 替代 setup.py 作为项目元数据。requirements.txt 锁定依赖版本，配合 pip-tools 管理。poetry/hatch/pdm 提供更完善的工作流。注意依赖安全审计 pip-audit。"),
    ("Python 异常处理最佳实践", "lesson",
     "捕获具体异常类不要用 bare except。try/except 包裹最小范围。else 子句在无异常时执行，finally 始终执行。raise from e 保留异常链，raise from None 抑制上下文。自定义异常继承 Exception 不是 BaseException。用 contextlib.suppress 忽略特定异常。"),
    ("Python 多进程编程模式", "lesson",
     "multiprocessing 绕过 GIL 实现真并行。Pool.map/imap 分发任务。进程间用 Queue/Pipe 通信，注意 picklable 限制。multiprocessing.Manager 提供共享数据结构。Process 的 daemon 标记控制主进程退出行为。concurrent.futures.ProcessPoolExecutor 提供更简洁接口。"),
    ("Python 代码性能分析工具", "lesson",
     "cProfile 统计函数调用次数和时间。profile 模块相同接口但纯 Python 实现更慢。line_profiler 逐行分析。memory_profiler 追踪内存。py-spy 无需侵入的采样分析器。perftool 可视化火焰图。timeit 微基准测试注意 JIT/缓存效应。"),
    ("Python C 扩展开发", "lesson",
     "Python C API 直接操作 PyObject。扩展模块用 PyMODINIT_FUNC 注册。引用计数 Py_INCREF/Py_DECREF 管理内存。Cython 快速编写 C 扩展。cffi 纯 Python 调用 C。pybind11 是 C++ 扩展首选。ctypes 加载动态库无需编译但较慢。"),
    ("Python 并发编程全景", "lesson",
     "线程 (threading): GIL 限制真并行，适合 I/O。进程 (multiprocessing): 真并行，IPC 开销。协程 (asyncio): 单线程异步，高并发 I/O。concurrent.futures: 统一线程池/进程池接口。选择建议: I/O 多用 asyncio，CPU 多用 multiprocessing。"),
    ("Python 数据库操作模式", "lesson",
     "DB-API 2.0 标准接口 (connect/cursor/execute/fetchall)。SQLAlchemy Core 提供 SQL 表达式语言，ORM 提供对象映射。使用连接池 (QueuePool/NullPool) 管理连接。上下文管理器自动提交/回滚。批量操作用 executemany。注意 SQL 注入用参数化查询。"),
    ("Python Web 框架对比", "lesson",
     "FastAPI: 异步优先，自动生成 OpenAPI 文档，Pydantic 校验。Flask: 轻量级，插件生态丰富。Django: 全栈框架，ORM/Admin/模板引擎内置。Sanic: 异步 HTTP 服务器。Litestar: 类型化 Web 框架。选择: 新项目用 FastAPI，Django 适合 CMS/管理后台。"),
    ("Python 测试金字塔", "lesson",
     "单元测试 (pytest): 验证个别函数。集成测试: 验证模块协作。端到端测试: 模拟用户行为。pytest fixtures 管理测试状态。conftest.py 共享 fixtures。mock 替换外部依赖。parametrize 覆盖多个输入。coverage 确保不低于 80%。TDD: 红→绿→重构。"),
    ("Python 序列化格式选型", "lesson",
     "JSON: 通用格式，不支持二进制和自定义类型。pickle: Python 专有，有安全风险，不支持跨版本。msgpack: 二进制格式，高性能。protobuf: 预定义 schema，多语言支持。YAML: 可读性强，用于配置文件。TOML: 配置文件首选。dataclass 配合 __json__ 自定义序列化。"),
    ("Python 闭包与变量作用域", "lesson",
     "Python 有 LEGB 作用域规则 (Local/Enclosing/Global/Builtin)。闭包捕获外部变量，nonlocal 声明写入权限。循环中创建闭包的延迟绑定陷阱 (后期绑定循环变量) 通过默认参数或 partial 解决。函数内 global 声明可写全局变量。inspect 模块可获取闭包变量。"),
    ("Python 迭代器与生成器", "lesson",
     "迭代器: __iter__/__next__ 协议。生成器: yield 暂停执行保存状态。生成器表达式: (x for x in iter) 惰性求值。yield from 委托子生成器。send() 向生成器注入值。itertools 提供常用迭代工具。注意生成器用完无法重置，用 tee/cache 缓存。"),
    ("Python 元类编程", "lesson",
     "元类是类的类，type 是所有类的默认元类。__new__ 创建类对象，__init__ 初始化。__prepare__ 控制类命名空间。常见用途: ORM (Django Model)、单例模式、接口检查、自动注册子类 (abc.ABCMeta)。过度使用降低可读性，优先考虑类装饰器。"),
    ("Python 异步上下文管理器", "lesson",
     "__aenter__/__aexit__ 支持 async with。contextlib.asynccontextmanager 将异步生成器转为异步上下文管理器。用于异步数据库连接、HTTP 会话管理。注意 asyncio 中阻塞 __aenter__ 会阻塞事件循环。异步文件操作使用 aiofiles。"),
    ("Python 描述符协议", "lesson",
     "描述符是实现 __get__/__set__/__delete__ 的对象。property 是内置描述符。数据描述符 (有 __set__) 优先于实例字典。非数据描述符 被实例同名属性覆盖。常见用途: 类型检查、惰性加载 (cached_property)、ORM 字段映射。描述符是 @property/@classmethod/@staticmethod 的基础。"),
    ("Python 安全编码实践", "lesson",
     "SQL 注入用参数化查询防。命令注入用 subprocess.run(shell=False)。路径遍历用 os.path.abspath 防。敏感信息不硬编码，用环境变量或密钥管理服务。pyjwt 处理 JWT 验证签名验证。ssl 模块处理证书验证。defusedxml 防 XML 注入攻击。hashlib 用 bcrypt/scrypt 做密码哈希。"),
    ("Python 性能优化清单", "lesson",
     "1. 选择合适数据结构 (list/set/dict/deque)。2. 局部变量查找比全局快。3. 列表推导比 for 循环快。4. map/filter 对简单操作更快。5. 避免在循环中创建新对象。6. 用 __slots__ 减少内存。7. 生成器代替列表减少内存。8. functools.lru_cache 缓存重复计算。9. 字符串拼接用 join。10. 专业库 (numpy/pandas) 处理数值计算。"),

    # ── 系统架构 (40条) ──
    ("微服务架构设计原则", "decision",
     "单一职责：每服务负责一个业务域。自治部署：独立部署不影响其他服务。数据去中心化：每服务自有数据库避免耦合。异步通信：事件驱动减少同步耦合。容错设计：熔断器/重试/超时。可观测性：集中日志/指标/追踪。API Gateway: 统一入口处理路由/认证/限流。Service Mesh: 边车代理处理通信。利弊：运维复杂度上升，不适合小项目。"),
    ("事件驱动架构模式", "architecture",
     "生产者发布事件，消费者异步处理。消息队列 (Kafka/RabbitMQ) 保证可靠传输。事件溯源: 存储所有事件，状态从事件流重建。CQRS: 读写分离，查询端用优化过的读模型。死信队列: 处理失败消息。幂等消费: 相同事件多次处理结果一致。顺序保证: 分区键管理顺序。"),
    ("C4 模型架构可视化", "architecture",
     "Level 1 (Context): 系统与外部用户/系统关系。Level 2 (Container): 应用/数据存储等容器。Level 3 (Component): 容器内组件关系。Level 4 (Code): 类/接口级别。相比 UML，C4 更关注系统全景。PlantUML/Mermaid 生成图表。Structurizr 提供 DSL 工具。结构图可保存在代码仓库与架构同步。"),
    ("分布式系统 CAP 定理", "lesson",
     "CAP: 一致性(Consistency)、可用性(Availability)、分区容错(Partition Tolerance) 三者最多同时满足两个。现实网络分区不可避免，所以系统必须在 CP 或 AP 之间取舍。ZooKeeper 选 CP，Cassandra 选 AP。PACELC 扩展: 分区时选 A/C，无分区时选低延迟/一致性。BASE (Basically Available, Soft state, Eventually consistent) 作为 ACID 的对立方案。"),
    ("分布式一致性算法 Raft", "lesson",
     "Raft 将一致性分解为: 领导选举 (Leader)、日志复制 (Log Replication)、安全 (Safety)。Leader 处理所有写请求。follower 复制日志后提交。term 递增选举，避免分裂投票。Raft 比 Paxos 更直观。etcd、TiKV 使用 Raft。日志匹配性质保证提交的日志最终一致。"),
    ("负载均衡策略对比", "architecture",
     "轮询 (Round Robin): 均匀分配。最少连接: 选择当前连接数最少的服务器。IP 哈希: 同一客户端始终路由到同一服务器，适合有状态服务。加权: 根据服务器处理能力分配。动态 (Least Response Time): 选择响应最快的服务器。Layer 4 (传输层): 基于 IP/端口，性能高。Layer 7 (应用层): 基于 HTTP 头/内容，灵活。一致性哈希: 增减服务器时最小化缓存失效。"),
    ("高可用架构设计", "architecture",
     "冗余: 多副本放置在不同故障域。自动故障转移: 心跳检测 + 自动切换。降级: 关闭非核心功能保障核心服务。限流: 令牌桶/漏桶限制请求速率。集群: 多节点组成集群，故障节点自动摘除。数据复制: 同步 (强一致性) 或异步 (最终一致性)。容量规划: N+1 冗余至少。灰度发布/蓝绿部署: 减少变更风险。"),
    ("缓存架构策略", "architecture",
     "缓存层次: 浏览器 → CDN → 反向代理 → 应用缓存 → 分布式缓存 → 数据库。缓存模式: Cache-Aside (旁路)、Read-Through (读穿)、Write-Behind (写后)、Write-Through (写穿)。缓存穿透: 布隆过滤器拦截不存在 key。缓存雪崩: 随机过期时间分散。缓存击穿: 互斥锁重建热点 key。淘汰策略: LRU/LFU/TTL。数据一致性: 先更新 DB 再删除缓存。"),
    ("数据库分库分表方案", "architecture",
     "垂直拆分: 按业务模块拆分不同数据库。水平拆分: 按某键 (user_id/order_id) 哈希或范围分片。分片键选择: 避免热点，考虑查询模式。ShardingSphere/vitess 提供中间件方案。跨分片查询: 全局表/字典表冗余或查询路由聚合。分布式 ID: 雪花算法/号段模式。注意分布式事务的复杂性。"),
    ("领域驱动设计 DDD", "architecture",
     "核心: 通用语言 (Ubiquitous Language) 连接代码和业务。战术模式: Entity (有标识)、Value Object (无标识不可变)、Aggregate (聚合根保证一致性)、Domain Event (领域事件)、Repository (聚合持久化)、Domain Service (无状态领域逻辑)。战略模式: Bounded Context (限界上下文)，Context Map (上下文映射) 定义集成方式。Event Storming 发现领域模型。"),
    ("六边形架构 (端口适配器)", "architecture",
     "核心领域逻辑独立于外部依赖。端口 (Ports): 领域定义的接口。适配器 (Adapters): 实现端口，连接数据库/消息/UI。驱动端 (Driving/Primary): 用户/API 调用领域。被驱动端 (Driven/Secondary): 领域调用数据库/外部服务。依赖方向始终向内: 外层依赖内层。好处: 测试时轻松替换适配器为 mock。"),
    ("消息队列选型指南", "decision",
     "Kafka: 高吞吐，持久化，适合日志/流处理。RabbitMQ: AMQP 协议，灵活路由，适合任务分发。Redis Streams: 轻量级，适合简单场景。NATS: 低延迟，云原生。Pulsar: 多租户，存储计算分离。选择依据: 吞吐量、延迟要求、持久化需求、运维复杂度、社区生态。消息幂等性: 消费端处理重复消息。"),
    ("API 设计最佳实践", "lesson",
     "RESTful: 资源导向 URL，HTTP 方法表达操作。版本控制: URL 前缀 (/v1/) 或 Accept 头。分页: offset/limit 或 cursor based。错误格式: 统一的 JSON 结构含 code/message/details。认证: Bearer Token (JWT) 或 OAuth2。限流: X-RateLimit-* 头反馈。HATEOAS: 响应含相关链接。OpenAPI/Swagger 文档自动生成。"),
    ("DDD 限界上下文集成模式", "architecture",
     "共享内核 (Shared Kernel): 两个上下文共享部分模型，紧密协作。客户/供应商 (Customer/Supplier): 上游决定接口，下游适配。顺从 (Conformist): 下游完全跟随上游，放弃自主。防腐层 (Anti-Corruption Layer): 下游创建翻译层隔离上游模型。开放主机服务 (OHS): 上游定义公共 API。发布语言 (Published Language): 通用文档格式。"),
    ("分布式链路追踪", "architecture",
     "Trace: 一次完整请求的调用链。Span: 一次 RPC/DB 调用。Context Propagation: 跨进程传递 trace_id/span_id。OpenTelemetry: CNCF 标准，集成 Jaeger/Zipkin。采样策略: 固定比例或自适应 (错误全采样)。用处: 定位慢调用、理解依赖拓扑、排查异常。注意追踪数据量大，需设置保留策略。"),
    ("时间序列数据库选型", "decision",
     "InfluxDB: 写入性能优，类 SQL 查询。Prometheus: 拉取模式，适合监控。TimescaleDB: PostgreSQL 扩展，SQL 兼容。ClickHouse: 列式存储，分析查询极快。VictoriaMetrics: 兼容 Prometheus，压缩率高。选择依据: 数据量级、查询模式 (点查询/范围扫描)、运维能力、SQL 需求。"),
    ("配置管理策略", "architecture",
     "环境变量: 简单直接，12-Factor 推荐。配置文件: 多环境 (dev/staging/prod) 分文件。配置中心: Apollo/Nacos，动态更新，灰度发布。Kubernetes ConfigMap/Secret: 容器化环境首选。敏感信息加密: Vault/HashiCorp 管理密钥。配置即代码: 纳入版本控制。feature flags 独立于常规配置管理。"),
    ("监控与可观测性", "architecture",
     "三大支柱: Metrics (指标)、Traces (追踪)、Logs (日志)。RED 方法论: Rate/Errors/Duration。USE 方法论: Utilization/Saturation/Errors。SLI 服务水平指标，SLO 服务水平目标，SLA 服务等级协议。告警: 设置合理阈值避免告警疲劳。Grafana 可视化，AlertManager 告警路由。错误预算: 允许的不可用时间，用于决策发布风险。"),
    ("云原生 12-Factor 应用", "lesson",
     "1. 代码库: 一份代码多份部署。2. 依赖: 显式声明隔离。3. 配置: 存储在环境。4. 后端服务: 作为附加资源。5. 构建/发布/运行: 严格分离。6. 进程: 无状态。7. 端口绑定: 通过端口暴露。8. 并发: 进程模型扩展。9. 可处置: 快速启动优雅终止。10. 环境等价: 开发/生产尽可能一致。11. 日志: 作为事件流。12. 管理进程: 作为一次性进程。"),
    ("熔断器设计模式", "architecture",
     "三种状态: Closed (正常)、Open (熔断)、Half-Open (试探)。Closed: 正常调用，记录失败率。超过阈值 → Open: 快速失败，不调远程。等待一段后 → Half-Open: 允许部分请求试探。成功 → Closed，失败 → Open。常见实现: Hystrix/Resilience4j/Sentinel。配合重试和超时使用，避免级联失败。"),
    ("灰度发布策略", "architecture",
     "金丝雀发布: 少量节点先更新，验证后全量。蓝绿部署: 两套完整环境切换。滚动更新: 逐个替换实例，Kubernetes 默认方式。特性开关 (Feature Flag): 代码部署 + 运行时控制。流量路由: 通过标签/权重分配。回滚: 问题发生时一键回退。关键: 监控异常、错误率、延迟变化，自动熔断。"),
    ("分布式事务解决方案", "architecture",
     "2PC (两阶段提交): Prepare + Commit，强一致但阻塞。TCC (Try-Confirm-Cancel): 业务层两阶段。Saga: 编排/协调两种模式，长事务拆解为本地事务加补偿。事务消息: 本地事务 + 消息表，RocketMQ 支持。Seata: AT 模式 (自动回滚) 和 TCC 模式。消息最终一致性: 最常用，允许短暂不一致。"),
    ("分布式 ID 生成方案", "architecture",
     "UUID: 无序，作为主键影响索引性能。雪花算法 (Snowflake): 时间戳(41b) + 机器 ID(10b) + 序号(12b)，有序递增。号段模式: Leaf-segment 预分配号段减少 DB 压力。Redis: INCRBY 原子生成。美团 Leaf: 号段 + 雪花双模式。关键: 时钟回拨处理策略，ID 有序性对 MySQL InnoDB 插入性能影响。"),
    ("服务降级与限流", "architecture",
     "降级: 关闭非核心功能或返回兜底结果。限流: 令牌桶 (平滑)、漏桶 (匀速率)、滑动窗口 (精确)。熔断: 停止调用故障服务。集群限流: Redis + Lua 原子化。Sentinel 提供规则配置。自适应限流: BBR 算法根据系统负载动态调整。优雅降级: 核心链路至少返回部分结果。"),
    # ... more memories ...
]

# Expand to 200 with varied content
MORE_MEMORIES = [
    ("Kubernetes Pod 调度策略", "lesson", "nodeName 硬指定节点。nodeSelector 简单标签匹配。亲和性 (Affinity): nodeAffinity 软硬亲和，podAffinity/podAntiAffinity 控制 Pod 间位置。污点与容忍 (Taint/Toleration): 节点排斥 Pod。拓扑分布约束 (TopologySpreadConstraints): 均匀分布到不同 zone。优先级与抢占: 高优 Pod 可驱逐低优。资源请求 (requests/limits): 调度依据和运行限制。"),
    ("Git 工作流策略", "lesson", "Git Flow: master + develop + feature/release/hotfix 分支，适合有版本发布的项目。GitHub Flow: master + feature 分支，CI/CD 友好。GitLab Flow: 环境分支 (预发布/生产) 控制部署。Trunk-Based: 短生命分支，小批量频繁合并，适合大团队。Commit 规范: Conventional Commits (feat/fix/docs/refactor)。"),
    ("CI/CD 流水线设计", "architecture", "持续集成: 代码提交自动构建+测试。持续交付: 自动化测试 + 手动发布决策。持续部署: 通过测试自动上线。Pipeline 阶段: 代码检查 → 单元测试 → 构建 → 集成测试 → 安全扫描 → 部署到环境。制品仓库: Docker Registry / Nexus / Artifactory。GitOps: Git 作为唯一声明源，Operator 自动同步。"),
    ("数据一致性模式", "architecture", "强一致性: 同步写所有副本，性能低。最终一致性: 异步复制，短暂不一致。因果一致性: 有因果关系的操作有序。单调读: 不会读到越来越旧的数据。读己之写: 写入后立即能读到。前缀一致性: 序列不交错。实现方式: 版本向量、CRDT 数据类型、逻辑时钟。反熵 (Anti-Entropy): 后台修复不一致数据。"),
    ("设计模式: 单例模式", "pattern", "确保类只有一个实例并提供全局访问点。Python 用 module-level 变量天然单例。线程安全使用 double-checked locking 或模块导入特性。Borg 模式: 共享状态而非身份 (所有实例共享 __dict__)。使用场景: 连接池、配置管理、日志对象。避免过度使用，它引入全局状态增加耦合和测试难度。"),
    ("设计模式: 工厂模式", "pattern", "简单工厂: 一个工厂类根据参数创建不同产品。工厂方法: 子类决定创建哪种产品。抽象工厂: 创建相关对象族而不指定具体类。Python 中常简化为函数返回不同类实例。注册表模式: 字典映射类型名到类。使用场景: 对象创建逻辑复杂、需要解耦客户端和具体类。"),
    ("设计模式: 观察者模式", "pattern", "对象(Subject)维护观察者列表，状态变化时通知所有观察者。Python: 可用列表维护回调函数或使用 signal/slot 库。发布订阅: 观察者模式变体，通过消息队列解耦 (发布者和订阅者互不知道)。弱引用避免内存泄漏。RxPy 响应式编程库实现流式观察。使用场景: GUI 事件处理、消息通知、数据绑定。"),
    ("设计模式: 策略模式", "pattern", "定义一系列算法，将每算法封装为可互换的对象。客户端选择策略而无需知道实现细节。Python: 函数是一等公民，可直接传函数替代策略类。与工厂配合: 工厂创建策略，客户端组合使用。使用场景: 排序方式选择、支付策略、压缩算法选择。避免策略过多导致的类膨胀。"),
    ("设计模式: 装饰器模式", "pattern", "动态给对象添加额外职责，比继承更灵活。通过包装器层层嵌套。Python 中 @ 语法糖本质是函数组合。注意包装层次过多影响性能。与代理模式区别: 装饰器增强功能，代理控制访问。使用场景: I/O 流的层层包装、中间件管道、缓存/日志/验证。"),
    ("设计模式: 适配器模式", "pattern", "将一个接口转换为客户期望的另一接口。类适配器: 通过多继承实现。对象适配器: 通过组合 (prefer)。Python 中协议允许鸭子类型，降低了适配器需求。将旧系统 API 适配到新接口。使用场景: 第三方库接口适配、遗留代码兼容层、数据格式转换。"),

    # AI & Machine Learning (30)
    ("Transformer 注意力机制", "lesson", "自注意力: 序列内元素互相注意，计算 query/key/value 矩阵。多头注意力: 多个独立注意力头捕捉不同子空间信息。位置编码: 正弦或可学习编码加入位置信息。缩放点积: 除以 sqrt(d_k) 防止 softmax 梯度消失。计算复杂度 O(n²) 对长序列是瓶颈。Flash Attention 优化内存访问。"),
    ("大语言模型训练方法", "lesson", "预训练 (Pre-training): 海量无标注文本，自回归语言建模。监督微调 (SFT): 指令-回答对训练遵循指令。RLHF (人类反馈强化学习): 训练奖励模型 + PPO 策略优化。DPO (直接偏好优化): 绕过奖励模型直接优化。LoRA (低秩适配): 仅训练低秩矩阵高效微调。QLoRA 降低内存同时保持精度。"),
    ("RAG 检索增强生成", "architecture", "检索 + 生成 + 提示 = RAG。文档切片策略: 固定长度/递归分割/语义分割。Embedding 模型选型: 维度/多语言/最大序列长度。向量数据库: Milvus/Qdrant/Weaviate/pgvector。检索优化: 混合搜索、重排序、HyDE 假设文档。上下文窗口利用率: 合并相关片段、内容组织策略。评估: 忠实度、答案相关性、上下文相关度。"),
    ("Agent 框架设计", "architecture", "ReAct 模式: 推理(Thought) + 行动(Action) + 观察(Observation) 循环。工具使用: 函数签名 + 描述让 LLM 选择调用。规划: 任务分解为子目标，动态调整。记忆: 短期(上下文窗口) + 长期(向量检索)。反思: 自我评估改进策略。多 Agent: 角色分工 + 消息协作。安全: 工具调用限制、输入验证。"),
    ("Prompt 工程最佳实践", "lesson", "少样本提示: 提供 2-3 个示例指导格式和风格。思维链 (CoT): '让我们一步步思考' 激发推理。角色设定: 设定专业角色提升质量。结构化输出: 指定 JSON/XML 格式。迭代优化: 测试 → 分析 → 改进。反面教材: 明确不要做什么。分步提示: 复杂任务拆解为多轮交互。上下文管理: 动态压缩/总结长对话。"),
    ("A-Mem 动态记忆架构", "architecture", "动态记忆: 自适应分配注意力和存储资源。新信息根据惊讶度 (Surprise) 决定记忆强度。遗忘机制: 衰减函数模拟艾宾浩斯曲线。层次化记忆: 从感觉记忆到情景记忆到语义记忆。预测编码: 记忆用于生成预测，减少处理冗余。与 Transformer 结合: 外部记忆槽作为上下文补充。"),
    ("向量数据库技术选型", "decision", "Milvus: 分布式架构，支持多种索引 (IVF/HNSW)，GPU 加速。Qdrant: Rust 编写，支持过滤和有效载荷。Weaviate: 内置 GraphQL API，对象属性与向量融合。Pinecone: SaaS 免运维，但数据在外。pgvector: PostgreSQL 扩展，与事务数据并存。选择依据: 数据量级 (百万/十亿)、低延迟需求、运维能力、是否需要过滤。"),
    ("LLM 幻觉问题与缓解", "lesson", "幻觉类型: 事实错误、虚构引用、过度自信错误推理。缓解: RAG 检索事实依据、限制回答范围、CoT 推理验证、自我一致性检查 (多次采样投票)。提示引导: '如果不确定就说不知道'。温度参数调节: 低温度减少随机性。后处理: 事实校验调用外部知识库。完全消除幻觉当前不可行，重点在设计容错系统。"),

    # Tools & DevOps (30)
    ("Docker 容器优化", "lesson", "多阶段构建: 分离构建环境和运行环境减小镜像。选择轻量基础镜像: alpine (注意 musl 兼容) 或 distroless。层缓存优化: 不常变的放前面。.dockerignore: 排除不需要文件。安全扫描: Trivy/Clair 检查漏洞。资源限制: --memory/--cpus 防止资源争抢。健康检查: HEALTHCHECK 指令确保容器存活。"),
    ("Kubernetes 资源管理", "lesson", "Pod: 最小调度单元，共享网络和存储命名空间。Deployment: 声明副本数和更新策略。Service: 稳定 IP/DNS 发现 Pod。Ingress: 外部 HTTP 路由到 Service。ConfigMap/Secret: 配置与代码分离。RBAC: 角色和角色绑定控制权限。PV/PVC: 持久存储抽象。HPA: 水平自动扩缩基于 CPU/内存。"),
    ("Terraform IaC 实践", "lesson", "声明式: 描述期望状态而非步骤。Provider: 云平台插件 (AWS/Azure/GCP)。State: 资源映射，远程存储 (S3 + DynamoDB) 支持团队协作。Module: 可复用的基础设施组件。Workspace: 环境隔离。Plan -> Apply 工作流: 预览后应用变更。敏感变量: 标记 sensitive 防止日志泄露。资源依赖: 隐式引用自动排序。"),
    ("日志采集与处理", "architecture", "采集: Filebeat/Fluentd/Logstash 从文件/stdout 收集。传输: Kafka 做缓冲削峰。处理: Logstash/Fluentd 过滤/解析/丰富。存储: ElasticSearch 搜索友好 / Loki 轻量高效 / ClickHouse 分析性能。查询: Kibana (ES) / Grafana (Loki)。结构化日志: JSON 格式避免正则解析。日志级别: DEBUG/INFO/WARN/ERROR 明确区分。"),
    ("性能压测方案", "architecture", "压测工具: JMeter (GUI)、wrk/wrk2 (HTTP)、vegeta (Go)、k6 (JS 脚本)、Locust (Python)。观察指标: QPS/RPS、P50/P90/P99 延迟、错误率、CPU/内存/网络。压测环境: 尽可能与生产配置一致。热身: 让 JIT/缓存预热后再收集。渐进式加压: 阶梯增加找到拐点。注意不要压测线上生产环境。"),
    ("GitOps 部署流水线", "architecture", "单一事实源: Git 存储库定义期望状态。Operator 模式: ArgoCD/Flux 监控 git 变更自动同步。Pull vs Push: Operator 拉取而非 CI 推送。回滚: Git revert 触发自动回滚。多集群: ApplicationSet 管理多集群部署。差异可视化: ArgoCD Web UI 展示 desired vs actual。密钥管理: Sealed Secrets 或 External Secrets Operator。"),
    ("身份认证与授权", "architecture", "OAuth2.0: 授权码流程/隐式/密码/客户端凭证。OIDC: 在 OAuth2 上加身份层，JWT 做 ID Token。SAML: 企业 SSO 常用。RBAC: 角色绑定权限。ABAC: 属性动态判定授权。JWT: Header.Payload.Signature，注意不要存敏感信息。Session 管理: 短生命周期 access token + 长生命周期 refresh token。2FA: TOTP 或 WebAuthn。"),
    ("Linux 性能排查工具", "lesson", "top/htop: 实时进程和系统资源。vmstat: 虚拟内存统计 (swap/si/so)。iostat: 磁盘 I/O (await/util)。netstat/ss: 网络连接状态。strace: 跟踪系统调用。perf: 性能分析采样。tcpdump: 抓包分析。dmesg: 内核日志。lsof: 列出打开的文件/端口。pidstat: 按进程统计资源。"),
    ("安全编码清单", "lesson", "输入验证: 所有用户输入视为不可信。输出编码: 按上下文(XSS/SQL/OS)正确编码。认证: 多因素认证，会话过期。授权: 最小权限原则，检查每个请求。加密: TLS 传输，静态数据加密，密钥轮转。日志: 记录安全事件但不包含敏感数据。依赖: 定期扫描 CVE 漏洞。CSRF: 同源检查 + Token。SSRF: URL 白名单。" ),
    ("前端性能优化", "lesson", "关键渲染路径优化: 减少关键资源大小(CSS/JS)。代码分割: 按路由懒加载。Tree Shaking: 移除未使用代码。图片优化: WebP/AVIF 格式，srcset 响应式。CDN: 全球节点加速静态资源分发。预加载: <link rel=preload>。缓存策略: Service Worker + Cache-Control。虚拟列表: 大列表只渲染可见项。Bundle 分析: webpack-bundle-analyzer。"),
]

ALL_MEMORIES = MEMORY_POOL + MORE_MEMORIES
ALL_MEMORIES = ALL_MEMORIES[:200]  # Ensure exactly 200

# ── 100 Recall Queries ──
RECALL_QUERIES = [
    "Python 异步编程", "微服务架构", "设计模式", "API 设计", "数据库优化",
    "缓存策略", "分布式系统", "容器化部署", "CI/CD 流水线", "代码质量",
    "Python 类型系统", "事件驱动", "高可用架构", "Kubernetes 调度", "日志监控",
    "RAG 检索", "LLM 训练", "Agent 设计", "向量数据库", "安全编码",
    "性能优化", "消息队列", "数据一致性", "负载均衡", "熔断降级",
    "Python 装饰器", "DDD 设计", "Git 工作流", "Docker 最佳实践", "Terraform",
    "Transformer 架构", "Prompt 工程", "会议安排", "项目管理", "代码审查",
    "Python 多线程", "分布式事务", "配置管理", "Linux 性能", "前端优化",
    "Python 测试", "GraphQL vs REST", "服务网格", "灰度发布", "可观测性",
    "Python 内存管理", "Cap 定理", "认证授权", "降级策略", "监控告警",
    "Python 协程", "六边形架构", "消息幂等", "网络协议", "密码安全",
    "Python 元类", "Saga 事务", "C4 模型", "GitOps", "2FA 认证",
    "Python 迭代器", "责任链模式", "连接池", "API Gateway", "JWT 安全",
    "Python 上下文管理", "命令模式", "读写分离", "服务发现", "CSRF 防护",
    "Python 闭包", "访问者模式", "分库分表", "配置中心", "SQL 注入",
    "Python dataclass", "状态模式", "分布式锁", "链路追踪", "XSS 防御",
    "Python 正则", "桥接模式", "限流算法", "日志结构化", "SSRF 防护",
    "Python 序列化", "享元模式", "时钟回拨", "火焰图分析", "供应链安全",
]

# ── Token estimation ──
TOKEN_MULTIPLIER = 0.3  # rough: 1 char ≈ 0.3 tokens

def estimate_tokens(text: str) -> int:
    return int(len(text) * TOKEN_MULTIPLIER)

def main():
    from sisyphus.memory.store import MemoryStore
    from sisyphus.memory.refined import RefinedStore
    from sisyphus.memory.dream import DreamEngine
    from sisyphus.memory.recall import Recall
    from sisyphus.memory.subagent import SubagentLauncher
    from sisyphus.memory.compression import Compressor

    tmp = Path(tempfile.mkdtemp()) / "mem"
    store = MemoryStore(base_path=tmp)
    refined = RefinedStore(base_path=tmp)
    subagent = SubagentLauncher(store_path=tmp)

    total_steps = 1 + 1 + len(RECALL_QUERIES) + 1  # write + dream + recalls + compress
    completed = 0
    total_tokens = 0
    start_time = time.time()

    def report(msg):
        nonlocal completed
        completed += 1
        elapsed = time.time() - start_time
        pct = completed / total_steps * 100
        bar = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
        print(f"[{bar}] {pct:.0f}% ({completed}/{total_steps}) | {elapsed:.0f}s | {msg}")

    # ── Step 1: Write 200 Memories ──
    print("\n╔══════════════════════════════════════════════════════════════╗")
    print("║  Sisyphus 大规模记忆测试 — 目标 100 万 token               ║")
    print("╚══════════════════════════════════════════════════════════════╝\n")

    for i, (title, mem_type, content) in enumerate(ALL_MEMORIES):
        store.create(title=title, type=mem_type, content=content, tags=[mem_type], importance=min(10, 5 + i % 5))
    content_chars = sum(len(m.content) + len(m.title) for m in store.list())
    write_tokens = estimate_tokens(" ".join(m.content + m.title for m in store.list()))
    total_tokens += write_tokens
    report(f"写入 200 条记忆 (content ~{content_chars} chars ≈ {write_tokens:,} tokens)")

    # ── Step 2: Dream ──
    print("\n🧠 Dream 反射中...")
    engine = DreamEngine(store=store, refined_store=refined, subagent=subagent)
    dream_start = time.time()
    reflections = engine.dream()
    dream_elapsed = time.time() - dream_start
    dream_tokens = write_tokens + estimate_tokens(json.dumps([{"id": r.id, "title": r.title} for r in reflections]))
    total_tokens += dream_tokens
    report(f"Dream: {len(reflections)} reflections ({dream_tokens:,} tokens, {dream_elapsed:.0f}s)")
    for r in reflections[:5]:
        print(f"  📍 {r.title}")

    # ── Step 3: 100 Recall Queries ──
    print(f"\n🔍 运行 {len(RECALL_QUERIES)} 次 Recall 查询...")
    recall = Recall(store=store, subagent=subagent)
    recall_hits = 0
    recall_fails = 0

    for i, query in enumerate(RECALL_QUERIES):
        try:
            results = recall.search(query=query, top_k=5)
            recall_tokens = estimate_tokens(query) + 6000  # ~6K tokens for memory index per call
            total_tokens += recall_tokens
            if results:
                recall_hits += 1
            else:
                recall_fails += 1
            if (i + 1) % 10 == 0:
                report(f"Recall {i+1}/{len(RECALL_QUERIES)} ({recall_hits} hits, {recall_fails} misses)")
        except Exception as e:
            recall_fails += 1
            print(f"  ⚠️  Recall {i+1} 失败: {e}")

    report(f"Recall 完成: {recall_hits} hits, {recall_fails} misses")

    # ── Step 4: Compress ──
    print("\n📦 Compress 压缩中...")
    compressor = Compressor(store=store, subagent=subagent)
    compress_start = time.time()
    compressed = compressor.compress()
    compress_elapsed = time.time() - compress_start
    compress_tokens = write_tokens  # same content going to LLM
    total_tokens += compress_tokens
    report(f"Compress: {compressed} memories ({compress_tokens:,} tokens, {compress_elapsed:.0f}s)")

    # ── Summary ──
    total_elapsed = time.time() - start_time
    print("\n" + "=" * 65)
    print("  测试完成!")
    print("=" * 65)
    print(f"  总耗时:          {total_elapsed:.0f}s ({total_elapsed/60:.1f} min)")
    print(f"  估计 Token 用量: {total_tokens:,}")
    print(f"  记忆总数:        {len(store.list())}")
    print(f"  反射数:          {len(reflections)}")
    print(f"  Recall 命中率:   {recall_hits}/{len(RECALL_QUERIES)} ({recall_hits/len(RECALL_QUERIES)*100:.0f}%)")
    print("=" * 65)

    # Write report
    report_path = Path.home() / "sisyphus-scale-test.json"
    result = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_tokens_estimated": total_tokens,
        "elapsed_seconds": total_elapsed,
        "memories_written": 200,
        "reflections_generated": len(reflections),
        "recall_queries": len(RECALL_QUERIES),
        "recall_hits": recall_hits,
        "recall_misses": recall_fails,
        "compressed": compressed,
        "model": os.environ.get("SISYPHUS_LLM_MODEL", "unknown"),
    }
    json.dump(result, open(report_path, "w"), indent=2, ensure_ascii=False)
    print(f"\n报告已保存: {report_path}")

if __name__ == "__main__":
    main()

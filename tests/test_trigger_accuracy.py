"""Trigger accuracy benchmark — 60 annotated test samples.

Each sample: (message, expected_trigger: bool, expected_level: str)
Level meanings: L0 (signal words), L1 (periodic/topic), L2 (backoff), "-" (no trigger)
"""

import pytest
from sisyphus.memory.trigger import should_retrieve_memory

SAMPLES = [
    # ── L0: explicit signal words ──
    ("remember this: the API key is in .env", True, "L0"),
    ("do you recall our decision about Postgres vs MySQL", True, "L0"),
    ("check memory for past security incidents", True, "L0"),
    ("回顾一下上个月的架构评审结果", True, "L0"),
    ("记住：生产环境禁止直接操作数据库", True, "L0"),
    ("记下了吗？我们上次定的那个规范", True, "L0"),
    ("把我刚才说的存下来", True, "L0"),
    ("把这个bug的修复方案备忘一下", True, "L0"),

    # ── L0: history references ──
    ("之前我们讨论过微服务的拆分方案", True, "L0"),
    ("上次定下来的那个API命名规范是什么", True, "L0"),
    ("前面提到过的部署流程再确认一遍", True, "L0"),
    ("上次我们说过要用jest替代mocha", True, "L0"),
    ("我们之前聊过日志采集的方案对吧", True, "L0"),

    # ── L0: memory questions ──
    ("你记得我们数据库的端口号吗", True, "L0"),
    ("你知道项目中用了哪些第三方库吗", True, "L0"),
    ("根据记忆中的配置，网关超时是多少", True, "L0"),
    ("你了解我们上次CI/CD流水线的改动不？", True, "L0"),
    ("以前讨论过缓存策略对吧", True, "L0"),

    # ── L0: mixed English/Chinese ──
    ("recall 我们上次讨论过的认证方案", True, "L0"),
    ("remember 之前的 JWT token 过期时间", True, "L0"),

    # ── should NOT trigger: normal chat ──
    ("帮我写一个函数处理用户输入", False, "-"),
    ("这段代码有bug，怎么修", False, "-"),
    ("测试通过了，还有别的吗", False, "-"),
    ("你好", False, "-"),
    ("hello", False, "-"),
    ("ok thanks", False, "-"),
    ("这个变量名可以改一下", False, "-"),
    ("Add a try-catch block here", False, "-"),
    ("run the tests and see if they pass", False, "-"),
    ("今天的天气怎么样", False, "-"),
    ("目前这个版本已经稳定了", False, "-"),

    # ── should NOT trigger: code discussion without memory reference ──
    ("这个函数的复杂度是O(n log n)对吧", False, "-"),
    ("import React from 'react'", False, "-"),
    ("把那个div改成section标签", False, "-"),
    ("SQL查询加了索引后快了三倍", False, "-"),
    ("重构一下这个模块，拆分职责", False, "-"),

    # ── edge cases: contains keyword but not triggering ──
    ("这句话你需要记得很清楚才行", False, "-"),
    ("之前没有考虑到这种情况吗", True, "L0"),  # 包含"之前"关键词，正则触发
    ("把记录保存到本地文件", False, "-"),

    # ── L0: more CJK patterns ──
    ("回忆一下之前做的性能测试结果", True, "L0"),
    ("之前说过使用Redis做缓存层", True, "L0"),
    ("我们聊过的那个灰度发布方案", True, "L0"),
    ("记录一下今天修复的这个空指针bug", True, "L0"),
    ("你清楚上次压测的QPS数据吗", True, "L0"),

    # ── should NOT trigger: short queries ──
    ("嗯", False, "-"),
    ("好", False, "-"),
    ("继续", False, "-"),
    ("然后呢", False, "-"),
    ("了解", False, "-"),
    ("明白", False, "-"),

    # ── L0: saving/recording intent ──
    ("存一下这个配置文件的路径", True, "L0"),
    ("记下来：CI流水线超时改为30分钟", True, "L0"),
    ("备忘：下周要升级Node版本到22", True, "L0"),
    ("把这段对话存到备忘录里", True, "L0"),

    # ── should NOT trigger: pure code ──
    ("const result = await fetch('/api/data')", False, "-"),
    ("def test_login(): assert response.status == 200", False, "-"),
    ("docker-compose up -d", False, "-"),
    ("git checkout -b feature/new-auth", False, "-"),

    # ── L0: memory system interaction ──
    ("search_memory 检索上次的部署方案", True, "L0"),
    ("recall the previous sprint retrospective notes", True, "L0"),
    ("根据记忆记录里的配置，端口是3000", True, "L0"),
    ("记忆里有没关于这个bug的相关信息", True, "L0"),
]


class TestTriggerAccuracy:
    @pytest.mark.parametrize("message,expected_trigger,expected_level", SAMPLES)
    def test_sample(self, message, expected_trigger, expected_level):
        result = should_retrieve_memory(message, turn_count=1, consecutive_misses=0)
        assert result.should_trigger == expected_trigger, \
            f"'{message}': expected trigger={expected_trigger}, got {result}"
        if expected_level != "-" and result.should_trigger:
            assert result.level == expected_level, \
                f"'{message}': expected level={expected_level}, got {result.level}"

    def test_coverage(self):
        trigger_count = sum(1 for _, t, _ in SAMPLES if t)
        total = len(SAMPLES)
        ratio = trigger_count / total
        assert total >= 50, f"Only {total} samples, need >= 50"
        assert 0.3 <= ratio <= 0.7, f"Trigger ratio {ratio:.0%} too skewed, aim 30-70%"
        print(f"\n  dataset: {total} samples, {trigger_count} trigger ({ratio:.0%})")

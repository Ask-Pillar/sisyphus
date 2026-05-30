"""Tests for memory retrieval trigger."""
import pytest
from sisyphus.memory.trigger import l0_signal_words, should_retrieve_memory, TriggerResult


class TestL0SignalWords:
    def test_empty_message(self):
        assert not l0_signal_words("")

    def test_none_message(self):
        assert not l0_signal_words(None)

    def test_explicit_remember(self):
        r = l0_signal_words("remember this project uses SQLite")
        assert r.should_trigger
        assert r.level == "L0"

    def test_recall_english(self):
        r = l0_signal_words("do you recall our discussion about Python types")
        assert r.should_trigger

    def test_memory_keyword(self):
        r = l0_signal_words("check memory for past decisions")
        assert r.should_trigger

    def test_remember_chinese(self):
        r = l0_signal_words("记住：这个项目需要做单元测试")
        assert r.should_trigger

    def test_review_chinese(self):
        r = l0_signal_words("回顾一下之前的架构决策")
        assert r.should_trigger

    def test_previous_chinese(self):
        r = l0_signal_words("上次我们讨论过这个问题")
        assert r.should_trigger

    def test_last_time_chinese(self):
        r = l0_signal_words("之前说过要用pytest做测试")
        assert r.should_trigger

    def test_mentioned_before(self):
        r = l0_signal_words("前面提到的小程序部署方案")
        assert r.should_trigger

    def test_question_pattern(self):
        r = l0_signal_words("你记得我们的数据库配置吗")
        assert r.should_trigger

    def test_knowledge_question(self):
        r = l0_signal_words("你知道我们上次定的规范不")
        assert r.should_trigger

    def test_record_command(self):
        r = l0_signal_words("记一下今天讨论的bug修复方案")
        assert r.should_trigger

    def test_memo_command(self):
        r = l0_signal_words("把这个存到备忘录")
        assert r.should_trigger
        assert r.reason == "l0_explicit"

    def test_no_trigger_normal_chat(self):
        r = l0_signal_words("this is a normal chat message about code")
        assert not r.should_trigger

    def test_no_trigger_code(self):
        r = l0_signal_words("add a new function to handle user input validation")
        assert not r.should_trigger

    def test_no_trigger_greeting(self):
        assert not l0_signal_words("你好")
        assert not l0_signal_words("hello")

    def test_memory_reference_pattern(self):
        r = l0_signal_words("根据记忆里的配置，端口是8080")
        assert r.should_trigger

    def test_mix_english_chinese(self):
        r = l0_signal_words("recall 上次我们讨论过的认证方案")
        assert r.should_trigger


class TestShouldRetrieve:
    def test_l0_overrides_backoff(self):
        r = should_retrieve_memory("记住这个配置", turn_count=10, consecutive_misses=5)
        assert r.should_trigger
        assert r.level == "L0"

    def test_backoff_after_misses(self):
        r = should_retrieve_memory("some random chat", turn_count=7, consecutive_misses=7)
        assert not r.should_trigger
        assert r.level == "L2"

    def test_default_trigger(self):
        r = should_retrieve_memory("any normal message", turn_count=3, consecutive_misses=0)
        assert r.should_trigger
        assert r.level == "L1"


class TestTriggerResult:
    def test_bool_true(self):
        t = TriggerResult(True, "L0", "test")
        assert t

    def test_bool_false(self):
        t = TriggerResult(False)
        assert not t

    def test_repr(self):
        t = TriggerResult(True, "L0", "signal:remember")
        assert "True" in repr(t)
        assert "L0" in repr(t)

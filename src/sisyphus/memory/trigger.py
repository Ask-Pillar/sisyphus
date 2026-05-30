"""Memory retrieval trigger — decides WHEN to invoke memory lookup.

Three levels:
  L0 — signal words (regex, < 1ms)
  L1 — lightweight rules (turn count, topic shift, < 5ms)
  L2 — exponential backoff (skip when no recent hits)
"""

import re
from typing import Optional, Set

L1_PERIOD = 5
L1_TOPIC_SHIFT_THRESHOLD = 0.3

SIGNAL_PATTERNS = [
    # English
    (r"\b(remember|recall|memory|memories)\b", "l0_explicit"),
    # Chinese — no \b, Chinese chars don't have word boundaries
    (r"(回顾|回忆|记住|记下|记一下|记录一下|存一下|存下来|备忘)", "l0_explicit"),
    (r"(之前|上次|上次我们|之前说过|前面提到|说过|聊过|讨论过)", "l0_history"),
    (r"根据.{0,5}(记忆|记录)", "l0_memory_ref"),
    (r"记忆.{0,3}(里|中)", "l0_memory_ref"),
    (r"(你记得|你知道|你了解|你清楚).{0,20}(吗|不|没)", "l0_question"),
    (r"记录.{0,3}(里|中)", "l0_memory_ref"),
    (r"以前.{0,5}(说过|聊过|讨论过)", "l0_history"),
]

_regexes = [(re.compile(p, re.IGNORECASE), reason) for p, reason in SIGNAL_PATTERNS]


class TriggerResult:
    def __init__(self, should_trigger: bool, level: str = "", reason: str = ""):
        self.should_trigger = should_trigger
        self.level = level
        self.reason = reason

    def __bool__(self):
        return self.should_trigger

    def __repr__(self):
        return f"TriggerResult(trigger={self.should_trigger}, level={self.level}, reason={self.reason})"


def l0_signal_words(message: str) -> TriggerResult:
    """L0: regex-based signal word matching. Fast, no LLM needed."""
    if not message or not message.strip():
        return TriggerResult(False)

    for regex, reason in _regexes:
        if regex.search(message):
            return TriggerResult(True, level="L0", reason=reason)
    return TriggerResult(False)


def l1_periodic(turn_count: int, period: int = L1_PERIOD) -> TriggerResult:
    """L1: trigger every N turns even without signal words."""
    if turn_count > 0 and turn_count % period == 0:
        return TriggerResult(True, level="L1", reason=f"periodic turn {turn_count}")
    return TriggerResult(False)


def l1_topic_shift(last_msg: str, current_msg: str, threshold: float = L1_TOPIC_SHIFT_THRESHOLD) -> TriggerResult:
    """L1: trigger when topic shifts significantly (keyword overlap < threshold).

    Uses Jaccard similarity of keyword sets from both messages.
    """
    if not last_msg or not current_msg:
        return TriggerResult(False)

    def _keywords(text: str) -> Set[str]:
        import jieba
        try:
            words = [w for w in jieba.cut(text) if len(w.strip()) >= 2]
        except ImportError:
            words = text.split()
        stopwords = {"的", "了", "是", "在", "和", "就", "都", "而", "及",
                     "a", "the", "is", "are", "to", "of", "in", "and", "or", "it", "that"}
        return {w.lower() for w in words if w.lower() not in stopwords}

    k1 = _keywords(last_msg)
    k2 = _keywords(current_msg)
    if not k1 or not k2:
        return TriggerResult(False)

    intersection = len(k1 & k2)
    union = len(k1 | k2)
    similarity = intersection / union if union > 0 else 1.0
    if similarity < threshold:
        return TriggerResult(True, level="L1", reason=f"topic shift similarity={similarity:.2f}")
    return TriggerResult(False)


def should_retrieve_memory(
    message: str,
    turn_count: int = 0,
    consecutive_misses: int = 0,
    last_message: str = "",
) -> TriggerResult:
    """Main entry point: decide whether to invoke memory retrieval.

    Cascade: L0 → L1 → L2
    """
    # L0: explicit signal words
    result = l0_signal_words(message)
    if result.should_trigger:
        return result

    # L1: periodic trigger
    result = l1_periodic(turn_count)
    if result.should_trigger:
        return result

    # L1: topic shift detection
    if last_message:
        result = l1_topic_shift(last_message, message)
        if result.should_trigger:
            return result

    # L2: exponential backoff — skip if too many misses in a row
    if consecutive_misses >= 3 and consecutive_misses >= turn_count * 0.5:
        return TriggerResult(False, level="L2", reason=f"backoff after {consecutive_misses} misses")

    # Default: skip retrieval for normal messages
    return TriggerResult(False, level="L1", reason="no trigger")

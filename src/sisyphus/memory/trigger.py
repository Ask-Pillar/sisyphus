"""Memory retrieval trigger — decides WHEN to invoke memory lookup.

Three levels:
  L0 — signal words (regex, < 1ms)
  L1 — lightweight rules (turn count, topic shift, < 5ms)
  L2 — exponential backoff (skip when no recent hits)
"""

import re
from typing import Optional

SIGNAL_PATTERNS = [
    # English
    (r"\b(remember|recall|memory|memories)\b", "l0_explicit"),
    # Chinese — no \b, Chinese chars don't have word boundaries
    (r"(回顾|回忆|记住|记下|记一下|存一下|存下来|备忘)", "l0_explicit"),
    (r"(之前|上次|上次我们|之前说过|前面提到|说过|聊过|讨论过)", "l0_history"),
    (r"根据.{0,5}(记忆|记录)", "l0_memory_ref"),
    (r"记忆.{0,3}(里|中)", "l0_memory_ref"),
    (r"(你记得|你知道|你了解|你清楚).{0,10}(吗|不|没)", "l0_question"),
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


def should_retrieve_memory(
    message: str,
    turn_count: int = 0,
    consecutive_misses: int = 0,
) -> TriggerResult:
    """Main entry point: decide whether to invoke memory retrieval.

    Cascade: L0 → L1 → L2
    """
    # L0: explicit signal words
    result = l0_signal_words(message)
    if result.should_trigger:
        return result

    # L2: exponential backoff — skip if too many misses in a row
    if consecutive_misses >= 3 and consecutive_misses >= turn_count * 0.5:
        return TriggerResult(False, level="L2", reason=f"backoff after {consecutive_misses} misses")

    # Default: trigger on most turns (L1 rules deferred to future)
    return TriggerResult(True, level="L1", reason="default")

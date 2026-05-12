from __future__ import annotations

# agent/anti_degeneration.py
# Protections against cognitive degradation patterns such as:
#   - reflection loops (same reflection generated repeatedly)
#   - duplicate self-generated tasks
#   - repetitive memory spam
#   - low-entropy / trivially similar observations
#
# Uses lightweight text similarity (no external dependencies).

import logging
import re
from collections import deque


# Minimum Jaccard similarity to consider two texts "too similar".
# 0.75 is a practical default that still catches near-duplicates while allowing
# moderate paraphrasing; to tune this, raise it to be stricter or lower it to be
# more permissive. Runtime config.yaml tuning is not implemented yet and would
# require a follow-up code change to load this threshold from configuration.
SIMILARITY_THRESHOLD = 0.75

# How many recent reflections to keep in the dedup window
REFLECTION_WINDOW = 20

# How many recent tasks to keep in the dedup window
TASK_WINDOW = 50


class AntiDegeneration:
    """Detects and suppresses degenerate cognitive patterns."""

    def __init__(self) -> None:
        self._recent_reflections: deque[str] = deque(maxlen=REFLECTION_WINDOW)
        self._recent_tasks: deque[str] = deque(maxlen=TASK_WINDOW)
        self.logger = logging.getLogger(__name__)

    # ------------------------------------------------------------------
    # Reflection deduplication
    # ------------------------------------------------------------------

    def is_reflection_duplicate(self, reflection: str) -> bool:
        """Return True if *reflection* is too similar to a recent one."""
        for prev in self._recent_reflections:
            if _jaccard(reflection, prev) >= SIMILARITY_THRESHOLD:
                self.logger.warning(
                    "Reflection suppressed (similarity ≥ %.2f): %.60s…",
                    SIMILARITY_THRESHOLD,
                    reflection,
                )
                return True
        return False

    def record_reflection(self, reflection: str) -> None:
        self._recent_reflections.append(reflection)

    # ------------------------------------------------------------------
    # Task deduplication
    # ------------------------------------------------------------------

    def is_task_duplicate(self, task: str) -> bool:
        """Return True if *task* is too similar to a recently seen task."""
        for prev in self._recent_tasks:
            if _jaccard(task, prev) >= SIMILARITY_THRESHOLD:
                return True
        return False

    def record_task(self, task: str) -> None:
        self._recent_tasks.append(task)

    # ------------------------------------------------------------------
    # Entropy check
    # ------------------------------------------------------------------

    def is_low_entropy(self, text: str, min_unique_words: int = 5) -> bool:
        """Return True if *text* has suspiciously low word diversity."""
        words = _tokenize(text)
        if not words:
            return True
        unique_ratio = len(set(words)) / len(words)
        return unique_ratio < 0.3 or len(set(words)) < min_unique_words

    # ------------------------------------------------------------------
    # Combined guard
    # ------------------------------------------------------------------

    def should_suppress_reflection(self, reflection: str) -> bool:
        """Return True if a reflection should be suppressed entirely."""
        if self.is_low_entropy(reflection):
            self.logger.warning("Reflection suppressed (low entropy): %.60s…", reflection)
            return True
        if self.is_reflection_duplicate(reflection):
            return True
        return False


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _tokenize(text: str) -> list[str]:
    """Lower-case word tokenisation, no external deps."""
    return re.findall(r"\b\w+\b", text.lower())


def _jaccard(a: str, b: str) -> float:
    """Compute token-level Jaccard similarity between two strings."""
    set_a = set(_tokenize(a))
    set_b = set(_tokenize(b))
    if not set_a and not set_b:
        return 1.0
    if not set_a or not set_b:
        return 0.0
    intersection = len(set_a & set_b)
    union = len(set_a | set_b)
    return intersection / union

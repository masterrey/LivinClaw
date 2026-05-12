from __future__ import annotations

# agent/cognitive_budget.py
# Tracks and enforces cognitive resource limits across a single agent lifetime.
# Limits include: tokens per tick, reflections per day, compactions per hour,
# maximum loaded topics, and maximum prompt size.

import logging
from datetime import datetime, UTC

# Rough prompt-size approximation; adjust if the active tokenizer differs materially.
CHARS_PER_TOKEN = 4


class CognitiveBudget:
    """Enforces configurable limits on agent cognitive resource usage."""

    def __init__(self, config: dict) -> None:
        cfg = config.get("cognitive_budget", {})
        self.max_tokens_per_tick: int = int(cfg.get("max_tokens_per_tick", 12000))
        self.max_loaded_topics: int = int(cfg.get("max_loaded_topics", 3))
        self.max_reflections_per_day: int = int(cfg.get("max_reflections_per_day", 20))
        self.reflection_cooldown_ticks: int = int(cfg.get("reflection_cooldown_ticks", 3))
        self.max_compactions_per_hour: int = int(cfg.get("max_compactions_per_hour", 2))
        self.max_prompt_chars: int = int(cfg.get("max_tokens_per_tick", 12000)) * CHARS_PER_TOKEN

        self._tokens_this_tick: int = 0
        self._reflections_today: int = 0
        self._compactions_this_hour: int = 0
        self._last_reflection_tick: int = -999
        self._day_key: str = _day_key()
        self._hour_key: str = _hour_key()

        self.logger = logging.getLogger(__name__)

    # ------------------------------------------------------------------
    # Tick boundary
    # ------------------------------------------------------------------

    def new_tick(self, tick_count: int) -> None:
        """Reset per-tick counters and roll over daily/hourly counters if needed."""
        self._tokens_this_tick = 0
        today = _day_key()
        if today != self._day_key:
            self._reflections_today = 0
            self._day_key = today
        hour = _hour_key()
        if hour != self._hour_key:
            self._compactions_this_hour = 0
            self._hour_key = hour

    # ------------------------------------------------------------------
    # Token budget
    # ------------------------------------------------------------------

    def can_use_tokens(self, estimated_tokens: int) -> bool:
        return (self._tokens_this_tick + estimated_tokens) <= self.max_tokens_per_tick

    def record_tokens(self, count: int) -> None:
        self._tokens_this_tick += count

    def tokens_remaining(self) -> int:
        return max(0, self.max_tokens_per_tick - self._tokens_this_tick)

    # ------------------------------------------------------------------
    # Reflection budget
    # ------------------------------------------------------------------

    def can_reflect(self, current_tick: int) -> bool:
        """Return True if a reflection is allowed right now."""
        ticks_since = current_tick - self._last_reflection_tick
        if ticks_since < self.reflection_cooldown_ticks:
            self.logger.debug(
                "Reflection blocked by cooldown (%d/%d ticks)",
                ticks_since,
                self.reflection_cooldown_ticks,
            )
            return False
        if self._reflections_today >= self.max_reflections_per_day:
            self.logger.debug("Daily reflection limit reached (%d)", self.max_reflections_per_day)
            return False
        return True

    def record_reflection(self, current_tick: int) -> None:
        self._reflections_today += 1
        self._last_reflection_tick = current_tick

    # ------------------------------------------------------------------
    # Compaction budget
    # ------------------------------------------------------------------

    def can_compact(self) -> bool:
        return self._compactions_this_hour < self.max_compactions_per_hour

    def record_compaction(self) -> None:
        self._compactions_this_hour += 1

    # ------------------------------------------------------------------
    # Prompt size
    # ------------------------------------------------------------------

    def clip_prompt(self, prompt: str) -> str:
        """Truncate prompt to stay within the cognitive budget."""
        if len(prompt) <= self.max_prompt_chars:
            return prompt
        self.logger.warning(
            "Prompt clipped from %d to %d chars by cognitive budget",
            len(prompt),
            self.max_prompt_chars,
        )
        return prompt[: self.max_prompt_chars]

    # ------------------------------------------------------------------
    # Status snapshot
    # ------------------------------------------------------------------

    def status(self) -> dict:
        return {
            "tokens_this_tick": self._tokens_this_tick,
            "max_tokens_per_tick": self.max_tokens_per_tick,
            "reflections_today": self._reflections_today,
            "max_reflections_per_day": self.max_reflections_per_day,
            "compactions_this_hour": self._compactions_this_hour,
            "max_compactions_per_hour": self.max_compactions_per_hour,
        }


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _day_key() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d")


def _hour_key() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H")

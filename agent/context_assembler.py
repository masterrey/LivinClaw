from __future__ import annotations

# agent/context_assembler.py
# Builds compact, budget-aware prompts for the main agent.
# Assembles short memory + selected topic branches + current task into a
# single prompt that never exceeds the cognitive budget.
#
# The assembler NEVER injects full long-term memory blindly.

import logging

from agent.cognitive_budget import CognitiveBudget
from guardian.token_estimator import TokenEstimator


# Character budget fractions sum to 0.85, leaving a 0.15 safety margin.
_SHORT_MEM_FRACTION = 0.20
_TOPIC_FRACTION = 0.50
_TASK_FRACTION = 0.15


class ContextAssembler:
    """Builds the final compact prompt from short memory, topic branches, and the current task."""

    def __init__(self, budget: CognitiveBudget) -> None:
        self.budget = budget
        self.estimator = TokenEstimator()
        self.logger = logging.getLogger(__name__)

    def assemble(
        self,
        task: str,
        short_memory_export: dict,
        loaded_topics: dict[str, str],
        extra_context: str = "",
    ) -> str:
        """Build and return the assembled prompt string.

        Args:
            task: The current task description.
            short_memory_export: Result of ``ShortMemory.export()``.
            loaded_topics: ``{topic_name: markdown_content}`` from the memory router.
            extra_context: Any additional context text to include (optional).
        """
        max_chars = self.budget.max_prompt_chars

        # ---- Short memory section ----
        short_section = _format_short_memory(short_memory_export)
        short_budget = int(max_chars * _SHORT_MEM_FRACTION)
        short_section = _clip(short_section, short_budget, "short-memory")

        # ---- Topic sections ----
        topic_budget = int(max_chars * _TOPIC_FRACTION)
        topic_section = _format_topics(loaded_topics, topic_budget)

        # ---- Task section ----
        task_budget = int(max_chars * _TASK_FRACTION)
        task_section = _clip(f"## Current Task\n{task}", task_budget, "task")

        # ---- Extra context ----
        remaining = max_chars - len(short_section) - len(topic_section) - len(task_section)
        extra_section = ""
        if extra_context and remaining > 100:
            extra_section = _clip(extra_context, remaining - 50, "extra-context")

        parts = [p for p in [short_section, topic_section, task_section, extra_section] if p]
        prompt = "\n\n".join(parts)

        # Final safety clip using the cognitive budget
        prompt = self.budget.clip_prompt(prompt)

        estimated_tokens = self.estimator.estimate(prompt)
        self.budget.record_tokens(estimated_tokens)
        self.logger.debug("Context assembled: ~%d tokens, %d chars", estimated_tokens, len(prompt))

        return prompt


# ------------------------------------------------------------------
# Formatting helpers
# ------------------------------------------------------------------

def _format_short_memory(export: dict) -> str:
    lines = ["## Working Memory"]
    if export.get("summary"):
        lines.append(f"Summary: {export['summary']}")
    recent_actions = export.get("actions", [])[-5:]
    if recent_actions:
        lines.append("Recent actions: " + " | ".join(recent_actions))
    recent_obs = export.get("observations", [])[-5:]
    if recent_obs:
        lines.append("Recent observations: " + " | ".join(recent_obs))
    intentions = export.get("open_intentions", [])[:3]
    if intentions:
        lines.append("Open intentions: " + ", ".join(intentions))
    return "\n".join(lines)


def _format_topics(loaded_topics: dict[str, str], budget: int) -> str:
    if not loaded_topics:
        return ""
    per_topic_budget = max(200, budget // max(1, len(loaded_topics)))
    parts = ["## Relevant Memory"]
    for name, content in loaded_topics.items():
        clipped = _clip(content, per_topic_budget, f"topic:{name}")
        if clipped.strip():
            parts.append(f"### {name}\n{clipped}")
    return "\n\n".join(parts)


def _clip(text: str, max_chars: int, label: str = "") -> str:
    if len(text) <= max_chars:
        return text
    tail = max(0, max_chars - 30)
    return text[:tail] + f"\n[...{label} clipped...]"

from __future__ import annotations

# agent/interaction_context.py
# Managed context builder for interactive chat.
# Assembles all available runtime state into a single explicit context object
# that is then used to build the LLM prompt.  The chat is NOT a separate chatbot;
# it is the conversational control surface of the same alive agent cognition.

import logging
from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# Default budget limits (can be overridden via config chat_context section)
# ---------------------------------------------------------------------------

_DEFAULT_MAX_PROMPT_CHARS = 6000
_DEFAULT_MAX_SHORT_MEMORY_CHARS = 1200
_DEFAULT_MAX_TOPIC_CHARS = 2000
_DEFAULT_MAX_PENDING_TASKS = 5
_DEFAULT_MAX_RECENT_OBSERVATIONS = 5
_DEFAULT_MAX_RECENT_ACTIONS = 5
_DEFAULT_MAX_LOADED_TOPICS = 2

# Minimum length (chars) for a user message to be considered potentially important.
_MIN_IMPORTANT_MSG_LEN = 10

# Keywords that suggest the message contains a user preference or instruction.
_PREFERENCE_KEYWORDS: frozenset[str] = frozenset(
    {
        "prefer",
        "prefiro",
        "prefere",
        "quero",
        "always",
        "never",
        "sempre",
        "nunca",
        "use",
        "usa",
        "foco",
        "focus",
        "workspace",
        "não use",
        "nao use",
        "deve",
        "should",
        "must",
        "preciso",
        "need",
        "importante",
        "important",
        "language",
        "idioma",
        "língua",
        "lingua",
        "respostas",
        "response",
        "responses",
        "direto",
        "direct",
        "curto",
        "short",
        "longo",
        "long",
    }
)

# Short messages that are clearly trivial and should not be saved.
_TRIVIAL_PATTERNS: frozenset[str] = frozenset(
    {
        "olá",
        "ola",
        "oi",
        "ok",
        "ok.",
        "okay",
        "sim",
        "yes",
        "no",
        "não",
        "nao",
        "teste",
        "test",
        "obrigado",
        "obrigada",
        "thanks",
        "thank you",
        "valeu",
        "hi",
        "hello",
        "hey",
    }
)

# ---------------------------------------------------------------------------
# Managed context dataclass
# ---------------------------------------------------------------------------

ACTION_POLICY = (
    "You may discuss actions and tools, but do not claim that a tool was executed "
    "unless the runtime actually executed it.\n"
    "If the user asks for an action, explain whether it should become a task, "
    "a future tool action, or a request requiring approval.\n"
    "Do not bypass the runtime, Guardian, or approval flow."
)


@dataclass
class InteractionContext:
    """One explicit managed context object for a single chat interaction."""

    user_message: str
    tick_type: str
    model_name: str
    short_memory_summary: str
    recent_observations: list[str] = field(default_factory=list)
    recent_actions: list[str] = field(default_factory=list)
    pending_tasks: list[str] = field(default_factory=list)
    routed_memory: dict[str, str] = field(default_factory=dict)
    action_policy: str = ACTION_POLICY
    budget_summary: dict[str, int | str | bool] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------


class InteractionContextBuilder:
    """Assembles managed chat context from available runtime components.

    All components are optional – the builder degrades gracefully when any
    source is unavailable.
    """

    def __init__(
        self,
        short_memory=None,
        task_manager=None,
        memory_router=None,
        cognitive_budget=None,
        config: dict | None = None,
    ) -> None:
        self.short_memory = short_memory
        self.task_manager = task_manager
        self.memory_router = memory_router
        self.cognitive_budget = cognitive_budget
        cfg = config or {}
        self.max_prompt_chars: int = int(cfg.get("max_prompt_chars", _DEFAULT_MAX_PROMPT_CHARS))
        self.max_short_memory_chars: int = int(cfg.get("max_short_memory_chars", _DEFAULT_MAX_SHORT_MEMORY_CHARS))
        self.max_topic_chars: int = int(cfg.get("max_topic_chars", _DEFAULT_MAX_TOPIC_CHARS))
        self.max_pending_tasks: int = int(cfg.get("max_pending_tasks", _DEFAULT_MAX_PENDING_TASKS))
        self.max_recent_observations: int = int(cfg.get("max_recent_observations", _DEFAULT_MAX_RECENT_OBSERVATIONS))
        self.max_recent_actions: int = int(cfg.get("max_recent_actions", _DEFAULT_MAX_RECENT_ACTIONS))
        self.max_loaded_topics: int = int(cfg.get("max_loaded_topics", _DEFAULT_MAX_LOADED_TOPICS))
        self.update_short_memory: bool = bool(cfg.get("update_short_memory", True))
        self.logger = logging.getLogger(__name__)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def build_for_message(self, message: str, runtime_context: dict) -> InteractionContext:
        """Build a managed InteractionContext for the given user message.

        Args:
            message: Raw user message text.
            runtime_context: Dict passed from the agent tick (tick_type, model_name, …).
        """
        warnings: list[str] = []

        tick_type = runtime_context.get("tick_type", "interactive")
        model_name = runtime_context.get("model_name", "Not available yet") or "Not available yet"

        # Short memory
        short_memory_summary, recent_observations, recent_actions = self._gather_short_memory(warnings)

        # Pending tasks
        pending_tasks = self._gather_pending_tasks(warnings)

        # Routed topic memory (use pre-loaded topics from runtime if available)
        preloaded = runtime_context.get("loaded_topics")
        routed_memory = self._gather_routed_memory(message, short_memory_summary, warnings, preloaded=preloaded)

        # Cognitive budget snapshot
        budget_summary = self._gather_budget_summary(warnings)

        return InteractionContext(
            user_message=message,
            tick_type=tick_type,
            model_name=model_name,
            short_memory_summary=short_memory_summary,
            recent_observations=recent_observations,
            recent_actions=recent_actions,
            pending_tasks=pending_tasks,
            routed_memory=routed_memory,
            action_policy=ACTION_POLICY,
            budget_summary=budget_summary,
            warnings=warnings,
        )

    # ------------------------------------------------------------------
    # Component gatherers (degrade gracefully)
    # ------------------------------------------------------------------

    def _gather_short_memory(
        self, warnings: list[str]
    ) -> tuple[str, list[str], list[str]]:
        if self.short_memory is None:
            warnings.append("Short memory not available")
            return "Not available yet", [], []

        summary = self.short_memory.summary or "Not available yet"
        summary = summary[: self.max_short_memory_chars]

        raw_obs = list(self.short_memory.observations)
        recent_obs = raw_obs[-self.max_recent_observations :]

        raw_acts = list(self.short_memory.actions)
        recent_acts = raw_acts[-self.max_recent_actions :]

        return summary, recent_obs, recent_acts

    def _gather_pending_tasks(self, warnings: list[str]) -> list[str]:
        if self.task_manager is None:
            warnings.append("Task manager not available")
            return []
        try:
            tasks = self.task_manager.get_pending_tasks(limit=self.max_pending_tasks)
            return tasks[: self.max_pending_tasks]
        except Exception as exc:
            self.logger.warning("Could not retrieve pending tasks: %s", exc)
            warnings.append("Pending tasks not available")
            return []

    def _gather_routed_memory(
        self, message: str, short_memory_text: str, warnings: list[str], preloaded: dict[str, str] | None = None
    ) -> dict[str, str]:
        # Use pre-loaded topics if available (avoids double routing in the same tick)
        if preloaded is not None:
            limited: dict[str, str] = {}
            chars_used = 0
            for name, content in list(preloaded.items())[: self.max_loaded_topics]:
                remaining_budget = self.max_topic_chars - chars_used
                if remaining_budget <= 0:
                    break
                clipped = content[: remaining_budget]
                limited[name] = clipped
                chars_used += len(clipped)
            return limited

        if self.memory_router is None:
            warnings.append("Topic memory routing not available yet")
            return {}
        try:
            loaded = self.memory_router.route(
                task=message,
                short_memory_text=short_memory_text,
            )
            # Limit number of topics and total char budget
            limited = {}
            chars_used = 0
            for name, content in list(loaded.items())[: self.max_loaded_topics]:
                remaining_budget = self.max_topic_chars - chars_used
                if remaining_budget <= 0:
                    break
                clipped = content[: remaining_budget]
                limited[name] = clipped
                chars_used += len(clipped)
            return limited
        except Exception as exc:
            self.logger.warning("Memory routing failed: %s", exc)
            warnings.append("Topic memory routing failed")
            return {}

    def _gather_budget_summary(self, warnings: list[str]) -> dict[str, int | str | bool]:
        if self.cognitive_budget is None:
            warnings.append("Cognitive budget not available")
            return {}
        try:
            return self.cognitive_budget.status()
        except Exception as exc:
            self.logger.warning("Could not retrieve cognitive budget status: %s", exc)
            warnings.append("Cognitive budget status not available")
            return {}

    # ------------------------------------------------------------------
    # ShortMemory update heuristic
    # ------------------------------------------------------------------

    def maybe_update_short_memory(self, message: str, response: str) -> None:
        """Write back to ShortMemory if the exchange appears worth remembering."""
        if not self.update_short_memory or self.short_memory is None:
            return
        if should_record_interaction(message, response):
            entry = f"User preference/instruction: {message[:200]}"
            self.short_memory.add_observation(entry, importance=0.75)
            self.logger.debug("Interaction recorded to ShortMemory: %s…", message[:60])


# ---------------------------------------------------------------------------
# Heuristic: should this interaction be saved to ShortMemory?
# ---------------------------------------------------------------------------


def should_record_interaction(message: str, response: str) -> bool:  # noqa: ARG001
    """Conservative heuristic: return True only for messages worth remembering.

    Trivial greetings, single-word acknowledgements, and very short messages
    are rejected.  Messages containing preference keywords or that are
    substantively long are accepted.
    """
    stripped = message.strip().lower()

    if stripped in _TRIVIAL_PATTERNS:
        return False

    if len(stripped) < _MIN_IMPORTANT_MSG_LEN:
        return False

    # Accept messages that contain preference/instruction vocabulary
    words = set(stripped.split())
    if words & _PREFERENCE_KEYWORDS:
        return True

    # Phrases like "não use WebSocket" or "use managed context"
    for kw in _PREFERENCE_KEYWORDS:
        if kw in stripped:
            return True

    # Accept longer messages (likely contain useful context)
    if len(stripped) >= 40:
        return True

    return False

from __future__ import annotations

# agent/interaction_responder.py
# Owns the interactive response decision logic.
# Classifies incoming interaction directives and generates appropriate responses.
# Greeting and status responses are deterministic (no LLM).
# Conversational questions use InteractionContextBuilder to assemble managed context
# and then call the LLM with that context as the prompt.

import logging
import re

GREETING_WORDS: frozenset[str] = frozenset(
    {
        "olá",
        "ola",
        "oi",
        "hello",
        "hi",
        "hey",
        "howdy",
        "bom",
        "boa",
    }
)

GREETING_PHRASES: tuple[str, ...] = (
    "bom dia",
    "boa tarde",
    "boa noite",
    "tudo bem",
    "tudo bom",
    "como vai",
    "como você está",
    "como voce esta",
)

# Patterns that indicate the user is asking for runtime status.
_STATUS_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\b@?status\b", re.IGNORECASE),
    re.compile(r"qual\s+(é\s+|e\s+)?seu\s+status", re.IGNORECASE),
    re.compile(r"como\s+(você\s+|voce\s+)?est[aá]", re.IGNORECASE),
    re.compile(r"você\s+est[aá]\s+funcionando", re.IGNORECASE),
    re.compile(r"voce\s+esta\s+funcionando", re.IGNORECASE),
    re.compile(r"pode\s+me\s+informar\s+o\s+status", re.IGNORECASE),
    re.compile(r"est[aá]\s+funcionando", re.IGNORECASE),
]

# Words that strongly suggest the message is in Portuguese.
_PORTUGUESE_MARKERS: frozenset[str] = frozenset(
    {
        "olá",
        "ola",
        "oi",
        "você",
        "voce",
        "pode",
        "seu",
        "sua",
        "qual",
        "como",
        "está",
        "esta",
        "são",
        "e",
        "é",
        "um",
        "uma",
        "para",
        "com",
        "por",
        "não",
        "nao",
        "que",
        "mais",
        "tarefa",
        "tarefas",
        "memória",
        "memoria",
        "ajudar",
        "pronto",
        "explique",
        "funcionando",
        "informar",
        "arquitetura",
        "bom",
        "boa",
        "preciso",
        "quero",
        "vamos",
        "minha",
        "meu",
        "pedir",
        "registrar",
        "notas",
        "conversar",
        "criar",
    }
)

from agent.interaction_context import InteractionContextBuilder, InteractionContext


def _build_prompt_from_context(ctx: InteractionContext) -> str:
    """Construct a managed LLM prompt from an InteractionContext."""
    lines: list[str] = [
        "You are LivinClaw, a local alive agent runtime.",
        "",
        "Identity:",
        "- You are not a normal chatbot.",
        "- You are a human-facing conversational control layer for an alive autonomous runtime.",
        "- You operate through inbox/outbox, ticks, short memory, long-term topic memory, tasks, and Guardian constraints.",
        "- Be natural and useful.",
        "- Use the same language as the user when possible.",
        "- Do not invent runtime state.",
        "- Do not claim tools were executed unless they were.",
        "- If the user asks for action, propose a task or controlled action path.",
        "- If context is unavailable, say it is not available yet.",
        "",
        "Current interaction context:",
        f"- tick type: {ctx.tick_type}",
        f"- model: {ctx.model_name}",
        f"- pending tasks: {len(ctx.pending_tasks)}",
    ]

    if ctx.budget_summary:
        tokens_used = ctx.budget_summary.get("tokens_this_tick", "?")
        tokens_max = ctx.budget_summary.get("max_tokens_per_tick", "?")
        lines.append(f"- budget: {tokens_used}/{tokens_max} tokens used this tick")

    lines += [
        "",
        "Short memory / RAM:",
        ctx.short_memory_summary or "Not available yet",
    ]

    if ctx.recent_observations:
        lines += ["", "Recent observations:"]
        lines += [f"- {obs}" for obs in ctx.recent_observations]

    if ctx.recent_actions:
        lines += ["", "Recent actions:"]
        lines += [f"- {act}" for act in ctx.recent_actions]

    if ctx.pending_tasks:
        lines += ["", "Pending tasks:"]
        lines += [f"- {t}" for t in ctx.pending_tasks]

    if ctx.routed_memory:
        lines += ["", "Relevant long-term memory topics:"]
        for topic, content in ctx.routed_memory.items():
            lines += [f"### {topic}", content[:500]]

    lines += [
        "",
        "Action/tool policy:",
        ctx.action_policy,
        "",
        "User message:",
        ctx.user_message,
    ]

    return "\n".join(lines)


class InteractionResponder:
    """Classifies interaction directives and generates appropriate responses.

    Supported directive types (mirrors InteractionManager.classify_directive output):
        - ``"status"``   → deterministic runtime status (no LLM)
        - ``"ask"``      → conversational answer via LLM using managed context
        - ``"message"``  → heuristic sub-classification: greeting / status / complex / freeform
        - anything else  → fallback acknowledgement

    The caller (alive_agent) still handles ``"task"`` and ``"note"`` directives
    before reaching this responder.
    """

    def __init__(
        self,
        llm_client=None,
        task_manager=None,
        short_memory=None,
        model_name: str = "",
        context_builder: InteractionContextBuilder | None = None,
    ) -> None:
        self.llm_client = llm_client
        self.task_manager = task_manager
        self.short_memory = short_memory
        self.model_name = model_name
        self.context_builder = context_builder
        self.logger = logging.getLogger(__name__)

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def respond(
        self,
        directive: str,
        content: str,
        context: dict | None = None,
    ) -> str:
        """Return an appropriate response string for the given directive."""
        ctx = context or {}
        if directive == "status":
            return self._respond_status(ctx)
        if directive == "ask":
            return self._respond_conversational(content, ctx)
        if directive == "message":
            return self._respond_message(content, ctx)
        return self._respond_fallback(content)

    # ------------------------------------------------------------------
    # Heuristic helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _is_portuguese(content: str) -> bool:
        tokens = set(re.split(r"\W+", content.lower()))
        return bool(tokens & _PORTUGUESE_MARKERS)

    @staticmethod
    def _is_greeting(content: str) -> bool:
        lower = content.strip().lower()
        # Check multi-word phrases first.
        for phrase in GREETING_PHRASES:
            if phrase in lower:
                return True
        # Check individual tokens.
        tokens = set(re.split(r"\W+", lower))
        return bool(tokens & GREETING_WORDS)

    @staticmethod
    def _is_status_request(content: str) -> bool:
        lower = content.strip().lower()
        return any(p.search(lower) for p in _STATUS_PATTERNS)

    def _classify_message(self, content: str) -> str:
        """Classify a bare (non-prefixed) message into a sub-category."""
        if self._is_greeting(content):
            return "greeting"
        if self._is_status_request(content):
            return "status"
        if self._is_complex_question(content):
            return "complex"
        return "freeform"

    @staticmethod
    def _is_complex_question(content: str) -> bool:
        """Return True for messages that are obviously substantive questions.

        These should be routed to the managed conversational path even without @ask.
        """
        lower = content.strip().lower()
        complex_patterns = [
            re.compile(r"\b(explain|explique|me explique)\b", re.IGNORECASE),
            re.compile(r"\b(how|como)\s+(do\s+you|you|você|voce)\b", re.IGNORECASE),
            re.compile(r"\b(what\s+can\s+you|o\s+que\s+você\s+pode)\b", re.IGNORECASE),
            re.compile(r"\b(arquitetura|architecture|funciona|work)\b", re.IGNORECASE),
            re.compile(r"\b(qual\s+a\s+diferença|what.s\s+the\s+difference)\b", re.IGNORECASE),
            re.compile(r"\b(o\s+que\s+você\s+lembra|what\s+do\s+you\s+remember)\b", re.IGNORECASE),
            re.compile(r"\b(como\s+você\s+funciona|how\s+do\s+you\s+work)\b", re.IGNORECASE),
            re.compile(r"\b(assuntos?\s+anteriores?|conversas?\s+anteriores?)\b", re.IGNORECASE),
            re.compile(r"\b(do\s+que\s+falamos\s+antes|sobre\s+o\s+que\s+falamos)\b", re.IGNORECASE),
            re.compile(r"\b(voc[eê]\s+lembra\s+da\s+conversa\s+anterior)\b", re.IGNORECASE),
            re.compile(r"\b(what\s+did\s+we\s+talk\s+about|previous\s+topics?|earlier\s+conversation)\b", re.IGNORECASE),
        ]
        return any(p.search(lower) for p in complex_patterns)

    # ------------------------------------------------------------------
    # Response builders
    # ------------------------------------------------------------------

    def _respond_greeting(self, is_pt: bool) -> str:
        if is_pt:
            return (
                "Olá! Estou ativo e pronto para ajudar. "
                "Você pode conversar comigo, criar tarefas com @task, "
                "registrar notas com @note ou pedir meu status com @status."
            )
        return (
            "Hello! I'm active and ready to help. "
            "You can chat with me, create tasks with @task, "
            "add notes with @note, or check my status with @status."
        )

    def _respond_status(self, ctx: dict) -> str:
        tick_type = ctx.get("tick_type", "interactive")
        pending_tasks: list[str] = ctx.get("pending_tasks", [])
        inbox_pending: int = ctx.get("inbox_pending", 0)
        model = ctx.get("model_name") or self.model_name or "Not available yet"

        lines = [
            "Status do LivinClaw:",
            f"- tick atual: {tick_type}",
            f"- tarefas pendentes: {len(pending_tasks)}",
            f"- mensagens pendentes: {inbox_pending}",
            f"- modelo: {model}",
        ]

        outbox_count = ctx.get("outbox_count")
        if outbox_count is not None:
            lines.append(f"- respostas no outbox: {outbox_count}")

        memory_summary: str = ctx.get("memory_summary", "")
        if memory_summary and memory_summary != "Estado inicial":
            lines.append(f"- resumo de memória: {memory_summary[:120]}")

        return "\n".join(lines)

    def _respond_conversational(self, content: str, ctx: dict) -> str:
        if not self.llm_client:
            return self._llm_fallback(content)

        # Build managed interaction context
        if self.context_builder is not None:
            interaction_ctx = self.context_builder.build_for_message(content, ctx)
            prompt = _build_prompt_from_context(interaction_ctx)
        else:
            # Fallback: minimal inline prompt when no context builder is available
            tick_type = ctx.get("tick_type", "interactive")
            pending_count = len(ctx.get("pending_tasks", []))
            memory_summary: str = ctx.get("memory_summary", "") or ""
            prompt = (
                "You are LivinClaw, a local alive agent runtime.\n"
                "Answer the user's message naturally and concisely.\n"
                "Do not pretend to have capabilities that are not implemented.\n"
                "You are not a normal chatbot; you operate through inbox/outbox, ticks, tasks, and memory.\n"
                "If the user asks about your architecture, explain the current runtime honestly.\n"
                "If information is unavailable, say it is not available yet.\n"
                f"Current context: tick={tick_type}, "
                f"pending_tasks={pending_count}, "
                f"memory_summary={memory_summary[:200] if memory_summary else 'none'}"
            )

        try:
            reply = self.llm_client.chat(
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": content},
                ],
                temperature=0.4,
                max_tokens=500,
            )
            if reply and reply.strip():
                if self.context_builder is not None:
                    self.context_builder.maybe_update_short_memory(content, reply)
                return reply.strip()
        except Exception as exc:
            self.logger.warning("LLM call failed during interactive tick: %s", exc)

        return self._llm_fallback(content)

    def _respond_freeform(self, content: str, is_pt: bool) -> str:
        if is_pt:
            return (
                "Entendi. Você pode transformar isso em uma tarefa com @task, "
                "registrar uma preferência com @note, "
                "fazer uma pergunta direta com @ask ou pedir o status com @status."
            )
        return (
            "Got it. You can turn this into a task with @task, "
            "record a preference with @note, "
            "ask a direct question with @ask, or check status with @status."
        )

    def _respond_message(self, content: str, ctx: dict) -> str:
        category = self._classify_message(content)
        is_pt = self._is_portuguese(content)

        if category == "greeting":
            return self._respond_greeting(is_pt)
        if category == "status":
            return self._respond_status(ctx)
        if category == "complex":
            return self._respond_conversational(content, ctx)
        return self._respond_freeform(content, is_pt)

    def _respond_fallback(self, content: str) -> str:
        if self._is_portuguese(content):
            return (
                "Recebi sua mensagem, mas não tenho certeza se devo tratar como conversa, "
                "tarefa, nota ou status. "
                "Use @task, @note, @status ou @ask para direcionar melhor."
            )
        return (
            "Received your message but I'm not sure how to handle it. "
            "Use @task, @note, @status, or @ask to be more specific."
        )

    def _llm_fallback(self, content: str) -> str:
        if self._is_portuguese(content):
            return (
                "Recebi sua pergunta, mas não consegui chamar o modelo local agora. "
                "Posso registrar isso como tarefa ou você pode verificar se o LM Studio está ativo."
            )
        return (
            "I received your question but could not reach the local model. "
            "You can register it as a task or check if LM Studio is running."
        )

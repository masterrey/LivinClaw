from __future__ import annotations

# agent/alive_agent.py
# Resident autonomous agent.  Extended with:
#   - Topic-tree long-term memory via MemoryRouter
#   - Sparse memory loading (MoE-style)
#   - Cognitive budget enforcement
#   - Anti-degeneration guards
#   - ContextAssembler for compact prompt construction
#   - Reflection cooldowns

import json
import logging
import threading
from enum import Enum
from pathlib import Path

from agent.anti_degeneration import AntiDegeneration
from agent.cognitive_budget import CognitiveBudget
from agent.context_assembler import ContextAssembler
from agent.planner import Planner
from agent.reflection import ReflectionEngine
from guardian.guardian import GuardianLayer
from interaction.interaction_manager import InteractionManager
from llm.llm_client import LLMClient
from memory.long_memory import LongMemory
from memory.memory_compactor import MemoryCompactor
from memory.memory_router import MemoryRouter
from memory.short_memory import ShortMemory
from tasks.task_manager import TaskManager
from tools.tool_registry import ToolRegistry


class TickType(str, Enum):
    SCHEDULED = "scheduled"
    INTERACTIVE = "interactive"
    RECOVERY = "recovery"
    MAINTENANCE = "maintenance"

    @classmethod
    def from_reason(cls, reason: str | TickType) -> TickType:
        if isinstance(reason, TickType):
            return reason
        normalized = (reason or "scheduled").strip().lower()
        for tick_type in cls:
            if tick_type.value == normalized:
                return tick_type
        return cls.SCHEDULED


class AliveAgent:
    def __init__(self, config: dict, root_dir: Path) -> None:
        self.config = config
        self.root_dir = root_dir
        self.logger = logging.getLogger(__name__)
        self.tick_count = 0
        self.tick_lock = threading.Lock()
        self.last_tick_type: TickType | None = None

        tasks_path = root_dir / config["paths"]["tasks"]
        memory_dir = root_dir / config["paths"]["memory_dir"]

        # Memory config
        mem_cfg = config.get("memory", {})
        importance_decay = float(mem_cfg.get("importance_decay", 0.95))

        self.short_memory = ShortMemory(importance_decay=importance_decay)
        self.long_memory = LongMemory(memory_dir)
        self.task_manager = TaskManager(tasks_path)
        self.planner = Planner()

        self.llm_client = LLMClient(
            base_url=config["model"]["base_url"],
            model=config["model"]["model"],
            temperature=config["model"]["temperature"],
        )
        self.reflection = ReflectionEngine(llm_client=self.llm_client)
        self.guardian = GuardianLayer(config["guardian"])
        self.memory_compactor = MemoryCompactor(self.long_memory, llm_client=self.llm_client)
        self.tools = ToolRegistry(self.long_memory)
        self.interaction: InteractionManager | None = None

        # Cognitive budget
        self.budget = CognitiveBudget(config)

        # Memory router (sparse topic loading)
        max_topics = self.budget.max_loaded_topics
        self.memory_router = MemoryRouter(
            indexer=self.long_memory.indexer,
            max_loaded_topics=max_topics,
        )

        # Context assembler
        self.context_assembler = ContextAssembler(self.budget)

        # Anti-degeneration guards
        self.anti_degen = AntiDegeneration()

        # Track which topics were loaded this tick (for per-topic compaction)
        self._loaded_topics_this_tick: list[str] = []

        interaction_cfg = config.get("interaction", {})
        if interaction_cfg.get("enabled", False):
            self.interaction = InteractionManager(
                inbox_path=root_dir / interaction_cfg.get("inbox_path", "workspace/inbox.md"),
                outbox_path=root_dir / interaction_cfg.get("outbox_path", "workspace/outbox.md"),
            )

    # ------------------------------------------------------------------
    # Task execution
    # ------------------------------------------------------------------

    def _execute_task(self, task: str, loaded_topics: dict[str, str]) -> str:
        assembled_context = self.context_assembler.assemble(
            task=task,
            short_memory_export=self.short_memory.export(),
            loaded_topics=loaded_topics,
        )
        plan = self.planner.plan_for_task(task, context_prompt=assembled_context)
        result = f"Task executada: {plan.task}. Motivo: {plan.reason}."
        self.short_memory.add_action(result, importance=0.7)
        self.long_memory.append_decision(result)
        # Route decision to topic tree
        self.long_memory.append_to_topic(result)
        return result

    # ------------------------------------------------------------------
    # Reflection (with cooldown and anti-degeneration)
    # ------------------------------------------------------------------

    def _is_reflection_enabled(self) -> bool:
        """Return True if reflection is enabled according to the active config."""
        reflection_cfg = self.config.get("reflection", {})
        agent_fallback = self.config["agent"].get("reflection_enabled", True)
        return reflection_cfg.get("enabled", agent_fallback)

    def _run_reflection(self, loaded_topics: dict[str, str]) -> None:
        if not self._is_reflection_enabled():
            return

        if not self.budget.can_reflect(self.tick_count):
            self.logger.info("Reflection skipped (cooldown or daily limit)")
            return

        assembled_context = self.context_assembler.assemble(
            task="idle reflection",
            short_memory_export=self.short_memory.export(),
            loaded_topics=loaded_topics,
        )
        reflection_text = self.reflection.reflect(
            short_summary=self.short_memory.summary,
            recent_actions=list(self.short_memory.actions),
            recent_observations=list(self.short_memory.observations),
            routed_context=assembled_context,
        )

        if self.anti_degen.should_suppress_reflection(reflection_text):
            self.logger.info("Reflection suppressed by anti-degeneration guard")
            return

        self.anti_degen.record_reflection(reflection_text)
        self.budget.record_reflection(self.tick_count)
        self.short_memory.add_observation(reflection_text, importance=0.6)
        self.long_memory.append_reflection(reflection_text)
        self.logger.info("Reflection recorded")

    # ------------------------------------------------------------------
    # Guardian checkpoint (extended with budget inspection)
    # ------------------------------------------------------------------

    def _guardian_checkpoint(self) -> None:
        guardian_cfg = self.config["guardian"]
        if not guardian_cfg.get("enabled", True):
            return

        if self.tick_count % max(1, guardian_cfg.get("check_every_ticks", 6)) != 0:
            return

        # Classic prompt-size check
        context_payload = json.dumps(self.short_memory.export(), ensure_ascii=False)
        report = self.guardian.check_prompt(
            context_payload,
            main_context_limit=guardian_cfg.get("main_context_limit", 16000),
            safe_context_ratio=guardian_cfg.get("safe_context_ratio", 0.7),
        )
        if report.action == "compress" and report.repaired_prompt:
            max_chars = self.config["agent"].get("max_short_summary_chars", 500)
            self.short_memory.summary = report.repaired_prompt[:max_chars]
            self.logger.warning("Guardian compressed short-memory summary")

        # Cognitive budget inspection
        budget_report = self.guardian.check_cognitive_budget(
            {**self.budget.status(), "max_loaded_topics": self.budget.max_loaded_topics},
            loaded_topic_count=len(self._loaded_topics_this_tick),
        )
        if budget_report.action == "compress":
            self.logger.warning("Guardian: prompt compression recommended due to token budget pressure")
        elif budget_report.action == "prune_branches":
            self.logger.warning("Guardian: too many memory branches loaded, prune recommended")

    # ------------------------------------------------------------------
    # Main tick
    # ------------------------------------------------------------------

    def tick(self, reason: str | TickType = TickType.SCHEDULED) -> None:
        tick_type = TickType.from_reason(reason)
        if not self.tick_lock.acquire(blocking=False):
            self.logger.info("Tick %s skipped because another tick is currently running", tick_type.value)
            return
        try:
            if tick_type == TickType.INTERACTIVE:
                self._run_interactive_tick()
            elif tick_type == TickType.MAINTENANCE:
                self._run_maintenance_tick()
            elif tick_type == TickType.RECOVERY:
                self._run_recovery_tick()
            else:
                self._run_scheduled_tick()
        finally:
            self.tick_lock.release()

    def _run_scheduled_tick(self) -> None:
        self.last_tick_type = TickType.SCHEDULED
        self.tick_count += 1
        self.logger.info("Tick #%s started (%s)", self.tick_count, TickType.SCHEDULED.value)
        self.budget.new_tick(self.tick_count)
        self._loaded_topics_this_tick = []

        pending = self.task_manager.get_pending_tasks(
            limit=self.config["agent"].get("max_tasks_per_tick", 3)
        )

        if pending:
            # Route relevant memory for the first task (representative query)
            first_task = pending[0]
            loaded_topics = self.memory_router.route(
                task=first_task,
                short_memory_text=self.short_memory.summary,
            )
            self._loaded_topics_this_tick = list(loaded_topics.keys())

            for task in pending:
                if self.anti_degen.is_task_duplicate(task):
                    self.task_manager.mark_done(task, "duplicate suppressed")
                    self.logger.info("Task suppressed as duplicate: %s", task)
                    continue
                self.anti_degen.record_task(task)
                result = self._execute_task(task, loaded_topics=loaded_topics)
                self.task_manager.mark_done(task, result)
                self.short_memory.add_observation(result, importance=0.6)
                self.long_memory.append_long_term(f"Task concluída: {task}")
                self.logger.info("Task completed: %s", task)
        else:
            # Idle tick: load general context and reflect
            loaded_topics = self.memory_router.route(
                task="idle reflection",
                short_memory_text=self.short_memory.summary,
            )
            self._loaded_topics_this_tick = list(loaded_topics.keys())

            if self.config["agent"].get("reflection_enabled", True):
                self._run_reflection(loaded_topics=loaded_topics)

        self.short_memory.summarize()

        # Per-topic compaction (only for topics that were active this tick).
        # No compaction of any kind runs when the hourly budget is exhausted.
        if not self.budget.can_compact():
            self.logger.info("Compaction skipped (hourly budget exhausted)")
        else:
            if self._loaded_topics_this_tick:
                self.memory_compactor.compact_topics_if_needed(self._loaded_topics_this_tick)
            else:
                # Fall back to legacy flat-file compaction when no topics were loaded.
                self.memory_compactor.compact_if_needed()
            self.budget.record_compaction()

        self._guardian_checkpoint()
        self.logger.info("Tick #%s finished (%s)", self.tick_count, TickType.SCHEDULED.value)

    def _run_interactive_tick(self) -> None:
        self.last_tick_type = TickType.INTERACTIVE
        self.tick_count += 1
        self.logger.info("Tick #%s started (%s)", self.tick_count, TickType.INTERACTIVE.value)
        self.budget.new_tick(self.tick_count)
        self._loaded_topics_this_tick = []
        interaction_cfg = self.config.get("interaction", {})
        if not interaction_cfg.get("enabled", False) or not self.interaction:
            self.logger.info("Interactive tick skipped: interaction layer disabled")
            return
        if not interaction_cfg.get("interactive_tick_enabled", True):
            self.logger.info("Interactive tick skipped by configuration")
            return

        interactive_cfg = self.config.get("interactive_tick", {})
        queue_limit = int(interaction_cfg.get("max_queue_size", 100))
        queue_report = self.guardian.check_interaction_queue(
            pending_count=self.interaction.pending_count(),
            max_queue_size=queue_limit,
            payload_integrity_ok=self.interaction.payload_integrity_ok(),
        )
        if queue_report.action == "sanitize_payload":
            self.logger.warning("Interactive inbox payload malformed; skipping tick processing")
            return
        if queue_report.action == "queue_overflow":
            self.logger.warning("Interactive inbox overflow risk detected: %s", queue_report.reason)

        pending = self.interaction.read_pending_messages(
            limit=int(interactive_cfg.get("max_messages_per_tick", 3))
        )
        if not pending:
            self.logger.info("Interactive tick finished with no pending inbox messages")
            return

        interactive_token_budget = int(interactive_cfg.get("max_tokens", 4000))
        estimated_tokens = sum(max(1, len(msg.content) // 4) for msg in pending)
        budget_report = self.guardian.check_cognitive_budget(
            {
                "tokens_this_tick": estimated_tokens,
                "max_tokens_per_tick": interactive_token_budget,
                "max_loaded_topics": int(interactive_cfg.get("max_loaded_topics", 2)),
            },
            loaded_topic_count=0,
        )
        if budget_report.action == "compress":
            self.logger.warning("Interactive token budget pressure detected: %s", budget_report.reason)

        query = pending[0].content
        max_loaded_topics = int(interactive_cfg.get("max_loaded_topics", 2))
        loaded_topics = self.memory_router.route(
            task=query,
            short_memory_text=self.short_memory.summary,
        )
        loaded_topics = dict(list(loaded_topics.items())[:max_loaded_topics])
        self._loaded_topics_this_tick = list(loaded_topics.keys())

        for message in pending:
            directive, payload = self.interaction.classify_directive(message.content)
            response_text = self._handle_interaction_directive(directive, payload)
            self.interaction.append_response(
                content=response_text,
                response_id=message.id,
                metadata={"directive": directive, "reply_to": message.id},
            )
            self.interaction.mark_processed(message.id)

            self.short_memory.add_observation(f"Human interaction ({directive}): {payload}", importance=0.8)
            self.short_memory.add_action(response_text, importance=0.6)
            self.long_memory.append_long_term(f"Interação processada ({directive}): {payload}")
            self.long_memory.append_to_topic(response_text)

        self.short_memory.summarize()
        self._guardian_checkpoint()
        self.logger.info("Tick #%s finished (%s)", self.tick_count, TickType.INTERACTIVE.value)

    def _handle_interaction_directive(self, directive: str, payload: str) -> str:
        cleaned = payload.strip()
        if directive == "invalid" or not cleaned:
            return "Mensagem inválida ignorada: conteúdo vazio."
        if directive == "task":
            created = self.task_manager.add_task(cleaned)
            if created:
                return f"Tarefa registrada para execução autônoma: {cleaned}"
            return f"Tarefa já existente na fila: {cleaned}"
        if directive == "note":
            self.short_memory.add_observation(f"Nota humana: {cleaned}", importance=0.7)
            self.long_memory.append_fact(f"Nota humana registrada: {cleaned}")
            return "Nota registrada na memória de trabalho e memória longa."
        if directive == "ask":
            return self._build_ask_state_response(question=cleaned)
        return f"Mensagem recebida e registrada para execução no loop autônomo: {cleaned}"

    def _build_ask_state_response(self, question: str) -> str:
        pending = self.task_manager.get_pending_tasks(limit=3)
        pending_text = ", ".join(pending) if pending else "nenhuma"
        last_tick = self.last_tick_type.value if self.last_tick_type else "none"
        summary = self.short_memory.summary
        return (
            "Estado atual do runtime:\n"
            f"- pergunta: {question}\n"
            f"- tick_atual: {TickType.INTERACTIVE.value}\n"
            f"- ultimo_tick: {last_tick}\n"
            f"- tarefas_pendentes: {pending_text}\n"
            f"- resumo_memoria_curta: {summary}"
        )

    def _run_maintenance_tick(self) -> None:
        self.last_tick_type = TickType.MAINTENANCE
        self.tick_count += 1
        self.logger.info("Tick #%s started (%s)", self.tick_count, TickType.MAINTENANCE.value)
        self.budget.new_tick(self.tick_count)
        self._loaded_topics_this_tick = []
        self._guardian_checkpoint()
        self.logger.info("Tick #%s finished (%s)", self.tick_count, TickType.MAINTENANCE.value)

    def _run_recovery_tick(self) -> None:
        self.last_tick_type = TickType.RECOVERY
        self.tick_count += 1
        self.logger.info("Tick #%s started (%s)", self.tick_count, TickType.RECOVERY.value)
        self.budget.new_tick(self.tick_count)
        self._loaded_topics_this_tick = []
        self._guardian_checkpoint()
        self.logger.info("Tick #%s finished (%s)", self.tick_count, TickType.RECOVERY.value)

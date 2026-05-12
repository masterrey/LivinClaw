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
from pathlib import Path

from agent.anti_degeneration import AntiDegeneration
from agent.cognitive_budget import CognitiveBudget
from agent.context_assembler import ContextAssembler
from agent.planner import Planner
from agent.reflection import ReflectionEngine
from guardian.guardian import GuardianLayer
from llm.llm_client import LLMClient
from memory.long_memory import LongMemory
from memory.memory_compactor import MemoryCompactor
from memory.memory_router import MemoryRouter
from memory.short_memory import ShortMemory
from tasks.task_manager import TaskManager
from tools.tool_registry import ToolRegistry


class AliveAgent:
    def __init__(self, config: dict, root_dir: Path) -> None:
        self.config = config
        self.root_dir = root_dir
        self.logger = logging.getLogger(__name__)
        self.tick_count = 0

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

    # ------------------------------------------------------------------
    # Task execution
    # ------------------------------------------------------------------

    def _execute_task(self, task: str) -> str:
        plan = self.planner.plan_for_task(task)
        result = f"Task executada: {plan.task}. Motivo: {plan.reason}."
        self.short_memory.add_action(result, importance=0.7)
        self.long_memory.append_decision(result)
        # Route decision to topic tree
        self.long_memory.append_to_topic(result)
        return result

    # ------------------------------------------------------------------
    # Reflection (with cooldown and anti-degeneration)
    # ------------------------------------------------------------------

    def _run_reflection(self) -> None:
        reflection_cfg = self.config.get("reflection", {})
        if not reflection_cfg.get("enabled", self.config["agent"].get("reflection_enabled", True)):
            return

        if not self.budget.can_reflect(self.tick_count):
            self.logger.info("Reflection skipped (cooldown or daily limit)")
            return

        reflection_text = self.reflection.reflect(
            short_summary=self.short_memory.summary,
            recent_actions=list(self.short_memory.actions),
            recent_observations=list(self.short_memory.observations),
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

    def tick(self) -> None:
        self.tick_count += 1
        self.logger.info("Tick #%s started", self.tick_count)
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
                    self.logger.info("Task skipped (duplicate detected): %s", task)
                    continue
                self.anti_degen.record_task(task)
                result = self._execute_task(task)
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
                self._run_reflection()

        self.short_memory.summarize()

        # Per-topic compaction (only for topics that were active this tick)
        if self.budget.can_compact() and self._loaded_topics_this_tick:
            self.memory_compactor.compact_topics_if_needed(self._loaded_topics_this_tick)
            self.budget.record_compaction()
        else:
            # Fall back to legacy flat-file compaction
            self.memory_compactor.compact_if_needed()

        self._guardian_checkpoint()
        self.logger.info("Tick #%s finished", self.tick_count)

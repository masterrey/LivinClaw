from __future__ import annotations

import json
import logging
from pathlib import Path

from agent.planner import Planner
from agent.reflection import ReflectionEngine
from guardian.guardian import GuardianLayer
from llm.llm_client import LLMClient
from memory.long_memory import LongMemory
from memory.memory_compactor import MemoryCompactor
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

        self.short_memory = ShortMemory()
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

    def _execute_task(self, task: str) -> str:
        plan = self.planner.plan_for_task(task)
        result = f"Task executada: {plan.task}. Motivo: {plan.reason}."
        self.short_memory.add_action(result)
        self.long_memory.append_decision(result)
        return result

    def _run_reflection(self) -> None:
        reflection_text = self.reflection.reflect(
            short_summary=self.short_memory.summary,
            recent_actions=list(self.short_memory.actions),
            recent_observations=list(self.short_memory.observations),
        )
        self.short_memory.add_observation(reflection_text)
        self.long_memory.append_reflection(reflection_text)
        self.logger.info("Reflection recorded")

    def _guardian_checkpoint(self) -> None:
        guardian_cfg = self.config["guardian"]
        if not guardian_cfg.get("enabled", True):
            return

        if self.tick_count % max(1, guardian_cfg.get("check_every_ticks", 6)) != 0:
            return

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

    def tick(self) -> None:
        self.tick_count += 1
        self.logger.info("Tick #%s started", self.tick_count)

        pending = self.task_manager.get_pending_tasks(limit=self.config["agent"].get("max_tasks_per_tick", 3))
        if pending:
            for task in pending:
                result = self._execute_task(task)
                self.task_manager.mark_done(task, result)
                self.short_memory.add_observation(result)
                self.long_memory.append_long_term(f"Task concluída: {task}")
                self.logger.info("Task completed: %s", task)
        elif self.config["agent"].get("reflection_enabled", True):
            self._run_reflection()

        self.short_memory.summarize()
        self.memory_compactor.compact_if_needed()
        self._guardian_checkpoint()
        self.logger.info("Tick #%s finished", self.tick_count)

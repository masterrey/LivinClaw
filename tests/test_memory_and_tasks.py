from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from guardian.guardian import GuardianLayer
from memory.short_memory import ShortMemory
from tasks.task_manager import TaskManager


class MiniClawCoreTests(unittest.TestCase):
    def test_short_memory_caps_at_twenty(self) -> None:
        mem = ShortMemory()
        for i in range(30):
            mem.add_action(f"a{i}")
            mem.add_observation(f"o{i}")

        self.assertEqual(20, len(mem.actions))
        self.assertEqual(20, len(mem.observations))
        self.assertEqual("a10", list(mem.actions)[0])

    def test_task_manager_marks_done(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tasks_file = Path(tmp) / "tasks.md"
            tasks_file.write_text("- [ ] tarefa A\n- [ ] tarefa B\n", encoding="utf-8")
            manager = TaskManager(tasks_file)

            pending = manager.get_pending_tasks(limit=1)
            self.assertEqual(["tarefa A"], pending)

            manager.mark_done("tarefa A", "ok")
            content = tasks_file.read_text(encoding="utf-8")
            self.assertIn("- [x] tarefa A — ok", content)

    def test_guardian_compresses_large_prompt(self) -> None:
        guardian = GuardianLayer(
            {
                "max_guardian_tokens": 3000,
                "main_context_limit": 16000,
                "safe_context_ratio": 0.7,
            }
        )
        huge_prompt = "x" * 60000
        report = guardian.check_prompt(huge_prompt, main_context_limit=16000, safe_context_ratio=0.7)
        self.assertEqual("compress", report.action)
        self.assertTrue(report.repaired_prompt)


class ShortMemoryImportanceTests(unittest.TestCase):
    def test_weighted_entries_added(self) -> None:
        mem = ShortMemory()
        mem.add_action("action one", importance=0.9)
        mem.add_observation("obs one", importance=0.3)
        self.assertEqual(2, len(mem.weighted_entries))
        self.assertAlmostEqual(0.9, mem.weighted_entries[0].importance)

    def test_importance_decay_on_summarize(self) -> None:
        mem = ShortMemory(importance_decay=0.5)
        mem.add_action("decay test", importance=1.0)
        mem.summarize()
        entry = mem.weighted_entries[0]
        self.assertAlmostEqual(0.5, entry.importance)

    def test_pruning_removes_low_importance(self) -> None:
        from memory.short_memory import MAX_WEIGHTED_ENTRIES
        mem = ShortMemory()
        # Fill beyond cap with low-importance entries
        for i in range(MAX_WEIGHTED_ENTRIES + 5):
            mem.add_action(f"low importance action {i}", importance=0.1)
        self.assertLessEqual(len(mem.weighted_entries), MAX_WEIGHTED_ENTRIES)

    def test_top_entries_returns_highest_importance(self) -> None:
        mem = ShortMemory()
        mem.add_action("low", importance=0.1)
        mem.add_action("high", importance=0.9)
        mem.add_action("mid", importance=0.5)
        top = mem.top_entries(n=1)
        self.assertEqual("high", top[0].text)


class TopicClassifierTests(unittest.TestCase):
    def test_classify_guardian_text(self) -> None:
        from memory.topic_classifier import TopicClassifier
        clf = TopicClassifier()
        topic = clf.classify("Guardian compressed an oversized prompt due to context limit")
        self.assertEqual("guardian", topic)

    def test_classify_mcp_text(self) -> None:
        from memory.topic_classifier import TopicClassifier
        clf = TopicClassifier()
        topic = clf.classify("MCP integration with JSON-RPC protocol invocation")
        self.assertEqual("mcp", topic)

    def test_default_topic_for_empty(self) -> None:
        from memory.topic_classifier import TopicClassifier, DEFAULT_TOPIC
        clf = TopicClassifier()
        self.assertEqual(DEFAULT_TOPIC, clf.classify(""))


class MemoryIndexerTests(unittest.TestCase):
    def test_index_creates_structure(self) -> None:
        from memory.memory_indexer import MemoryIndexer
        with tempfile.TemporaryDirectory() as tmp:
            indexer = MemoryIndexer(Path(tmp))
            self.assertTrue((Path(tmp) / "index.md").exists())
            topics = [t["name"] for t in indexer.all_topics()]
            self.assertIn("guardian", topics)
            self.assertIn("mcp", topics)

    def test_append_and_load(self) -> None:
        from memory.memory_indexer import MemoryIndexer
        with tempfile.TemporaryDirectory() as tmp:
            indexer = MemoryIndexer(Path(tmp))
            indexer.append_to_topic_file("guardian", "incidents.md", "Test incident")
            content = indexer.load_topic_files("guardian")
            self.assertIn("Test incident", content)

    def test_importance_update(self) -> None:
        from memory.memory_indexer import MemoryIndexer
        with tempfile.TemporaryDirectory() as tmp:
            indexer = MemoryIndexer(Path(tmp))
            indexer.update_importance("mcp", 0.99)
            self.assertAlmostEqual(0.99, indexer.get_topic("mcp")["importance"])


class MemoryRouterTests(unittest.TestCase):
    def test_router_limits_topics(self) -> None:
        from memory.memory_indexer import MemoryIndexer
        from memory.memory_router import MemoryRouter
        with tempfile.TemporaryDirectory() as tmp:
            indexer = MemoryIndexer(Path(tmp))
            router = MemoryRouter(indexer, max_loaded_topics=2)
            loaded = router.route("guardian compressed oversized prompt", "")
            self.assertLessEqual(len(loaded), 2)

    def test_router_never_loads_all(self) -> None:
        from memory.memory_indexer import MemoryIndexer, DEFAULT_TOPICS
        from memory.memory_router import MemoryRouter
        with tempfile.TemporaryDirectory() as tmp:
            indexer = MemoryIndexer(Path(tmp))
            total_topics = len(DEFAULT_TOPICS)
            router = MemoryRouter(indexer, max_loaded_topics=total_topics - 1)
            loaded = router.route("some unrelated text", "")
            self.assertLess(len(loaded), total_topics)


class CognitiveBudgetTests(unittest.TestCase):
    def _make_budget(self, **overrides):
        from agent.cognitive_budget import CognitiveBudget
        cfg = {
            "cognitive_budget": {
                "max_tokens_per_tick": 1000,
                "max_loaded_topics": 3,
                "max_reflections_per_day": 5,
                "reflection_cooldown_ticks": 2,
                "max_compactions_per_hour": 1,
                **overrides,
            }
        }
        return CognitiveBudget(cfg)

    def test_can_reflect_respects_cooldown(self) -> None:
        budget = self._make_budget(reflection_cooldown_ticks=3)
        self.assertTrue(budget.can_reflect(current_tick=1))
        budget.record_reflection(current_tick=1)
        self.assertFalse(budget.can_reflect(current_tick=2))  # only 1 tick later
        self.assertTrue(budget.can_reflect(current_tick=4))   # 3 ticks later

    def test_daily_reflection_limit(self) -> None:
        budget = self._make_budget(max_reflections_per_day=2, reflection_cooldown_ticks=1)
        budget.record_reflection(0)
        budget.record_reflection(1)
        self.assertFalse(budget.can_reflect(2))

    def test_token_budget_tracking(self) -> None:
        budget = self._make_budget(max_tokens_per_tick=100)
        budget.new_tick(1)
        self.assertTrue(budget.can_use_tokens(50))
        budget.record_tokens(90)
        self.assertFalse(budget.can_use_tokens(20))

    def test_prompt_clipping(self) -> None:
        budget = self._make_budget(max_tokens_per_tick=10)  # 40 chars budget
        long_prompt = "x" * 200
        clipped = budget.clip_prompt(long_prompt)
        self.assertLessEqual(len(clipped), 60)  # some slack for the clip marker


class AntiDegenerationTests(unittest.TestCase):
    def test_duplicate_reflection_suppressed(self) -> None:
        from agent.anti_degeneration import AntiDegeneration
        ad = AntiDegeneration()
        text = "manter estabilidade e priorizar tarefas pendentes com foco em resultados"
        ad.record_reflection(text)
        self.assertTrue(ad.is_reflection_duplicate(text))

    def test_unique_reflection_allowed(self) -> None:
        from agent.anti_degeneration import AntiDegeneration
        ad = AntiDegeneration()
        ad.record_reflection("reflection about architecture module design")
        # Completely different text
        self.assertFalse(ad.is_reflection_duplicate("totally different topic about users"))

    def test_low_entropy_detection(self) -> None:
        from agent.anti_degeneration import AntiDegeneration
        ad = AntiDegeneration()
        self.assertTrue(ad.is_low_entropy("x x x x x x x x x x x"))

    def test_task_deduplication(self) -> None:
        from agent.anti_degeneration import AntiDegeneration
        ad = AntiDegeneration()
        task = "implement the guardian layer safety check system"
        ad.record_task(task)
        self.assertTrue(ad.is_task_duplicate(task))


class GuardianCognitiveBudgetTests(unittest.TestCase):
    def test_guardian_reports_prune_when_too_many_topics(self) -> None:
        guardian = GuardianLayer({"max_guardian_tokens": 3000})
        report = guardian.check_cognitive_budget(
            {"tokens_this_tick": 100, "max_tokens_per_tick": 12000, "max_loaded_topics": 3},
            loaded_topic_count=5,
        )
        self.assertEqual("prune_branches", report.action)

    def test_guardian_ok_within_budget(self) -> None:
        guardian = GuardianLayer({"max_guardian_tokens": 3000})
        report = guardian.check_cognitive_budget(
            {"tokens_this_tick": 100, "max_tokens_per_tick": 12000, "max_loaded_topics": 3},
            loaded_topic_count=2,
        )
        self.assertEqual("none", report.action)


class ContextAssemblerTests(unittest.TestCase):
    def _make_assembler(self):
        from agent.cognitive_budget import CognitiveBudget
        from agent.context_assembler import ContextAssembler
        budget = CognitiveBudget({"cognitive_budget": {"max_tokens_per_tick": 4000}})
        return ContextAssembler(budget)

    def test_assembles_all_sections(self) -> None:
        assembler = self._make_assembler()
        export = {"summary": "test summary", "actions": ["a1"], "observations": ["o1"], "open_intentions": []}
        prompt = assembler.assemble("do something", export, {"guardian": "guardian content"})
        self.assertIn("Current Task", prompt)
        self.assertIn("Working Memory", prompt)

    def test_prompt_respects_budget(self) -> None:
        from agent.cognitive_budget import CognitiveBudget
        from agent.context_assembler import ContextAssembler
        budget = CognitiveBudget({"cognitive_budget": {"max_tokens_per_tick": 50}})  # tiny budget
        assembler = ContextAssembler(budget)
        export = {"summary": "x" * 1000, "actions": [], "observations": [], "open_intentions": []}
        prompt = assembler.assemble("task", export, {})
        self.assertLessEqual(len(prompt), 50 * 4 + 100)  # allow small overshoot for clip marker


class PlannerAndReflectionContextWiringTests(unittest.TestCase):
    def test_planner_marks_context_aware_reason_when_context_present(self) -> None:
        from agent.planner import Planner
        planner = Planner()
        plan = planner.plan_for_task("do task", context_prompt="## Relevant Memory\nx")
        self.assertIn("routed memory context", plan.reason)

    def test_reflection_fallback_mentions_routed_context(self) -> None:
        from agent.reflection import ReflectionEngine
        reflection = ReflectionEngine(llm_client=None)
        text = reflection.reflect(
            short_summary="summary",
            recent_actions=["a1"],
            recent_observations=["o1"],
            routed_context="## Relevant Memory\nguardian incident",
        )
        self.assertIn("com contexto roteado", text)

    def test_reflection_llm_prompt_includes_routed_context(self) -> None:
        from agent.reflection import ReflectionEngine

        class FakeLLMClient:
            def __init__(self) -> None:
                self.messages: list[dict] = []

            def chat(self, messages):
                self.messages = messages
                return "ok"

        llm = FakeLLMClient()
        reflection = ReflectionEngine(llm_client=llm)
        routed_context = "## Relevant Memory\nmcp decision x"
        reflection.reflect(
            short_summary="summary",
            recent_actions=["a1"],
            recent_observations=["o1"],
            routed_context=routed_context,
        )
        self.assertTrue(llm.messages)
        user_prompt = llm.messages[1]["content"]
        self.assertIn(routed_context, user_prompt)


class AliveAgentDuplicateTaskTests(unittest.TestCase):
    def test_duplicate_task_is_marked_done_with_suppression_result(self) -> None:
        from agent.alive_agent import AliveAgent

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tasks_file = root / "workspace" / "tasks.md"
            tasks_file.parent.mkdir(parents=True, exist_ok=True)
            tasks_file.write_text("- [ ] tarefa A\n", encoding="utf-8")

            config = {
                "agent": {
                    "max_tasks_per_tick": 3,
                    "reflection_enabled": False,
                    "max_short_summary_chars": 500,
                },
                "guardian": {
                    "enabled": False,
                    "check_every_ticks": 6,
                    "max_guardian_tokens": 3000,
                    "main_context_limit": 16000,
                    "safe_context_ratio": 0.7,
                },
                "model": {
                    "base_url": "http://127.0.0.1:1234/v1",
                    "model": "test-model",
                    "temperature": 0.3,
                },
                "paths": {
                    "tasks": "workspace/tasks.md",
                    "memory_dir": "workspace/memory",
                },
                "memory": {"importance_decay": 0.95},
                "cognitive_budget": {
                    "max_tokens_per_tick": 1000,
                    "max_loaded_topics": 3,
                    "max_reflections_per_day": 5,
                    "reflection_cooldown_ticks": 2,
                    "max_compactions_per_hour": 1,
                },
                "reflection": {"enabled": False},
            }

            agent = AliveAgent(config=config, root_dir=root)
            agent.anti_degen.record_task("tarefa A")

            agent.tick()

            content = tasks_file.read_text(encoding="utf-8")
            self.assertIn("- [x] tarefa A — duplicate suppressed", content)
            self.assertEqual([], agent.task_manager.get_pending_tasks())


if __name__ == "__main__":
    unittest.main()

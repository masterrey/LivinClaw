from __future__ import annotations

# tests/test_interaction_context.py
# Tests for InteractionContextBuilder, InteractionContext, and related integration.
# All tests use mocked LLM clients and mock memory components.
# No running LM Studio is required.

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch, call

from agent.interaction_context import (
    InteractionContext,
    InteractionContextBuilder,
    should_record_interaction,
    ACTION_POLICY,
)
from agent.interaction_responder import InteractionResponder, _build_prompt_from_context
from agent.alive_agent import AliveAgent, TickType
from memory.short_memory import ShortMemory


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_builder(
    short_memory=None,
    task_manager=None,
    memory_router=None,
    cognitive_budget=None,
    config=None,
) -> InteractionContextBuilder:
    return InteractionContextBuilder(
        short_memory=short_memory,
        task_manager=task_manager,
        memory_router=memory_router,
        cognitive_budget=cognitive_budget,
        config=config or {},
    )


def _base_config() -> dict:
    return {
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
        "interaction": {
            "enabled": True,
            "interactive_tick_enabled": True,
            "inbox_path": "workspace/inbox.md",
            "outbox_path": "workspace/outbox.md",
            "max_queue_size": 100,
        },
        "interactive_tick": {
            "reflection_enabled": False,
            "memory_compaction_enabled": False,
            "max_loaded_topics": 2,
            "max_tokens": 4000,
            "prioritize_inbox": True,
            "max_messages_per_tick": 3,
        },
        "chat_context": {
            "max_prompt_chars": 6000,
            "max_short_memory_chars": 1200,
            "max_topic_chars": 2000,
            "max_pending_tasks": 5,
            "max_recent_observations": 5,
            "max_recent_actions": 5,
            "max_loaded_topics": 2,
            "update_short_memory": True,
        },
    }


def _make_agent(tmp_root: Path) -> AliveAgent:
    tasks_file = tmp_root / "workspace/tasks.md"
    tasks_file.parent.mkdir(parents=True, exist_ok=True)
    tasks_file.write_text("", encoding="utf-8")
    return AliveAgent(config=_base_config(), root_dir=tmp_root)


# ---------------------------------------------------------------------------
# InteractionContextBuilder unit tests
# ---------------------------------------------------------------------------


class BuilderWithShortMemoryTests(unittest.TestCase):
    def test_builds_context_with_short_memory_summary(self) -> None:
        sm = ShortMemory()
        sm.summary = "Agent is working on PR #8."
        builder = _make_builder(short_memory=sm)
        ctx = builder.build_for_message("hello", {"tick_type": "interactive", "model_name": "m1"})
        self.assertIsInstance(ctx, InteractionContext)
        self.assertEqual("Agent is working on PR #8.", ctx.short_memory_summary)

    def test_builds_context_includes_pending_tasks(self) -> None:
        task_manager = MagicMock()
        task_manager.get_pending_tasks.return_value = ["task A", "task B"]
        builder = _make_builder(task_manager=task_manager)
        ctx = builder.build_for_message("what are my tasks?", {})
        self.assertIn("task A", ctx.pending_tasks)
        self.assertIn("task B", ctx.pending_tasks)

    def test_truncates_long_short_memory(self) -> None:
        sm = ShortMemory()
        sm.summary = "x" * 2000
        builder = _make_builder(short_memory=sm, config={"max_short_memory_chars": 100})
        ctx = builder.build_for_message("test", {})
        self.assertLessEqual(len(ctx.short_memory_summary), 100)

    def test_respects_max_pending_tasks(self) -> None:
        task_manager = MagicMock()
        task_manager.get_pending_tasks.return_value = [f"task {i}" for i in range(20)]
        builder = _make_builder(task_manager=task_manager, config={"max_pending_tasks": 3})
        ctx = builder.build_for_message("tasks?", {})
        self.assertLessEqual(len(ctx.pending_tasks), 3)

    def test_degrades_gracefully_when_short_memory_missing(self) -> None:
        builder = _make_builder(short_memory=None)
        ctx = builder.build_for_message("test", {})
        self.assertEqual("Not available yet", ctx.short_memory_summary)
        self.assertIn("Short memory not available", ctx.warnings)

    def test_degrades_gracefully_when_task_manager_missing(self) -> None:
        builder = _make_builder(task_manager=None)
        ctx = builder.build_for_message("test", {})
        self.assertEqual([], ctx.pending_tasks)
        self.assertIn("Task manager not available", ctx.warnings)

    def test_degrades_gracefully_when_memory_router_missing(self) -> None:
        builder = _make_builder(memory_router=None)
        ctx = builder.build_for_message("test", {})
        self.assertEqual({}, ctx.routed_memory)
        self.assertIn("Topic memory routing not available yet", ctx.warnings)

    def test_degrades_gracefully_when_cognitive_budget_missing(self) -> None:
        builder = _make_builder(cognitive_budget=None)
        ctx = builder.build_for_message("test", {})
        self.assertEqual({}, ctx.budget_summary)
        self.assertIn("Cognitive budget not available", ctx.warnings)

    def test_includes_recent_observations(self) -> None:
        sm = ShortMemory()
        sm.add_observation("obs one", importance=0.5)
        sm.add_observation("obs two", importance=0.5)
        builder = _make_builder(short_memory=sm)
        ctx = builder.build_for_message("test", {})
        self.assertIn("obs one", ctx.recent_observations)
        self.assertIn("obs two", ctx.recent_observations)

    def test_includes_recent_actions(self) -> None:
        sm = ShortMemory()
        sm.add_action("action alpha", importance=0.5)
        builder = _make_builder(short_memory=sm)
        ctx = builder.build_for_message("test", {})
        self.assertIn("action alpha", ctx.recent_actions)

    def test_tick_type_and_model_name_from_runtime_context(self) -> None:
        builder = _make_builder()
        ctx = builder.build_for_message("hello", {"tick_type": "maintenance", "model_name": "gpt-test"})
        self.assertEqual("maintenance", ctx.tick_type)
        self.assertEqual("gpt-test", ctx.model_name)

    def test_action_policy_always_present(self) -> None:
        builder = _make_builder()
        ctx = builder.build_for_message("test", {})
        self.assertEqual(ACTION_POLICY, ctx.action_policy)

    def test_all_components_integrated(self) -> None:
        sm = ShortMemory()
        sm.summary = "Agent is ready."
        sm.add_observation("obs", importance=0.5)
        sm.add_action("act", importance=0.5)

        task_manager = MagicMock()
        task_manager.get_pending_tasks.return_value = ["task X"]

        memory_router = MagicMock()
        memory_router.route.return_value = {"topic_a": "content A"}

        cognitive_budget = MagicMock()
        cognitive_budget.status.return_value = {"tokens_this_tick": 100, "max_tokens_per_tick": 1000}

        builder = _make_builder(
            short_memory=sm,
            task_manager=task_manager,
            memory_router=memory_router,
            cognitive_budget=cognitive_budget,
        )
        ctx = builder.build_for_message("how do you work?", {"tick_type": "interactive", "model_name": "test"})

        self.assertEqual("Agent is ready.", ctx.short_memory_summary)
        self.assertIn("task X", ctx.pending_tasks)
        self.assertIn("topic_a", ctx.routed_memory)
        self.assertEqual(100, ctx.budget_summary.get("tokens_this_tick"))
        self.assertEqual([], ctx.warnings)


# ---------------------------------------------------------------------------
# InteractionResponder integration with context builder
# ---------------------------------------------------------------------------


class ResponderContextBuilderIntegrationTests(unittest.TestCase):
    def _make_responder_with_builder(self, llm_return: str = "LLM reply") -> tuple:
        sm = ShortMemory()
        sm.summary = "short memory test"

        task_manager = MagicMock()
        task_manager.get_pending_tasks.return_value = []

        builder = InteractionContextBuilder(
            short_memory=sm,
            task_manager=task_manager,
        )

        mock_llm = MagicMock()
        mock_llm.chat.return_value = llm_return

        responder = InteractionResponder(
            llm_client=mock_llm,
            model_name="test-model",
            context_builder=builder,
        )
        return responder, mock_llm, builder

    def test_ask_uses_interaction_context_builder(self) -> None:
        responder, mock_llm, builder = self._make_responder_with_builder()
        with patch.object(builder, "build_for_message", wraps=builder.build_for_message) as spy:
            responder.respond("ask", "me explique sua arquitetura", {"tick_type": "interactive"})
            spy.assert_called_once_with("me explique sua arquitetura", {"tick_type": "interactive"})

    def test_complex_bare_question_uses_context_builder(self) -> None:
        responder, mock_llm, builder = self._make_responder_with_builder()
        with patch.object(builder, "build_for_message", wraps=builder.build_for_message) as spy:
            responder.respond("message", "me explique sua arquitetura", {"tick_type": "interactive"})
            spy.assert_called_once_with("me explique sua arquitetura", {"tick_type": "interactive"})

    def test_greeting_does_not_invoke_context_builder(self) -> None:
        responder, mock_llm, builder = self._make_responder_with_builder()
        with patch.object(builder, "build_for_message") as spy:
            responder.respond("message", "olá")
            spy.assert_not_called()

    def test_status_does_not_invoke_context_builder(self) -> None:
        responder, mock_llm, builder = self._make_responder_with_builder()
        with patch.object(builder, "build_for_message") as spy:
            responder.respond("status", "")
            spy.assert_not_called()

    def test_task_directive_does_not_invoke_context_builder(self) -> None:
        # @task is handled by AliveAgent before reaching the responder.
        # This test verifies the responder's fallback path does not call builder.
        responder, mock_llm, builder = self._make_responder_with_builder()
        with patch.object(builder, "build_for_message") as spy:
            # "task" directive reaches _respond_fallback (not a task command path)
            responder.respond("task", "create something")
            spy.assert_not_called()

    def test_note_directive_does_not_invoke_context_builder(self) -> None:
        responder, mock_llm, builder = self._make_responder_with_builder()
        with patch.object(builder, "build_for_message") as spy:
            responder.respond("note", "some note content")
            spy.assert_not_called()


# ---------------------------------------------------------------------------
# Prompt content tests
# ---------------------------------------------------------------------------


class PromptContentTests(unittest.TestCase):
    def _make_context(self, **kwargs) -> InteractionContext:
        defaults = dict(
            user_message="test message",
            tick_type="interactive",
            model_name="test-model",
            short_memory_summary="summary here",
            recent_observations=["obs1"],
            recent_actions=["act1"],
            pending_tasks=["task1"],
            routed_memory={"topic_a": "topic content"},
            action_policy=ACTION_POLICY,
            budget_summary={"tokens_this_tick": 50, "max_tokens_per_tick": 1000},
            warnings=[],
        )
        defaults.update(kwargs)
        return InteractionContext(**defaults)

    def test_prompt_includes_action_tool_policy(self) -> None:
        ctx = self._make_context()
        prompt = _build_prompt_from_context(ctx)
        self.assertIn("do not claim that a tool was executed", prompt)

    def test_prompt_includes_short_memory_summary(self) -> None:
        ctx = self._make_context(short_memory_summary="Agent is ready for PR #8.")
        prompt = _build_prompt_from_context(ctx)
        self.assertIn("Agent is ready for PR #8.", prompt)

    def test_prompt_does_not_include_full_long_term_memory(self) -> None:
        # Routed memory is bounded; only the keys that were loaded appear in the prompt
        ctx = self._make_context(routed_memory={"topic_a": "small snippet"})
        prompt = _build_prompt_from_context(ctx)
        self.assertIn("topic_a", prompt)
        self.assertIn("small snippet", prompt)
        # Full long-term memory dump would be much larger; here it is bounded
        self.assertLessEqual(len(prompt), 10000)

    def test_prompt_includes_pending_tasks(self) -> None:
        ctx = self._make_context(pending_tasks=["task alpha", "task beta"])
        prompt = _build_prompt_from_context(ctx)
        self.assertIn("task alpha", prompt)
        self.assertIn("task beta", prompt)

    def test_prompt_includes_tick_type_and_model(self) -> None:
        ctx = self._make_context(tick_type="maintenance", model_name="gpt-4-test")
        prompt = _build_prompt_from_context(ctx)
        self.assertIn("maintenance", prompt)
        self.assertIn("gpt-4-test", prompt)


# ---------------------------------------------------------------------------
# ShortMemory update heuristic
# ---------------------------------------------------------------------------


class ShouldRecordInteractionTests(unittest.TestCase):
    def test_greeting_not_saved(self) -> None:
        self.assertFalse(should_record_interaction("olá", "Olá!"))
        self.assertFalse(should_record_interaction("ok", ""))
        self.assertFalse(should_record_interaction("teste", "ok"))
        self.assertFalse(should_record_interaction("obrigado", "de nada"))

    def test_preference_messages_are_saved(self) -> None:
        self.assertTrue(should_record_interaction("prefiro respostas em português e diretas", "ok"))
        self.assertTrue(should_record_interaction("vamos focar no PR #8 como workspace vivo", "ok"))
        self.assertTrue(should_record_interaction("não use WebSocket ainda", "ok"))
        self.assertTrue(should_record_interaction("o chat deve usar a mesma memória RAM do agente", "ok"))

    def test_long_messages_are_saved(self) -> None:
        long_msg = "esta é uma mensagem muito longa que deve ser salva porque tem mais de quarenta caracteres"
        self.assertTrue(should_record_interaction(long_msg, "ok"))

    def test_very_short_messages_not_saved(self) -> None:
        self.assertFalse(should_record_interaction("hi", ""))
        self.assertFalse(should_record_interaction("sim", ""))

    def test_builder_calls_maybe_update_short_memory_on_success(self) -> None:
        sm = ShortMemory()
        task_manager = MagicMock()
        task_manager.get_pending_tasks.return_value = []
        builder = InteractionContextBuilder(
            short_memory=sm,
            task_manager=task_manager,
            config={"update_short_memory": True},
        )
        # A preference-style message should be saved
        preference_msg = "prefiro respostas sempre em português"
        builder.maybe_update_short_memory(preference_msg, "Entendido.")
        obs_texts = list(sm.observations)
        self.assertTrue(any("prefiro" in o.lower() for o in obs_texts))

    def test_builder_does_not_update_short_memory_for_trivial_greeting(self) -> None:
        sm = ShortMemory()
        task_manager = MagicMock()
        task_manager.get_pending_tasks.return_value = []
        builder = InteractionContextBuilder(
            short_memory=sm,
            task_manager=task_manager,
            config={"update_short_memory": True},
        )
        builder.maybe_update_short_memory("olá", "Olá!")
        self.assertEqual(0, len(list(sm.observations)))


# ---------------------------------------------------------------------------
# AliveAgent integration: context builder is wired correctly
# ---------------------------------------------------------------------------


class AliveAgentContextBuilderWiringTests(unittest.TestCase):
    def test_agent_has_interaction_context_builder(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            agent = _make_agent(Path(tmp))
            self.assertIsNotNone(agent.interaction_context_builder)

    def test_responder_has_context_builder_from_agent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            agent = _make_agent(Path(tmp))
            self.assertIsNotNone(agent.interaction_responder.context_builder)

    def test_context_builder_uses_same_short_memory_as_agent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            agent = _make_agent(Path(tmp))
            self.assertIs(
                agent.interaction_context_builder.short_memory,
                agent.short_memory,
            )

    def test_ask_via_full_tick_uses_managed_context(self) -> None:
        """@ask during an interactive tick calls build_for_message."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            agent = _make_agent(root)
            assert agent.interaction is not None
            agent.interaction.append_user_message("@ask how do you work?")

            builder = agent.interaction_context_builder
            with patch.object(builder, "build_for_message", wraps=builder.build_for_message) as spy:
                with patch.object(agent.llm_client, "chat", return_value="I use ticks."):
                    agent.tick(reason=TickType.INTERACTIVE)
            spy.assert_called_once()

    def test_greeting_tick_does_not_use_context_builder(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            agent = _make_agent(root)
            assert agent.interaction is not None
            agent.interaction.append_user_message("olá")

            builder = agent.interaction_context_builder
            with patch.object(builder, "build_for_message") as spy:
                agent.tick(reason=TickType.INTERACTIVE)
            spy.assert_not_called()

    def test_status_tick_does_not_use_context_builder(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            agent = _make_agent(root)
            assert agent.interaction is not None
            agent.interaction.append_user_message("@status")

            builder = agent.interaction_context_builder
            with patch.object(builder, "build_for_message") as spy:
                agent.tick(reason=TickType.INTERACTIVE)
            spy.assert_not_called()

    def test_task_tick_does_not_use_context_builder(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            agent = _make_agent(root)
            assert agent.interaction is not None
            agent.interaction.append_user_message("@task Write tests for PR #8")

            builder = agent.interaction_context_builder
            with patch.object(builder, "build_for_message") as spy:
                agent.tick(reason=TickType.INTERACTIVE)
            spy.assert_not_called()

    def test_note_tick_does_not_use_context_builder(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            agent = _make_agent(root)
            assert agent.interaction is not None
            agent.interaction.append_user_message("@note prefer short responses")

            builder = agent.interaction_context_builder
            with patch.object(builder, "build_for_message") as spy:
                agent.tick(reason=TickType.INTERACTIVE)
            spy.assert_not_called()

    def test_short_memory_updated_for_important_user_preference(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            agent = _make_agent(root)
            assert agent.interaction is not None
            preference = "prefiro respostas sempre em português e diretas"
            agent.interaction.append_user_message(f"@ask {preference}")

            with patch.object(agent.llm_client, "chat", return_value="Entendido."):
                agent.tick(reason=TickType.INTERACTIVE)

            obs_list = list(agent.short_memory.observations)
            # At least one observation should mention the preference
            self.assertTrue(any("prefiro" in obs.lower() for obs in obs_list))

    def test_short_memory_not_updated_for_trivial_greeting(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            agent = _make_agent(root)
            assert agent.interaction is not None
            agent.interaction.append_user_message("olá")

            obs_before = list(agent.short_memory.observations)
            agent.tick(reason=TickType.INTERACTIVE)
            obs_after = list(agent.short_memory.observations)

            # The tick itself adds observations for the interaction, but none from
            # the heuristic update path (which only runs for @ask / complex paths).
            # We verify no "User preference" entry was added.
            pref_obs = [o for o in obs_after if "User preference" in o]
            self.assertEqual(0, len(pref_obs))


if __name__ == "__main__":
    unittest.main()

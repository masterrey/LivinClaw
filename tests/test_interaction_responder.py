from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from agent.alive_agent import AliveAgent, TickType
from agent.interaction_responder import InteractionResponder
from interaction.interaction_manager import InteractionManager


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_responder(llm_client=None) -> InteractionResponder:
    return InteractionResponder(
        llm_client=llm_client,
        model_name="test-model",
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
    }


def _make_agent(tmp_root: Path) -> AliveAgent:
    tasks_file = tmp_root / "workspace/tasks.md"
    tasks_file.parent.mkdir(parents=True, exist_ok=True)
    tasks_file.write_text("", encoding="utf-8")
    return AliveAgent(config=_base_config(), root_dir=tmp_root)


# ---------------------------------------------------------------------------
# Classification unit tests
# ---------------------------------------------------------------------------


class ClassificationTests(unittest.TestCase):
    """Verify that the responder correctly classifies message content."""

    def test_greeting_classification_english(self) -> None:
        r = _make_responder()
        result = r._classify_message("hello")
        self.assertEqual("greeting", result)

    def test_greeting_classification_portuguese(self) -> None:
        r = _make_responder()
        for word in ("olá", "oi", "bom dia", "boa tarde", "boa noite", "tudo bem"):
            with self.subTest(word=word):
                self.assertEqual("greeting", r._classify_message(word))

    def test_status_classification(self) -> None:
        r = _make_responder()
        for phrase in ("status", "@status", "qual seu status?", "você está funcionando?"):
            with self.subTest(phrase=phrase):
                self.assertEqual("status", r._classify_message(phrase))

    def test_freeform_classification(self) -> None:
        r = _make_responder()
        result = r._classify_message("quero organizar uma tarefa")
        self.assertEqual("freeform", result)

    def test_previous_topics_question_classification(self) -> None:
        r = _make_responder()
        result = r._classify_message("quais foram os assuntos anteriores que conversamos?")
        self.assertEqual("complex", result)

    def test_portuguese_detection_true(self) -> None:
        r = _make_responder()
        self.assertTrue(r._is_portuguese("olá como vai você"))

    def test_portuguese_detection_false(self) -> None:
        r = _make_responder()
        self.assertFalse(r._is_portuguese("everything is fine here"))


# ---------------------------------------------------------------------------
# Response content tests (no LLM needed)
# ---------------------------------------------------------------------------


class GreetingResponseTests(unittest.TestCase):
    def test_portuguese_greeting_response(self) -> None:
        r = _make_responder()
        response = r.respond("message", "olá")
        self.assertIn("Olá", response)
        self.assertIn("@task", response)
        self.assertIn("@note", response)
        self.assertIn("@status", response)

    def test_english_greeting_response(self) -> None:
        r = _make_responder()
        response = r.respond("message", "hello")
        self.assertIn("Hello", response)
        self.assertIn("@task", response)

    def test_greeting_does_not_call_llm(self) -> None:
        mock_llm = MagicMock()
        r = _make_responder(llm_client=mock_llm)
        r.respond("message", "olá")
        mock_llm.chat.assert_not_called()


class StatusResponseTests(unittest.TestCase):
    def _ctx(self) -> dict:
        return {
            "tick_type": "interactive",
            "pending_tasks": ["task one", "task two"],
            "inbox_pending": 3,
            "model_name": "openai/gpt-oss-20b",
            "memory_summary": "",
        }

    def test_status_directive_returns_deterministic_status(self) -> None:
        r = _make_responder()
        response = r.respond("status", "", self._ctx())
        self.assertIn("Status do LivinClaw", response)
        self.assertIn("tick atual: interactive", response)
        self.assertIn("tarefas pendentes: 2", response)
        self.assertIn("mensagens pendentes: 3", response)
        self.assertIn("openai/gpt-oss-20b", response)

    def test_status_via_text_message(self) -> None:
        r = _make_responder()
        response = r.respond("message", "pode me informar o status?", self._ctx())
        self.assertIn("Status do LivinClaw", response)

    def test_status_does_not_call_llm(self) -> None:
        mock_llm = MagicMock()
        r = _make_responder(llm_client=mock_llm)
        r.respond("status", "", self._ctx())
        mock_llm.chat.assert_not_called()

    def test_status_text_trigger_does_not_call_llm(self) -> None:
        mock_llm = MagicMock()
        r = _make_responder(llm_client=mock_llm)
        r.respond("message", "status", {})
        mock_llm.chat.assert_not_called()

    def test_status_no_model_uses_fallback_label(self) -> None:
        r = InteractionResponder(model_name="")
        response = r.respond("status", "", {"model_name": ""})
        self.assertIn("Not available yet", response)


# ---------------------------------------------------------------------------
# Conversational / @ask tests
# ---------------------------------------------------------------------------


class ConversationalResponseTests(unittest.TestCase):
    def test_ask_routes_to_llm(self) -> None:
        mock_llm = MagicMock()
        mock_llm.chat.return_value = "Sou o LivinClaw, um runtime local."
        r = _make_responder(llm_client=mock_llm)
        response = r.respond("ask", "me explique sua arquitetura")
        mock_llm.chat.assert_called_once()
        self.assertEqual("Sou o LivinClaw, um runtime local.", response)

    def test_ask_llm_failure_returns_fallback(self) -> None:
        mock_llm = MagicMock()
        mock_llm.chat.side_effect = ConnectionError("LM Studio not running")
        r = _make_responder(llm_client=mock_llm)
        response = r.respond("ask", "me explique sua arquitetura")
        self.assertIn("não consegui", response)

    def test_ask_no_llm_client_returns_fallback(self) -> None:
        r = _make_responder(llm_client=None)
        response = r.respond("ask", "me explique sua arquitetura")
        self.assertIn("não consegui", response)

    def test_ask_llm_returns_empty_string_uses_fallback(self) -> None:
        mock_llm = MagicMock()
        mock_llm.chat.return_value = ""
        r = _make_responder(llm_client=mock_llm)
        response = r.respond("ask", "o que você pode fazer?")
        self.assertIn("não consegui", response)

    def test_ask_english_fallback(self) -> None:
        mock_llm = MagicMock()
        mock_llm.chat.side_effect = ConnectionError("offline")
        r = _make_responder(llm_client=mock_llm)
        response = r.respond("ask", "explain your architecture")
        self.assertIn("could not reach", response)

    def test_history_question_without_ask_routes_to_llm(self) -> None:
        mock_llm = MagicMock()
        mock_llm.chat.return_value = "Falamos sobre memória e tarefas."
        r = _make_responder(llm_client=mock_llm)
        response = r.respond("message", "do que falamos antes?")
        mock_llm.chat.assert_called_once()
        self.assertEqual("Falamos sobre memória e tarefas.", response)


# ---------------------------------------------------------------------------
# Freeform / fallback tests
# ---------------------------------------------------------------------------


class FreeformAndFallbackTests(unittest.TestCase):
    def test_freeform_portuguese_guides_user(self) -> None:
        r = _make_responder()
        response = r.respond("message", "quero organizar uma tarefa")
        self.assertIn("@task", response)
        self.assertIn("@note", response)

    def test_unknown_directive_returns_fallback(self) -> None:
        r = _make_responder()
        response = r.respond("unknown_directive", "algo qualquer")
        self.assertIn("@task", response)
        self.assertIn("@ask", response)

    def test_fallback_message_portuguese(self) -> None:
        r = _make_responder()
        response = r._respond_fallback("algo que não sei tratar")
        self.assertIn("@task", response)
        self.assertIn("não tenho certeza", response)

    def test_fallback_message_english(self) -> None:
        r = _make_responder()
        response = r._respond_fallback("something I cannot handle")
        self.assertIn("not sure", response)


# ---------------------------------------------------------------------------
# Integration: every processed interactive message produces outbox response
# ---------------------------------------------------------------------------


class OutboxResponseIntegrationTests(unittest.TestCase):
    def _run_tick(self, tmp: str, messages: list[str], llm_return: str = "") -> str:
        root = Path(tmp)
        agent = _make_agent(root)
        assert agent.interaction is not None

        for msg in messages:
            agent.interaction.append_user_message(msg)

        with patch.object(
            agent.interaction_responder.llm_client,
            "chat",
            return_value=llm_return,
        ):
            agent.tick(reason=TickType.INTERACTIVE)

        return (root / "workspace/outbox.md").read_text(encoding="utf-8")

    def test_greeting_produces_outbox_response(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            outbox = self._run_tick(tmp, ["olá"])
            self.assertIn("## MSG_", outbox)
            self.assertIn("Olá", outbox)

    def test_status_produces_outbox_response(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            outbox = self._run_tick(tmp, ["@status"])
            self.assertIn("Status do LivinClaw", outbox)

    def test_task_produces_outbox_response(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            outbox = self._run_tick(tmp, ["@task Criar resumo do Guardian"])
            self.assertIn("Tarefa registrada", outbox)

    def test_note_produces_outbox_response(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            outbox = self._run_tick(tmp, ["@note Prefiro respostas curtas"])
            self.assertIn("Nota registrada", outbox)

    def test_ask_produces_outbox_response(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            outbox = self._run_tick(
                tmp,
                ["@ask me explique sua arquitetura"],
                llm_return="Minha arquitetura usa ticks.",
            )
            self.assertIn("Minha arquitetura usa ticks.", outbox)

    def test_ask_llm_failure_still_produces_outbox_response(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            agent = _make_agent(root)
            assert agent.interaction is not None
            agent.interaction.append_user_message("@ask me explique sua arquitetura")

            with patch.object(
                agent.interaction_responder.llm_client,
                "chat",
                side_effect=ConnectionError("offline"),
            ):
                agent.tick(reason=TickType.INTERACTIVE)

            outbox = (root / "workspace/outbox.md").read_text(encoding="utf-8")
            self.assertIn("## MSG_", outbox)
            self.assertIn("não consegui", outbox)

    def test_multiple_messages_each_produce_response(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            outbox = self._run_tick(
                tmp,
                ["olá", "@status", "@task Tarefa de teste"],
            )
            # Three responses expected.
            self.assertEqual(3, outbox.count("## MSG_"))

    def test_freeform_message_produces_outbox_response(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            outbox = self._run_tick(tmp, ["quero organizar uma tarefa"])
            self.assertIn("## MSG_", outbox)
            self.assertIn("@task", outbox)

    def test_portuguese_status_request_text_produces_status_response(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            outbox = self._run_tick(tmp, ["pode me informar o status?"])
            self.assertIn("Status do LivinClaw", outbox)


# ---------------------------------------------------------------------------
# interact_manager classify_directive unit tests
# ---------------------------------------------------------------------------


class ClassifyDirectiveTests(unittest.TestCase):
    def _mgr(self) -> InteractionManager:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            mgr = InteractionManager(root / "inbox.md", root / "outbox.md")
        return mgr

    def test_status_prefix_recognized(self) -> None:
        mgr = InteractionManager(Path("/tmp/i.md"), Path("/tmp/o.md"))
        directive, payload = mgr.classify_directive("@status")
        self.assertEqual("status", directive)
        self.assertEqual("", payload)

    def test_bare_text_returns_message_directive(self) -> None:
        mgr = InteractionManager(Path("/tmp/i.md"), Path("/tmp/o.md"))
        directive, payload = mgr.classify_directive("olá")
        self.assertEqual("message", directive)
        self.assertEqual("olá", payload)

    def test_ask_prefix_still_recognized(self) -> None:
        mgr = InteractionManager(Path("/tmp/i.md"), Path("/tmp/o.md"))
        directive, payload = mgr.classify_directive("@ask explain yourself")
        self.assertEqual("ask", directive)
        self.assertEqual("explain yourself", payload)


if __name__ == "__main__":
    unittest.main()

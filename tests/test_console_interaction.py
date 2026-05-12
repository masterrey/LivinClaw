from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from interaction.interaction_manager import InteractionManager
from interaction.message import InteractionMessage
from scripts.console_chat import process_console_turn, should_exit
from scripts.show_latest_outbox import get_latest_outbox_response, render_latest_outbox


def _write_config(root: Path) -> None:
    (root / "config.yaml").write_text(
        "interaction:\n  inbox_path: workspace/inbox.md\n  outbox_path: workspace/outbox.md\n",
        encoding="utf-8",
    )


class ShowLatestOutboxTests(unittest.TestCase):
    def test_render_latest_outbox_returns_latest_response_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_config(root)
            manager = InteractionManager(root / "workspace/inbox.md", root / "workspace/outbox.md")
            manager.append_response("primeira resposta", response_id="MSG_0001")
            manager.append_response("resposta final", response_id="MSG_0002")

            rendered = render_latest_outbox(root)

            self.assertIn("LivinClaw response:", rendered)
            self.assertIn("resposta final", rendered)
            self.assertNotIn("primeira resposta", rendered)

    def test_render_latest_outbox_handles_empty_outbox(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_config(root)
            outbox = root / "workspace/outbox.md"
            outbox.parent.mkdir(parents=True, exist_ok=True)
            outbox.write_text("# Outbox\n\n", encoding="utf-8")

            self.assertEqual("[LivinClaw] No response available yet.", render_latest_outbox(root))

    def test_render_latest_outbox_does_not_mutate_outbox(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_config(root)
            manager = InteractionManager(root / "workspace/inbox.md", root / "workspace/outbox.md")
            manager.append_response("imutável", response_id="MSG_0001")
            outbox = root / "workspace/outbox.md"
            before = outbox.read_text(encoding="utf-8")

            render_latest_outbox(root)

            self.assertEqual(before, outbox.read_text(encoding="utf-8"))

    def test_render_latest_outbox_handles_malformed_outbox(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_config(root)
            outbox = root / "workspace/outbox.md"
            outbox.parent.mkdir(parents=True, exist_ok=True)
            outbox.write_text("# Outbox\n\n## MSG_0001\nMetadata:\n```json\n{bad json\n```\n", encoding="utf-8")

            latest, error = get_latest_outbox_response(root)

            self.assertIsNone(latest)
            self.assertEqual("Outbox is malformed.", error)


class ConsoleChatHelperTests(unittest.TestCase):
    def test_process_console_turn_returns_latest_response(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fake_response = InteractionMessage(
                id="MSG_0001",
                sender="agent",
                source="local",
                content="Estado atual do runtime",
                status="sent",
            )

            with (
                patch("scripts.console_chat.append_message") as append_message_mock,
                patch("scripts.console_chat.run_interactive_tick", return_value=(True, None)),
                patch("scripts.console_chat.get_latest_outbox_response", return_value=(fake_response, None)),
            ):
                response = process_console_turn("@ask Tudo certo?", root)

            append_message_mock.assert_called_once_with(content="@ask Tudo certo?", root=root, source="console")
            self.assertEqual("Estado atual do runtime", response)

    def test_process_console_turn_handles_tick_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with (
                patch("scripts.console_chat.append_message"),
                patch("scripts.console_chat.run_interactive_tick", return_value=(False, "LM Studio timeout")),
            ):
                response = process_console_turn("@ask Tudo certo?", root)

            self.assertEqual("[LivinClaw] Interactive tick failed: LM Studio timeout", response)

    def test_should_exit_recognizes_supported_commands(self) -> None:
        self.assertTrue(should_exit("exit"))
        self.assertTrue(should_exit("quit"))
        self.assertTrue(should_exit("/exit"))
        self.assertFalse(should_exit("@ask status"))


if __name__ == "__main__":
    unittest.main()

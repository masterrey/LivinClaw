from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from interaction.interaction_manager import InteractionManager
from ui import actions


class UIActionsTests(unittest.TestCase):
    def test_actions_append_messages_through_interaction_manager(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with patch("ui.actions.InteractionManager") as manager_cls:
                manager = manager_cls.return_value
                manager.append_user_message.return_value.id = "MSG_0001"

                ok, msg = actions.append_user_message("@ask status", root=root)

                self.assertTrue(ok)
                self.assertEqual("MSG_0001", msg)
                manager.append_user_message.assert_called_once()

    def test_actions_do_not_call_llm_directly_and_use_runtime_cli(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with patch("ui.actions.subprocess.run") as run_mock:
                run_mock.return_value.returncode = 0
                run_mock.return_value.stdout = ""
                run_mock.return_value.stderr = ""

                ok, _ = actions.run_interactive_tick(root)

                self.assertTrue(ok)
                command = run_mock.call_args.args[0]
                self.assertIn("alive_agent/main.py", command)
                self.assertIn("--interactive", command)

    def test_latest_response_reader_works(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "config.yaml").write_text(
                "interaction:\n  inbox_path: workspace/inbox.md\n  outbox_path: workspace/outbox.md\n",
                encoding="utf-8",
            )
            manager = InteractionManager(root / "workspace/inbox.md", root / "workspace/outbox.md")
            manager.append_response("hello", response_id="MSG_0001")

            content, error = actions.read_latest_outbox_response(root)

            self.assertIsNone(error)
            self.assertEqual("hello", content)


if __name__ == "__main__":
    unittest.main()

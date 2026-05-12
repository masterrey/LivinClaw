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

    def test_queue_only_action_still_appends_to_inbox(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = InteractionManager(root / "workspace/inbox.md", root / "workspace/outbox.md")

            ok, message_id = actions.append_user_message("queued", root=root)

            self.assertTrue(ok)
            self.assertTrue(message_id.startswith("MSG_"))
            pending_ids = [msg.id for msg in manager.read_pending_messages()]
            self.assertIn(message_id, pending_ids)

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

    def test_latest_message_reader_returns_message_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "config.yaml").write_text(
                "interaction:\n  inbox_path: workspace/inbox.md\n  outbox_path: workspace/outbox.md\n",
                encoding="utf-8",
            )
            manager = InteractionManager(root / "workspace/inbox.md", root / "workspace/outbox.md")
            manager.append_response("hello", response_id="MSG_0007")

            latest, error = actions.read_latest_outbox_message(root)

            self.assertIsNone(error)
            self.assertIsNotNone(latest)
            assert latest is not None
            self.assertEqual("MSG_0007", latest.id)
            self.assertEqual("hello", latest.content)

    def test_new_outbox_response_reader_detects_stale_latest_message(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "config.yaml").write_text(
                "interaction:\n  inbox_path: workspace/inbox.md\n  outbox_path: workspace/outbox.md\n",
                encoding="utf-8",
            )
            manager = InteractionManager(root / "workspace/inbox.md", root / "workspace/outbox.md")
            manager.append_response("first", response_id="MSG_0001")

            content, has_new, error = actions.read_new_outbox_response("MSG_0001", root)

            self.assertIsNone(error)
            self.assertFalse(has_new)
            self.assertIsNone(content)

            manager.append_response("second", response_id="MSG_0002")

            content, has_new, error = actions.read_new_outbox_response("MSG_0001", root)

            self.assertIsNone(error)
            self.assertTrue(has_new)
            self.assertEqual("second", content)

    def test_send_message_and_run_tick_returns_matching_response_by_message_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "config.yaml").write_text(
                "interaction:\n  inbox_path: workspace/inbox.md\n  outbox_path: workspace/outbox.md\n",
                encoding="utf-8",
            )
            manager = InteractionManager(root / "workspace/inbox.md", root / "workspace/outbox.md")
            seed = manager.append_user_message("seed", source="test")
            manager.mark_processed(seed.id)
            manager.append_response("old", response_id="MSG_0001")

            def run_with_matching_response(*args, **kwargs):
                pending = manager.read_pending_messages()
                if pending:
                    current = pending[-1]
                    manager.mark_processed(current.id)
                    manager.append_response("fresh", response_id=current.id)
                class Result:
                    returncode = 0
                    stdout = ""
                    stderr = ""
                return Result()

            with patch("ui.actions.subprocess.run", side_effect=run_with_matching_response):
                ok, data = actions.send_message_and_run_tick("hello", root)

            self.assertTrue(ok)
            self.assertTrue(data["tick_ok"])
            self.assertTrue(data["response_found"])
            self.assertEqual("fresh", data["response"])
            self.assertEqual("MSG_0002", data["message_id"])

    def test_send_message_and_run_tick_does_not_return_stale_latest_response(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "config.yaml").write_text(
                "interaction:\n  inbox_path: workspace/inbox.md\n  outbox_path: workspace/outbox.md\n",
                encoding="utf-8",
            )
            manager = InteractionManager(root / "workspace/inbox.md", root / "workspace/outbox.md")
            seed = manager.append_user_message("seed", source="test")
            manager.mark_processed(seed.id)
            manager.append_response("old", response_id="MSG_0001")

            with patch("ui.actions.subprocess.run") as run_mock:
                run_mock.return_value.returncode = 0
                run_mock.return_value.stdout = ""
                run_mock.return_value.stderr = ""

                ok, data = actions.send_message_and_run_tick("hello", root)

            self.assertTrue(ok)
            self.assertTrue(data["tick_ok"])
            self.assertFalse(data["response_found"])
            self.assertIsNone(data["response"])
            self.assertEqual("MSG_0002", data["message_id"])


if __name__ == "__main__":
    unittest.main()

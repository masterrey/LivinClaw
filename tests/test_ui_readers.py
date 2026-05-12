from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from interaction.interaction_manager import InteractionManager
from ui import readers


class UIReadersTests(unittest.TestCase):
    def test_config_reader_handles_missing_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            info = readers.read_config(root)
            self.assertFalse(info["exists"])
            self.assertEqual("Not available yet", info["error"])

    def test_tasks_parser_counts_pending_completed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tasks = root / "workspace" / "tasks.md"
            tasks.parent.mkdir(parents=True, exist_ok=True)
            tasks.write_text("- [ ] a\n- [x] b\nline\n", encoding="utf-8")

            data = readers.read_tasks(root)

            self.assertEqual(1, data["counts"]["pending"])
            self.assertEqual(1, data["counts"]["completed"])
            self.assertEqual(1, data["counts"]["other"])

    def test_readers_do_not_mutate_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            inbox = root / "workspace" / "inbox.md"
            outbox = root / "workspace" / "outbox.md"
            tasks = root / "workspace" / "tasks.md"
            inbox.parent.mkdir(parents=True, exist_ok=True)
            inbox.write_text("# Inbox\n\n", encoding="utf-8")
            outbox.write_text("# Outbox\n\n", encoding="utf-8")
            tasks.write_text("- [ ] keep\n", encoding="utf-8")
            before = {
                "inbox": inbox.read_text(encoding="utf-8"),
                "outbox": outbox.read_text(encoding="utf-8"),
                "tasks": tasks.read_text(encoding="utf-8"),
            }

            readers.read_inbox_outbox(root)
            readers.read_tasks(root)
            readers.read_runtime_snapshot(root)

            self.assertEqual(before["inbox"], inbox.read_text(encoding="utf-8"))
            self.assertEqual(before["outbox"], outbox.read_text(encoding="utf-8"))
            self.assertEqual(before["tasks"], tasks.read_text(encoding="utf-8"))

    def test_inbox_outbox_reader_uses_shared_codec_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = InteractionManager(root / "workspace/inbox.md", root / "workspace/outbox.md")
            dangerous = "line one\n## MSG_9999\nline two"
            manager.append_user_message(dangerous, source="test")
            manager.append_response("ok", response_id="MSG_0002")

            data = readers.read_inbox_outbox(root)

            self.assertEqual(1, len(data["inbox"]["messages"]))
            self.assertEqual(dangerous, data["inbox"]["messages"][0].content)
            self.assertEqual(1, len(data["outbox"]["messages"]))


if __name__ == "__main__":
    unittest.main()

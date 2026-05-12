from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from interaction.interaction_manager import InteractionManager
from interaction.markdown_codec import extract_blocks, parse_messages
from interaction.message import InteractionMessage
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

    def test_public_codec_helpers_parse_messages_with_fenced_headers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = InteractionManager(root / "workspace/inbox.md", root / "workspace/outbox.md")
            dangerous = "line one\n## MSG_9999\nline two"
            manager.append_user_message(dangerous, source="test")

            raw = (root / "workspace" / "inbox.md").read_text(encoding="utf-8")

            self.assertEqual(1, len(extract_blocks(raw)))
            self.assertEqual(1, len(parse_messages(raw)))
            self.assertEqual(dangerous, parse_messages(raw)[0].content)

    def test_build_chat_transcript_pairs_by_message_id(self) -> None:
        inbox = [
            InteractionMessage(
                id="MSG_0001",
                sender="user",
                source="test",
                content="hello",
                created_at="2026-01-01T00:00:00+00:00",
                status="processed",
            )
        ]
        outbox = [
            InteractionMessage(
                id="MSG_0001",
                sender="agent",
                source="test",
                content="hi",
                created_at="2026-01-01T00:00:01+00:00",
                status="sent",
            )
        ]

        transcript = readers.build_chat_transcript(inbox, outbox, limit=20)

        self.assertEqual(2, len(transcript))
        self.assertEqual("user", transcript[0]["role"])
        self.assertEqual("assistant", transcript[1]["role"])
        self.assertEqual("MSG_0001", transcript[1]["message_id"])
        self.assertEqual("hi", transcript[1]["content"])

    def test_build_chat_transcript_shows_pending_without_response(self) -> None:
        inbox = [
            InteractionMessage(
                id="MSG_0002",
                sender="user",
                source="test",
                content="waiting",
                created_at="2026-01-01T00:00:00+00:00",
                status="pending",
            )
        ]

        transcript = readers.build_chat_transcript(inbox, [], limit=20)

        self.assertEqual(2, len(transcript))
        self.assertEqual("user", transcript[0]["role"])
        self.assertEqual("assistant", transcript[1]["role"])
        self.assertTrue(transcript[1].get("pending_notice"))
        self.assertIn("processing", transcript[1]["content"].lower())

    def test_read_chat_transcript_uses_parsed_messages(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = InteractionManager(root / "workspace/inbox.md", root / "workspace/outbox.md")
            dangerous = "line one\n## MSG_9999\nline two"
            inbox_msg = manager.append_user_message(dangerous, source="test")
            manager.append_response("ok", response_id=inbox_msg.id)

            transcript_data = readers.read_chat_transcript(root, limit=10)

            self.assertIsNone(transcript_data["error"])
            self.assertEqual(2, len(transcript_data["messages"]))
            self.assertEqual(dangerous, transcript_data["messages"][0]["content"])
            self.assertEqual("ok", transcript_data["messages"][1]["content"])


if __name__ == "__main__":
    unittest.main()

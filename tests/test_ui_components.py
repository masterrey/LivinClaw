from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from ui import components


class _DummyContext:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def metric(self, *args, **kwargs):
        return None


class DummyStreamlit:
    def columns(self, count):
        return [_DummyContext() for _ in range(count)]

    def metric(self, *args, **kwargs):
        return None

    def subheader(self, *args, **kwargs):
        return None

    def info(self, *args, **kwargs):
        return None

    def expander(self, *args, **kwargs):
        return _DummyContext()

    def caption(self, *args, **kwargs):
        return None

    def write(self, *args, **kwargs):
        return None

    def markdown(self, *args, **kwargs):
        return None

    def text_area(self, *args, **kwargs):
        return None

    def container(self, *args, **kwargs):
        return _DummyContext()

    def chat_message(self, *args, **kwargs):
        return _DummyContext()


class UIComponentsTests(unittest.TestCase):
    def test_chat_helpers_render_without_mutating_workspace_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            inbox = root / "workspace" / "inbox.md"
            outbox = root / "workspace" / "outbox.md"
            inbox.parent.mkdir(parents=True, exist_ok=True)
            inbox.write_text("# Inbox\n\n", encoding="utf-8")
            outbox.write_text("# Outbox\n\n", encoding="utf-8")
            before_inbox = inbox.read_text(encoding="utf-8")
            before_outbox = outbox.read_text(encoding="utf-8")

            st = DummyStreamlit()
            components.render_chat_status_strip(
                st,
                {
                    "model_provider": "openai",
                    "model_name": "gpt-oss-20b",
                    "counts": {"tasks_pending": 0, "inbox_pending": 0},
                    "errors": {"config": None, "inbox": None, "outbox": None},
                },
            )
            components.render_chat_transcript(
                st,
                [
                    {"role": "user", "content": "olá", "message_id": "MSG_0001", "created_at": "now", "status": "processed"},
                    {"role": "assistant", "content": "oi", "message_id": "MSG_0001", "created_at": "now", "status": "sent"},
                ],
            )
            components.render_managed_context_panel(st, {})

            self.assertEqual(before_inbox, inbox.read_text(encoding="utf-8"))
            self.assertEqual(before_outbox, outbox.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()

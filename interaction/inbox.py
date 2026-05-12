from __future__ import annotations

import re
from pathlib import Path

from interaction.markdown_codec import _serialize_message, parse_messages
from interaction.message import InteractionMessage

_MESSAGE_ID_RE = re.compile(r"^MSG_(\d+)$")


class InboxStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.write_text("# Inbox\n\n", encoding="utf-8")

    def load_messages(self) -> list[InteractionMessage]:
        raw = self.path.read_text(encoding="utf-8")
        return parse_messages(raw)

    def next_message_id(self) -> str:
        numbers = []
        for message in self.load_messages():
            match = _MESSAGE_ID_RE.match(message.id)
            if match:
                numbers.append(int(match.group(1)))
        nxt = max(numbers, default=0) + 1
        return f"MSG_{nxt:04d}"

    def append(self, message: InteractionMessage) -> InteractionMessage:
        if not message.id:
            message.id = self.next_message_id()
        block = _serialize_message(message)
        with self.path.open("a", encoding="utf-8") as file:
            if self.path.stat().st_size > 0:
                file.write("\n")
            file.write(block)
            file.write("\n")
        return message

    def save_messages(self, messages: list[InteractionMessage]) -> None:
        payload = "# Inbox\n\n"
        serialized = [_serialize_message(msg) for msg in messages]
        if serialized:
            payload += "\n\n".join(serialized) + "\n"
        self.path.write_text(payload, encoding="utf-8")

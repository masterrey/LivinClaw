from __future__ import annotations

from pathlib import Path

from interaction.markdown_codec import _extract_blocks, _parse_block, _serialize_message
from interaction.message import InteractionMessage, InteractionResponse


class OutboxStore:
    def __init__(self, path: Path, create_if_missing: bool = True) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if create_if_missing and not self.path.exists():
            self.path.write_text("# Outbox\n\n", encoding="utf-8")

    def append(self, response: InteractionResponse) -> InteractionResponse:
        message = InteractionMessage(
            id=response.id,
            sender=response.sender,
            source=response.source,
            content=response.content,
            created_at=response.created_at,
            processed_at=response.processed_at,
            status=response.status,
            metadata=response.metadata,
        )
        block = _serialize_message(message)
        with self.path.open("a", encoding="utf-8") as file:
            if self.path.stat().st_size > 0:
                file.write("\n")
            file.write(block)
            file.write("\n")
        return response

    def load_messages(self) -> list[InteractionMessage]:
        if not self.path.exists():
            return []
        raw = self.path.read_text(encoding="utf-8")
        messages: list[InteractionMessage] = []
        for block in _extract_blocks(raw):
            parsed = _parse_block(block)
            if parsed is not None:
                messages.append(parsed)
        return messages

    def latest_message(self) -> InteractionMessage | None:
        messages = self.load_messages()
        if not messages:
            return None
        return messages[-1]

    def payload_integrity_ok(self) -> bool:
        if not self.path.exists():
            return True
        raw = self.path.read_text(encoding="utf-8")
        header_count = len(_extract_blocks(raw))
        parsed_count = len(self.load_messages())
        return header_count == parsed_count

from __future__ import annotations

from pathlib import Path

from interaction.inbox import _serialize_message
from interaction.message import InteractionMessage, InteractionResponse


class OutboxStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
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

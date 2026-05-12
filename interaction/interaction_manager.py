from __future__ import annotations

from datetime import datetime, UTC
from pathlib import Path

from interaction.inbox import InboxStore
from interaction.markdown_codec import _extract_blocks
from interaction.message import InteractionMessage, InteractionResponse
from interaction.outbox import OutboxStore


class InteractionManager:
    def __init__(self, inbox_path: Path, outbox_path: Path) -> None:
        self.inbox = InboxStore(inbox_path)
        self.outbox = OutboxStore(outbox_path)

    def classify_directive(self, content: str) -> tuple[str, str]:
        stripped = content.strip()
        if not stripped:
            return "invalid", ""
        first_line, _, remainder = stripped.partition("\n")
        if first_line.startswith("@task"):
            payload = first_line.replace("@task", "", 1).strip()
            payload = payload or remainder.strip()
            return "task", payload
        if first_line.startswith("@ask"):
            payload = first_line.replace("@ask", "", 1).strip()
            payload = payload or remainder.strip()
            return "ask", payload
        if first_line.startswith("@note"):
            payload = first_line.replace("@note", "", 1).strip()
            payload = payload or remainder.strip()
            return "note", payload
        return "ask", stripped

    def append_user_message(
        self,
        content: str,
        source: str = "local",
        metadata: dict | None = None,
    ) -> InteractionMessage:
        pending = self.read_pending_messages()
        for msg in pending:
            if msg.sender == "user" and msg.source == source and msg.content == content:
                return msg
        message = InteractionMessage(
            id=self.inbox.next_message_id(),
            sender="user",
            source=source,
            content=content,
            status="pending",
            metadata=metadata or {},
        )
        return self.inbox.append(message)

    def read_pending_messages(self, limit: int | None = None) -> list[InteractionMessage]:
        pending = [m for m in self.inbox.load_messages() if m.status == "pending"]
        if limit is None:
            return pending
        return pending[:limit]

    def mark_processed(self, message_id: str) -> bool:
        messages = self.inbox.load_messages()
        updated = False
        for msg in messages:
            if msg.id == message_id and msg.status == "pending":
                msg.status = "processed"
                msg.processed_at = datetime.now(UTC).isoformat()
                updated = True
                break
        if updated:
            self.inbox.save_messages(messages)
        return updated

    def append_response(
        self,
        content: str,
        metadata: dict | None = None,
        source: str = "local",
        response_id: str | None = None,
    ) -> InteractionResponse:
        response = InteractionResponse(
            id=response_id or self.inbox.next_message_id(),
            sender="agent",
            source=source,
            content=content,
            status="sent",
            metadata=metadata or {},
        )
        return self.outbox.append(response)

    def pending_count(self) -> int:
        return len(self.read_pending_messages())

    def payload_integrity_ok(self) -> bool:
        raw = self.inbox.path.read_text(encoding="utf-8")
        header_count = len(_extract_blocks(raw))
        parsed_count = len(self.inbox.load_messages())
        return header_count == parsed_count

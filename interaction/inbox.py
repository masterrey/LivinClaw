from __future__ import annotations

import json
import re
from datetime import datetime, UTC
from pathlib import Path

from interaction.message import InteractionMessage

_MESSAGE_HEADER_RE = re.compile(r"^## MSG_(\d+)$", re.MULTILINE)
_MESSAGE_ID_RE = re.compile(r"^MSG_(\d+)$")
_FENCE_OPEN_RE = re.compile(r"^(`{3,})(?:\S*)?$")


def _max_run(text: str, char: str) -> int:
    max_len = 0
    current = 0
    for c in text:
        if c == char:
            current += 1
            max_len = max(max_len, current)
        else:
            current = 0
    return max_len


def _fence_for(text: str) -> str:
    return "`" * max(3, _max_run(text, "`") + 1)


def _message_to_payload(message: InteractionMessage) -> dict:
    return {
        "id": message.id,
        "sender": message.sender,
        "source": message.source,
        "created_at": message.created_at,
        "processed_at": message.processed_at,
        "status": message.status,
        "metadata": message.metadata,
    }


def _serialize_message(message: InteractionMessage) -> str:
    metadata_json = json.dumps(_message_to_payload(message), ensure_ascii=False, sort_keys=True)
    metadata_fence = _fence_for(metadata_json)
    content_fence = _fence_for(message.content)
    return (
        f"## {message.id}\n\n"
        "Metadata:\n"
        f"{metadata_fence}json\n{metadata_json}\n{metadata_fence}\n\n"
        "Content:\n"
        f"{content_fence}text\n{message.content}\n{content_fence}\n"
    )


def _extract_blocks(raw: str) -> list[str]:
    lines = raw.splitlines()
    starts: list[int] = []
    fence_delimiter: str | None = None
    for i, line in enumerate(lines):
        stripped = line.strip()
        if fence_delimiter is None:
            match = _FENCE_OPEN_RE.match(stripped)
            if match:
                fence_delimiter = match.group(1)
                continue
            if _MESSAGE_HEADER_RE.match(stripped):
                starts.append(i)
            continue
        if stripped == fence_delimiter:
            fence_delimiter = None
    if not starts:
        return []
    starts.append(len(lines))
    blocks: list[str] = []
    for i in range(len(starts) - 1):
        block = "\n".join(lines[starts[i] : starts[i + 1]]).strip()
        if block:
            blocks.append(block)
    return blocks


def _parse_block(block: str) -> InteractionMessage | None:
    lines = block.splitlines()
    if len(lines) < 6 or not lines[0].startswith("## MSG_"):
        return None

    message_id = lines[0].replace("## ", "", 1).strip()
    try:
        metadata_idx = lines.index("Metadata:")
        content_idx = lines.index("Content:")
    except ValueError:
        return None
    if metadata_idx + 2 >= len(lines) or content_idx + 2 >= len(lines):
        return None

    metadata_fence = lines[metadata_idx + 1].strip()
    metadata_match = _FENCE_OPEN_RE.match(metadata_fence)
    if metadata_match is None:
        return None
    metadata_open = metadata_match.group(1)
    metadata_close_idx = None
    for idx in range(metadata_idx + 2, len(lines)):
        if lines[idx] == metadata_open:
            metadata_close_idx = idx
            break
    if metadata_close_idx is None:
        return None

    content_fence = lines[content_idx + 1].strip()
    content_match = _FENCE_OPEN_RE.match(content_fence)
    if content_match is None:
        return None
    content_open = content_match.group(1)
    content_close_idx = None
    for idx in range(content_idx + 2, len(lines)):
        if lines[idx] == content_open:
            content_close_idx = idx
            break
    if content_close_idx is None:
        return None

    metadata_payload = "\n".join(lines[metadata_idx + 2 : metadata_close_idx])
    content_payload = "\n".join(lines[content_idx + 2 : content_close_idx])
    try:
        data = json.loads(metadata_payload)
    except json.JSONDecodeError:
        return None

    return InteractionMessage(
        id=data.get("id", message_id),
        sender=data.get("sender", "user"),
        source=data.get("source", "local"),
        content=content_payload,
        created_at=data.get("created_at", datetime.now(UTC).isoformat()),
        processed_at=data.get("processed_at"),
        status=data.get("status", "pending"),
        metadata=data.get("metadata", {}),
    )


class InboxStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.write_text("# Inbox\n\n", encoding="utf-8")

    def load_messages(self) -> list[InteractionMessage]:
        raw = self.path.read_text(encoding="utf-8")
        messages: list[InteractionMessage] = []
        for block in _extract_blocks(raw):
            parsed = _parse_block(block)
            if parsed is not None:
                messages.append(parsed)
        return messages

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

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, UTC


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


@dataclass
class InteractionMessage:
    id: str
    sender: str
    source: str
    content: str
    created_at: str = field(default_factory=utc_now_iso)
    processed_at: str | None = None
    status: str = "pending"
    metadata: dict = field(default_factory=dict)


@dataclass
class InteractionResponse:
    id: str
    sender: str
    source: str
    content: str
    created_at: str = field(default_factory=utc_now_iso)
    processed_at: str | None = None
    status: str = "sent"
    metadata: dict = field(default_factory=dict)

from __future__ import annotations

from datetime import datetime, UTC
from pathlib import Path


class LongMemory:
    def __init__(self, memory_dir: Path) -> None:
        self.memory_dir = memory_dir
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        self.long_term = self.memory_dir / "long_term.md"
        self.reflections = self.memory_dir / "reflections.md"
        self.decisions = self.memory_dir / "decisions.md"
        self.facts = self.memory_dir / "facts.md"

        for file_path in [self.long_term, self.reflections, self.decisions, self.facts]:
            if not file_path.exists():
                file_path.write_text("", encoding="utf-8")

    def _append(self, path: Path, text: str) -> None:
        stamp = datetime.now(UTC).isoformat()
        with path.open("a", encoding="utf-8") as file:
            file.write(f"\n- [{stamp}] {text}\n")

    def append_long_term(self, text: str) -> None:
        self._append(self.long_term, text)

    def append_reflection(self, text: str) -> None:
        self._append(self.reflections, text)

    def append_decision(self, text: str) -> None:
        self._append(self.decisions, text)

    def append_fact(self, text: str) -> None:
        self._append(self.facts, text)

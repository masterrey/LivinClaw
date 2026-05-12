from __future__ import annotations

# memory/long_memory.py
# Long-term persistent memory.
# Extends the original flat-file approach with topic-tree support so that
# specific observations can be routed to the correct topic branch.
# All legacy methods (append_long_term, append_reflection, etc.) remain intact.

from datetime import datetime, UTC
from pathlib import Path

from memory.memory_indexer import MemoryIndexer
from memory.topic_classifier import TopicClassifier


class LongMemory:
    def __init__(self, memory_dir: Path) -> None:
        self.memory_dir = memory_dir
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        # Legacy flat files – kept for backward compatibility
        self.long_term = self.memory_dir / "long_term.md"
        self.reflections = self.memory_dir / "reflections.md"
        self.decisions = self.memory_dir / "decisions.md"
        self.facts = self.memory_dir / "facts.md"

        for file_path in [self.long_term, self.reflections, self.decisions, self.facts]:
            if not file_path.exists():
                file_path.write_text("", encoding="utf-8")

        # Topic-tree components
        self.indexer = MemoryIndexer(memory_dir)
        self.classifier = TopicClassifier()

    # ------------------------------------------------------------------
    # Legacy flat-file API (unchanged)
    # ------------------------------------------------------------------

    def _append(self, path: Path, text: str) -> None:
        stamp = datetime.now(UTC).isoformat()
        with path.open("a", encoding="utf-8") as file:
            file.write(f"\n- [{stamp}] {text}\n")

    def append_long_term(self, text: str) -> None:
        self._append(self.long_term, text)

    def append_reflection(self, text: str) -> None:
        self._append(self.reflections, text)
        # Also persist to the topic-tree reflections branch
        self.indexer.append_to_topic_file("reflections", "reflections.md", text)

    def append_decision(self, text: str) -> None:
        self._append(self.decisions, text)

    def append_fact(self, text: str) -> None:
        self._append(self.facts, text)

    # ------------------------------------------------------------------
    # Topic-tree API
    # ------------------------------------------------------------------

    def append_to_topic(self, text: str, topic: str | None = None, filename: str | None = None) -> None:
        """Route *text* to the correct topic branch.

        If *topic* is None the classifier picks the best-matching topic.
        If *filename* is None the classifier suggests a file within that topic.
        """
        if topic is None:
            topic, suggested_file = self.classifier.classify_with_file(text)
        else:
            _, suggested_file = self.classifier.classify_with_file(text)

        if filename is None:
            filename = suggested_file

        self.indexer.append_to_topic_file(topic, filename, text)

    def load_topics(self, topic_names: list[str]) -> dict[str, str]:
        """Load and return content for each named topic branch."""
        return {name: self.indexer.load_topic_files(name) for name in topic_names}

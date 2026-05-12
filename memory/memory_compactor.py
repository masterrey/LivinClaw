from __future__ import annotations

# memory/memory_compactor.py
# Memory compactor with per-topic compaction support.
# Topic-level compaction only touches the files inside a single topic directory,
# leaving all other branches untouched – this prevents cross-contamination.

import logging
from pathlib import Path


class MemoryCompactor:
    def __init__(self, long_memory, llm_client=None, max_chars_per_file: int = 12000) -> None:
        self.long_memory = long_memory
        self.llm_client = llm_client
        self.max_chars_per_file = max_chars_per_file
        self.logger = logging.getLogger(__name__)

    # ------------------------------------------------------------------
    # File-level compaction (unchanged internal helper)
    # ------------------------------------------------------------------

    def _compact_file(self, file_path: Path) -> None:
        content = file_path.read_text(encoding="utf-8")
        if len(content) <= self.max_chars_per_file:
            return

        if self.llm_client is not None:
            try:
                summary = self.llm_client.chat(
                    [
                        {"role": "system", "content": "Compacte memória preservando fatos e decisões."},
                        {"role": "user", "content": content[-20000:]},
                    ]
                )
                file_path.write_text(summary.strip() + "\n", encoding="utf-8")
                return
            except Exception as exc:
                self.logger.warning("LLM compaction failed for %s: %s", file_path.name, exc)

        lines = [line.strip() for line in content.splitlines() if line.strip()]
        deduplicated = list(dict.fromkeys(lines))
        file_path.write_text("\n".join(deduplicated[-200:]) + "\n", encoding="utf-8")

    # ------------------------------------------------------------------
    # Global flat-file compaction (legacy behaviour, preserved)
    # ------------------------------------------------------------------

    def compact_if_needed(self) -> None:
        """Compact all legacy flat memory files when they exceed the size limit."""
        for file_path in [
            self.long_memory.long_term,
            self.long_memory.reflections,
            self.long_memory.decisions,
            self.long_memory.facts,
        ]:
            self._compact_file(file_path)

    # ------------------------------------------------------------------
    # Per-topic compaction (new)
    # ------------------------------------------------------------------

    def compact_topic(self, topic_name: str) -> None:
        """Compact only the files inside a single topic directory.

        All other topic branches remain untouched.
        """
        indexer = getattr(self.long_memory, "indexer", None)
        if indexer is None:
            self.logger.warning("LongMemory has no indexer – cannot do per-topic compaction")
            return

        topic_dir = indexer.topic_dir(topic_name)
        if topic_dir is None or not topic_dir.exists():
            self.logger.debug("Topic directory not found for '%s'", topic_name)
            return

        compacted = 0
        for fpath in topic_dir.iterdir():
            if fpath.suffix == ".md":
                self._compact_file(fpath)
                compacted += 1

        self.logger.info("Per-topic compaction finished for '%s' (%d files)", topic_name, compacted)

    def compact_topics_if_needed(self, topic_names: list[str]) -> None:
        """Run per-topic compaction for each listed topic name."""
        for name in topic_names:
            self.compact_topic(name)

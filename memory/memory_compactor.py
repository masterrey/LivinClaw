from __future__ import annotations

import logging
from pathlib import Path


class MemoryCompactor:
    def __init__(self, long_memory, llm_client=None, max_chars_per_file: int = 12000) -> None:
        self.long_memory = long_memory
        self.llm_client = llm_client
        self.max_chars_per_file = max_chars_per_file
        self.logger = logging.getLogger(__name__)

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

    def compact_if_needed(self) -> None:
        for file_path in [
            self.long_memory.long_term,
            self.long_memory.reflections,
            self.long_memory.decisions,
            self.long_memory.facts,
        ]:
            self._compact_file(file_path)

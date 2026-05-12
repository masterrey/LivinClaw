from __future__ import annotations

# memory/memory_router.py
# Sparse topic-memory router inspired by Mixture-of-Experts activation.
# Analyses the current task and short-memory snapshot, scores all known topics
# for relevance, and returns ONLY the top-N most relevant topic branches.
#
# The router NEVER loads all topics at once – this is a hard invariant.

import logging
import re
from datetime import datetime, UTC

from memory.memory_indexer import MemoryIndexer
from memory.topic_classifier import TOPIC_KEYWORDS

_SEMANTIC_WEIGHT = 0.60
_RECENCY_WEIGHT = 0.15
_IMPORTANCE_WEIGHT = 0.25


class MemoryRouter:
    """Selects and loads only the most relevant memory branches for a given context."""

    def __init__(self, indexer: MemoryIndexer, max_loaded_topics: int = 3) -> None:
        self.indexer = indexer
        self.max_loaded_topics = max_loaded_topics
        self.logger = logging.getLogger(__name__)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def route(self, task: str, short_memory_text: str = "") -> dict[str, str]:
        """Score topics and return loaded content for the top-N branches.

        Returns a dict mapping topic_name → markdown_content.
        At most *max_loaded_topics* topics are returned.
        """
        combined_text = f"{task} {short_memory_text}"
        scores = self._score_topics(combined_text)

        # Select top-N by score; never exceed max_loaded_topics
        sorted_topics = sorted(scores, key=lambda t: scores[t], reverse=True)
        top_topics = sorted_topics[: self.max_loaded_topics]

        self.logger.info(
            "MemoryRouter selected topics %s (scores: %s)",
            top_topics,
            {t: round(scores[t], 3) for t in top_topics},
        )

        loaded: dict[str, str] = {}
        for name in top_topics:
            content = self.indexer.load_topic_files(name)
            if content.strip():
                loaded[name] = content

        return loaded

    def score_only(self, task: str, short_memory_text: str = "") -> dict[str, float]:
        """Return relevance scores for all topics without loading files."""
        combined = f"{task} {short_memory_text}"
        return self._score_topics(combined)

    # ------------------------------------------------------------------
    # Relevance scoring
    # ------------------------------------------------------------------

    def _score_topics(self, text: str) -> dict[str, float]:
        """Compute a composite relevance score for each topic.

        Score components:
        - semantic_score: keyword frequency normalised to [0, 1]
        - recency_bonus:  boost for recently accessed topics
        - importance:     stored importance weight from the index
        """
        lower = text.lower()
        all_topics = self.indexer.all_topics()
        scores: dict[str, float] = {}

        for meta in all_topics:
            name = meta["name"]
            keywords = TOPIC_KEYWORDS.get(name, [])

            # Keyword hit count → normalised semantic score
            hit_count = sum(
                len(re.findall(r"\b" + re.escape(kw) + r"\b", lower))
                for kw in keywords
            )
            max_hits = max(1, len(keywords))
            semantic = min(1.0, hit_count / max_hits)

            # Recency bonus: topics accessed in the last hour get a small bump
            recency = _recency_bonus(meta.get("last_access", ""))

            # Importance weight from the index
            importance = float(meta.get("importance", 0.5))

            # Weighted composite (semantic-first routing with lighter recency/importance boosts)
            composite = (
                _SEMANTIC_WEIGHT * semantic
                + _RECENCY_WEIGHT * recency
                + _IMPORTANCE_WEIGHT * importance
            )
            scores[name] = round(composite, 4)

        return scores


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _recency_bonus(last_access_iso: str) -> float:
    """Return a [0, 1] bonus based on how recently the topic was accessed."""
    if not last_access_iso:
        return 0.0
    try:
        last = datetime.fromisoformat(last_access_iso)
        # Make it timezone-aware if needed
        if last.tzinfo is None:
            last = last.replace(tzinfo=UTC)
        now = datetime.now(UTC)
        seconds_ago = (now - last).total_seconds()
        if seconds_ago < 3600:  # within the last hour
            return 0.5
        if seconds_ago < 86400:  # within the last day
            return 0.2
        return 0.05
    except (ValueError, TypeError):
        return 0.0

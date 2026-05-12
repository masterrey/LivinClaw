from __future__ import annotations

# memory/short_memory.py
# RAM short-term memory with importance scoring, decay, and self-pruning.
# The legacy deque-based API (actions / observations) is preserved for full
# backward compatibility.  The new weighted_entries list is used by the
# cognitive budget and context assembler for importance-aware selection.

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, UTC
from typing import Literal


EntryType = Literal["action", "observation"]

# Entries below this threshold are preferentially pruned when cap is exceeded.
PRUNE_IMPORTANCE_THRESHOLD = 0.3

# Cognitive-weight cap for weighted_entries (soft limit)
MAX_WEIGHTED_ENTRIES = 40

# Per-tick importance decay applied during summarize()
DEFAULT_IMPORTANCE_DECAY = 0.95


@dataclass
class MemoryEntry:
    """A single short-memory entry with metadata for importance-based pruning."""

    text: str
    importance: float = 0.5
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    entry_type: EntryType = "observation"
    cognitive_weight: float = 1.0


class ShortMemory:
    def __init__(self, importance_decay: float = DEFAULT_IMPORTANCE_DECAY) -> None:
        self.summary = "Estado inicial"
        # Legacy deques – preserved for backward compatibility and existing tests
        self.actions: deque[str] = deque(maxlen=20)
        self.observations: deque[str] = deque(maxlen=20)
        self.open_intentions: list[str] = []
        self.current_state: dict[str, str] = {"mode": "idle"}
        # New weighted entries for importance-aware memory management
        self.weighted_entries: list[MemoryEntry] = []
        self.importance_decay = importance_decay

    # ------------------------------------------------------------------
    # Entry addition
    # ------------------------------------------------------------------

    def add_action(self, action: str, importance: float = 0.5) -> None:
        self.actions.append(action)
        self._add_weighted(action, importance, "action")

    def add_observation(self, observation: str, importance: float = 0.5) -> None:
        self.observations.append(observation)
        self._add_weighted(observation, importance, "observation")

    def _add_weighted(self, text: str, importance: float, entry_type: EntryType) -> None:
        entry = MemoryEntry(text=text, importance=importance, entry_type=entry_type)
        self.weighted_entries.append(entry)
        self._prune_if_needed()

    # ------------------------------------------------------------------
    # Decay and pruning
    # ------------------------------------------------------------------

    def _apply_decay(self) -> None:
        """Decay importance of all weighted entries by one step."""
        for entry in self.weighted_entries:
            entry.importance = round(entry.importance * self.importance_decay, 4)

    def _prune_if_needed(self) -> None:
        """Remove low-importance entries when the cap is exceeded."""
        if len(self.weighted_entries) <= MAX_WEIGHTED_ENTRIES:
            return
        # Sort by importance ascending; remove cheapest entries first
        self.weighted_entries.sort(key=lambda e: e.importance)
        excess = len(self.weighted_entries) - MAX_WEIGHTED_ENTRIES
        # Prefer to prune entries below threshold first
        prunable = [e for e in self.weighted_entries if e.importance < PRUNE_IMPORTANCE_THRESHOLD]
        to_remove = prunable[:excess] if prunable else self.weighted_entries[:excess]
        for e in to_remove:
            self.weighted_entries.remove(e)

    # ------------------------------------------------------------------
    # Summarize (called each tick)
    # ------------------------------------------------------------------

    def summarize(self) -> None:
        self._apply_decay()
        recent_actions = list(self.actions)[-3:]
        recent_obs = list(self.observations)[-3:]
        self.summary = (
            f"Ações recentes: {recent_actions} | "
            f"Observações recentes: {recent_obs} | "
            f"Intenções abertas: {self.open_intentions[:3]}"
        )

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def export(self) -> dict:
        return {
            "summary": self.summary,
            "actions": list(self.actions),
            "observations": list(self.observations),
            "open_intentions": self.open_intentions[:10],
            "current_state": self.current_state,
        }

    def export_weighted(self) -> list[dict]:
        """Return weighted entries sorted by importance (highest first)."""
        sorted_entries = sorted(self.weighted_entries, key=lambda e: e.importance, reverse=True)
        return [
            {
                "text": e.text,
                "importance": e.importance,
                "timestamp": e.timestamp,
                "type": e.entry_type,
                "cognitive_weight": e.cognitive_weight,
            }
            for e in sorted_entries
        ]

    def top_entries(self, n: int = 10) -> list[MemoryEntry]:
        """Return the top-N entries by importance."""
        return sorted(self.weighted_entries, key=lambda e: e.importance, reverse=True)[:n]

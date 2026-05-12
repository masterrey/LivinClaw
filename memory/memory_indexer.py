from __future__ import annotations

# memory/memory_indexer.py
# Manages the topic-tree memory index stored as human-readable Markdown.
# Each topic entry tracks: name, description, path, tags, last_access, importance.

import logging
from datetime import datetime, UTC
from pathlib import Path


DEFAULT_TOPICS: list[dict] = [
    {
        "name": "architecture",
        "description": "Architectural decisions and runtime structure",
        "path": "topics/architecture/",
        "tags": ["runtime", "modularity", "design"],
        "importance": 0.80,
    },
    {
        "name": "mcp",
        "description": "MCP integration and JSON-RPC tooling",
        "path": "topics/mcp/",
        "tags": ["tools", "protocol", "integration"],
        "importance": 0.75,
    },
    {
        "name": "llm_runtime",
        "description": "LLM runtime behavior, failures and optimizations",
        "path": "topics/llm_runtime/",
        "tags": ["llm", "performance", "failures"],
        "importance": 0.75,
    },
    {
        "name": "guardian",
        "description": "Guardian layer incidents and homeostasis events",
        "path": "topics/guardian/",
        "tags": ["guardian", "safety", "compression"],
        "importance": 0.70,
    },
    {
        "name": "user_preferences",
        "description": "User preferences and interaction patterns",
        "path": "topics/user_preferences/",
        "tags": ["user", "preferences", "behavior"],
        "importance": 0.60,
    },
    {
        "name": "reflections",
        "description": "Agent self-reflections and meta-cognition",
        "path": "topics/reflections/",
        "tags": ["reflection", "learning", "meta"],
        "importance": 0.65,
    },
]

# Sub-files that exist inside each topic directory
TOPIC_FILES: dict[str, list[str]] = {
    "architecture": ["summary.md", "decisions.md", "facts.md"],
    "mcp": ["summary.md", "decisions.md", "facts.md"],
    "llm_runtime": ["summary.md", "failures.md", "optimizations.md"],
    "guardian": ["summary.md", "incidents.md"],
    "user_preferences": ["summary.md", "facts.md"],
    "reflections": ["reflections.md"],
}


class MemoryIndexer:
    """Maintains a lightweight Markdown index of all memory topics."""

    def __init__(self, memory_dir: Path) -> None:
        self.memory_dir = memory_dir
        self.index_path = memory_dir / "index.md"
        self.logger = logging.getLogger(__name__)
        self._topics: dict[str, dict] = {}
        self._ensure_structure()
        self._load()

    # ------------------------------------------------------------------
    # Initialisation helpers
    # ------------------------------------------------------------------

    def _ensure_structure(self) -> None:
        """Create topic directories and stub files if they don't exist."""
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        for topic in DEFAULT_TOPICS:
            topic_dir = self.memory_dir / topic["path"]
            topic_dir.mkdir(parents=True, exist_ok=True)
            for fname in TOPIC_FILES.get(topic["name"], ["summary.md"]):
                fpath = topic_dir / fname
                if not fpath.exists():
                    fpath.write_text("", encoding="utf-8")

    # ------------------------------------------------------------------
    # Index I/O
    # ------------------------------------------------------------------

    def _load(self) -> None:
        """Load index from index.md, or seed with defaults if not present."""
        if not self.index_path.exists():
            self._topics = {t["name"]: dict(t) for t in DEFAULT_TOPICS}
            for t in self._topics.values():
                t.setdefault("last_access", "")
            self._save()
            return

        content = self.index_path.read_text(encoding="utf-8")
        self._topics = _parse_index(content)
        # Merge any new default topics that aren't in the index yet
        for default in DEFAULT_TOPICS:
            if default["name"] not in self._topics:
                entry = dict(default)
                entry.setdefault("last_access", "")
                self._topics[default["name"]] = entry
        self._save()

    def _save(self) -> None:
        """Persist the index to index.md in human-readable Markdown."""
        lines = ["# Memory Index\n"]
        for name, meta in self._topics.items():
            tags = ", ".join(meta.get("tags", []))
            lines += [
                f"## {name}\n",
                f"- Description: {meta.get('description', '')}\n",
                f"- Path: {meta.get('path', '')}\n",
                f"- Tags: {tags}\n",
                f"- Importance: {meta.get('importance', 0.5):.2f}\n",
                f"- LastAccess: {meta.get('last_access', '')}\n",
                "\n",
            ]
        self.index_path.write_text("".join(lines), encoding="utf-8")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def all_topics(self) -> list[dict]:
        """Return all topic metadata records."""
        return list(self._topics.values())

    def get_topic(self, name: str) -> dict | None:
        return self._topics.get(name)

    def topic_dir(self, name: str) -> Path | None:
        meta = self._topics.get(name)
        if not meta:
            return None
        return self.memory_dir / meta["path"]

    def update_importance(self, name: str, importance: float) -> None:
        if name in self._topics:
            self._topics[name]["importance"] = max(0.0, min(1.0, importance))
            self._save()

    def record_access(self, name: str) -> None:
        if name in self._topics:
            self._topics[name]["last_access"] = datetime.now(UTC).isoformat()
            self._save()

    def load_topic_files(self, name: str) -> str:
        """Load all Markdown files under a topic directory and return concatenated text."""
        topic_dir = self.topic_dir(name)
        if topic_dir is None or not topic_dir.exists():
            return ""
        parts: list[str] = []
        for fpath in sorted(topic_dir.iterdir()):
            if fpath.suffix == ".md":
                text = fpath.read_text(encoding="utf-8").strip()
                if text:
                    parts.append(f"### {name}/{fpath.name}\n{text}")
        self.record_access(name)
        return "\n\n".join(parts)

    def append_to_topic_file(self, name: str, filename: str, text: str) -> None:
        """Append a timestamped entry to a specific file inside a topic directory."""
        topic_dir = self.topic_dir(name)
        if topic_dir is None:
            self.logger.warning("Unknown topic '%s', falling back to architecture", name)
            topic_dir = self.topic_dir("architecture")
            if topic_dir is None:
                return
        topic_dir.mkdir(parents=True, exist_ok=True)
        fpath = topic_dir / filename
        stamp = datetime.now(UTC).isoformat()
        with fpath.open("a", encoding="utf-8") as f:
            f.write(f"\n- [{stamp}] {text}\n")


# ------------------------------------------------------------------
# Parser helpers
# ------------------------------------------------------------------

def _parse_index(content: str) -> dict[str, dict]:
    """Parse a Markdown index file into a dict keyed by topic name."""
    topics: dict[str, dict] = {}
    current: dict | None = None
    for line in content.splitlines():
        line = line.strip()
        if line.startswith("## "):
            name = line[3:].strip()
            current = {"name": name}
            topics[name] = current
        elif current is not None and line.startswith("- "):
            body = line[2:]
            if ": " in body:
                key, _, value = body.partition(": ")
                key_norm = key.strip().lower().replace(" ", "_")
                value = value.strip()
                if key_norm == "tags":
                    current["tags"] = [t.strip() for t in value.split(",") if t.strip()]
                elif key_norm == "importance":
                    try:
                        current["importance"] = float(value)
                    except ValueError:
                        import logging
                        logging.getLogger(__name__).debug(
                            "Invalid importance value '%s' for topic '%s', using default 0.5",
                            value,
                            current.get("name", "?"),
                        )
                        current["importance"] = 0.5
                else:
                    current[key_norm] = value
    return topics

from __future__ import annotations

# memory/topic_classifier.py
# Keyword-based topic classifier. Maps text snippets to the most relevant
# topic branch. Designed to be replaced with an LLM-backed version later.

import re

# Keyword → topic mapping.  Keys are topic names matching memory_indexer defaults.
TOPIC_KEYWORDS: dict[str, list[str]] = {
    "architecture": [
        "architecture", "runtime", "loop", "modular", "design", "structure",
        "refactor", "component", "module", "system", "tick",
    ],
    "mcp": [
        "mcp", "json-rpc", "jsonrpc", "tool", "protocol", "integration",
        "unity", "server", "endpoint", "api", "invoke",
    ],
    "llm_runtime": [
        "llm", "model", "inference", "token", "prompt", "context",
        "temperature", "openai", "lmstudio", "response", "completion",
    ],
    "guardian": [
        "guardian", "compress", "oversized", "limit", "safety", "repair",
        "budget", "overflow", "check", "homeostasis", "protect",
    ],
    "user_preferences": [
        "user", "prefer", "setting", "option", "configure", "behavior",
        "style", "format", "language",
    ],
    "reflections": [
        "reflect", "reflexão", "learning", "introspect", "meta", "insight",
        "analysis", "evaluate",
    ],
}

# Default topic used when no match is found
DEFAULT_TOPIC = "architecture"


class TopicClassifier:
    """Assigns text to a topic based on keyword frequency."""

    def classify(self, text: str) -> str:
        """Return the best-matching topic name for *text*."""
        if not text:
            return DEFAULT_TOPIC

        lower = text.lower()
        scores: dict[str, int] = {}
        for topic, keywords in TOPIC_KEYWORDS.items():
            count = sum(
                len(re.findall(r"\b" + re.escape(kw) + r"\b", lower))
                for kw in keywords
            )
            if count > 0:
                scores[topic] = count

        if not scores:
            return DEFAULT_TOPIC
        return max(scores, key=scores.__getitem__)

    def classify_with_file(self, text: str) -> tuple[str, str]:
        """Return (topic_name, suggested_filename) for the given text."""
        topic = self.classify(text)
        filename = _suggest_filename(topic, text)
        return topic, filename


def _suggest_filename(topic: str, text: str) -> str:
    """Suggest the most appropriate markdown file within a topic for *text*."""
    lower = text.lower()

    if topic == "guardian":
        return "incidents.md"
    if topic == "reflections":
        return "reflections.md"
    if topic == "user_preferences":
        return "facts.md"
    if topic == "llm_runtime":
        if any(w in lower for w in ("fail", "error", "crash", "timeout", "exception")):
            return "failures.md"
        if any(w in lower for w in ("optim", "speed", "latency", "fast", "slow")):
            return "optimizations.md"
        return "summary.md"
    # architecture / mcp / default
    if any(w in lower for w in ("decision", "decided", "choose", "chose", "adopt")):
        return "decisions.md"
    if any(w in lower for w in ("fact", "know", "observe", "note")):
        return "facts.md"
    return "summary.md"

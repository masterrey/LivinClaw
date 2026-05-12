from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from agent.alive_agent import AliveAgent, TickType
from interaction.interaction_manager import InteractionManager


def _base_config() -> dict:
    return {
        "agent": {
            "max_tasks_per_tick": 3,
            "reflection_enabled": False,
            "max_short_summary_chars": 500,
        },
        "guardian": {
            "enabled": False,
            "check_every_ticks": 6,
            "max_guardian_tokens": 3000,
            "main_context_limit": 16000,
            "safe_context_ratio": 0.7,
        },
        "model": {
            "base_url": "http://127.0.0.1:1234/v1",
            "model": "test-model",
            "temperature": 0.3,
        },
        "paths": {
            "tasks": "workspace/tasks.md",
            "memory_dir": "workspace/memory",
        },
        "memory": {"importance_decay": 0.95},
        "cognitive_budget": {
            "max_tokens_per_tick": 1000,
            "max_loaded_topics": 3,
            "max_reflections_per_day": 5,
            "reflection_cooldown_ticks": 2,
            "max_compactions_per_hour": 1,
        },
        "reflection": {"enabled": False},
        "interaction": {
            "enabled": True,
            "interactive_tick_enabled": True,
            "inbox_path": "workspace/inbox.md",
            "outbox_path": "workspace/outbox.md",
            "max_queue_size": 100,
        },
        "interactive_tick": {
            "reflection_enabled": False,
            "memory_compaction_enabled": False,
            "max_loaded_topics": 2,
            "max_tokens": 4000,
            "prioritize_inbox": True,
            "max_messages_per_tick": 3,
        },
    }


class InteractionManagerTests(unittest.TestCase):
    def test_inbox_append_and_safe_markdown_serialization(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = InteractionManager(root / "workspace/inbox.md", root / "workspace/outbox.md")
            dangerous = "## fake\n```text\nescape?\n```\n|a|b|\n<script>x</script>"
            manager.append_user_message(dangerous)

            pending = manager.read_pending_messages()
            self.assertEqual(1, len(pending))
            self.assertEqual(dangerous, pending[0].content)

            raw = (root / "workspace/inbox.md").read_text(encoding="utf-8")
            self.assertIn("Metadata:", raw)
            self.assertIn("Content:", raw)

    def test_outbox_append(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = InteractionManager(root / "workspace/inbox.md", root / "workspace/outbox.md")
            manager.append_response("ok", response_id="MSG_0001")
            raw = (root / "workspace/outbox.md").read_text(encoding="utf-8")
            self.assertIn("## MSG_0001", raw)
            self.assertIn("ok", raw)

    def test_malformed_markdown_handling(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            inbox = root / "workspace/inbox.md"
            inbox.parent.mkdir(parents=True, exist_ok=True)
            inbox.write_text("# Inbox\n\n## MSG_0001\nMetadata:\n```json\n{bad json\n```\n", encoding="utf-8")
            manager = InteractionManager(inbox, root / "workspace/outbox.md")
            self.assertFalse(manager.payload_integrity_ok())
            self.assertEqual([], manager.read_pending_messages())

    def test_duplicate_interaction_safety(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = InteractionManager(root / "workspace/inbox.md", root / "workspace/outbox.md")
            first = manager.append_user_message("@ask status")
            second = manager.append_user_message("@ask status")
            self.assertEqual(first.id, second.id)
            self.assertEqual(1, manager.pending_count())


class InteractiveTickTests(unittest.TestCase):
    def test_interactive_tick_dispatch_and_processing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tasks_file = root / "workspace/tasks.md"
            tasks_file.parent.mkdir(parents=True, exist_ok=True)
            tasks_file.write_text("", encoding="utf-8")

            agent = AliveAgent(config=_base_config(), root_dir=root)
            assert agent.interaction is not None
            agent.interaction.append_user_message("@task Create architecture summary")

            agent.tick(reason=TickType.INTERACTIVE)

            inbox_content = (root / "workspace/inbox.md").read_text(encoding="utf-8")
            outbox_content = (root / "workspace/outbox.md").read_text(encoding="utf-8")
            tasks_content = tasks_file.read_text(encoding="utf-8")

            self.assertIn('"status": "processed"', inbox_content)
            self.assertIn("## MSG_0001", outbox_content)
            self.assertIn("- [ ] Create architecture summary", tasks_content)

    def test_lock_prevents_concurrent_tick_execution(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tasks_file = root / "workspace/tasks.md"
            tasks_file.parent.mkdir(parents=True, exist_ok=True)
            tasks_file.write_text("", encoding="utf-8")
            agent = AliveAgent(config=_base_config(), root_dir=root)

            acquired = agent.tick_lock.acquire(blocking=False)
            self.assertTrue(acquired)
            try:
                agent.tick(reason=TickType.INTERACTIVE)
            finally:
                agent.tick_lock.release()
            self.assertEqual(0, agent.tick_count)


if __name__ == "__main__":
    unittest.main()

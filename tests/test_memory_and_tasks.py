from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from guardian.guardian import GuardianLayer
from memory.short_memory import ShortMemory
from tasks.task_manager import TaskManager


class MiniClawCoreTests(unittest.TestCase):
    def test_short_memory_caps_at_twenty(self) -> None:
        mem = ShortMemory()
        for i in range(30):
            mem.add_action(f"a{i}")
            mem.add_observation(f"o{i}")

        self.assertEqual(20, len(mem.actions))
        self.assertEqual(20, len(mem.observations))
        self.assertEqual("a10", list(mem.actions)[0])

    def test_task_manager_marks_done(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tasks_file = Path(tmp) / "tasks.md"
            tasks_file.write_text("- [ ] tarefa A\n- [ ] tarefa B\n", encoding="utf-8")
            manager = TaskManager(tasks_file)

            pending = manager.get_pending_tasks(limit=1)
            self.assertEqual(["tarefa A"], pending)

            manager.mark_done("tarefa A", "ok")
            content = tasks_file.read_text(encoding="utf-8")
            self.assertIn("- [x] tarefa A — ok", content)

    def test_guardian_compresses_large_prompt(self) -> None:
        guardian = GuardianLayer(
            {
                "max_guardian_tokens": 3000,
                "main_context_limit": 16000,
                "safe_context_ratio": 0.7,
            }
        )
        huge_prompt = "x" * 60000
        report = guardian.check_prompt(huge_prompt, main_context_limit=16000, safe_context_ratio=0.7)
        self.assertEqual("compress", report.action)
        self.assertTrue(report.repaired_prompt)


if __name__ == "__main__":
    unittest.main()

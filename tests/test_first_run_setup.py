from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import yaml

from scripts.bootstrap_first_run import ensure_config_from_example, ensure_workspace_files
from scripts.send_message import append_message


class FirstRunSetupTests(unittest.TestCase):
    def test_config_example_exists_and_is_parseable(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        config_example = repo_root / "config.example.yaml"
        self.assertTrue(config_example.exists())

        data = yaml.safe_load(config_example.read_text(encoding="utf-8"))
        self.assertIsInstance(data, dict)

        expected_sections = {
            "agent",
            "guardian",
            "model",
            "paths",
            "memory",
            "cognitive_budget",
            "reflection",
            "interaction",
            "interactive_tick",
        }
        self.assertTrue(expected_sections.issubset(set(data.keys())))

    def test_setup_helper_does_not_overwrite_existing_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            template = root / "config.example.yaml"
            config = root / "config.yaml"

            template.write_text("model:\n  base_url: http://127.0.0.1:1234/v1\n", encoding="utf-8")
            config.write_text("agent:\n  name: keep-me\n", encoding="utf-8")

            created = ensure_config_from_example(root)
            self.assertFalse(created)
            self.assertEqual("agent:\n  name: keep-me\n", config.read_text(encoding="utf-8"))

    def test_workspace_bootstrap_is_non_destructive(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workspace = root / "workspace"
            workspace.mkdir(parents=True, exist_ok=True)

            inbox = workspace / "inbox.md"
            outbox = workspace / "outbox.md"
            tasks = workspace / "tasks.md"

            inbox.write_text("# Inbox\n\ncustom\n", encoding="utf-8")
            outbox.write_text("# Outbox\n\ncustom\n", encoding="utf-8")
            tasks.write_text("- [ ] existing task\n", encoding="utf-8")

            ensure_workspace_files(root)

            self.assertEqual("# Inbox\n\ncustom\n", inbox.read_text(encoding="utf-8"))
            self.assertEqual("# Outbox\n\ncustom\n", outbox.read_text(encoding="utf-8"))
            self.assertEqual("- [ ] existing task\n", tasks.read_text(encoding="utf-8"))
            self.assertTrue((workspace / "logs").exists())

    def test_send_message_appends_safe_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "config.yaml").write_text(
                "interaction:\n  inbox_path: workspace/inbox.md\n  outbox_path: workspace/outbox.md\n",
                encoding="utf-8",
            )

            payload = "## fake\n```text\nhello\n```\n<script>x</script>"
            message_id = append_message(content=payload, root=root)

            inbox_raw = (root / "workspace/inbox.md").read_text(encoding="utf-8")
            self.assertIn(message_id, inbox_raw)
            self.assertIn("Metadata:", inbox_raw)
            self.assertIn("Content:", inbox_raw)


if __name__ == "__main__":
    unittest.main()

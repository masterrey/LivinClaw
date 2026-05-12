from __future__ import annotations

import argparse
from pathlib import Path

import yaml

from interaction.interaction_manager import InteractionManager


def _interaction_paths_from_config(root: Path) -> tuple[Path, Path]:
    config_path = root / "config.yaml"
    if not config_path.exists():
        return root / "workspace/inbox.md", root / "workspace/outbox.md"

    data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    interaction_cfg = data.get("interaction", {})
    inbox_rel = interaction_cfg.get("inbox_path", "workspace/inbox.md")
    outbox_rel = interaction_cfg.get("outbox_path", "workspace/outbox.md")
    return root / inbox_rel, root / outbox_rel


def append_message(content: str, root: Path, source: str = "cli") -> str:
    inbox_path, outbox_path = _interaction_paths_from_config(root)
    manager = InteractionManager(inbox_path=inbox_path, outbox_path=outbox_path)
    message = manager.append_user_message(content=content, source=source, metadata={"via": "send_message.py"})
    return message.id


def main() -> None:
    parser = argparse.ArgumentParser(description="Append a safe user message to LivinClaw inbox")
    parser.add_argument("message", nargs="+", help="Message content (example: @task Do X)")
    parser.add_argument("--source", default="cli", help="Message source label")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    content = " ".join(args.message).strip()
    if not content:
        raise SystemExit("Message cannot be empty")

    message_id = append_message(content=content, root=root, source=args.source)
    print(f"Appended message {message_id} to inbox")


if __name__ == "__main__":
    main()

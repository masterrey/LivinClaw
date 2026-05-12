from __future__ import annotations

import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def ensure_config_from_example(root: Path = ROOT) -> bool:
    config_path = root / "config.yaml"
    template_path = root / "config.example.yaml"

    if config_path.exists():
        return False
    if not template_path.exists():
        raise FileNotFoundError("config.example.yaml not found")

    shutil.copyfile(template_path, config_path)
    return True


def ensure_workspace_files(root: Path = ROOT) -> None:
    workspace_dir = root / "workspace"
    logs_dir = workspace_dir / "logs"
    memory_dir = workspace_dir / "memory"

    workspace_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)
    memory_dir.mkdir(parents=True, exist_ok=True)

    inbox = workspace_dir / "inbox.md"
    outbox = workspace_dir / "outbox.md"
    tasks = workspace_dir / "tasks.md"

    if not inbox.exists():
        inbox.write_text("# Inbox\n\n", encoding="utf-8")
    if not outbox.exists():
        outbox.write_text("# Outbox\n\n", encoding="utf-8")
    if not tasks.exists():
        tasks.write_text("# Tasks\n\n", encoding="utf-8")


def main() -> None:
    created_config = ensure_config_from_example(ROOT)
    ensure_workspace_files(ROOT)

    if created_config:
        print("Created config.yaml from config.example.yaml")
    else:
        print("config.yaml already exists (left unchanged)")

    print("Workspace bootstrap complete.")


if __name__ == "__main__":
    main()

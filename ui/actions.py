from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from interaction.interaction_manager import InteractionManager
from scripts.send_message import _interaction_paths_from_config
from scripts.show_latest_outbox import get_latest_outbox_response


ROOT = Path(__file__).resolve().parents[1]


def append_user_message(content: str, root: Path = ROOT, source: str = "dashboard") -> tuple[bool, str]:
    payload = content.strip()
    if not payload:
        return False, "Message cannot be empty."

    try:
        inbox_path, outbox_path = _interaction_paths_from_config(root)
        manager = InteractionManager(inbox_path=inbox_path, outbox_path=outbox_path)
        message = manager.append_user_message(
            content=payload,
            source=source,
            metadata={"via": "streamlit_dashboard"},
        )
    except Exception as exc:
        return False, f"Could not append message: {exc}"

    return True, message.id


def _run_tick(flag: str, root: Path = ROOT) -> tuple[bool, str]:
    command = [sys.executable, "alive_agent/main.py", flag]
    try:
        result = subprocess.run(command, cwd=root, capture_output=True, text=True, check=False)
    except Exception as exc:
        return False, f"Could not execute tick: {exc}"

    if result.returncode == 0:
        return True, "Tick executed successfully."

    parts = [part.strip() for part in (result.stderr, result.stdout) if part and part.strip()]
    output = "\n".join(parts).strip()
    if not output:
        output = f"exit code {result.returncode}"
    lines = output.splitlines()
    last_line = lines[-1].strip() if lines else output
    return False, last_line


def run_interactive_tick(root: Path = ROOT) -> tuple[bool, str]:
    return _run_tick("--interactive", root=root)


def run_scheduled_tick(root: Path = ROOT) -> tuple[bool, str]:
    return _run_tick("--once", root=root)


def read_latest_outbox_response(root: Path = ROOT) -> tuple[str | None, str | None]:
    latest, error = get_latest_outbox_response(root)
    if error:
        return None, error
    if latest is None:
        return None, None
    return latest.content, None

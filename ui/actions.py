from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from interaction.interaction_manager import InteractionManager
from interaction.message import InteractionMessage
from interaction.outbox import OutboxStore
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


def read_latest_outbox_message(root: Path = ROOT) -> tuple[InteractionMessage | None, str | None]:
    return get_latest_outbox_response(root)


def read_latest_outbox_response(root: Path = ROOT) -> tuple[str | None, str | None]:
    latest, error = read_latest_outbox_message(root)
    if error:
        return None, error
    if latest is None:
        return None, None
    return latest.content, None


def read_new_outbox_response(
    previous_message_id: str | None, root: Path = ROOT
) -> tuple[str | None, bool, str | None]:
    latest, error = read_latest_outbox_message(root)
    if error:
        return None, False, error
    if latest is None or latest.id == previous_message_id:
        return None, False, None
    return latest.content, True, None


def read_outbox_response_by_message_id(
    message_id: str | None, root: Path = ROOT
) -> tuple[InteractionMessage | None, str | None]:
    if not message_id:
        return None, "Message ID is required."
    try:
        _, outbox_path = _interaction_paths_from_config(root)
        store = OutboxStore(outbox_path, create_if_missing=False)
        messages = store.load_messages()
    except Exception as exc:
        return None, f"Could not read outbox: {exc}"

    for message in reversed(messages):
        if message.id == message_id:
            return message, None
    return None, None


def send_message_and_run_tick(content: str, root: Path = ROOT) -> tuple[bool, dict]:
    result = {
        "message_id": None,
        "tick_ok": False,
        "tick_message": "Not available yet",
        "response": None,
        "response_found": False,
        "error": None,
    }

    append_ok, append_message = append_user_message(content, root=root)
    if not append_ok:
        result["error"] = append_message
        result["tick_message"] = "Message was not queued."
        return False, result

    message_id = append_message
    result["message_id"] = message_id

    tick_ok, tick_message = run_interactive_tick(root=root)
    result["tick_ok"] = tick_ok
    result["tick_message"] = tick_message

    response_message, response_error = read_outbox_response_by_message_id(message_id, root=root)
    if response_error:
        result["error"] = response_error
    elif response_message is not None:
        result["response"] = response_message.content
        result["response_found"] = True

    overall_ok = tick_ok and result["error"] is None
    return overall_ok, result

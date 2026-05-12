from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from scripts.send_message import append_message
from scripts.show_latest_outbox import get_latest_outbox_response

EXIT_COMMANDS = {"exit", "quit", "/exit"}


def should_exit(user_input: str) -> bool:
    return user_input.strip().lower() in EXIT_COMMANDS


def run_interactive_tick(root: Path) -> tuple[bool, str | None]:
    command = [sys.executable, "alive_agent/main.py", "--interactive"]
    result = subprocess.run(command, cwd=root, capture_output=True, text=True, check=False)
    if result.returncode == 0:
        return True, None

    output = "\n".join(part.strip() for part in (result.stderr, result.stdout) if part.strip())
    if not output:
        output = f"exit code {result.returncode}"
    last_line = output.splitlines()[-1].strip()
    return False, last_line


def process_console_turn(user_input: str, root: Path) -> str | None:
    message = user_input.strip()
    if not message:
        return None

    append_message(content=message, root=root, source="console")
    success, error = run_interactive_tick(root)
    if not success:
        return f"[LivinClaw] Interactive tick failed: {error}"

    latest, response_error = get_latest_outbox_response(root)
    if response_error:
        return f"[LivinClaw] {response_error}"
    if latest is None:
        return "[LivinClaw] No response available yet."
    return latest.content


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    print("LivinClaw Console")
    print("Type /exit to quit.")
    print()
    print("Examples:")
    print("  olá")
    print("  @status")
    print("  @ask me explique sua arquitetura")
    print("  @task revisar memória")
    print("  @note prefiro respostas curtas")
    print()

    while True:
        try:
            user_input = input("You> ")
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if should_exit(user_input):
            break

        response = process_console_turn(user_input, root)
        if response is None:
            continue

        print()
        print("LivinClaw>")
        print(response)
        print()


if __name__ == "__main__":
    main()

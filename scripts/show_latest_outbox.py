from __future__ import annotations

from pathlib import Path

import yaml

from interaction.message import InteractionMessage
from interaction.outbox import OutboxStore
from scripts.send_message import _interaction_paths_from_config


def _resolve_outbox_path(root: Path) -> tuple[Path | None, str | None]:
    try:
        _, outbox_path = _interaction_paths_from_config(root)
    except yaml.YAMLError as exc:
        return None, f"Could not read config.yaml: {exc}"
    except Exception as exc:
        return None, f"Could not resolve outbox path: {exc}"
    return outbox_path, None


def get_latest_outbox_response(root: Path) -> tuple[InteractionMessage | None, str | None]:
    outbox_path, path_error = _resolve_outbox_path(root)
    if path_error:
        return None, path_error
    if outbox_path is None or not outbox_path.exists():
        return None, None

    store = OutboxStore(outbox_path, create_if_missing=False)
    if not store.payload_integrity_ok():
        return None, "Outbox is malformed."

    latest = store.latest_message()
    if latest is None:
        return None, None
    return latest, None


def render_latest_outbox(root: Path, include_message_id: bool = False) -> str:
    latest, error = get_latest_outbox_response(root)
    if error:
        return f"[LivinClaw] {error}"
    if latest is None:
        return "[LivinClaw] No response available yet."

    lines: list[str] = []
    if include_message_id:
        lines.append(f"[msg: {latest.id}]")
        lines.append("")
    lines.append("LivinClaw response:")
    lines.append("")
    lines.append(latest.content)
    return "\n".join(lines)


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    print(render_latest_outbox(root=root))


if __name__ == "__main__":
    main()

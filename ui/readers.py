from __future__ import annotations

from pathlib import Path

import yaml

from interaction.markdown_codec import _extract_blocks, _parse_block


ROOT = Path(__file__).resolve().parents[1]


def _safe_load_yaml(path: Path) -> tuple[dict, str | None]:
    if not path.exists():
        return {}, "Not available yet"
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        return {}, f"YAML error: {exc}"
    except OSError as exc:
        return {}, f"Could not read file: {exc}"
    if not isinstance(data, dict):
        return {}, "Invalid YAML structure"
    return data, None


def read_config(root: Path = ROOT) -> dict:
    config_path = root / "config.yaml"
    config, error = _safe_load_yaml(config_path)
    return {
        "path": config_path,
        "exists": config_path.exists(),
        "data": config,
        "error": error,
    }


def resolve_runtime_paths(root: Path = ROOT) -> dict[str, Path]:
    config_info = read_config(root)
    cfg = config_info["data"]
    paths_cfg = cfg.get("paths", {}) if isinstance(cfg, dict) else {}
    interaction_cfg = cfg.get("interaction", {}) if isinstance(cfg, dict) else {}

    tasks_rel = paths_cfg.get("tasks", "workspace/tasks.md")
    memory_rel = paths_cfg.get("memory_dir", "workspace/memory")
    logs_rel = paths_cfg.get("logs_dir", "workspace/logs")
    inbox_rel = interaction_cfg.get("inbox_path", "workspace/inbox.md")
    outbox_rel = interaction_cfg.get("outbox_path", "workspace/outbox.md")

    return {
        "tasks": root / tasks_rel,
        "memory_dir": root / memory_rel,
        "logs_dir": root / logs_rel,
        "log_file": (root / logs_rel) / "agent.log",
        "inbox": root / inbox_rel,
        "outbox": root / outbox_rel,
    }


def _parse_message_file(path: Path) -> dict:
    if not path.exists():
        return {
            "path": path,
            "exists": False,
            "messages": [],
            "error": "Not available yet",
            "warning": None,
            "raw": "",
        }

    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        return {
            "path": path,
            "exists": True,
            "messages": [],
            "error": f"Could not read file: {exc}",
            "warning": None,
            "raw": "",
        }

    blocks = _extract_blocks(raw)
    messages = []
    for block in blocks:
        parsed = _parse_block(block)
        if parsed is not None:
            messages.append(parsed)

    warning = None
    if len(blocks) != len(messages):
        warning = "Some message blocks could not be parsed. Showing parsed messages only."

    return {
        "path": path,
        "exists": True,
        "messages": messages,
        "error": None,
        "warning": warning,
        "raw": raw,
    }


def read_inbox_outbox(root: Path = ROOT) -> dict:
    paths = resolve_runtime_paths(root)
    inbox = _parse_message_file(paths["inbox"])
    outbox = _parse_message_file(paths["outbox"])

    pending = sum(1 for m in inbox["messages"] if m.status == "pending")
    processed = sum(1 for m in inbox["messages"] if m.status == "processed")

    return {
        "inbox": inbox,
        "outbox": outbox,
        "counts": {
            "inbox_pending": pending,
            "inbox_processed": processed,
            "outbox_total": len(outbox["messages"]),
        },
    }


def read_tasks(root: Path = ROOT) -> dict:
    tasks_path = resolve_runtime_paths(root)["tasks"]
    if not tasks_path.exists():
        return {
            "path": tasks_path,
            "exists": False,
            "pending": [],
            "completed": [],
            "other": [],
            "raw": "",
            "error": "Not available yet",
        }

    try:
        raw = tasks_path.read_text(encoding="utf-8")
    except OSError as exc:
        return {
            "path": tasks_path,
            "exists": True,
            "pending": [],
            "completed": [],
            "other": [],
            "raw": "",
            "error": f"Could not read file: {exc}",
        }

    pending: list[str] = []
    completed: list[str] = []
    other: list[str] = []
    for line in raw.splitlines():
        stripped = line.strip()
        if stripped.startswith("- [ ] "):
            pending.append(stripped[6:])
        elif stripped.lower().startswith("- [x] "):
            completed.append(stripped[6:])
        elif stripped:
            other.append(stripped)

    return {
        "path": tasks_path,
        "exists": True,
        "pending": pending,
        "completed": completed,
        "other": other,
        "raw": raw,
        "error": None,
        "counts": {
            "pending": len(pending),
            "completed": len(completed),
            "other": len(other),
        },
    }


def read_logs(root: Path = ROOT, tail_lines: int = 100, text_filter: str = "") -> dict:
    log_path = resolve_runtime_paths(root)["log_file"]
    if not log_path.exists():
        return {
            "path": log_path,
            "exists": False,
            "lines": [],
            "error": "Not available yet",
        }

    try:
        lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError as exc:
        return {
            "path": log_path,
            "exists": True,
            "lines": [],
            "error": f"Could not read file: {exc}",
        }

    selected = lines[-tail_lines:] if tail_lines > 0 else lines
    if text_filter:
        needle = text_filter.lower()
        selected = [line for line in selected if needle in line.lower()]

    return {
        "path": log_path,
        "exists": True,
        "lines": selected,
        "error": None,
    }


def read_memory_index(root: Path = ROOT) -> dict:
    memory_dir = resolve_runtime_paths(root)["memory_dir"]
    topics_dir = memory_dir / "topics"

    topics: list[str] = []
    if topics_dir.exists() and topics_dir.is_dir():
        topics = sorted(p.name for p in topics_dir.iterdir() if p.is_dir())

    legacy_files = []
    if memory_dir.exists() and memory_dir.is_dir():
        legacy_files = sorted(str(p.relative_to(memory_dir)) for p in memory_dir.glob("*.md") if p.is_file())

    return {
        "memory_dir": memory_dir,
        "topics_dir": topics_dir,
        "topics": topics,
        "legacy_files": legacy_files,
        "exists": memory_dir.exists(),
    }


def read_memory_topic(root: Path = ROOT, topic: str | None = None) -> dict:
    index = read_memory_index(root)
    topics_dir: Path = index["topics_dir"]

    if not topic:
        return {
            "topic": None,
            "files": [],
            "error": "Not available yet",
        }

    topic_dir = topics_dir / topic
    if not topic_dir.exists() or not topic_dir.is_dir():
        return {
            "topic": topic,
            "files": [],
            "error": "Not available yet",
        }

    files = []
    for file_path in sorted(topic_dir.glob("*.md")):
        try:
            content = file_path.read_text(encoding="utf-8")
        except OSError as exc:
            content = f"Could not read file: {exc}"
        files.append({"name": file_path.name, "content": content})

    return {
        "topic": topic,
        "files": files,
        "error": None,
    }


def read_legacy_memory_file(root: Path = ROOT, relative_name: str = "") -> dict:
    memory_dir = resolve_runtime_paths(root)["memory_dir"]
    target = memory_dir / relative_name
    if not relative_name or not target.exists() or not target.is_file():
        return {"file": relative_name, "content": "", "error": "Not available yet"}

    try:
        content = target.read_text(encoding="utf-8")
    except OSError as exc:
        return {"file": relative_name, "content": "", "error": f"Could not read file: {exc}"}

    return {"file": relative_name, "content": content, "error": None}


def read_runtime_snapshot(root: Path = ROOT) -> dict:
    config_info = read_config(root)
    config = config_info["data"]
    model_cfg = config.get("model", {}) if isinstance(config, dict) else {}

    io_info = read_inbox_outbox(root)
    tasks_info = read_tasks(root)
    logs_info = read_logs(root, tail_lines=200)

    last_tick = "Not available yet"
    if logs_info["lines"]:
        last_tick = logs_info["lines"][-1]

    return {
        "model_provider": model_cfg.get("provider", "Unknown"),
        "model_name": model_cfg.get("model", "Unknown"),
        "base_url": model_cfg.get("base_url", "Unknown"),
        "last_tick_line": last_tick,
        "counts": {
            "inbox_pending": io_info["counts"]["inbox_pending"],
            "inbox_processed": io_info["counts"]["inbox_processed"],
            "outbox_total": io_info["counts"]["outbox_total"],
            "tasks_pending": tasks_info.get("counts", {}).get("pending", 0),
            "tasks_completed": tasks_info.get("counts", {}).get("completed", 0),
        },
        "errors": {
            "config": config_info["error"],
            "inbox": io_info["inbox"]["error"],
            "outbox": io_info["outbox"]["error"],
            "tasks": tasks_info["error"],
            "logs": logs_info["error"],
        },
    }

from __future__ import annotations

from pathlib import Path


class TaskManager:
    def __init__(self, tasks_path: Path) -> None:
        self.tasks_path = tasks_path
        self.tasks_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.tasks_path.exists():
            self.tasks_path.write_text("- [ ] tarefa inicial\n", encoding="utf-8")

    def _load_lines(self) -> list[str]:
        return self.tasks_path.read_text(encoding="utf-8").splitlines()

    def get_pending_tasks(self, limit: int = 3) -> list[str]:
        pending: list[str] = []
        for line in self._load_lines():
            stripped = line.strip()
            if stripped.startswith("- [ ] "):
                pending.append(stripped[6:])
            if len(pending) >= limit:
                break
        return pending

    def mark_done(self, task: str, result: str = "") -> None:
        updated: list[str] = []
        marked = False
        for line in self._load_lines():
            stripped = line.strip()
            if not marked and stripped == f"- [ ] {task}":
                suffix = f" — {result}" if result else ""
                updated.append(f"- [x] {task}{suffix}")
                marked = True
            else:
                updated.append(line)
        self.tasks_path.write_text("\n".join(updated) + "\n", encoding="utf-8")

    def add_task(self, task: str) -> bool:
        normalized = task.strip()
        if not normalized:
            return False
        for line in self._load_lines():
            stripped = line.strip()
            if stripped == f"- [ ] {normalized}" or stripped.startswith(f"- [x] {normalized}"):
                return False
        with self.tasks_path.open("a", encoding="utf-8") as file:
            file.write(f"- [ ] {normalized}\n")
        return True

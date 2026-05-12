from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PlannedAction:
    task: str
    reason: str


class Planner:
    def plan_for_task(self, task: str) -> PlannedAction:
        return PlannedAction(task=task, reason="Execute pending task from task queue")

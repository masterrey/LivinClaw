from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PlannedAction:
    task: str
    reason: str


class Planner:
    def plan_for_task(self, task: str, context_prompt: str = "") -> PlannedAction:
        if context_prompt.strip():
            reason = "Execute pending task from queue using sparse topic-filtered routed memory context"
        else:
            reason = "Execute pending task from task queue"
        return PlannedAction(task=task, reason=reason)

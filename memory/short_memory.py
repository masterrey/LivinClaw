from __future__ import annotations

from collections import deque


class ShortMemory:
    def __init__(self) -> None:
        self.summary = "Estado inicial"
        self.actions: deque[str] = deque(maxlen=20)
        self.observations: deque[str] = deque(maxlen=20)
        self.open_intentions: list[str] = []
        self.current_state: dict[str, str] = {"mode": "idle"}

    def add_action(self, action: str) -> None:
        self.actions.append(action)

    def add_observation(self, observation: str) -> None:
        self.observations.append(observation)

    def summarize(self) -> None:
        recent_actions = list(self.actions)[-3:]
        recent_obs = list(self.observations)[-3:]
        self.summary = (
            f"Ações recentes: {recent_actions} | "
            f"Observações recentes: {recent_obs} | "
            f"Intenções abertas: {self.open_intentions[:3]}"
        )

    def export(self) -> dict:
        return {
            "summary": self.summary,
            "actions": list(self.actions),
            "observations": list(self.observations),
            "open_intentions": self.open_intentions[:10],
            "current_state": self.current_state,
        }

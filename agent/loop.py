from __future__ import annotations

import logging
import time


class AgentLoop:
    def __init__(self, agent, tick_minutes: int = 10) -> None:
        self.agent = agent
        self.tick_minutes = tick_minutes
        self.logger = logging.getLogger(__name__)

    def tick(self) -> None:
        self.logger.info("Starting tick")
        self.agent.tick()
        self.logger.info("Tick finished")

    def run_forever(self) -> None:
        while True:
            self.tick()
            time.sleep(self.tick_minutes * 60)

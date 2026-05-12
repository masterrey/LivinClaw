from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import yaml

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from agent.alive_agent import AliveAgent
from agent.loop import AgentLoop


def load_config(config_path: Path) -> dict:
    with config_path.open("r", encoding="utf-8") as file:
        return yaml.safe_load(file)


def setup_logging(logs_dir: Path) -> None:
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_file = logs_dir / "agent.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[logging.FileHandler(log_file, encoding="utf-8"), logging.StreamHandler(sys.stdout)],
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="MiniClaw Alive")
    parser.add_argument("--config", default="config.yaml", help="Path to config YAML")
    parser.add_argument("--once", action="store_true", help="Run a single scheduled tick and exit")
    parser.add_argument("--interactive", action="store_true", help="Run a single interactive tick and exit")
    args = parser.parse_args()

    root = Path.cwd()
    config = load_config(root / args.config)
    setup_logging(root / config["paths"]["logs_dir"])

    agent = AliveAgent(config=config, root_dir=root)
    loop = AgentLoop(agent=agent, tick_minutes=config["agent"]["tick_minutes"])

    if args.once:
        loop.tick()
        return

    if args.interactive:
        loop.tick(reason="interactive")
        return

    loop.run_forever()


if __name__ == "__main__":
    main()

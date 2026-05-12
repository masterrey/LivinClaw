from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from guardian.json_repair import JsonRepair
from guardian.prompt_compressor import PromptCompressor
from guardian.token_estimator import TokenEstimator


@dataclass
class GuardianReport:
    ok: bool
    reason: str
    action: str
    repaired_prompt: str | None = None


class GuardianLayer:
    def __init__(self, config: dict) -> None:
        self.max_guardian_tokens = int(config.get("max_guardian_tokens", 3000))
        self.token_estimator = TokenEstimator()
        self.prompt_compressor = PromptCompressor()
        self.json_repair = JsonRepair()

    def check_prompt(self, prompt: str, main_context_limit: int, safe_context_ratio: float) -> GuardianReport:
        tokens = self.token_estimator.estimate(prompt)
        safe_limit = int(main_context_limit * safe_context_ratio)

        if tokens <= min(self.max_guardian_tokens, safe_limit):
            return GuardianReport(ok=True, reason="Prompt within safe limits", action="none")

        target = min(self.max_guardian_tokens, safe_limit)
        repaired = self.prompt_compressor.compress(prompt, target_tokens=target)
        return GuardianReport(
            ok=True,
            reason=f"Prompt compressed from ~{tokens} tokens to target ~{target}",
            action="compress",
            repaired_prompt=repaired,
        )

    def validate_json(self, payload: str) -> tuple[bool, object | None, GuardianReport]:
        ok, parsed = self.json_repair.repair(payload)
        if ok:
            return True, parsed, GuardianReport(ok=True, reason="JSON valid/repaired", action="repair_json")
        return False, None, GuardianReport(ok=False, reason="Invalid JSON", action="retry")

    def run_with_recovery(self, call: Callable[[], str], retries: int = 2) -> tuple[bool, str]:
        for attempt in range(retries + 1):
            response = call()
            if response and response.strip():
                return True, response
            if attempt == retries:
                return False, ""
        return False, ""

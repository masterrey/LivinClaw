from __future__ import annotations

# guardian/guardian.py
# Guardian lightweight homeostasis layer.
# Extended to inspect cognitive budget usage and trigger mitigations when
# loaded-topic count, estimated prompt size, or budget usage exceed limits.

import logging
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


MIN_LOADED_TOPICS = 3  # floor for loaded topic branch limits


class GuardianLayer:
    def __init__(self, config: dict) -> None:
        self.max_guardian_tokens = int(config.get("max_guardian_tokens", 3000))
        self.token_estimator = TokenEstimator()
        self.prompt_compressor = PromptCompressor()
        self.json_repair = JsonRepair()
        self.logger = logging.getLogger(__name__)

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

    def check_cognitive_budget(self, budget_status: dict, loaded_topic_count: int) -> GuardianReport:
        """Inspect cognitive budget usage and return a report with recommended action.

        Triggers:
        - ``compress`` when token usage exceeds 85 % of the per-tick budget.
        - ``prune_branches`` when more than ``max_loaded_topics`` branches are loaded.
        - ``none`` when everything is within limits.
        """
        max_tokens = budget_status.get("max_tokens_per_tick", 12000)
        used_tokens = budget_status.get("tokens_this_tick", 0)
        token_ratio = used_tokens / max_tokens if max_tokens else 0.0

        if token_ratio > 0.85:
            self.logger.warning(
                "Guardian: token budget at %.0f%% (%d/%d) — recommending prompt compression",
                token_ratio * 100,
                used_tokens,
                max_tokens,
            )
            return GuardianReport(
                ok=False,
                reason=f"Token usage at {token_ratio * 100:.0f}% of budget",
                action="compress",
            )

        max_topics = budget_status.get("max_loaded_topics", MIN_LOADED_TOPICS)
        # Guard against a configured limit smaller than the absolute minimum
        effective_limit = max(MIN_LOADED_TOPICS, max_topics)
        if loaded_topic_count > effective_limit:
            self.logger.warning(
                "Guardian: %d topic branches loaded (max %d) — recommending branch pruning",
                loaded_topic_count,
                max_topics,
            )
            return GuardianReport(
                ok=False,
                reason=f"{loaded_topic_count} branches loaded, exceeds limit {max_topics}",
                action="prune_branches",
            )

        return GuardianReport(ok=True, reason="Cognitive budget within limits", action="none")

    def validate_json(self, payload: str) -> tuple[bool, object | None, GuardianReport]:
        ok, parsed = self.json_repair.repair(payload)
        if ok:
            return True, parsed, GuardianReport(ok=True, reason="JSON valid/repaired", action="repair_json")
        return False, None, GuardianReport(ok=False, reason="Invalid JSON", action="retry")

    def check_interaction_queue(
        self,
        pending_count: int,
        max_queue_size: int,
        payload_integrity_ok: bool,
    ) -> GuardianReport:
        if not payload_integrity_ok:
            return GuardianReport(
                ok=False,
                reason="Malformed interaction payload detected in inbox",
                action="sanitize_payload",
            )
        if pending_count > max_queue_size:
            return GuardianReport(
                ok=False,
                reason=f"Interaction queue overflow risk ({pending_count}/{max_queue_size})",
                action="queue_overflow",
            )
        return GuardianReport(ok=True, reason="Interaction queue within limits", action="none")

    def run_with_recovery(self, call: Callable[[], str], retries: int = 2) -> tuple[bool, str]:
        for attempt in range(retries + 1):
            response = call()
            if response and response.strip():
                return True, response
            if attempt == retries:
                return False, ""
        return False, ""

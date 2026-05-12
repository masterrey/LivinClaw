from __future__ import annotations

import logging
from datetime import datetime, UTC


class ReflectionEngine:
    def __init__(self, llm_client=None) -> None:
        self.llm_client = llm_client
        self.logger = logging.getLogger(__name__)

    def reflect(
        self,
        short_summary: str,
        recent_actions: list[str],
        recent_observations: list[str],
        routed_context: str = "",
    ) -> str:
        prompt = (
            "Analise as últimas ações e gere uma reflexão curta em português com: "
            "aprendizado, risco e próximo foco.\n"
            f"Resumo: {short_summary}\n"
            f"Ações: {recent_actions[-5:]}\n"
            f"Observações: {recent_observations[-5:]}"
        )
        if routed_context.strip():
            prompt += f"\nContexto roteado relevante:\n{routed_context}"
        if self.llm_client is not None:
            try:
                return self.llm_client.chat(
                    [
                        {"role": "system", "content": "Você é um motor de reflexão operacional."},
                        {"role": "user", "content": prompt},
                    ]
                )
            except Exception as exc:
                self.logger.warning("Reflection LLM failed, using local fallback: %s", exc)

        now = datetime.now(UTC).isoformat()
        context_hint = " com contexto roteado" if routed_context.strip() else ""
        return (
            f"[{now}] Reflexão local{context_hint}: manter estabilidade, reduzir contexto e priorizar "
            "tarefas pendentes com registro objetivo de resultados."
        )

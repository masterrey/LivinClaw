from __future__ import annotations

from datetime import datetime, UTC


class ReflectionEngine:
    def __init__(self, llm_client=None) -> None:
        self.llm_client = llm_client

    def reflect(self, short_summary: str, recent_actions: list[str], recent_observations: list[str]) -> str:
        prompt = (
            "Analise as últimas ações e gere uma reflexão curta em português com: "
            "aprendizado, risco e próximo foco.\n"
            f"Resumo: {short_summary}\n"
            f"Ações: {recent_actions[-5:]}\n"
            f"Observações: {recent_observations[-5:]}"
        )
        if self.llm_client is not None:
            try:
                return self.llm_client.chat(
                    [
                        {"role": "system", "content": "Você é um motor de reflexão operacional."},
                        {"role": "user", "content": prompt},
                    ]
                )
            except Exception:
                pass

        now = datetime.now(UTC).isoformat()
        return (
            f"[{now}] Reflexão local: manter estabilidade, reduzir contexto e priorizar "
            "tarefas pendentes com registro objetivo de resultados."
        )

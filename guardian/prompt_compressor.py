from __future__ import annotations


class PromptCompressor:
    def compress(self, prompt: str, target_tokens: int) -> str:
        if not prompt:
            return prompt

        approx_chars = max(100, target_tokens * 4)
        if len(prompt) <= approx_chars:
            return prompt

        head_size = int(approx_chars * 0.6)
        tail_size = max(0, approx_chars - head_size - 30)
        tail = prompt[-tail_size:] if tail_size else ""
        return f"{prompt[:head_size]}\n\n[...PROMPT COMPACTADO...]\n\n{tail}"

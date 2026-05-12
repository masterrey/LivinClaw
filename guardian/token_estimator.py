from __future__ import annotations


class TokenEstimator:
    def __init__(self) -> None:
        try:
            import tiktoken  # type: ignore

            self._encoder = tiktoken.get_encoding("cl100k_base")
        except Exception:
            self._encoder = None

    def estimate(self, text: str) -> int:
        if not text:
            return 0
        if self._encoder is not None:
            return len(self._encoder.encode(text))
        return max(1, len(text) // 4)

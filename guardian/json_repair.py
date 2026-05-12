from __future__ import annotations

import json
import re
from typing import Any


class JsonRepair:
    @staticmethod
    def _strip_code_fences(content: str) -> str:
        cleaned = content.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?", "", cleaned).strip()
            cleaned = re.sub(r"```$", "", cleaned).strip()
        return cleaned

    def repair(self, content: str) -> tuple[bool, Any]:
        cleaned = self._strip_code_fences(content)

        try:
            return True, json.loads(cleaned)
        except json.JSONDecodeError:
            pass

        cleaned = re.sub(r",\s*([}\]])", r"\1", cleaned)
        cleaned = cleaned.replace("\n", " ")

        try:
            return True, json.loads(cleaned)
        except json.JSONDecodeError:
            return False, None

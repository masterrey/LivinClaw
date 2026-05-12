from __future__ import annotations

from pathlib import Path


class ToolRegistry:
    def __init__(self, long_memory) -> None:
        self.long_memory = long_memory
        self.tools = {
            "read_file": self.read_file,
            "write_file": self.write_file,
            "create_file": self.create_file,
            "write_memory": self.write_memory,
        }

    def list_tools(self) -> list[dict]:
        return [
            {
                "name": name,
                "description": description,
                "inputSchema": {"type": "object"},
            }
            for name, description in {
                "read_file": "Lê o conteúdo textual de um arquivo UTF-8 pelo caminho informado.",
                "write_file": "Sobrescreve um arquivo UTF-8 com o conteúdo fornecido.",
                "create_file": "Cria arquivo e diretórios pais, opcionalmente com conteúdo inicial.",
                "write_memory": "Grava entrada de memória persistente em long_term/reflections/decisions/facts.",
            }.items()
        ]

    def read_file(self, path: str) -> str:
        return Path(path).read_text(encoding="utf-8")

    def write_file(self, path: str, content: str) -> str:
        Path(path).write_text(content, encoding="utf-8")
        return "ok"

    def create_file(self, path: str, content: str = "") -> str:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return "ok"

    def write_memory(self, kind: str, content: str) -> str:
        if kind == "long_term":
            self.long_memory.append_long_term(content)
        elif kind == "reflection":
            self.long_memory.append_reflection(content)
        elif kind == "decision":
            self.long_memory.append_decision(content)
        elif kind == "fact":
            self.long_memory.append_fact(content)
        else:
            raise ValueError(f"Unknown memory kind: {kind}")
        return "ok"

# LivinClaw

MiniClaw Alive é um agente autônomo contínuo em Python com:

- loop vivo por ticks (`while True`)
- memória curta em RAM (limitada)
- memória longa persistente em Markdown
- camada Guardian leve para homeostase operacional
- arquitetura modular preparada para evolução futura com MCP

## Estrutura

- `alive_agent/main.py`
- `agent/`
- `guardian/`
- `memory/`
- `tasks/`
- `tools/`
- `llm/`
- `workspace/`

## Dependências

- `requests`
- `pyyaml`
- opcional: `tiktoken`

## Execução

```bash
python /home/runner/work/LivinClaw/LivinClaw/alive_agent/main.py --once
```

Para execução contínua:

```bash
python /home/runner/work/LivinClaw/LivinClaw/alive_agent/main.py
```

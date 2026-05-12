# LivinClaw

MiniClaw Alive é um agente autônomo contínuo em Python com:

- loop vivo por ticks (`while True`)
- memória curta em RAM com pontuação de importância e poda automática
- memória longa persistente em Markdown com árvore de tópicos
- carregamento esparso de memória inspirado em Mixture-of-Experts (MoE)
- sistema de orçamento cognitivo para limitar tokens, reflexões e compactações
- camada Guardian leve para homeostase operacional com inspeção de orçamento
- proteções anti-degeneração (deduplicação de reflexões, detecção de loops)
- arquitetura modular preparada para evolução futura com MCP

## Arquitetura de Memória

### Memória de Trabalho (RAM)

A memória curta (`ShortMemory`) rastreia ações e observações recentes em
janelas com tamanho máximo de 20 itens cada. As entradas agora têm metadados:

```json
{
  "text": "...",
  "importance": 0.82,
  "timestamp": "...",
  "type": "observation"
}
```

Entradas de baixa importância são descartadas primeiro quando o limite é
atingido. A importância decai a cada tick (`importance_decay = 0.95`).

### Árvore de Tópicos (Long-Term Memory)

A memória longa usa uma hierarquia de diretórios em `workspace/memory/topics/`:

```
workspace/memory/
  index.md               ← índice legível por humanos
  topics/
    architecture/        summary.md  decisions.md  facts.md
    mcp/                 summary.md  decisions.md  facts.md
    llm_runtime/         summary.md  failures.md   optimizations.md
    guardian/            summary.md  incidents.md
    user_preferences/    summary.md  facts.md
    reflections/         reflections.md
```

O índice (`index.md`) registra por tópico: descrição, caminho, tags,
importância e último acesso — tudo em Markdown legível.

### Carregamento Esparso de Memória (MoE)

O `MemoryRouter` analisa a tarefa atual e a memória de trabalho para pontuar
todos os tópicos e carregar **apenas os N mais relevantes** (padrão: 3).
Tópicos irrelevantes permanecem inativos.

Componentes da pontuação:
- **relevância semântica** — frequência de palavras-chave no texto da tarefa
- **bônus de recência** — tópicos acessados recentemente recebem impulso
- **importância** — peso armazenado no índice

> O roteador **nunca** carrega todos os tópicos ao mesmo tempo.

### Classificador de Tópicos

O `TopicClassifier` usa roteamento por palavras-chave para decidir em qual
branch um fragmento de memória deve ser salvo.  Por exemplo:

- `"Guardian repaired oversized prompt"` → `guardian/incidents.md`
- `"Unity MCP architecture decision"` → `mcp/decisions.md`

## Orçamento Cognitivo

O `CognitiveBudget` impõe limites configuráveis:

```yaml
cognitive_budget:
  max_tokens_per_tick: 12000
  max_loaded_topics: 3
  max_reflections_per_day: 20
  reflection_cooldown_ticks: 3
  max_compactions_per_hour: 2
```

## Montador de Contexto

O `ContextAssembler` constrói prompts compactos a partir de:

1. Memória de trabalho (20 % do orçamento)
2. Ramos de tópicos relevantes (50 % do orçamento)
3. Tarefa atual (15 % do orçamento)

O assembler **nunca** injeta toda a memória longa cegamente.

## Sistemas Anti-Degeneração

O `AntiDegeneration` previne:

- **loops de reflexão** — detecta similaridade de Jaccard ≥ 0,75 com reflexões anteriores
- **tarefas duplicadas** — impede reenvio de tarefas idênticas à fila
- **baixa entropia** — suprime reflexões trivialmente repetitivas

## Cooldowns de Reflexão

Reflexões só ocorrem quando:

1. Nenhuma tarefa pendente está na fila (tick ocioso)
2. `reflection_cooldown_ticks` ticks passaram desde a última reflexão
3. O limite diário `max_reflections_per_day` não foi atingido

## Integração com Guardian

O Guardian agora inspeciona:

- tamanho estimado do prompt
- uso do orçamento de tokens
- número de ramos de memória carregados

e recomenda `compress` ou `prune_branches` quando os limites são excedidos.

## Compactação por Tópico

A compactação agora ocorre por tópico individualmente. Apenas os arquivos do
tópico ativo são compactados; os demais branches permanecem intactos.

## Estrutura

- `alive_agent/main.py`
- `agent/` — `alive_agent.py`, `cognitive_budget.py`, `anti_degeneration.py`, `context_assembler.py`
- `guardian/`
- `memory/` — `short_memory.py`, `long_memory.py`, `memory_indexer.py`, `memory_router.py`, `topic_classifier.py`, `memory_compactor.py`
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
python alive_agent/main.py --once
```

Para execução contínua:

```bash
python alive_agent/main.py
```

## Testes

```bash
python -m unittest discover -s tests -q
```

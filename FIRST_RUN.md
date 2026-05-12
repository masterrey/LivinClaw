# FIRST_RUN (Windows)

## 1) Requirements

- Windows 10/11
- Python 3.10+ in PATH
- LM Studio installed
- A loaded chat model in LM Studio

## 2) Run setup.bat

From the repository root, double-click `setup.bat` or run in CMD/PowerShell:

```bat
setup.bat
```

This will:
- create `.venv` (if missing)
- install dependencies locally
- create `config.yaml` from `config.example.yaml` (only if `config.yaml` is missing)
- create safe workspace files/folders without overwriting existing data

## 3) Start LM Studio

- Open LM Studio
- Load your model (for example `openai/gpt-oss-20b`)
- Enable local server mode (OpenAI-compatible API)
- Keep `base_url` as `http://127.0.0.1:1234/v1`

## 4) Check the model endpoint

In a terminal:

```bat
curl http://127.0.0.1:1234/v1/models
```

You should receive JSON with one or more models.

## 5) Run one tick

```bat
run_once.bat
```

## 6) Run continuous mode

```bat
run_alive.bat
```

Stop with `Ctrl+C` in the terminal window.

## 7) First local interaction

`workspace/inbox.md` and `workspace/outbox.md` are **structured storage files** that
the agent runtime reads and writes via a safe serialization format. Do not edit them
manually — any free-form text you add can break the block format and cause messages
to be silently skipped.

Recommended first interaction:

```bat
interact.bat "@ask Tudo certo?"
```

This keeps the architecture intact:

- console is the local interaction surface
- Inbox/Outbox remain the persistent storage
- the response still comes from an interactive tick

For a continuous terminal loop:

```bat
chat.bat
```

If you want the manual step-by-step flow, use `send_message.bat` to append messages safely:

```bat
send_message.bat "@task Create a short summary of the current agent architecture"
send_message.bat "@ask What is your current status?"
send_message.bat "@note Prefer short answers during first-run tests"
```

Then run one interactive tick to process pending inbox messages:

```bat
run_interactive.bat
python scripts\show_latest_outbox.py
```

The workspace remains observable for debugging and inspection:

| File / Folder | Purpose |
|---|---|
| `workspace/inbox.md` | Observable: pending and processed messages |
| `workspace/outbox.md` | Observable: agent responses |
| `workspace/tasks.md` | Observable: task queue |
| `workspace/logs/agent.log` | Runtime log |
| `workspace/memory/` | Persistent memory branches |

## 8) Run tests

```bat
run_tests.bat
```

## Optional: Visual Dashboard

Install optional UI dependency:

```bat
setup_ui.bat
```

Run local dashboard:

```bat
run_dashboard.bat
```

Use the Chat tab to send a message and run an interactive tick.
Use Runtime/Tasks/Memory/Inbox-Outbox/Logs tabs to observe the alive agent state.

The dashboard is local-only and does not bypass runtime flow.

## 9) Troubleshooting

- **Python not found**: reinstall Python and enable PATH integration.
- **LM Studio connection errors**: confirm server is running on `127.0.0.1:1234`.
- **Wrong model name**: update `model.model` in `config.yaml`.
- **Missing .venv error in run scripts**: run `setup.bat` first.
- **No response shown yet**: verify inbox has a pending message (`send_message.bat`) and run `interact.bat`, `chat.bat`, or `run_interactive.bat`.
- **Do not edit inbox.md manually**: use `send_message.bat` to preserve the structured block format.

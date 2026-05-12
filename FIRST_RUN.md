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

## 7) Send messages and run an interactive tick

`workspace/inbox.md` and `workspace/outbox.md` are **structured storage files** that
the agent runtime reads and writes via a safe serialization format. Do not edit them
manually — any free-form text you add can break the block format and cause messages
to be silently skipped.

Use `send_message.bat` to append messages safely:

```bat
send_message.bat "@task Create a short summary of the current agent architecture"
send_message.bat "@ask What is your current status?"
send_message.bat "@note Prefer short answers during first-run tests"
```

Then run one interactive tick to process pending inbox messages:

```bat
run_interactive.bat
```

Or use `interact.bat` to send a message and run the tick in one step:

```bat
interact.bat "@task Create a short summary of the current agent architecture"
```

After the tick completes, inspect the workspace to see results:

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

## 9) Troubleshooting

- **Python not found**: reinstall Python and enable PATH integration.
- **LM Studio connection errors**: confirm server is running on `127.0.0.1:1234`.
- **Wrong model name**: update `model.model` in `config.yaml`.
- **Missing .venv error in run scripts**: run `setup.bat` first.
- **No output in outbox**: verify inbox has a pending message (`send_message.bat`) and run `run_interactive.bat` or `run_once.bat`.
- **Do not edit inbox.md manually**: use `send_message.bat` to preserve the structured block format.

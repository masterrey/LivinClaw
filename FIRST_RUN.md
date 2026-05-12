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

## 7) Test inbox/outbox interaction

Recommended (safe serialization via existing `InteractionManager`):

```bat
.venv\Scripts\python.exe scripts\send_message.py "@task Create a short summary of the current agent architecture"
```

Then run one tick:

```bat
run_once.bat
```

Inspect:
- `workspace/inbox.md`
- `workspace/outbox.md`
- `workspace/tasks.md`
- `workspace/logs/agent.log`
- `workspace/memory/`

Manual fallback (if needed): edit `workspace/inbox.md` carefully in the existing message block format.

## 8) Run tests

```bat
run_tests.bat
```

## 9) Troubleshooting

- **Python not found**: reinstall Python and enable PATH integration.
- **LM Studio connection errors**: confirm server is running on `127.0.0.1:1234`.
- **Wrong model name**: update `model.model` in `config.yaml`.
- **Missing .venv error in run scripts**: run `setup.bat` first.
- **No output in outbox**: verify inbox has pending message and run `run_once.bat`.

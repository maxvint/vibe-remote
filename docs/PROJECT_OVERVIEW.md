# Project Overview

Vibe Remote lets you control local coding agents from Slack. It runs on your machine, routes Slack messages to an agent CLI, and streams results back without sending your codebase off-device.

## How It Works (High Level)

1. You send a message in Slack.
2. Vibe Remote routes it to the configured agent.
3. The agent reads/writes local files and streams output.
4. You review or continue the thread in Slack.

## Repository Layout

- `main.py`: Entry point wiring `config.V2Config` into the controller.
- `core/`: Orchestration and handlers (including `core/handlers/`).
- `modules/agents/`: Agent backends and registry.
- `modules/im/`: IM transports (Slack-first abstraction).
- `config/`: Defaults and validation (`config/v2_config.py`).
- `ui/`: React + Vite + TypeScript frontend.
- `docs/`: User and developer documentation.
- `tests/`: Test files (pytest style when present).

## Common Commands

- Install: `uv tool install vibe`
- Run: `vibe`
- Status: `vibe status`
- Stop: `vibe stop`
- Restart: `vibe`

## UI Development

1. Edit files in `ui/src/`.
2. Build assets with `npm run build` (from `ui/`).
3. For local preview, install editable: `uv tool install --force --editable .`
4. Restart `vibe` to load the new assets.

## Configuration Notes

- Agent routing is configured via Slack Agent Settings.
- OpenCode: `OPENCODE_ENABLED=true` and `OPENCODE_CLI_PATH`.
- Codex: `CODEX_ENABLED=true` and `CODEX_CLI_PATH`.
- Default work dir: `_tmp/`.

## Runtime Data

- Logs: `~/.vibe_remote/logs/vibe_remote.log`
- State: `~/.vibe_remote/state/`

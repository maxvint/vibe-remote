# Local Development Guide

A quick reference for developing Vibe Remote locally.

## Prerequisites

- Python 3.10+
- Node.js 18+ (for UI development)
- [uv](https://docs.astral.sh/uv/) (recommended) or pip
- At least one coding agent: Claude Code, OpenCode, or Codex

## Project Structure

```
vibe-remote/
├── main.py              # Service entry point
├── vibe/                # CLI module
├── config/              # Configuration and validation
├── core/                # Core orchestration
│   └── handlers/        # Message and event handlers
├── modules/
│   ├── agents/          # Agent backends (Claude, OpenCode, Codex)
│   └── im/              # IM transports (Slack)
└── ui/                  # React frontend (Vite + Tailwind)
```

## Quick Start

### 1. Clone and Setup

```bash
git clone https://github.com/cyhhao/vibe-remote.git
cd vibe-remote

# Create virtual environment
uv venv
source .venv/bin/activate  # or `.venv\Scripts\activate` on Windows

# Install dependencies
uv pip install -e .
```

### 2. Run Backend (Development)

```bash
# Direct execution
python main.py

# Or via CLI
vibe
```

### 3. Run UI (Development)

```bash
cd ui
bun install   # or npm install
bun dev       # or npm run dev
```

The UI dev server runs at `http://localhost:5173` with hot reload.

## Common Commands

| Command | Description |
|---------|-------------|
| `vibe` | Start the service |
| `vibe status` | Check if running |
| `vibe stop` | Stop the service |
| `vibe doctor` | Diagnose issues |
| `python main.py` | Run backend directly |
| `cd ui && bun dev` | Start UI dev server |
| `cd ui && bun build` | Build UI for production |

## Configuration

- **Config files**: `~/.vibe_remote/`
- **Logs**: `~/.vibe_remote/logs/vibe_remote.log`
- **State**: `~/.vibe_remote/state/`
- **Default working dir**: `_tmp/`

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `OPENCODE_ENABLED` | Enable OpenCode agent | `false` |
| `OPENCODE_CLI_PATH` | Path to OpenCode CLI | - |
| `CODEX_ENABLED` | Enable Codex agent | `true` |
| `CODEX_CLI_PATH` | Path to Codex CLI | - |

## Development Tips

1. **Logs** - Watch logs in real-time:
   ```bash
   tail -f ~/.vibe_remote/logs/vibe_remote.log
   ```

2. **UI + Backend** - Run both for full development:
   - Terminal 1: `python main.py`
   - Terminal 2: `cd ui && bun dev`

3. **Testing** - Manual E2E check:
   - Start bot: `vibe`
   - In Slack: `@Vibe Remote /start`

## Code Style

- PEP 8, 4-space indentation
- `snake_case` for functions, `PascalCase` for classes
- Type hints for public functions
- Use Black/Ruff if desired, keep diffs focused

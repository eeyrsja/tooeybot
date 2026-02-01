# Tooeybot Runtime

Python runtime for the Tooeybot agent.

## Requirements
- Python 3.12+
- Linux environment (Ubuntu VM)

## Installation

```bash
cd /path/to/tooeybot/runtime
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Configuration

Copy `config.example.yaml` to `config.yaml` and adjust settings:
- LLM provider and endpoint
- Agent home directory
- Logging preferences

## Running

```bash
# Single tick (process one task)
python -m tooeybot tick

# Continuous mode (run until stopped)
python -m tooeybot run

# Health check
python -m tooeybot health
```

## Development

```bash
# Run tests
pytest

# Type checking
mypy tooeybot/
```

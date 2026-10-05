#!/usr/bin/env bash

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
PYTHON="$PROJECT_DIR/.venv/bin/python"

if [[ ! -x "$PYTHON" ]]; then
    printf 'Project virtual environment is missing. Set it up before launching the app.\n' >&2
    exit 1
fi

exec "$PYTHON" "$PROJECT_DIR/app.py" "$@"

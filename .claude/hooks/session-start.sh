#!/bin/bash
# Bill Pop — SessionStart hook for Claude Code on the web.
# Installs Python deps into a project venv so tests, linters, and Alembic work.
set -euo pipefail

# Only run in the remote (web) environment; local users manage their own venv.
if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

cd "$CLAUDE_PROJECT_DIR"

# Create the venv once; container state is cached after the hook completes.
if [ ! -d .venv ]; then
  python3 -m venv .venv
fi

# Idempotent: pip install is a no-op when everything is already satisfied.
# requirements-dev.txt pulls in runtime deps plus the linter, test runner, and
# httpx (needed by fastapi.testclient.TestClient).
./.venv/bin/pip install --quiet --upgrade pip
./.venv/bin/pip install --quiet -r requirements-dev.txt

# Activate the venv for the rest of the session so `python`, `pytest`, `ruff`,
# and `alembic` resolve to the project environment.
echo "export VIRTUAL_ENV=\"$CLAUDE_PROJECT_DIR/.venv\"" >> "$CLAUDE_ENV_FILE"
echo "export PATH=\"$CLAUDE_PROJECT_DIR/.venv/bin:\$PATH\"" >> "$CLAUDE_ENV_FILE"

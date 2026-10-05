#!/usr/bin/env bash
# One-time setup for the isolated browser-automation sub-agent (browser-use).
#
# browser-use pins openai==2.x, which conflicts with the main app's openai>=3.x,
# so it lives in its OWN venv (.venv-browser) and is driven via subprocess
# (src/tandem/mac/browse_worker.py). After this, restart the backend and the
# `web_task` tool lights up.
set -euo pipefail
cd "$(dirname "$0")/.."

echo "① Creating .venv-browser (python 3.11)…"
uv venv .venv-browser --python 3.11

echo "② Installing browser-use (heavy — a minute or two)…"
uv pip install --python .venv-browser/bin/python 'browser-use>=0.13.0'

# browser-use 0.13 drives your system Google Chrome over CDP (find_chrome_executable),
# so no separate Chromium download is needed — just make sure Google Chrome is installed.
if [ ! -e "/Applications/Google Chrome.app" ]; then
  echo "⚠️  Google Chrome not found in /Applications — install it so web_task has a browser to drive."
fi

echo "✅ Browser sub-agent ready. Restart the backend to pick up the web_task tool."

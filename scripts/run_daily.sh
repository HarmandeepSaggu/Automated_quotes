#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ -x .venv/bin/python ]]; then
  .venv/bin/python main.py --yes
else
  python3 main.py --yes
fi

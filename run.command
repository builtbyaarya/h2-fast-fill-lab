#!/bin/bash
# Aarya Chiripal, AME 310 Engineering Thermodynamics I, Prof. Penkova, USC, Fall 2026.
# H2 Fast-Fill Lab, run.command: double-click launcher for macOS. It starts the app; it is not part of the model.
# First run: creates a private virtual environment and installs the pinned packages
# from requirements.txt. Later runs: just starts the app.
# The environment lives in ~/.venvs (outside any cloud-synced folder) so Google Drive
# or iCloud never tries to upload its ~20,000 files.
cd "$(dirname "$0")"
VENV="$HOME/.venvs/h2-fast-fill-lab"

pick_python() {
  for c in python3.13 python3.12 python3.11 python3.10 python3; do
    if command -v "$c" >/dev/null 2>&1; then
      if "$c" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null; then
        echo "$c"; return 0
      fi
    fi
  done
  return 1
}

if [ ! -x "$VENV/bin/python" ]; then
  PY=$(pick_python) || {
    echo "Python 3.10 or newer is needed. Install it from https://www.python.org/downloads/macos/ and run this file again."
    open "https://www.python.org/downloads/macos/"
    read -r -p "Press Return to close."
    exit 1
  }
  echo "Setting up the app for the first time with $($PY --version). This takes a minute or two."
  mkdir -p "$HOME/.venvs"
  "$PY" -m venv "$VENV" || { echo "Could not create the virtual environment."; read -r -p "Press Return to close."; exit 1; }
  "$VENV/bin/python" -m pip install --upgrade pip >/dev/null
  "$VENV/bin/python" -m pip install -r requirements.txt || { echo "Package install failed. Check the internet connection and run again."; read -r -p "Press Return to close."; exit 1; }
fi

echo "Starting H2 Fast-Fill Lab at http://localhost:8501 . Close this window to stop the app."
( sleep 4; open "http://localhost:8501" ) &
"$VENV/bin/python" -m streamlit run app.py --server.headless true --browser.gatherUsageStats false

#!/usr/bin/env bash
set -e

cd "$(dirname "$0")"

echo "============================================"
echo "  Alchequant - Starting..."
echo "  http://localhost:8501"
echo "============================================"

if command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN="python3"
elif command -v python >/dev/null 2>&1; then
  PYTHON_BIN="python"
else
  echo "[ERROR] Python was not found. Please install Python 3.10+ or activate your virtual environment."
  exit 1
fi

if ! "$PYTHON_BIN" -c "import streamlit" >/dev/null 2>&1; then
  echo "[ERROR] Streamlit is not installed in the current Python environment."
  echo "Run: $PYTHON_BIN -m pip install -r requirements.txt"
  exit 1
fi

"$PYTHON_BIN" -m streamlit run app.py --server.port 8501

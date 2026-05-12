#!/usr/bin/env bash
# Used by Finder / AppleScript launcher (no Terminal). Starts Streamlit if needed and opens the browser.

set -euo pipefail
BASE="$(cd "$(dirname "$0")" && pwd)"
URL="http://127.0.0.1:8501"
LOG="$HOME/Library/Logs/beverage_dashboard_streamlit.log"

if curl -sf "${URL}/" >/dev/null 2>&1; then
  open "$URL"
  exit 0
fi

if [[ ! -x "$BASE/.venv/bin/streamlit" ]]; then
  echo "Missing venv Streamlit under $BASE/.venv — run pip install there first." >&2
  exit 2
fi

cd "$BASE"
nohup .venv/bin/streamlit run app.py \
  --server.headless true \
  --server.address 127.0.0.1 \
  --server.port 8501 >>"$LOG" 2>&1 &
for _ in $(jot 40); do
  if curl -sf "${URL}/" >/dev/null 2>&1; then
    open "$URL"
    exit 0
  fi
  sleep 0.5
done
open "$URL"
exit 0

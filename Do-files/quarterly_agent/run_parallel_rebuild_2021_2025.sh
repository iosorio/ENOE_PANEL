#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
ACK_FILE="$REPO_ROOT/Do-files/quarterly_agent/state/locks/onedrive_paused.ok"

PYTHON_BIN="${PYTHON_BIN:-python3}"
STATA_BIN="${STATA_BIN:-stata-mp}"
WORKERS="${WORKERS:-3}"
PANEL_START_YEAR="${PANEL_START_YEAR:-2005}"
START_YEAR="${START_YEAR:-2021}"
START_QUARTER="${START_QUARTER:-1}"
END_YEAR="${END_YEAR:-2025}"
END_QUARTER="${END_QUARTER:-3}"

if [[ ! -f "$ACK_FILE" ]]; then
  echo "Blocked: OneDrive pause acknowledgement file not found."
  echo "1) Pause OneDrive manually."
  echo "2) Confirm pause:"
  echo "   touch \"$ACK_FILE\""
  exit 2
fi

exec "$PYTHON_BIN" "$SCRIPT_DIR/phase2_rebuild_range_parallel.py" \
  --repo-root "$REPO_ROOT" \
  --start-year "$START_YEAR" \
  --start-quarter "$START_QUARTER" \
  --end-year "$END_YEAR" \
  --end-quarter "$END_QUARTER" \
  --workers "$WORKERS" \
  --panel-start-year "$PANEL_START_YEAR" \
  --stata-bin "$STATA_BIN" \
  "$@"

#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

PYTHON_BIN="${PYTHON_BIN:-python3}"
STATA_BIN="${STATA_BIN:-stata-mp}"
PANEL_START_YEAR="${PANEL_START_YEAR:-2005}"
QC_ENGINE="${QC_ENGINE:-python-quarterly}"

usage() {
  cat <<'EOF'
Usage:
  bash Do-files/quarterly_agent/run_qc_only.sh 2025Q4 [extra flags]
  bash Do-files/quarterly_agent/run_qc_only.sh 2025 4 [extra flags]
  bash Do-files/quarterly_agent/run_qc_only.sh --year 2025 --quarter 4 [extra flags]

Environment overrides:
  PYTHON_BIN=python3
  STATA_BIN=stata-mp
  PANEL_START_YEAR=2005
  QC_ENGINE=python-quarterly

Examples:
  bash Do-files/quarterly_agent/run_qc_only.sh 2025Q4
  bash Do-files/quarterly_agent/run_qc_only.sh 2025 4 --dry-run
  QC_ENGINE=stata-sequential bash Do-files/quarterly_agent/run_qc_only.sh 2025Q4
EOF
}

has_flag() {
  local needle="$1"
  shift
  local arg
  for arg in "$@"; do
    if [[ "$arg" == "$needle" ]]; then
      return 0
    fi
  done
  return 1
}

YEAR=""
QUARTER=""
EXTRA_ARGS=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help)
      usage
      exit 0
      ;;
    --year)
      YEAR="${2:-}"
      shift 2
      ;;
    --quarter)
      QUARTER="${2:-}"
      shift 2
      ;;
    --*)
      EXTRA_ARGS+=("$1")
      if [[ $# -ge 2 && "${2:-}" != --* ]]; then
        EXTRA_ARGS+=("$2")
        shift 2
      else
        shift
      fi
      ;;
    *)
      if [[ -z "$YEAR" && "$1" =~ ^([0-9]{4})Q([1-4])$ ]]; then
        YEAR="${BASH_REMATCH[1]}"
        QUARTER="${BASH_REMATCH[2]}"
        shift
      elif [[ -z "$YEAR" && "$1" =~ ^[0-9]{4}$ && $# -ge 2 && "${2:-}" =~ ^[1-4]$ ]]; then
        YEAR="$1"
        QUARTER="$2"
        shift 2
      else
        EXTRA_ARGS+=("$1")
        shift
      fi
      ;;
  esac
done

if [[ -z "$YEAR" || -z "$QUARTER" ]]; then
  echo "ERROR: year and quarter are required." >&2
  usage >&2
  exit 2
fi

CMD=(
  "$PYTHON_BIN"
  "$SCRIPT_DIR/run_quarterly_agent.py"
  --repo-root "$REPO_ROOT"
  --target-year "$YEAR"
  --target-quarter "$QUARTER"
  --qc-only
)

if ! has_flag --panel-start-year "${EXTRA_ARGS[@]}"; then
  CMD+=(--panel-start-year "$PANEL_START_YEAR")
fi

if ! has_flag --stata-bin "${EXTRA_ARGS[@]}"; then
  CMD+=(--stata-bin "$STATA_BIN")
fi

if ! has_flag --qc-engine "${EXTRA_ARGS[@]}"; then
  CMD+=(--qc-engine "$QC_ENGINE")
fi

CMD+=("${EXTRA_ARGS[@]}")

exec "${CMD[@]}"

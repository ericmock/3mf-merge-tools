#!/usr/bin/env bash
set -euo pipefail

APP_NAME="3MF Merge Tools"
if [ "${INSTALL_DIR:-}" ]; then
    INSTALL_DIR="$INSTALL_DIR"
elif [ -f "$HOME/.local/share/3mf-merge-tools/scripts/review_duplicate_3mf_models.py" ]; then
    INSTALL_DIR="$HOME/.local/share/3mf-merge-tools"
else
    INSTALL_DIR="/Library/Application Support/3mf-merge-tools"
fi
REVIEW_SCRIPT="$INSTALL_DIR/scripts/review_duplicate_3mf_models.py"
PYTHON_BIN="${PYTHON:-python3}"

alert() {
    /usr/bin/osascript -e 'on run argv' \
        -e 'display dialog (item 1 of argv) buttons {"OK"} default button "OK" with title "3MF Merge Tools"' \
        -e 'end run' -- "$1" >/dev/null
}

notify() {
    /usr/bin/osascript -e 'on run argv' \
        -e 'display notification (item 1 of argv) with title "3MF Merge Tools"' \
        -e 'end run' -- "$1" >/dev/null
}

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
    alert "Python 3 is required but was not found. Install Python 3 and try again."
    exit 1
fi

if [ ! -f "$REVIEW_SCRIPT" ]; then
    alert "The duplicate review script was not found at:\n\n$REVIEW_SCRIPT\n\nRun the 3mf-merge-tools installer and try again."
    exit 1
fi

inputs=()
for item in "$@"; do
    case "$item" in
        *.3mf|*.3MF)
            if [ -f "$item" ]; then
                inputs+=("$item")
            fi
            ;;
    esac
done

if [ "${#inputs[@]}" -lt 1 ]; then
    alert "Select one or more .3mf files in Finder, then run this Quick Action again."
    exit 0
fi

first_dir=$(dirname "${inputs[0]}")
timestamp=$(date +%Y%m%d_%H%M%S)
report_path="$first_dir/duplicate_model_review_$timestamp.txt"

tmp_parent="${TMPDIR:-/tmp}"
tmp_parent="${tmp_parent%/}"
log_file=$(mktemp "$tmp_parent/3mf-duplicate-review-service.XXXXXX")

if {
    echo "Selected input files:"
    printf ' - %s\n' "${inputs[@]}"
    echo "Report file:"
    printf ' - %s\n' "$report_path"
    echo
    "$PYTHON_BIN" "$REVIEW_SCRIPT" --cross-file "${inputs[@]}"
} >"$report_path" 2>"$log_file"; then
    /usr/bin/open -R "$report_path" >/dev/null 2>&1 || true
    /usr/bin/open "$report_path" >/dev/null 2>&1 || true
    notify "Reviewed ${#inputs[@]} 3MF file(s)."
    exit 0
fi

message=$("$PYTHON_BIN" - "$log_file" "$report_path" <<'PY'
from pathlib import Path
import sys

log_text = Path(sys.argv[1]).read_text(errors="replace")
report_path = Path(sys.argv[2])
if len(log_text) > 3000:
    log_text = log_text[-3000:]
print(f"Duplicate review failed. Partial report:\n\n{report_path}\n\nDetails:\n\n{log_text}")
PY
)

alert "$message"
exit 1

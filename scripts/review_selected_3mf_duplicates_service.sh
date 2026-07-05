#!/usr/bin/env bash
set -euo pipefail

APP_NAME="3MF Merge Tools"
if [ "${INSTALL_DIR:-}" ]; then
    INSTALL_DIR="$INSTALL_DIR"
elif [ -f "$HOME/.local/share/3mf-merge-tools/scripts/deduplicate_3mf_models_ui.py" ]; then
    INSTALL_DIR="$HOME/.local/share/3mf-merge-tools"
else
    INSTALL_DIR="/Library/Application Support/3mf-merge-tools"
fi
UI_SCRIPT="$INSTALL_DIR/scripts/deduplicate_3mf_models_ui.py"
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

if [ ! -f "$UI_SCRIPT" ]; then
    alert "The duplicate model UI script was not found at:\n\n$UI_SCRIPT\n\nRun the 3mf-merge-tools installer and try again."
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
    alert "Select one .3mf file in Finder, then run this Quick Action again."
    exit 0
fi

if [ "${#inputs[@]}" -gt 1 ]; then
    alert "Select exactly one .3mf file for the duplicate model editor. The editor saves a deduplicated copy of that one project."
    exit 0
fi

tmp_parent="${TMPDIR:-/tmp}"
tmp_parent="${tmp_parent%/}"
log_file=$(mktemp "$tmp_parent/3mf-deduplicate-ui-service.XXXXXX")

/usr/bin/nohup "$PYTHON_BIN" "$UI_SCRIPT" "${inputs[0]}" >"$log_file" 2>&1 &
ui_pid=$!
sleep 0.5

if kill -0 "$ui_pid" >/dev/null 2>&1; then
    notify "Opened the 3MF duplicate model editor."
    exit 0
fi

message=$("$PYTHON_BIN" - "$log_file" <<'PY'
from pathlib import Path
import sys

log_text = Path(sys.argv[1]).read_text(errors="replace")
if len(log_text) > 3000:
    log_text = log_text[-3000:]
print(f"Could not open the 3MF duplicate model editor. Details:\n\n{log_text}")
PY
)

alert "$message"
exit 1

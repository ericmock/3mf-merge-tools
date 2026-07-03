#!/usr/bin/env bash
set -euo pipefail

APP_NAME="3MF Merge Tools"
if [ "${INSTALL_DIR:-}" ]; then
    INSTALL_DIR="$INSTALL_DIR"
elif [ -f "$HOME/.local/share/3mf-merge-tools/scripts/merge_bambu_3mf.py" ]; then
    INSTALL_DIR="$HOME/.local/share/3mf-merge-tools"
else
    INSTALL_DIR="/Library/Application Support/3mf-merge-tools"
fi
MERGE_SCRIPT="$INSTALL_DIR/scripts/merge_bambu_3mf.py"
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

if [ ! -f "$MERGE_SCRIPT" ]; then
    alert "The merge script was not found at:\n\n$MERGE_SCRIPT\n\nRun the 3mf-merge-tools installer and try again."
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

if [ "${#inputs[@]}" -lt 2 ]; then
    alert "Select at least two .3mf files in Finder, then run this Quick Action again."
    exit 0
fi

first_dir=$(dirname "${inputs[0]}")
default_name="MERGED_BUILD_PLATES.3mf"

output_path=$(/usr/bin/osascript \
    -e 'on run argv' \
    -e 'try' \
    -e 'set defaultFolder to POSIX file (item 1 of argv)' \
    -e 'set chosenFile to choose file name with prompt "Save merged 3MF as:" default name (item 2 of argv) default location defaultFolder' \
    -e 'POSIX path of chosenFile' \
    -e 'on error number -128' \
    -e 'return ""' \
    -e 'end try' \
    -e 'end run' -- "$first_dir" "$default_name"
)

if [ -z "$output_path" ]; then
    exit 0
fi

case "$output_path" in
    *.3mf|*.3MF) ;;
    *) output_path="${output_path}.3mf" ;;
esac

tmp_parent="${TMPDIR:-/tmp}"
tmp_parent="${tmp_parent%/}"
log_file=$(mktemp "$tmp_parent/3mf-merge-service.XXXXXX")

if {
    echo "Selected input files:"
    printf ' - %s\n' "${inputs[@]}"
    echo "Output file:"
    printf ' - %s\n' "$output_path"
    echo
    "$PYTHON_BIN" "$MERGE_SCRIPT" "${inputs[@]}" -o "$output_path"
} >"$log_file" 2>&1; then
    /usr/bin/open -R "$output_path" >/dev/null 2>&1 || true
    notify "Merged ${#inputs[@]} files."
    exit 0
fi

message=$("$PYTHON_BIN" - "$log_file" <<'PY'
from pathlib import Path
import sys

text = Path(sys.argv[1]).read_text(errors="replace")
if len(text) > 3500:
    text = text[-3500:]
print("Merge failed. Details:\n\n" + text)
PY
)

alert "$message"
exit 1

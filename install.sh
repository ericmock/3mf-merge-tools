#!/usr/bin/env sh
set -eu

PROJECT_NAME="3mf-merge-tools"
INSTALL_DIR="${INSTALL_DIR:-"$HOME/.local/share/$PROJECT_NAME"}"
BIN_DIR="${BIN_DIR:-"$HOME/.local/bin"}"

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)

find_python() {
    if [ "${PYTHON:-}" ]; then
        command -v "$PYTHON" >/dev/null 2>&1 || {
            echo "Configured PYTHON was not found: $PYTHON" >&2
            exit 1
        }
        echo "$PYTHON"
        return
    fi

    if command -v python3 >/dev/null 2>&1; then
        echo "python3"
        return
    fi

    if command -v python >/dev/null 2>&1; then
        echo "python"
        return
    fi

    echo "Python 3.10 or newer is required, but no python executable was found." >&2
    exit 1
}

PYTHON_BIN=$(find_python)

"$PYTHON_BIN" - <<'PY'
import sys

if sys.version_info < (3, 10):
    version = ".".join(str(part) for part in sys.version_info[:3])
    raise SystemExit(f"Python 3.10 or newer is required; found {version}")
PY

mkdir -p "$INSTALL_DIR/scripts" "$BIN_DIR"

cp "$SCRIPT_DIR/scripts/merge_bambu_3mf.py" "$INSTALL_DIR/scripts/merge_bambu_3mf.py"
cp "$SCRIPT_DIR/scripts/inspect_3mf_plates.py" "$INSTALL_DIR/scripts/inspect_3mf_plates.py"
if [ -f "$SCRIPT_DIR/scripts/merge_selected_3mf_service.sh" ]; then
    cp "$SCRIPT_DIR/scripts/merge_selected_3mf_service.sh" "$INSTALL_DIR/scripts/merge_selected_3mf_service.sh"
fi
chmod 755 "$INSTALL_DIR/scripts/"*

cat > "$BIN_DIR/3mf-merge" <<EOF
#!/usr/bin/env sh
exec "$PYTHON_BIN" "$INSTALL_DIR/scripts/merge_bambu_3mf.py" "\$@"
EOF

cat > "$BIN_DIR/3mf-inspect-plates" <<EOF
#!/usr/bin/env sh
exec "$PYTHON_BIN" "$INSTALL_DIR/scripts/inspect_3mf_plates.py" "\$@"
EOF

chmod 755 "$BIN_DIR/3mf-merge" "$BIN_DIR/3mf-inspect-plates"

echo "Installed $PROJECT_NAME"
echo "  scripts: $INSTALL_DIR/scripts"
echo "  commands: $BIN_DIR/3mf-merge, $BIN_DIR/3mf-inspect-plates"

case ":$PATH:" in
    *":$BIN_DIR:"*) ;;
    *)
        echo
        echo "Add this to your shell profile if the commands are not found:"
        echo "  export PATH=\"\$PATH:$BIN_DIR\""
        ;;
esac

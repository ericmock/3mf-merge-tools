#!/usr/bin/env sh
set -eu

PROJECT_NAME="3mf-merge-tools"
INSTALL_DIR="${INSTALL_DIR:-"$HOME/.local/share/$PROJECT_NAME"}"
BIN_DIR="${BIN_DIR:-"$HOME/.local/bin"}"

rm -f "$BIN_DIR/3mf-merge" "$BIN_DIR/3mf-inspect-plates" "$BIN_DIR/3mf-review-duplicates"
rm -rf "$INSTALL_DIR"

echo "Removed $PROJECT_NAME"

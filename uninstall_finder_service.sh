#!/usr/bin/env bash
set -euo pipefail

SERVICE_NAME="Merge 3MF Build Plates"
SERVICE_DIR="$HOME/Library/Services/$SERVICE_NAME.workflow"

rm -rf "$SERVICE_DIR"

if [ -x /System/Library/CoreServices/pbs ]; then
    /System/Library/CoreServices/pbs -update || true
fi

echo "Removed Finder Quick Action: $SERVICE_NAME"

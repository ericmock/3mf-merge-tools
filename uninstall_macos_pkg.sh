#!/usr/bin/env bash
set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
    echo "Run with sudo: sudo $0" >&2
    exit 1
fi

rm -f /usr/local/bin/3mf-merge /usr/local/bin/3mf-inspect-plates /usr/local/bin/3mf-review-duplicates /usr/local/bin/3mf-deduplicate-ui
rm -rf "/Library/Application Support/3mf-merge-tools"
rm -rf "/Library/Services/Merge 3MF Build Plates.workflow"
rm -rf "/Library/Services/Review 3MF Duplicate Models.workflow"

if [ -x /System/Library/CoreServices/pbs ]; then
    /System/Library/CoreServices/pbs -update || true
fi

pkgutil --forget com.ericmock.3mf-merge-tools >/dev/null 2>&1 || true

echo "Removed 3mf-merge-tools package install."

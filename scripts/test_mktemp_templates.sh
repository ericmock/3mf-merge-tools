#!/usr/bin/env bash
set -euo pipefail

tmp_test_dir=$(mktemp -d "${TMPDIR:-/tmp}/3mf-merge-mktemp-test.XXXXXX")
trap 'rm -rf "$tmp_test_dir"' EXIT

# Regression guard for macOS/BSD mktemp: XXXXXX must be at the end of the
# template, otherwise stale literal files can make Automator fail.
: > "$tmp_test_dir/3mf-merge-service.XXXXXX.log"

tmp_parent="${tmp_test_dir%/}"
log_file=$(mktemp "$tmp_parent/3mf-merge-service.XXXXXX")
test -f "$log_file"

uti_base=$(mktemp "$tmp_parent/3mf-merge-tools-uti.XXXXXX")
uti_file="${uti_base}.3mf"
mv "$uti_base" "$uti_file"
test -f "$uti_file"

echo "mktemp templates OK"

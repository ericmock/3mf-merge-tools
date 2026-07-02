#!/usr/bin/env bash
set -euo pipefail

VERSION="${VERSION:-0.1.0}"
IDENTIFIER="${IDENTIFIER:-com.ericmock.3mf-merge-tools}"
PACKAGE_NAME="3mf-merge-tools-${VERSION}.pkg"
BUILD_ROOT="${BUILD_ROOT:-/tmp/3mf-merge-tools-pkg-build}"
REPO_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PAYLOAD="$BUILD_ROOT/payload"
SCRIPTS_DIR="$BUILD_ROOT/scripts"
OUTPUT_DIR="${OUTPUT_DIR:-$REPO_ROOT/dist}"
SERVICE_DIR="$PAYLOAD/Library/Services/Merge 3MF Build Plates.workflow"
APP_SUPPORT="$PAYLOAD/Library/Application Support/3mf-merge-tools"

rm -rf "$BUILD_ROOT"
mkdir -p "$APP_SUPPORT/scripts" "$PAYLOAD/usr/local/bin" "$SERVICE_DIR/Contents" "$SCRIPTS_DIR" "$OUTPUT_DIR"

install -m 755 "$REPO_ROOT/scripts/merge_bambu_3mf.py" "$APP_SUPPORT/scripts/merge_bambu_3mf.py"
install -m 755 "$REPO_ROOT/scripts/inspect_3mf_plates.py" "$APP_SUPPORT/scripts/inspect_3mf_plates.py"
install -m 755 "$REPO_ROOT/scripts/merge_selected_3mf_service.sh" "$APP_SUPPORT/scripts/merge_selected_3mf_service.sh"

cat > "$PAYLOAD/usr/local/bin/3mf-merge" <<'EOF'
#!/usr/bin/env sh
exec python3 "/Library/Application Support/3mf-merge-tools/scripts/merge_bambu_3mf.py" "$@"
EOF

cat > "$PAYLOAD/usr/local/bin/3mf-inspect-plates" <<'EOF'
#!/usr/bin/env sh
exec python3 "/Library/Application Support/3mf-merge-tools/scripts/inspect_3mf_plates.py" "$@"
EOF

chmod 755 "$PAYLOAD/usr/local/bin/3mf-merge" "$PAYLOAD/usr/local/bin/3mf-inspect-plates"

cat > "$SERVICE_DIR/Contents/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
	<key>NSServices</key>
	<array>
		<dict>
			<key>NSBackgroundColorName</key>
			<string>background</string>
			<key>NSIconName</key>
			<string>NSActionTemplate</string>
			<key>NSMenuItem</key>
			<dict>
				<key>default</key>
				<string>Merge 3MF Build Plates</string>
			</dict>
			<key>NSMessage</key>
			<string>runWorkflowAsService</string>
			<key>NSRequiredContext</key>
			<dict>
				<key>NSApplicationIdentifier</key>
				<string>com.apple.finder</string>
			</dict>
			<key>NSSendFileTypes</key>
			<array>
				<string>com.hildahandcraft.3mf</string>
			</array>
		</dict>
	</array>
</dict>
</plist>
PLIST

cat > "$SERVICE_DIR/Contents/document.wflow" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
	<key>actions</key>
	<array>
		<dict>
			<key>action</key>
			<dict>
				<key>ActionBundlePath</key>
				<string>/System/Library/Automator/Run Shell Script.action</string>
				<key>ActionName</key>
				<string>Run Shell Script</string>
				<key>ActionParameters</key>
				<dict>
					<key>CheckedForUserDefaultShell</key>
					<true/>
					<key>COMMAND_STRING</key>
					<string>&quot;/Library/Application Support/3mf-merge-tools/scripts/merge_selected_3mf_service.sh&quot; &quot;$@&quot;</string>
					<key>inputMethod</key>
					<integer>1</integer>
					<key>shell</key>
					<string>/bin/zsh</string>
					<key>source</key>
					<string></string>
				</dict>
				<key>AMAccepts</key>
				<dict>
					<key>Container</key>
					<string>List</string>
					<key>Optional</key>
					<true/>
					<key>Types</key>
					<array>
						<string>com.apple.cocoa.string</string>
					</array>
				</dict>
				<key>AMActionVersion</key>
				<string>2.0.3</string>
				<key>AMApplication</key>
				<array>
					<string>Automator</string>
				</array>
				<key>AMProvides</key>
				<dict>
					<key>Container</key>
					<string>List</string>
					<key>Types</key>
					<array>
						<string>com.apple.cocoa.string</string>
					</array>
				</dict>
				<key>BundleIdentifier</key>
				<string>com.apple.RunShellScript</string>
				<key>CanShowSelectedItemsWhenRun</key>
				<false/>
				<key>CanShowWhenRun</key>
				<true/>
				<key>Class Name</key>
				<string>RunShellScriptAction</string>
				<key>InputUUID</key>
				<string>4E3D13F6-67EF-4D20-B4BE-89245E1303F1</string>
				<key>OutputUUID</key>
				<string>8C3A7C4D-6226-41EA-A6F9-66243F6E6C8A</string>
				<key>UUID</key>
				<string>2C6BD528-A1B6-4369-9B63-A6C984A3A0BD</string>
			</dict>
			<key>isViewVisible</key>
			<integer>1</integer>
		</dict>
	</array>
	<key>AMApplicationBuild</key>
	<string>528</string>
	<key>AMApplicationVersion</key>
	<string>2.10</string>
	<key>AMDocumentVersion</key>
	<string>2</string>
	<key>connectors</key>
	<dict/>
	<key>workflowMetaData</key>
	<dict>
		<key>serviceApplicationBundleID</key>
		<string>com.apple.finder</string>
		<key>serviceApplicationPath</key>
		<string>/System/Library/CoreServices/Finder.app</string>
		<key>serviceInputTypeIdentifier</key>
		<string>com.apple.Automator.fileSystemObject</string>
		<key>serviceOutputTypeIdentifier</key>
		<string>com.apple.Automator.nothing</string>
		<key>serviceProcessesInput</key>
		<false/>
		<key>workflowTypeIdentifier</key>
		<string>com.apple.Automator.servicesMenu</string>
	</dict>
</dict>
</plist>
PLIST

cat > "$SCRIPTS_DIR/postinstall" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
tar -xzf "$SCRIPT_DIR/payload.tar.gz" -C /
chmod 755 \
    /usr/local/bin/3mf-merge \
    /usr/local/bin/3mf-inspect-plates \
    "/Library/Application Support/3mf-merge-tools/scripts/merge_bambu_3mf.py" \
    "/Library/Application Support/3mf-merge-tools/scripts/inspect_3mf_plates.py" \
    "/Library/Application Support/3mf-merge-tools/scripts/merge_selected_3mf_service.sh"

INFO="/Library/Services/Merge 3MF Build Plates.workflow/Contents/Info.plist"
TMP_3MF=$(mktemp "${TMPDIR:-/tmp}/3mf-merge-tools-uti.XXXXXX.3mf")
THREEMF_UTI=$(mdls -raw -name kMDItemContentType "$TMP_3MF" 2>/dev/null || true)
rm -f "$TMP_3MF"

if [ -z "$THREEMF_UTI" ] || [ "$THREEMF_UTI" = "(null)" ]; then
    THREEMF_UTI="com.hildahandcraft.3mf"
fi

if [ -f "$INFO" ]; then
    plutil -replace NSServices.0.NSSendFileTypes -json "[\"$THREEMF_UTI\"]" "$INFO" || true
fi

if [ -x /System/Library/CoreServices/pbs ]; then
    /System/Library/CoreServices/pbs -update || true
fi

exit 0
EOF

chmod 755 "$SCRIPTS_DIR/postinstall"

plutil -lint "$SERVICE_DIR/Contents/Info.plist" "$SERVICE_DIR/Contents/document.wflow" >/dev/null
bash -n "$APP_SUPPORT/scripts/merge_selected_3mf_service.sh" "$SCRIPTS_DIR/postinstall"
python3 -m py_compile "$REPO_ROOT/scripts/merge_bambu_3mf.py" "$REPO_ROOT/scripts/inspect_3mf_plates.py"

find "$PAYLOAD" -name "__pycache__" -type d -prune -exec rm -rf {} +
find "$PAYLOAD" "$SCRIPTS_DIR" -name "._*" -delete
if command -v xattr >/dev/null 2>&1; then
    xattr -cr "$PAYLOAD" "$SCRIPTS_DIR" || true
    find "$PAYLOAD" "$SCRIPTS_DIR" -print0 | xargs -0 xattr -d com.apple.provenance 2>/dev/null || true
fi

COPYFILE_DISABLE=1 tar -czf "$SCRIPTS_DIR/payload.tar.gz" -C "$PAYLOAD" .
COPYFILE_DISABLE=1 pkgbuild \
    --nopayload \
    --scripts "$SCRIPTS_DIR" \
    --identifier "$IDENTIFIER" \
    --version "$VERSION" \
    "$OUTPUT_DIR/$PACKAGE_NAME"

echo "$OUTPUT_DIR/$PACKAGE_NAME"

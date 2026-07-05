#!/usr/bin/env bash
set -euo pipefail

SERVICE_NAME="Merge 3MF Build Plates"
SERVICE_DIR="$HOME/Library/Services/$SERVICE_NAME.workflow"
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
tmp_parent="${TMPDIR:-/tmp}"
tmp_parent="${tmp_parent%/}"
TMP_3MF_BASE=$(mktemp "$tmp_parent/3mf-merge-tools-uti.XXXXXX")
TMP_3MF="${TMP_3MF_BASE}.3mf"
mv "$TMP_3MF_BASE" "$TMP_3MF"
THREEMF_UTI=$(mdls -raw -name kMDItemContentType "$TMP_3MF" 2>/dev/null || true)
rm -f "$TMP_3MF"

if [ -z "$THREEMF_UTI" ] || [ "$THREEMF_UTI" = "(null)" ]; then
    THREEMF_UTI="com.hildahandcraft.3mf"
fi

"$SCRIPT_DIR/install.sh"

mkdir -p "$SERVICE_DIR/Contents"

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
				<string>__THREEMF_UTI__</string>
			</array>
		</dict>
	</array>
</dict>
</plist>
PLIST

/usr/bin/python3 - "$SERVICE_DIR/Contents/Info.plist" "$THREEMF_UTI" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
uti = sys.argv[2]
path.write_text(path.read_text().replace("__THREEMF_UTI__", uti))
PY

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
					<string>&quot;$HOME/.local/share/3mf-merge-tools/scripts/merge_selected_3mf_service.sh&quot; &quot;$@&quot;</string>
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
		<key>applicationBundleID</key>
		<string>com.apple.finder</string>
		<key>applicationPath</key>
		<string>/System/Library/CoreServices/Finder.app</string>
		<key>inputTypeIdentifier</key>
		<string>com.apple.Automator.fileSystemObject</string>
		<key>outputTypeIdentifier</key>
		<string>com.apple.Automator.nothing</string>
		<key>presentationMode</key>
		<integer>15</integer>
		<key>processesInput</key>
		<false/>
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
		<key>systemImageName</key>
		<string>NSActionTemplate</string>
		<key>useAutomaticInputType</key>
		<false/>
		<key>workflowTypeIdentifier</key>
		<string>com.apple.Automator.servicesMenu</string>
	</dict>
</dict>
</plist>
PLIST

plutil -lint "$SERVICE_DIR/Contents/Info.plist" "$SERVICE_DIR/Contents/document.wflow" >/dev/null

REVIEW_SERVICE_NAME="Review 3MF Duplicate Models"
REVIEW_SERVICE_DIR="$HOME/Library/Services/$REVIEW_SERVICE_NAME.workflow"
mkdir -p "$REVIEW_SERVICE_DIR/Contents"

cat > "$REVIEW_SERVICE_DIR/Contents/Info.plist" <<'PLIST'
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
				<string>Review 3MF Duplicate Models</string>
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
				<string>__THREEMF_UTI__</string>
			</array>
		</dict>
	</array>
</dict>
</plist>
PLIST

/usr/bin/python3 - "$REVIEW_SERVICE_DIR/Contents/Info.plist" "$THREEMF_UTI" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
uti = sys.argv[2]
path.write_text(path.read_text().replace("__THREEMF_UTI__", uti))
PY

cat > "$REVIEW_SERVICE_DIR/Contents/document.wflow" <<'PLIST'
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
					<string>&quot;$HOME/.local/share/3mf-merge-tools/scripts/review_selected_3mf_duplicates_service.sh&quot; &quot;$@&quot;</string>
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
				<string>6A14D980-60C4-46C7-872F-55C51F8A6A3C</string>
				<key>OutputUUID</key>
				<string>7AF7D7EA-0701-4B39-9942-6A764A56C964</string>
				<key>UUID</key>
				<string>07FB4BDF-30E0-4978-B739-06947B0320FD</string>
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
		<key>applicationBundleID</key>
		<string>com.apple.finder</string>
		<key>applicationPath</key>
		<string>/System/Library/CoreServices/Finder.app</string>
		<key>inputTypeIdentifier</key>
		<string>com.apple.Automator.fileSystemObject</string>
		<key>outputTypeIdentifier</key>
		<string>com.apple.Automator.nothing</string>
		<key>presentationMode</key>
		<integer>15</integer>
		<key>processesInput</key>
		<false/>
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
		<key>systemImageName</key>
		<string>NSActionTemplate</string>
		<key>useAutomaticInputType</key>
		<false/>
		<key>workflowTypeIdentifier</key>
		<string>com.apple.Automator.servicesMenu</string>
	</dict>
</dict>
</plist>
PLIST

plutil -lint "$REVIEW_SERVICE_DIR/Contents/Info.plist" "$REVIEW_SERVICE_DIR/Contents/document.wflow" >/dev/null

if [ -x /System/Library/CoreServices/pbs ]; then
    /System/Library/CoreServices/pbs -update || true
fi

echo "Installed Finder Quick Action: $SERVICE_NAME"
echo "Location: $SERVICE_DIR"
echo "Installed Finder Quick Action: $REVIEW_SERVICE_NAME"
echo "Location: $REVIEW_SERVICE_DIR"

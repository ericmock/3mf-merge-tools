Schubox 3MF Merge Tools
=======================

This repository contains the reusable scripts used to merge Bambu Studio /
OrcaSlicer 3MF project files while preserving build plates and plate names.

Scripts
-------

scripts/merge_bambu_3mf.py
  Merges Bambu/Orca 3MF project archives. It preserves plate metadata,
  renumbers object IDs, copies external model payloads, and writes relationship
  XML in the plain form expected by Bambu Studio's importer.

scripts/inspect_3mf_plates.py
  Prints each 3MF project's build items, config objects, plates, plate names,
  and object assignments. This is useful for checking a file before and after
  a Bambu Studio round-trip.

scripts/review_duplicate_3mf_models.py
  Reviews one or more 3MF archives and reports top-level model objects with
  duplicate geometry. It includes object names and plate assignments when the
  archive contains Bambu/Orca metadata.

scripts/deduplicate_3mf_models_ui.py
  Opens a small UI for one 3MF file, shows duplicate model groups, lets you
  choose which duplicate model objects to remove, and saves a new deduplicated
  copy. The source 3MF is not modified in place.

scripts/validate_3mf_project.py
  Checks a Bambu/Orca 3MF project for broken object references, missing model
  settings, empty plates, missing thumbnails, and ZIP issues.

Installer
---------

Run this from a checkout of the repository:

./install.sh

The installer requires Python 3.10 or newer. No third-party Python packages are
needed. It installs the scripts to:

~/.local/share/3mf-merge-tools/scripts

and creates these commands:

3mf-merge
3mf-inspect-plates
3mf-review-duplicates
3mf-deduplicate-ui
3mf-validate-project

If ~/.local/bin is not already on your PATH, the installer prints the line to
add to your shell profile.

To remove the installed commands and copied scripts:

./uninstall.sh

Finder Quick Actions
--------------------

To install macOS Finder Quick Actions for selected 3MF files:

./install_finder_service.sh

After installing it, select two or more .3mf files in Finder, Control-click,
then choose Quick Actions > Merge 3MF Build Plates. The action asks where to
save the merged 3MF, runs the merge, and reveals the output file in Finder.

You can also select one .3mf file, Control-click, then choose Quick Actions >
Review 3MF Duplicate Models. The action opens the duplicate model editor, where
you can choose which duplicate model objects to remove and save a new
deduplicated copy. The source 3MF is not modified in place.

The Quick Actions register with Finder for the current system's .3mf content
type, so they should appear in the Finder contextual menu when all selected
files are .3mf files. The wrappers still validate the selection before running.

To remove the Finder Quick Actions:

./uninstall_finder_service.sh

Mac Installer Package
---------------------

To build a double-clickable macOS installer package:

./build_macos_pkg.sh

The package is written to:

dist/3mf-merge-tools-0.3.0.pkg

The package installs:

/Library/Application Support/3mf-merge-tools/scripts
/usr/local/bin/3mf-merge
/usr/local/bin/3mf-inspect-plates
/usr/local/bin/3mf-review-duplicates
/usr/local/bin/3mf-deduplicate-ui
/usr/local/bin/3mf-validate-project
/Library/Services/Merge 3MF Build Plates.workflow
/Library/Services/Review 3MF Duplicate Models.workflow

This makes the command-line tools and the Finder Quick Actions available
system-wide. The postinstall script refreshes the Services menu and updates the
Finder actions to use the current system's .3mf content type.

To remove a package install:

sudo ./uninstall_macos_pkg.sh

Important Notes
---------------

Bambu Studio and OrcaSlicer have a practical 36-plate project limit. The merge
script refuses to produce larger projects by default, so large batches should
be split into multiple output files.

The original Schubox source 3MF files and generated merged 3MF outputs are not
included here because they are large binary project files.

Example
-------

python3 scripts/merge_bambu_3mf.py input_a.3mf input_b.3mf -o merged.3mf
python3 scripts/inspect_3mf_plates.py merged.3mf

After installation, the same commands are:

3mf-merge input_a.3mf input_b.3mf -o merged.3mf
3mf-inspect-plates merged.3mf
3mf-review-duplicates merged.3mf
3mf-deduplicate-ui merged.3mf
3mf-validate-project merged.3mf

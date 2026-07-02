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

If ~/.local/bin is not already on your PATH, the installer prints the line to
add to your shell profile.

To remove the installed commands and copied scripts:

./uninstall.sh

Finder Quick Action
-------------------

To install a macOS Finder Quick Action for selected 3MF files:

./install_finder_service.sh

After installing it, select two or more .3mf files in Finder, Control-click,
then choose Quick Actions > Merge 3MF Build Plates. The action asks where to
save the merged 3MF, runs the merge, and reveals the output file in Finder.

To remove the Finder Quick Action:

./uninstall_finder_service.sh

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

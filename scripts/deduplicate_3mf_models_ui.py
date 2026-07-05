#!/usr/bin/env python3
"""Interactive UI for removing duplicate model objects from a 3MF copy."""

from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
import threading
import zipfile
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import xml.etree.ElementTree as ET

import review_duplicate_3mf_models as duplicate_review


CORE_NS = duplicate_review.CORE_NS
BAMBU_NS = "http://schemas.bambulab.com/package/2021"
PROD_NS = duplicate_review.PROD_NS

ET.register_namespace("", CORE_NS)
ET.register_namespace("BambuStudio", BAMBU_NS)
ET.register_namespace("p", PROD_NS)


def metadata_value(element: ET.Element, key: str) -> str | None:
    return duplicate_review.metadata_value(element, key)


def serialize_xml(root: ET.Element) -> bytes:
    try:
        ET.indent(root, space=" ")
    except AttributeError:
        pass
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def remove_build_objects(data: bytes, remove_ids: set[str]) -> bytes:
    root = ET.fromstring(data)
    resources = root.find(duplicate_review.qname(CORE_NS, "resources"))
    if resources is not None:
        for obj in list(resources):
            if obj.tag == duplicate_review.qname(CORE_NS, "object") and obj.get("id") in remove_ids:
                resources.remove(obj)

    build = root.find(duplicate_review.qname(CORE_NS, "build"))
    if build is not None:
        for item in list(build):
            if item.tag == duplicate_review.qname(CORE_NS, "item") and item.get("objectid") in remove_ids:
                build.remove(item)

    return serialize_xml(root)


def remove_model_settings_objects(data: bytes, remove_ids: set[str]) -> bytes:
    root = ET.fromstring(data)

    for child in list(root):
        if child.tag == "object" and child.get("id") in remove_ids:
            root.remove(child)

    for plate in root.findall("plate"):
        for instance in list(plate):
            if instance.tag != "model_instance":
                continue
            object_id = metadata_value(instance, "object_id")
            if object_id in remove_ids:
                plate.remove(instance)

    for assemble in root.findall("assemble"):
        for item in list(assemble):
            if item.tag == "assemble_item" and item.get("object_id") in remove_ids:
                assemble.remove(item)

    return serialize_xml(root)


def write_deduplicated_3mf(source: Path, output: Path, remove_ids: set[str]) -> None:
    if not remove_ids:
        raise ValueError("No model objects were selected for removal.")
    if source.resolve() == output.resolve():
        raise ValueError("Choose a new output path; the source 3MF is not modified in place.")

    output.parent.mkdir(parents=True, exist_ok=True)
    temp_dir = Path(tempfile.mkdtemp(prefix="3mf_deduplicate_", dir="/tmp"))
    temp_output = temp_dir / output.name

    try:
        with zipfile.ZipFile(source, "r") as zin, zipfile.ZipFile(temp_output, "w") as zout:
            for info in zin.infolist():
                data = zin.read(info.filename)
                if info.filename == "3D/3dmodel.model":
                    data = remove_build_objects(data, remove_ids)
                elif info.filename == "Metadata/model_settings.config":
                    data = remove_model_settings_objects(data, remove_ids)
                zout.writestr(info, data)
        shutil.move(str(temp_output), output)
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


class DeduplicateApp(tk.Tk):
    def __init__(self, initial_file: Path | None = None) -> None:
        super().__init__()
        self.title("3MF Duplicate Model Editor")
        self.geometry("1040x680")
        self.minsize(900, 520)

        self.source_path: Path | None = None
        self.report: dict | None = None
        self.row_occurrences: dict[str, dict] = {}
        self.selected_remove_ids: set[str] = set()
        self.reviewing = False

        self._build_ui()
        if initial_file is not None:
            initial_path = initial_file.resolve()
            self.file_var.set(str(initial_path))
            self.show_reviewing_state()
            self.after(100, lambda: self.load_file(initial_path))

    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)

        top = ttk.Frame(self, padding=10)
        top.grid(row=0, column=0, sticky="ew")
        top.columnconfigure(1, weight=1)

        ttk.Button(top, text="Open 3MF...", command=self.choose_file).grid(row=0, column=0, padx=(0, 8))
        self.file_var = tk.StringVar(value="No file loaded")
        ttk.Label(top, textvariable=self.file_var, anchor="w").grid(row=0, column=1, sticky="ew")

        summary = ttk.Frame(self, padding=(10, 0, 10, 8))
        summary.grid(row=1, column=0, sticky="ew")
        summary.columnconfigure(0, weight=1)
        self.summary_var = tk.StringVar(value="Open a 3MF file to review duplicate model groups.")
        ttk.Label(summary, textvariable=self.summary_var, anchor="w").grid(row=0, column=0, sticky="ew")
        self.progress = ttk.Progressbar(summary, mode="indeterminate", length=170)
        self.progress.grid(row=0, column=1, sticky="e", padx=(12, 0))
        self.progress.grid_remove()

        columns = ("remove", "object_id", "name", "faces", "plates")
        self.tree = ttk.Treeview(self, columns=columns, show="tree headings", selectmode="browse")
        self.tree.heading("#0", text="Duplicate Group")
        self.tree.heading("remove", text="Remove")
        self.tree.heading("object_id", text="Object")
        self.tree.heading("name", text="Model Name")
        self.tree.heading("faces", text="Faces")
        self.tree.heading("plates", text="Plates")
        self.tree.column("#0", width=210, stretch=False)
        self.tree.column("remove", width=76, anchor="center", stretch=False)
        self.tree.column("object_id", width=70, anchor="center", stretch=False)
        self.tree.column("name", width=300)
        self.tree.column("faces", width=80, anchor="e", stretch=False)
        self.tree.column("plates", width=300)
        self.tree.grid(row=2, column=0, sticky="nsew", padx=10)
        self.tree.bind("<Double-1>", self.toggle_selected_row)
        self.tree.bind("<space>", self.toggle_selected_row)

        scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        scrollbar.grid(row=2, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=scrollbar.set)

        bottom = ttk.Frame(self, padding=10)
        bottom.grid(row=3, column=0, sticky="ew")
        bottom.columnconfigure(0, weight=1)

        self.select_button = ttk.Button(bottom, text="Select All But First", command=self.select_all_but_first)
        self.select_button.grid(row=0, column=1, padx=4)
        self.clear_button = ttk.Button(bottom, text="Clear Removals", command=self.clear_removals)
        self.clear_button.grid(row=0, column=2, padx=4)
        self.save_button = ttk.Button(bottom, text="Save Deduplicated Copy...", command=self.save_copy)
        self.save_button.grid(row=0, column=3, padx=(12, 0))

    def show_reviewing_state(self) -> None:
        self.reviewing = True
        self.summary_var.set("Finding duplicate model geometry...")
        self.tree.delete(*self.tree.get_children())
        self.tree.insert(
            "",
            "end",
            text="Scanning selected 3MF...",
            values=("", "", "This can take a moment for large projects.", "", ""),
            open=True,
        )
        self.progress.grid()
        self.progress.start(12)
        self.select_button.configure(state="disabled")
        self.clear_button.configure(state="disabled")
        self.save_button.configure(state="disabled")

    def hide_reviewing_state(self) -> None:
        self.reviewing = False
        self.progress.stop()
        self.progress.grid_remove()
        self.select_button.configure(state="normal")
        self.clear_button.configure(state="normal")
        self.save_button.configure(state="normal")

    def choose_file(self) -> None:
        filename = filedialog.askopenfilename(
            title="Choose a 3MF file",
            filetypes=(("3MF files", "*.3mf *.3MF"), ("All files", "*.*")),
        )
        if filename:
            self.load_file(Path(filename))

    def load_file(self, path: Path) -> None:
        self.source_path = path.resolve()
        self.file_var.set(str(self.source_path))
        self.row_occurrences.clear()
        self.selected_remove_ids.clear()
        self.show_reviewing_state()
        self.update_idletasks()

        threading.Thread(target=self._review_worker, args=(self.source_path,), daemon=True).start()

    def _review_worker(self, path: Path) -> None:
        try:
            report = duplicate_review.review_file(path)
            error: Exception | None = None
        except Exception as exc:
            report = None
            error = exc
        self.after(0, lambda: self.finish_review(path, report, error))

    def finish_review(self, path: Path, report: dict | None, error: Exception | None) -> None:
        if self.source_path != path:
            return
        self.hide_reviewing_state()
        if error is not None:
            self.report = None
            self.summary_var.set("Review failed.")
            messagebox.showerror("Review Failed", str(error), parent=self)
            return

        self.report = report
        self.populate_tree()

    def populate_tree(self) -> None:
        self.tree.delete(*self.tree.get_children())
        self.row_occurrences.clear()
        self.selected_remove_ids.clear()

        assert self.report is not None
        groups = self.report["duplicate_groups"]
        self.summary_var.set(
            f"Reviewed {self.report['reviewed_models']} model object(s); "
            f"found {len(groups)} duplicate group(s). Double-click a model row to toggle removal."
        )

        for group_index, group in enumerate(groups, start=1):
            parent = self.tree.insert(
                "",
                "end",
                text=f"Group {group_index}",
                values=("", "", f"{len(group['occurrences'])} matching models", "", group["signature"]),
                open=True,
            )
            occurrences = list(group["occurrences"])
            for occurrence_index, occurrence in enumerate(occurrences):
                object_id = occurrence["object_id"]
                remove = occurrence_index > 0
                if remove:
                    self.selected_remove_ids.add(object_id)
                row_id = self.tree.insert(
                    parent,
                    "end",
                    text="",
                    values=(
                        "[x]" if remove else "[ ]",
                        object_id,
                        occurrence["name"] or "(unnamed)",
                        occurrence["face_count"],
                        ", ".join(occurrence["plates"]) if occurrence["plates"] else "(no plate assignment)",
                    ),
                )
                self.row_occurrences[row_id] = occurrence

    def toggle_selected_row(self, event: tk.Event | None = None) -> str:
        row_id = self.tree.focus()
        if row_id not in self.row_occurrences:
            return "break"
        object_id = self.row_occurrences[row_id]["object_id"]
        if object_id in self.selected_remove_ids:
            self.selected_remove_ids.remove(object_id)
            self.tree.set(row_id, "remove", "[ ]")
        else:
            self.selected_remove_ids.add(object_id)
            self.tree.set(row_id, "remove", "[x]")
        return "break"

    def select_all_but_first(self) -> None:
        self.selected_remove_ids.clear()
        for parent in self.tree.get_children(""):
            children = self.tree.get_children(parent)
            for index, row_id in enumerate(children):
                occurrence = self.row_occurrences.get(row_id)
                if occurrence is None:
                    continue
                if index > 0:
                    self.selected_remove_ids.add(occurrence["object_id"])
                    self.tree.set(row_id, "remove", "[x]")
                else:
                    self.tree.set(row_id, "remove", "[ ]")

    def clear_removals(self) -> None:
        self.selected_remove_ids.clear()
        for row_id in self.row_occurrences:
            self.tree.set(row_id, "remove", "[ ]")

    def save_copy(self) -> None:
        if self.source_path is None:
            messagebox.showinfo("No File", "Open a 3MF file first.", parent=self)
            return
        if not self.selected_remove_ids:
            messagebox.showinfo("No Models Selected", "Select one or more duplicate model rows to remove.", parent=self)
            return

        default_name = f"{self.source_path.stem}_deduplicated.3mf"
        output = filedialog.asksaveasfilename(
            title="Save deduplicated 3MF copy",
            initialdir=str(self.source_path.parent),
            initialfile=default_name,
            defaultextension=".3mf",
            filetypes=(("3MF files", "*.3mf"), ("All files", "*.*")),
        )
        if not output:
            return

        output_path = Path(output)
        try:
            write_deduplicated_3mf(self.source_path, output_path, self.selected_remove_ids)
        except Exception as exc:
            messagebox.showerror("Save Failed", str(exc), parent=self)
            return

        messagebox.showinfo(
            "Deduplicated Copy Saved",
            f"Removed {len(self.selected_remove_ids)} model object(s).\n\n{output_path}",
            parent=self,
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", nargs="?", type=Path, help="Optional 3MF file to open.")
    args = parser.parse_args()
    app = DeduplicateApp(args.path)
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

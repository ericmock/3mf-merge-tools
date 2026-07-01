#!/usr/bin/env python3
"""Merge Bambu Studio / OrcaSlicer project 3MF build plates.

The script preserves slicer build plates by appending the source
`Metadata/model_settings.config` plate entries, renumbering plate ids and
object ids, and copying plate thumbnails plus object model payloads into one
project archive.
"""

from __future__ import annotations

import argparse
import copy
import glob
import json
import math
import os
from pathlib import Path, PurePosixPath
import shutil
import sys
import tempfile
import uuid
import zipfile
import xml.etree.ElementTree as ET


CORE_NS = "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"
BAMBU_NS = "http://schemas.bambulab.com/package/2021"
PROD_NS = "http://schemas.microsoft.com/3dmanufacturing/production/2015/06"
RELS_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
SLICER_MAX_PLATES = 36

ET.register_namespace("", CORE_NS)
ET.register_namespace("BambuStudio", BAMBU_NS)
ET.register_namespace("p", PROD_NS)

P_UUID = f"{{{PROD_NS}}}UUID"
P_PATH = f"{{{PROD_NS}}}path"


def qname(namespace: str, name: str) -> str:
    return f"{{{namespace}}}{name}"


def parse_xml(data: bytes) -> ET.Element:
    return ET.fromstring(data)


def indent(tree_or_element: ET.ElementTree | ET.Element) -> None:
    try:
        ET.indent(tree_or_element, space=" ")
    except AttributeError:
        pass


def fresh_uuid() -> str:
    return str(uuid.uuid4())


def rewrite_uuids(element: ET.Element) -> None:
    if P_UUID in element.attrib:
        element.set(P_UUID, fresh_uuid())
    for child in list(element):
        rewrite_uuids(child)


def clone(element: ET.Element) -> ET.Element:
    return copy.deepcopy(element)


def list_3mf_files(cwd: Path, output: Path) -> list[Path]:
    files = [Path(p) for p in glob.glob(str(cwd / "*.3mf"))]
    files.extend(Path(p) for p in glob.glob(str(cwd / "*.3MF")))
    unique = sorted({p.resolve() for p in files})
    return [p for p in unique if p != output.resolve()]


def compute_column_count(count: int) -> int:
    value = math.sqrt(float(count))
    round_value = round(value)
    if value > round_value:
        return round_value + 1
    return round_value


def parse_point(value: str) -> tuple[float, float]:
    x_text, y_text = value.split("x", 1)
    return float(x_text), float(y_text)


def printable_size(project_settings: dict) -> tuple[float, float]:
    points = [parse_point(point) for point in project_settings["printable_area"]]
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    return max(xs) - min(xs), max(ys) - min(ys)


def plate_origin(plate_id: int, cols: int, width: float, depth: float) -> tuple[float, float]:
    index = plate_id - 1
    row = index // cols
    col = index % cols
    return col * width * 1.2, -row * depth * 1.2


def translate_transform(transform: str | None, dx: float, dy: float) -> str | None:
    if transform is None:
        return None
    values = transform.split()
    if len(values) < 12:
        return transform
    numbers = [float(value) for value in values]
    numbers[9] += dx
    numbers[10] += dy
    return " ".join(f"{value:.15g}" for value in numbers)


def identity_transform() -> str:
    return "1 0 0 0 1 0 0 0 1 0 0 0"


def transform_to_matrix(transform: str | None) -> list[list[float]]:
    values = [1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0]
    if transform:
        parsed = [float(value) for value in transform.split()]
        if len(parsed) == 12:
            values = parsed
    matrix = [
        [values[0], values[3], values[6], values[9]],
        [values[1], values[4], values[7], values[10]],
        [values[2], values[5], values[8], values[11]],
        [0.0, 0.0, 0.0, 1.0],
    ]
    return matrix


def matrix_to_transform(matrix: list[list[float]]) -> str:
    values = [
        matrix[0][0],
        matrix[1][0],
        matrix[2][0],
        matrix[0][1],
        matrix[1][1],
        matrix[2][1],
        matrix[0][2],
        matrix[1][2],
        matrix[2][2],
        matrix[0][3],
        matrix[1][3],
        matrix[2][3],
    ]
    return " ".join(f"{value:.15g}" for value in values)


def compose_transforms(outer: str | None, inner: str | None) -> str:
    outer_matrix = transform_to_matrix(outer)
    inner_matrix = transform_to_matrix(inner)
    result = [[0.0 for _ in range(4)] for _ in range(4)]
    for row in range(4):
        for col in range(4):
            result[row][col] = sum(outer_matrix[row][idx] * inner_matrix[idx][col] for idx in range(4))
    return matrix_to_transform(result)


def zip_read_required(zf: zipfile.ZipFile, name: str, source: Path) -> bytes:
    try:
        return zf.read(name)
    except KeyError as exc:
        raise RuntimeError(f"{source.name} is missing {name}") from exc


def write_xml(path: Path, root: ET.Element, declaration: bool = True) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    indent(root)
    tree = ET.ElementTree(root)
    tree.write(path, encoding="utf-8", xml_declaration=declaration)


def copy_zip_member(zf: zipfile.ZipFile, member: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with zf.open(member) as src, dest.open("wb") as out:
        shutil.copyfileobj(src, out)


def relationship_root() -> ET.Element:
    return ET.Element("Relationships", {"xmlns": RELS_NS})


def add_relationship(root: ET.Element, rel_id: int, target: str) -> None:
    ET.SubElement(
        root,
        "Relationship",
        {
            "Target": target,
            "Id": f"rel-{rel_id}",
            "Type": "http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel",
        },
    )


def metadata_value(element: ET.Element, key: str) -> str | None:
    for child in list(element):
        if child.tag == "metadata" and child.get("key") == key:
            return child.get("value")
    return None


def set_metadata_value(element: ET.Element, key: str, value: str) -> None:
    for child in list(element):
        if child.tag == "metadata" and child.get("key") == key:
            child.set("value", value)
            return
    ET.SubElement(element, "metadata", {"key": key, "value": value})


def translated_plate_delta(
    old_plate_id: str,
    new_plate_id: int,
    source_cols: int,
    source_width: float,
    source_depth: float,
    output_cols: int,
    output_width: float,
    output_depth: float,
) -> tuple[float, float]:
    old_x, old_y = plate_origin(int(old_plate_id), source_cols, source_width, source_depth)
    new_x, new_y = plate_origin(new_plate_id, output_cols, output_width, output_depth)
    return new_x - old_x, new_y - old_y


def copy_plate_artifacts(
    zf: zipfile.ZipFile,
    zip_names: set[str],
    staging: Path,
    old_plate_id: str,
    new_plate_id: int,
) -> None:
    patterns = (
        ("Metadata/plate_{old}.png", "Metadata/plate_{new}.png"),
        ("Metadata/plate_{old}_small.png", "Metadata/plate_{new}_small.png"),
        ("Metadata/plate_no_light_{old}.png", "Metadata/plate_no_light_{new}.png"),
        ("Metadata/top_{old}.png", "Metadata/top_{new}.png"),
        ("Metadata/pick_{old}.png", "Metadata/pick_{new}.png"),
    )
    for source_pattern, dest_pattern in patterns:
        source_name = source_pattern.format(old=old_plate_id)
        if source_name not in zip_names:
            continue
        dest_name = dest_pattern.format(new=new_plate_id)
        copy_zip_member(zf, source_name, staging / dest_name)


def update_plate_artifact_refs(plate: ET.Element, new_plate_id: int) -> None:
    ref_names = {
        "thumbnail_file": f"Metadata/plate_{new_plate_id}.png",
        "thumbnail_no_light_file": f"Metadata/plate_no_light_{new_plate_id}.png",
        "top_file": f"Metadata/top_{new_plate_id}.png",
        "pick_file": f"Metadata/pick_{new_plate_id}.png",
    }
    for key, value in ref_names.items():
        set_metadata_value(plate, key, value)


def plate_object_map(settings_root: ET.Element) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for plate in settings_root.findall("plate"):
        plate_id = metadata_value(plate, "plater_id")
        if plate_id is None:
            continue
        for instance in plate.findall("model_instance"):
            object_id = metadata_value(instance, "object_id")
            if object_id is not None:
                mapping[object_id] = plate_id
    return mapping


def update_project_thumbnail_metadata(root: ET.Element) -> None:
    for meta in root.findall(qname(CORE_NS, "metadata")):
        name = meta.get("name")
        if name == "Thumbnail_Middle":
            meta.text = "/Metadata/plate_1.png"
        elif name == "Thumbnail_Small":
            meta.text = "/Metadata/plate_1_small.png"
        elif name in {"Title", "ProfileTitle"}:
            meta.text = "Merged Schubox Build Plates"


def collect_model_ids(root: ET.Element) -> set[int]:
    ids: set[int] = set()
    for object_element in root.findall(f".//{qname(CORE_NS, 'object')}"):
        value = object_element.get("id")
        if value is not None:
            ids.add(int(value))
    for component in root.findall(f".//{qname(CORE_NS, 'component')}"):
        value = component.get("objectid")
        if value is not None:
            ids.add(int(value))
    for item in root.findall(f".//{qname(CORE_NS, 'item')}"):
        value = item.get("objectid")
        if value is not None:
            ids.add(int(value))
    return ids


def collect_source_ids(zf: zipfile.ZipFile, model_root: ET.Element, zip_names: set[str]) -> set[int]:
    ids = collect_model_ids(model_root)
    for name in zip_names:
        if name.startswith("3D/Objects/") and name.endswith(".model"):
            ids.update(collect_model_ids(parse_xml(zf.read(name))))
    try:
        settings_root = parse_xml(zf.read("Metadata/model_settings.config"))
    except KeyError:
        return ids
    for object_element in settings_root.findall("object"):
        value = object_element.get("id")
        if value is not None:
            ids.add(int(value))
        for part in object_element.findall("part"):
            part_id = part.get("id")
            if part_id is not None:
                ids.add(int(part_id))
    return ids


def offset_model_ids(root: ET.Element, id_offset: int) -> None:
    for object_element in root.findall(f".//{qname(CORE_NS, 'object')}"):
        value = object_element.get("id")
        if value is not None:
            object_element.set("id", str(int(value) + id_offset))
    for component in root.findall(f".//{qname(CORE_NS, 'component')}"):
        value = component.get("objectid")
        if value is not None:
            component.set("objectid", str(int(value) + id_offset))
    for item in root.findall(f".//{qname(CORE_NS, 'item')}"):
        value = item.get("objectid")
        if value is not None:
            item.set("objectid", str(int(value) + id_offset))


def model_children(root: ET.Element) -> tuple[ET.Element, ET.Element]:
    resources = root.find(qname(CORE_NS, "resources"))
    build = root.find(qname(CORE_NS, "build"))
    if resources is None or build is None:
        raise RuntimeError("3D/3dmodel.model is missing resources or build")
    return resources, build


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "inputs",
        nargs="*",
        type=Path,
        help="Source .3mf files. Defaults to all .3mf files in the current folder.",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("SCHUBOX_ALL_BUILD_PLATES_MERGED.3mf"),
        help="Output 3MF path.",
    )
    parser.add_argument(
        "--allow-over-max-plates",
        action="store_true",
        help="Allow output above Bambu/Orca's known 36-plate UI limit.",
    )
    args = parser.parse_args()

    cwd = Path.cwd()
    output = args.output if args.output.is_absolute() else cwd / args.output
    sources = [p.resolve() for p in args.inputs] if args.inputs else list_3mf_files(cwd, output)
    if not sources:
        raise RuntimeError("No source .3mf files found")

    for source in sources:
        if not source.exists():
            raise RuntimeError(f"Source file not found: {source}")

    source_plate_counts: dict[Path, int] = {}
    total_input_plates = 0
    for source in sources:
        with zipfile.ZipFile(source, "r") as zf:
            settings_root = parse_xml(zip_read_required(zf, "Metadata/model_settings.config", source))
            plate_count = len(settings_root.findall("plate"))
            source_plate_counts[source] = plate_count
            total_input_plates += plate_count

    if total_input_plates > SLICER_MAX_PLATES and not args.allow_over_max_plates:
        raise RuntimeError(
            f"merged project would contain {total_input_plates} plates, but Bambu Studio/OrcaSlicer "
            f"support at most {SLICER_MAX_PLATES}; split the inputs into multiple outputs"
        )

    staging_root = Path(tempfile.mkdtemp(prefix="merge_bambu_3mf_", dir="/tmp"))
    staging = staging_root / "package"
    staging.mkdir(parents=True)

    try:
        first = sources[0]
        with zipfile.ZipFile(first, "r") as first_zip:
            first_names = set(first_zip.namelist())
            output_project_settings = json.loads(
                zip_read_required(first_zip, "Metadata/project_settings.config", first)
            )
            output_width, output_depth = printable_size(output_project_settings)
            for member in (
                "[Content_Types].xml",
                "_rels/.rels",
                "Metadata/project_settings.config",
                "Metadata/slice_info.config",
                "Metadata/filament_sequence.json",
                "Metadata/brim_ear_points.txt",
            ):
                if member in first_names:
                    copy_zip_member(first_zip, member, staging / member)

            # Keep useful model-page auxiliary assets from the base package.
            for member in first_zip.namelist():
                if member.startswith("Auxiliaries/") and not member.endswith("/"):
                    copy_zip_member(first_zip, member, staging / member)

            combined_model_root = parse_xml(zip_read_required(first_zip, "3D/3dmodel.model", first))
            update_project_thumbnail_metadata(combined_model_root)
            combined_resources, combined_build = model_children(combined_model_root)
            for child in list(combined_resources):
                combined_resources.remove(child)
            for child in list(combined_build):
                combined_build.remove(child)

        combined_config_root = ET.Element("config")
        combined_config_objects: list[ET.Element] = []
        combined_config_plates: list[ET.Element] = []
        combined_config_assembles: list[ET.Element] = []
        rels_root = relationship_root()
        cut_root = ET.Element("objects")

        next_global_id = 1
        next_plate_id = 1
        next_identify_id = 1
        next_object_file_id = 1
        next_rel_id = 1
        output_cols = compute_column_count(total_input_plates)

        summary_rows: list[tuple[str, int, list[str]]] = []

        for source_index, source in enumerate(sources, start=1):
            with zipfile.ZipFile(source, "r") as zf:
                zip_names = set(zf.namelist())
                model_root = parse_xml(zip_read_required(zf, "3D/3dmodel.model", source))
                source_resources, source_build = model_children(model_root)
                settings_root = parse_xml(zip_read_required(zf, "Metadata/model_settings.config", source))
                source_project_settings = json.loads(zip_read_required(zf, "Metadata/project_settings.config", source))
                source_width, source_depth = printable_size(source_project_settings)
                source_cols = compute_column_count(source_plate_counts[source])
                old_object_to_plate = plate_object_map(settings_root)
                old_plate_to_new_plate: dict[str, int] = {}
                for source_plate_offset, plate in enumerate(settings_root.findall("plate")):
                    old_plate_id = metadata_value(plate, "plater_id") or str(source_plate_offset + 1)
                    old_plate_to_new_plate[old_plate_id] = next_plate_id + source_plate_offset
                source_object_final_transform: dict[str, str] = {}
                for item in list(source_build):
                    source_object_id = item.get("objectid")
                    if source_object_id is None:
                        continue
                    final_transform = item.get("transform")
                    old_plate_id = old_object_to_plate.get(source_object_id)
                    if old_plate_id in old_plate_to_new_plate:
                        dx, dy = translated_plate_delta(
                            old_plate_id,
                            old_plate_to_new_plate[old_plate_id],
                            source_cols,
                            source_width,
                            source_depth,
                            output_cols,
                            output_width,
                            output_depth,
                        )
                        final_transform = translate_transform(final_transform, dx, dy)
                    source_object_final_transform[source_object_id] = final_transform or identity_transform()
                source_ids = collect_source_ids(zf, model_root, zip_names)
                source_max_id = max(source_ids) if source_ids else 0
                id_offset = next_global_id - 1

                object_id_map: dict[str, str] = {}
                path_map: dict[str, str] = {}

                for object_element in list(source_resources):
                    source_object_id = object_element.get("id")
                    if source_object_id is None:
                        continue

                    new_object_id = str(int(source_object_id) + id_offset)
                    object_id_map[source_object_id] = new_object_id

                    object_copy = clone(object_element)
                    object_copy.set("id", new_object_id)
                    rewrite_uuids(object_copy)

                    for component in object_copy.iter(qname(CORE_NS, "component")):
                        old_component_object_id = component.get("objectid")
                        if old_component_object_id is not None:
                            component.set("objectid", str(int(old_component_object_id) + id_offset))
                        old_path = component.get(P_PATH)
                        if not old_path:
                            continue
                        normalized_old_path = str(PurePosixPath(old_path.lstrip("/")))
                        if normalized_old_path not in zip_names:
                            raise RuntimeError(f"{source.name} references missing object path {old_path}")
                        if normalized_old_path not in path_map:
                            new_path = f"3D/Objects/object_{next_object_file_id}.model"
                            next_object_file_id += 1
                            path_map[normalized_old_path] = new_path
                            sub_model_root = parse_xml(zf.read(normalized_old_path))
                            offset_model_ids(sub_model_root, id_offset)
                            write_xml(staging / new_path, sub_model_root)
                            add_relationship(rels_root, next_rel_id, f"/{new_path}")
                            next_rel_id += 1
                        component.set(P_PATH, f"/{path_map[normalized_old_path]}")

                    combined_resources.append(object_copy)

                for item in list(source_build):
                    source_object_id = item.get("objectid")
                    if source_object_id not in object_id_map:
                        continue
                    item_copy = clone(item)
                    item_copy.set("objectid", object_id_map[source_object_id])
                    item_copy.set("transform", source_object_final_transform[source_object_id])
                    if P_UUID in item_copy.attrib:
                        item_copy.set(P_UUID, fresh_uuid())
                    combined_build.append(item_copy)

                for config_object in settings_root.findall("object"):
                    source_object_id = config_object.get("id")
                    if source_object_id not in object_id_map:
                        continue
                    config_object_copy = clone(config_object)
                    config_object_copy.set("id", object_id_map[source_object_id])
                    for part in config_object_copy.findall("part"):
                        part_id = part.get("id")
                        if part_id is not None:
                            part.set("id", str(int(part_id) + id_offset))
                    for assemble_item in config_object_copy.findall(".//assemble_item"):
                        assemble_object_id = assemble_item.get("object_id")
                        if assemble_object_id is not None:
                            assemble_item.set("object_id", str(int(assemble_object_id) + id_offset))
                            old_plate_id = old_object_to_plate.get(assemble_object_id)
                            if old_plate_id in old_plate_to_new_plate:
                                dx, dy = translated_plate_delta(
                                    old_plate_id,
                                    old_plate_to_new_plate[old_plate_id],
                                    source_cols,
                                    source_width,
                                    source_depth,
                                    output_cols,
                                    output_width,
                                    output_depth,
                                )
                                translated = translate_transform(assemble_item.get("transform"), dx, dy)
                                if translated is not None:
                                    assemble_item.set("transform", translated)
                    combined_config_objects.append(config_object_copy)

                for assemble in settings_root.findall("assemble"):
                    assemble_copy = clone(assemble)
                    for assemble_item in assemble_copy.findall("assemble_item"):
                        assemble_object_id = assemble_item.get("object_id")
                        if assemble_object_id is None:
                            continue
                        old_plate_id = old_object_to_plate.get(assemble_object_id)
                        assemble_item.set("object_id", str(int(assemble_object_id) + id_offset))
                        if old_plate_id in old_plate_to_new_plate:
                            dx, dy = translated_plate_delta(
                                old_plate_id,
                                old_plate_to_new_plate[old_plate_id],
                                source_cols,
                                source_width,
                                source_depth,
                                output_cols,
                                output_width,
                                output_depth,
                            )
                            translated = translate_transform(assemble_item.get("transform"), dx, dy)
                            if translated is not None:
                                assemble_item.set("transform", translated)
                    combined_config_assembles.append(assemble_copy)

                plate_names: list[str] = []
                for plate in settings_root.findall("plate"):
                    plate_copy = clone(plate)
                    old_plate_id = metadata_value(plate, "plater_id") or "1"
                    plate_name = metadata_value(plate, "plater_name") or ""
                    plate_names.append(plate_name)

                    set_metadata_value(plate_copy, "plater_id", str(next_plate_id))
                    update_plate_artifact_refs(plate_copy, next_plate_id)
                    copy_plate_artifacts(zf, zip_names, staging, old_plate_id, next_plate_id)

                    for instance in plate_copy.findall("model_instance"):
                        source_object_id = metadata_value(instance, "object_id")
                        if source_object_id in object_id_map:
                            set_metadata_value(instance, "object_id", object_id_map[source_object_id])
                        if metadata_value(instance, "identify_id") is not None:
                            set_metadata_value(instance, "identify_id", str(next_identify_id))
                            next_identify_id += 1

                    combined_config_plates.append(plate_copy)
                    next_plate_id += 1

                for source_object_id, new_object_id in object_id_map.items():
                    cut_object = ET.SubElement(cut_root, "object", {"id": new_object_id})
                    ET.SubElement(
                        cut_object,
                        "cut_id",
                        {"id": "0", "check_sum": "1", "connectors_cnt": "0"},
                    )

                summary_rows.append((source.name, len(plate_names), plate_names))
                next_global_id += source_max_id

        total_plates = next_plate_id - 1

        for element in combined_config_objects:
            combined_config_root.append(element)
        for element in combined_config_plates:
            combined_config_root.append(element)
        for element in combined_config_assembles:
            combined_config_root.append(element)

        write_xml(staging / "3D/3dmodel.model", combined_model_root)
        write_xml(staging / "Metadata/model_settings.config", combined_config_root)
        write_xml(staging / "3D/_rels/3dmodel.model.rels", rels_root)
        write_xml(staging / "Metadata/cut_information.xml", cut_root)

        tmp_output = staging_root / output.name
        with zipfile.ZipFile(tmp_output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as out_zip:
            for path in sorted(staging.rglob("*")):
                if path.is_file():
                    out_zip.write(path, path.relative_to(staging).as_posix())

        output.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(tmp_output), output)

        total_objects = len(combined_resources.findall(qname(CORE_NS, "object")))
        print(f"Wrote {output}")
        print(f"Merged {len(sources)} source files, {total_plates} plates, {total_objects} model objects.")
        for source_name, count, plate_names in summary_rows:
            display_names = ", ".join(name if name else "(unnamed)" for name in plate_names)
            print(f"- {source_name}: {count} plate(s): {display_names}")
    finally:
        shutil.rmtree(staging_root, ignore_errors=True)

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)

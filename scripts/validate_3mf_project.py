#!/usr/bin/env python3
"""Validate Bambu/Orca 3MF project references after merge or deduplication."""

from __future__ import annotations

import argparse
import sys
import zipfile
from collections import Counter
from pathlib import Path
import xml.etree.ElementTree as ET


CORE_NS = "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"


def qname(namespace: str, tag: str) -> str:
    return f"{{{namespace}}}{tag}"


def metadata_value(element: ET.Element, key: str) -> str | None:
    for metadata in element.findall("metadata"):
        if metadata.get("key") == key:
            return metadata.get("value")
    return None


def parse_xml_from_zip(zf: zipfile.ZipFile, name: str) -> ET.Element | None:
    try:
        data = zf.read(name)
    except KeyError:
        return None
    return ET.fromstring(data)


def validate(path: Path) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    try:
        zf = zipfile.ZipFile(path, "r")
    except zipfile.BadZipFile as exc:
        return [f"not a valid ZIP archive: {exc}"], warnings

    with zf:
        bad_members = zf.testzip()
        if bad_members:
            errors.append(f"ZIP CRC check failed at {bad_members}")

        names = set(zf.namelist())
        name_counts = Counter(zf.namelist())
        for name, count in sorted(name_counts.items()):
            if count > 1:
                warnings.append(f"duplicate ZIP entry: {name} appears {count} times")

        model_root = parse_xml_from_zip(zf, "3D/3dmodel.model")
        if model_root is None:
            errors.append("missing 3D/3dmodel.model")
            model_object_ids: set[str] = set()
            build_object_ids: set[str] = set()
        else:
            resources = model_root.find(qname(CORE_NS, "resources"))
            build = model_root.find(qname(CORE_NS, "build"))
            model_object_ids = {
                obj.get("id", "")
                for obj in (list(resources) if resources is not None else [])
                if obj.tag == qname(CORE_NS, "object") and obj.get("id")
            }
            build_object_ids = {
                item.get("objectid", "")
                for item in (list(build) if build is not None else [])
                if item.tag == qname(CORE_NS, "item") and item.get("objectid")
            }
            for object_id in sorted(build_object_ids - model_object_ids, key=int_key):
                errors.append(f"build item references missing 3D model object id {object_id}")

        settings_root = parse_xml_from_zip(zf, "Metadata/model_settings.config")
        if settings_root is None:
            warnings.append("missing Metadata/model_settings.config")
            return errors, warnings

        config_object_ids = {
            obj.get("id", "")
            for obj in settings_root.findall("object")
            if obj.get("id")
        }
        for object_id in sorted(config_object_ids - model_object_ids, key=int_key):
            errors.append(f"model_settings object id {object_id} is missing from 3D/3dmodel.model")
        for object_id in sorted(model_object_ids - config_object_ids, key=int_key):
            warnings.append(f"3D model object id {object_id} has no model_settings object")

        for obj in settings_root.findall("object"):
            object_id = obj.get("id", "")
            source_file = metadata_value(obj, "source_file")
            if source_file and source_file.startswith("3D/Objects/") and source_file not in names:
                errors.append(f"object id {object_id} references missing source_file {source_file}")

        used_plate_indices: set[int] = set()
        for plate_index, plate in enumerate(settings_root.findall("plate"), start=1):
            plate_name = metadata_value(plate, "plater_name") or metadata_value(plate, "name") or str(plate_index)
            model_instances = plate.findall("model_instance")
            if not model_instances:
                warnings.append(f"plate {plate_index} ({plate_name}) has no model_instance entries")
            for instance in model_instances:
                object_id = metadata_value(instance, "object_id")
                if not object_id:
                    errors.append(f"plate {plate_index} ({plate_name}) has a model_instance without object_id")
                    continue
                used_plate_indices.add(plate_index)
                if object_id not in config_object_ids:
                    errors.append(f"plate {plate_index} ({plate_name}) references missing settings object id {object_id}")
                if object_id not in model_object_ids:
                    errors.append(f"plate {plate_index} ({plate_name}) references missing 3D model object id {object_id}")

        for assemble in settings_root.findall("assemble"):
            for item in assemble.findall("assemble_item"):
                object_id = item.get("object_id")
                if object_id and object_id not in config_object_ids:
                    errors.append(f"assemble_item references missing settings object id {object_id}")

        for plate_index in used_plate_indices:
            for suffix in ("", "_small"):
                image_name = f"Metadata/plate_{plate_index}{suffix}.png"
                if image_name not in names:
                    warnings.append(f"used plate {plate_index} has no thumbnail {image_name}")

    return errors, warnings


def int_key(value: str) -> tuple[int, str]:
    try:
        return (0, f"{int(value):010d}")
    except ValueError:
        return (1, value)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+", type=Path)
    args = parser.parse_args()

    exit_code = 0
    for path in args.paths:
        errors, warnings = validate(path)
        print(path)
        if not errors and not warnings:
            print("  OK")
            continue
        for error in errors:
            print(f"  ERROR: {error}")
        for warning in warnings:
            print(f"  WARNING: {warning}")
        if errors:
            exit_code = 1
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())

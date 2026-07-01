#!/usr/bin/env python3
"""Inspect Bambu/Orca 3MF plate-to-object assignments."""

from __future__ import annotations

import argparse
from pathlib import Path
import zipfile
import xml.etree.ElementTree as ET


CORE_NS = "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"


def qname(namespace: str, name: str) -> str:
    return f"{{{namespace}}}{name}"


def metadata_value(element: ET.Element, key: str) -> str | None:
    for child in list(element):
        if child.tag == "metadata" and child.get("key") == key:
            return child.get("value")
    return None


def object_name_map(settings_root: ET.Element) -> dict[str, str]:
    names: dict[str, str] = {}
    for obj in settings_root.findall("object"):
        object_id = obj.get("id")
        if object_id is None:
            continue
        names[object_id] = metadata_value(obj, "name") or ""
    return names


def inspect(path: Path) -> None:
    with zipfile.ZipFile(path, "r") as zf:
        settings_root = ET.fromstring(zf.read("Metadata/model_settings.config"))
        model_root = ET.fromstring(zf.read("3D/3dmodel.model"))

    build_items = [
        item.get("objectid")
        for item in model_root.findall(f".//{qname(CORE_NS, 'build')}/{qname(CORE_NS, 'item')}")
    ]
    names = object_name_map(settings_root)
    print(path)
    print(f"build items: {len(build_items)}")
    print(f"config objects: {len(names)}")
    print(f"plates: {len(settings_root.findall('plate'))}")
    for plate in settings_root.findall("plate"):
        plate_id = metadata_value(plate, "plater_id") or "?"
        plate_name = metadata_value(plate, "plater_name") or ""
        object_ids = [
            metadata_value(instance, "object_id") or "?"
            for instance in plate.findall("model_instance")
        ]
        display = ", ".join(
            f"{object_id}:{names.get(object_id, '')}".rstrip(":")
            for object_id in object_ids[:8]
        )
        suffix = "" if len(object_ids) <= 8 else f", ... +{len(object_ids) - 8}"
        print(f"{plate_id:>2} {plate_name:<42} {len(object_ids):>3} [{display}{suffix}]")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+", type=Path)
    args = parser.parse_args()
    for index, path in enumerate(args.paths):
        if index:
            print()
        inspect(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

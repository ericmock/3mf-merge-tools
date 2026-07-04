#!/usr/bin/env python3
"""Review 3MF files for duplicate model geometry."""

from __future__ import annotations

import argparse
import glob
import hashlib
import json
from pathlib import Path
import sys
import zipfile
import xml.etree.ElementTree as ET


CORE_NS = "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"
PROD_NS = "http://schemas.microsoft.com/3dmanufacturing/production/2015/06"
P_PATH = f"{{{PROD_NS}}}path"


def qname(namespace: str, name: str) -> str:
    return f"{{{namespace}}}{name}"


def local_name(name: str) -> str:
    if "}" in name:
        return name.rsplit("}", 1)[1]
    return name


def list_3mf_files(cwd: Path) -> list[Path]:
    files = [Path(p) for p in glob.glob(str(cwd / "*.3mf"))]
    files.extend(Path(p) for p in glob.glob(str(cwd / "*.3MF")))
    return sorted({p.resolve() for p in files})


def metadata_value(element: ET.Element, key: str) -> str | None:
    for child in list(element):
        if child.tag == "metadata" and child.get("key") == key:
            return child.get("value")
    return None


def normalized_number(value: str) -> str:
    try:
        number = float(value)
    except ValueError:
        return value
    if abs(number) < 1e-9:
        number = 0.0
    return f"{number:.9g}"


def normalized_attr_value(value: str) -> str:
    parts = value.split()
    if len(parts) > 1:
        return " ".join(normalized_number(part) for part in parts)
    return normalized_number(value)


def update_canonical_hash(hasher: "hashlib._Hash", element: ET.Element) -> None:
    ignored_attrs = {"id", "UUID", "path"}
    hasher.update(f"<{local_name(element.tag)}".encode("utf-8"))
    attrs = []
    for key, value in element.attrib.items():
        if local_name(key) in ignored_attrs:
            continue
        attrs.append((local_name(key), normalized_attr_value(value)))
    for key, value in sorted(attrs):
        hasher.update(f"|{key}={value}".encode("utf-8"))
    text = (element.text or "").strip()
    if text:
        hasher.update(f">{text}".encode("utf-8"))
    for child in list(element):
        update_canonical_hash(hasher, child)
    hasher.update(f"</{local_name(element.tag)}>".encode("utf-8"))


def canonical_element_hash(element: ET.Element) -> str:
    hasher = hashlib.sha256()
    update_canonical_hash(hasher, element)
    return hasher.hexdigest()


def parse_config(zf: zipfile.ZipFile) -> tuple[dict[str, str], dict[str, list[str]], dict[str, str]]:
    names: dict[str, str] = {}
    plates: dict[str, list[str]] = {}
    face_counts: dict[str, str] = {}
    try:
        root = ET.fromstring(zf.read("Metadata/model_settings.config"))
    except KeyError:
        return names, plates, face_counts

    for obj in root.findall("object"):
        object_id = obj.get("id")
        if object_id is None:
            continue
        names[object_id] = metadata_value(obj, "name") or ""
        for child in list(obj):
            if child.tag == "metadata" and child.get("face_count"):
                face_counts[object_id] = child.get("face_count") or ""

    for plate in root.findall("plate"):
        plate_name = metadata_value(plate, "plater_name") or ""
        plate_id = metadata_value(plate, "plater_id") or "?"
        label = plate_name if plate_name else f"plate {plate_id}"
        for instance in plate.findall("model_instance"):
            object_id = metadata_value(instance, "object_id")
            if object_id is not None:
                plates.setdefault(object_id, []).append(label)

    return names, plates, face_counts


def model_paths(zf: zipfile.ZipFile) -> list[str]:
    paths = ["3D/3dmodel.model"]
    paths.extend(
        name
        for name in sorted(zf.namelist())
        if name.startswith("3D/Objects/") and name.endswith(".model")
    )
    return paths


def load_model_objects(zf: zipfile.ZipFile) -> dict[tuple[str, str], ET.Element]:
    objects: dict[tuple[str, str], ET.Element] = {}
    for model_path in model_paths(zf):
        try:
            root = ET.fromstring(zf.read(model_path))
        except KeyError:
            continue
        resources = root.find(qname(CORE_NS, "resources"))
        if resources is None:
            continue
        for obj in resources.findall(qname(CORE_NS, "object")):
            object_id = obj.get("id")
            if object_id is not None:
                objects[(model_path, object_id)] = obj
    return objects


def top_level_object_ids(zf: zipfile.ZipFile, names: dict[str, str]) -> list[str]:
    ids: list[str] = []
    try:
        root = ET.fromstring(zf.read("3D/3dmodel.model"))
    except KeyError:
        return sorted(names)

    build = root.find(qname(CORE_NS, "build"))
    if build is not None:
        ids.extend(
            object_id
            for object_id in (item.get("objectid") for item in build.findall(qname(CORE_NS, "item")))
            if object_id is not None
        )

    ids.extend(names)
    return sorted(set(ids), key=lambda value: (0, int(value)) if value.isdigit() else (1, value))


def resolve_component_path(current_path: str, component: ET.Element) -> str:
    component_path = component.get(P_PATH) or component.get("path")
    if component_path:
        return component_path.lstrip("/")
    return current_path


def object_signature(
    objects: dict[tuple[str, str], ET.Element],
    model_path: str,
    object_id: str,
    cache: dict[tuple[str, str], str],
    stack: set[tuple[str, str]] | None = None,
) -> str:
    key = (model_path, object_id)
    if key in cache:
        return cache[key]
    if stack is None:
        stack = set()
    if key in stack:
        return f"cycle:{model_path}:{object_id}"
    stack.add(key)

    obj = objects.get(key)
    if obj is None:
        stack.remove(key)
        return f"missing:{model_path}:{object_id}"

    mesh = obj.find(qname(CORE_NS, "mesh"))
    if mesh is not None:
        signature = "mesh:" + canonical_element_hash(mesh)
    else:
        components = obj.find(qname(CORE_NS, "components"))
        if components is None:
            signature = "empty"
        else:
            parts = []
            for component in components.findall(qname(CORE_NS, "component")):
                child_path = resolve_component_path(model_path, component)
                child_id = component.get("objectid") or ""
                transform = normalized_attr_value(component.get("transform") or "")
                child_sig = object_signature(objects, child_path, child_id, cache, stack)
                parts.append(f"component:{transform}:{child_sig}")
            signature = "components:" + "|".join(parts)

    stack.remove(key)
    cache[key] = signature
    return signature


def short_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def review_file(path: Path) -> dict:
    with zipfile.ZipFile(path, "r") as zf:
        names, plates, face_counts = parse_config(zf)
        objects = load_model_objects(zf)
        top_ids = top_level_object_ids(zf, names)

    occurrences = []
    signature_cache: dict[tuple[str, str], str] = {}
    for object_id in top_ids:
        signature = object_signature(objects, "3D/3dmodel.model", object_id, signature_cache)
        if signature == "empty" or signature.startswith("missing:"):
            continue
        occurrences.append(
            {
                "file": str(path),
                "object_id": object_id,
                "name": names.get(object_id, ""),
                "plates": plates.get(object_id, []),
                "face_count": face_counts.get(object_id, ""),
                "signature": short_hash(signature),
            }
        )

    groups_by_signature: dict[str, list[dict]] = {}
    for occurrence in occurrences:
        groups_by_signature.setdefault(occurrence["signature"], []).append(occurrence)

    duplicate_groups = [
        {"signature": signature, "occurrences": items}
        for signature, items in sorted(groups_by_signature.items())
        if len(items) > 1
    ]

    return {
        "file": str(path),
        "reviewed_models": len(occurrences),
        "duplicate_group_count": len(duplicate_groups),
        "duplicate_model_count": sum(len(group["occurrences"]) for group in duplicate_groups),
        "duplicate_groups": duplicate_groups,
        "models": occurrences,
    }


def cross_file_duplicate_groups(file_reports: list[dict]) -> list[dict]:
    by_signature: dict[str, list[dict]] = {}
    for report in file_reports:
        for occurrence in report["models"]:
            by_signature.setdefault(occurrence["signature"], []).append(occurrence)

    return [
        {"signature": signature, "occurrences": occurrences}
        for signature, occurrences in sorted(by_signature.items())
        if len({item["file"] for item in occurrences}) > 1
    ]


def print_report(report: dict, verbose: bool) -> None:
    print(report["file"])
    print(f"  reviewed models: {report['reviewed_models']}")
    print(f"  duplicate groups: {report['duplicate_group_count']}")
    if not report["duplicate_groups"]:
        return
    for index, group in enumerate(report["duplicate_groups"], start=1):
        print(f"  group {index}: {len(group['occurrences'])} matching models ({group['signature']})")
        for occurrence in group["occurrences"]:
            name = occurrence["name"] or "(unnamed)"
            plates = ", ".join(occurrence["plates"]) if occurrence["plates"] else "(no plate assignment)"
            face_count = f", faces: {occurrence['face_count']}" if occurrence["face_count"] else ""
            print(f"    object {occurrence['object_id']}: {name}{face_count}; plates: {plates}")
        if not verbose and index >= 20:
            remaining = len(report["duplicate_groups"]) - index
            if remaining:
                print(f"    ... {remaining} more duplicate group(s); rerun with --verbose to show all")
            break


def print_cross_file_report(groups: list[dict], verbose: bool) -> None:
    print("Cross-file duplicate models")
    print(f"  duplicate groups: {len(groups)}")
    for index, group in enumerate(groups, start=1):
        print(f"  group {index}: {len(group['occurrences'])} matching models ({group['signature']})")
        for occurrence in group["occurrences"]:
            name = occurrence["name"] or "(unnamed)"
            file_name = Path(occurrence["file"]).name
            plates = ", ".join(occurrence["plates"]) if occurrence["plates"] else "(no plate assignment)"
            face_count = f", faces: {occurrence['face_count']}" if occurrence["face_count"] else ""
            print(f"    {file_name} object {occurrence['object_id']}: {name}{face_count}; plates: {plates}")
        if not verbose and index >= 20:
            remaining = len(groups) - index
            if remaining:
                print(f"    ... {remaining} more cross-file duplicate group(s); rerun with --verbose to show all")
            break


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "paths",
        nargs="*",
        type=Path,
        help="3MF files to review. Defaults to all .3mf files in the current folder.",
    )
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    parser.add_argument("--verbose", action="store_true", help="Show every duplicate group.")
    parser.add_argument(
        "--fail-on-duplicates",
        action="store_true",
        help="Exit with status 2 when duplicate models are found.",
    )
    parser.add_argument(
        "--cross-file",
        action="store_true",
        help="Also report duplicate model geometry that appears in more than one input file.",
    )
    args = parser.parse_args()

    paths = [path.resolve() for path in args.paths] if args.paths else list_3mf_files(Path.cwd())
    if not paths:
        raise RuntimeError("No .3mf files found")

    reports = []
    errors = []
    for path in paths:
        try:
            reports.append(review_file(path))
        except Exception as exc:
            errors.append({"file": str(path), "error": str(exc)})

    cross_groups = cross_file_duplicate_groups(reports) if args.cross_file else []
    output = {"files": reports, "cross_file_duplicate_groups": cross_groups, "errors": errors}
    if args.json:
        print(json.dumps(output, indent=2))
    else:
        for index, report in enumerate(reports):
            if index:
                print()
            print_report(report, args.verbose)
        if args.cross_file:
            print()
            print_cross_file_report(cross_groups, args.verbose)
        if errors:
            print()
            print("Errors:")
            for error in errors:
                print(f"  {error['file']}: {error['error']}")

    if errors:
        return 1
    if args.fail_on_duplicates and (any(report["duplicate_group_count"] for report in reports) or cross_groups):
        return 2
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)

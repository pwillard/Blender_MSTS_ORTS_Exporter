#!/usr/bin/env python
"""Build GitHub release ZIP files for the Blender MSTS/ORTS exporter.

Creates two separate archives:
- Blender-installable add-on ZIP containing io_export_mstsexporter/
- Documentation ZIP containing MstsExporterDocumentation/ plus top-level docs
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import shutil
import sys
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


ROOT = Path(__file__).resolve().parent
ADDON_DIR = ROOT / "io_export_mstsexporter"
DOCS_DIR = ROOT / "MstsExporterDocumentation"
DEFAULT_OUTPUT_DIR = ROOT / "dist"
ADDON_PREFIX = "io_export_mstsexporter"
DOCS_PREFIX = "MstsExporterDocumentation"
EXCLUDED_DIR_NAMES = {"__pycache__", ".git", ".pytest_cache"}
EXCLUDED_SUFFIXES = {".pyc", ".pyo"}


class PackageError(RuntimeError):
    pass


def read_exporter_version() -> str:
    exporter_path = ADDON_DIR / "export_msts.py"
    try:
        module_ast = ast.parse(exporter_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise PackageError(f"Unable to read {exporter_path}: {exc}") from exc

    for node in module_ast.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "bl_info":
                    bl_info = ast.literal_eval(node.value)
                    version = bl_info.get("version")
                    if not isinstance(version, tuple):
                        raise PackageError("bl_info['version'] is not a tuple")
                    return ".".join(str(part) for part in version)

    raise PackageError(f"Could not find bl_info version in {exporter_path}")


def iter_files(base_dir: Path):
    if not base_dir.is_dir():
        raise PackageError(f"Missing required directory: {base_dir}")

    for path in sorted(base_dir.rglob("*")):
        if not path.is_file():
            continue
        relative_parts = path.relative_to(base_dir).parts
        if any(part in EXCLUDED_DIR_NAMES for part in relative_parts):
            continue
        if path.suffix.lower() in EXCLUDED_SUFFIXES:
            continue
        yield path


def write_zip(zip_path: Path, entries: list[tuple[Path, str]]) -> None:
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(zip_path, "w", compression=ZIP_DEFLATED) as zf:
        for source_path, archive_name in entries:
            zf.write(source_path, archive_name)


def build_addon_entries() -> list[tuple[Path, str]]:
    entries: list[tuple[Path, str]] = []
    for source_path in iter_files(ADDON_DIR):
        archive_name = Path(ADDON_PREFIX) / source_path.relative_to(ADDON_DIR)
        entries.append((source_path, archive_name.as_posix()))

    required_archive_names = {
        f"{ADDON_PREFIX}/__init__.py",
        f"{ADDON_PREFIX}/export_msts.py",
    }
    archive_names = {archive_name for _, archive_name in entries}
    missing = sorted(required_archive_names - archive_names)
    if missing:
        raise PackageError(f"Add-on ZIP would be missing required files: {', '.join(missing)}")

    return entries


def build_docs_entries() -> list[tuple[Path, str]]:
    entries: list[tuple[Path, str]] = []
    for source_path in iter_files(DOCS_DIR):
        archive_name = Path(DOCS_PREFIX) / source_path.relative_to(DOCS_DIR)
        entries.append((source_path, archive_name.as_posix()))

    for top_level_name in ("README.MD", "GPL LICENSE.txt"):
        source_path = ROOT / top_level_name
        if source_path.is_file():
            entries.append((source_path, top_level_name))

    if not entries:
        raise PackageError(f"Documentation ZIP would be empty: {DOCS_DIR}")

    return entries


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def describe_entries(label: str, entries: list[tuple[Path, str]]) -> None:
    print(f"{label}: {len(entries)} files")
    for _, archive_name in entries:
        print(f"  {archive_name}")


def build_release(output_dir: Path, clean: bool, dry_run: bool) -> int:
    version = read_exporter_version()
    addon_zip = output_dir / f"MSTS_ORTS_Exporter_AddOn_v{version}.zip"
    docs_zip = output_dir / f"MSTS_ORTS_Exporter_Documentation_v{version}.zip"

    addon_entries = build_addon_entries()
    docs_entries = build_docs_entries()

    if dry_run:
        print(f"Version: {version}")
        print(f"Output directory: {output_dir}")
        describe_entries("Add-on ZIP", addon_entries)
        describe_entries("Documentation ZIP", docs_entries)
        return 0

    if clean and output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    write_zip(addon_zip, addon_entries)
    write_zip(docs_zip, docs_entries)

    release_files = (addon_zip, docs_zip)
    checksums_path = output_dir / "SHA256SUMS.txt"
    checksum_lines = [f"{sha256_file(path)}  {path.name}\n" for path in release_files]
    checksums_path.write_text("".join(checksum_lines), encoding="utf-8", newline="\n")

    print(f"Version: {version}")
    for path in release_files:
        size = path.stat().st_size
        print(f"Created: {path} ({size:,} bytes)")
    print(f"Created: {checksums_path}")
    return 0


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create add-on and documentation ZIP files for a GitHub release."
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory to write release ZIP files into. Default: ./dist",
    )
    parser.add_argument(
        "--no-clean",
        action="store_true",
        help="Do not remove the output directory before packaging.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List package contents without creating ZIP files.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        return build_release(
            output_dir=args.output_dir,
            clean=not args.no_clean,
            dry_run=args.dry_run,
        )
    except PackageError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

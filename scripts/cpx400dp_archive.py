#!/usr/bin/env python3
"""Safely archive an experiment CSV and any matching report/console sidecars.

This program never deletes or modifies source files and never contacts
a PSU. ZIP creation is atomic and no-clobber on normal Linux filesystems.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile
import zipfile

BLOCK = 1024 * 1024


def _digest(source):
    h = hashlib.sha256()
    with source.open("rb") as stream:
        for piece in iter(lambda: stream.read(BLOCK), b""):
            h.update(piece)
    return h.hexdigest()


def gather(measurements):
    """Return flat source paths and paths inside the archive."""
    path = Path(measurements).resolve(strict=True)
    if not path.is_file() or not path.name.endswith(".csv"):
        raise ValueError("Input must be an existing measurement CSV")
    if "_measurements" not in path.stem:
        raise ValueError("Input name must contain _measurements")
    parent = path.parent
    stem = path.stem
    relatives = [path]
    for target_stem in (stem.replace("_measurements", "_report", 1),
                        stem.replace("_measurements", "_console", 1)):
        for suffix in ((".html",) if "_report" in target_stem else (".log",)):
            candidate = parent / (target_stem + suffix)
            if candidate.is_file():
                relatives.append(candidate)
    data_folder = parent / (stem.replace("_measurements", "_report", 1) + "_data")
    report_path = parent / (stem.replace("_measurements", "_report", 1) + ".html")
    # Do not silently produce a portable ZIP that loses the raw detail
    # files needed by the new large-recording HTML viewer.
    if report_path.is_file() and not data_folder.is_dir():
        with report_path.open(encoding="utf-8", errors="replace") as report_stream:
            if any("This large-recording report uses local detail chunks" in line
                   for line in report_stream):
                raise ValueError("Streaming report is missing its companion data directory")
    if data_folder.is_dir():
        # A large report must not be archived without its matching HTML.
        report_path = parent / (stem.replace("_measurements", "_report", 1) + ".html")
        if report_path not in relatives:
            raise ValueError("Report data directory exists without matching report HTML")
        relatives.extend(sorted(p for p in data_folder.rglob("*") if p.is_file()))
    result = []
    for file in relatives:
        # Reject symlinks anywhere below the output folder to prevent
        # unintended external-file inclusion.
        if file.is_symlink() or any(p.is_symlink() for p in file.parents if p != parent):
            raise ValueError("Symlinks are not allowed in experiment archive inputs")
        relative = file.relative_to(parent)
        if not file.is_file():
            raise ValueError("Non-file archive input: " + str(file))
        result.append((file, relative.as_posix()))
    return result


def archive(measurements, destination=None):
    source = Path(measurements).resolve(strict=True)
    if destination is None:
        target = source.with_name(source.stem + "_archive.zip")
    else:
        target = Path(destination).expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        raise FileExistsError("Refusing to overwrite existing archive: " + str(target))
    files = gather(source)
    if not files:
        raise ValueError("No files to archive")
    temp_path = None
    try:
        fd, tempname = tempfile.mkstemp(prefix=".cpx_archive_", suffix=".tmp",
                                        dir=target.parent)
        temp_path = Path(tempname)
        with os.fdopen(fd, "wb") as stream:
            manifest = {"format": 1, "source": source.name, "files": {}}
            with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED,
                                 compresslevel=6, allowZip64=True) as zf:
                for file, name in files:
                    stat_before = file.stat()
                    checksum = _digest(file)
                    zf.write(file, name)
                    stat_after = file.stat()
                    if (stat_before.st_size != stat_after.st_size or
                            stat_before.st_mtime_ns != stat_after.st_mtime_ns):
                        raise RuntimeError("Source changed during archive: " + str(file))
                    manifest["files"][name] = {
                        "size": stat_after.st_size, "sha256": checksum}
                zf.writestr("MANIFEST.json", json.dumps(manifest, indent=2))
            stream.flush()
            os.fsync(stream.fileno())
        # Verify actual ZIP content, not just the original files.
        with zipfile.ZipFile(temp_path, "r") as check:
            if check.testzip() is not None:
                raise RuntimeError("ZIP integrity verification failed")
            for name, metadata in manifest["files"].items():
                digest = hashlib.sha256()
                size = 0
                with check.open(name) as data:
                    for block in iter(lambda: data.read(BLOCK), b""):
                        digest.update(block)
                        size += len(block)
                if digest.hexdigest() != metadata["sha256"] or size != metadata["size"]:
                    raise RuntimeError("Archived content checksum mismatch: " + name)
        # Hard-link then unlink the temp: atomic publish and never overwrite.
        os.link(temp_path, target)
        return target
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("measurements", type=Path)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args(argv)
    try:
        result = archive(args.measurements, args.output)
    except (OSError, ValueError, RuntimeError, zipfile.BadZipFile) as error:
        parser.exit(1, "ARCHIVE ERROR: " + str(error) + "\n")
    print("Archived and verified:", result)
    print("Source data retained unchanged; never delete raw logs automatically.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

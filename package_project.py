"""Create the distributable WorkSync AI source zip."""

from __future__ import annotations

import hashlib
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "WorkSyncAI"
OUTPUT = ROOT / "WorkSyncAI.zip"

EXCLUDED_DIRS = {
    "node_modules",
    ".venv",
    "__pycache__",
    ".pytest_cache",
    ".vite",
    "_tmp",
    "pytest_tmp",
    "chrome-profile",
    "chrome-shot",
    "chrome-shot2",
    "chrome-shot3",
    "chrome-shot4",
    "chrome2",
    "chrome3",
    "chrome4",
    "repro_run_b",
    "starter_data",
    "pytest-cache-files-5ktjjws_",
    "pytest-cache-files-e80zxx9y",
    ".tmp",
}

EXCLUDED_SUFFIXES = {".pyc", ".pyo", ".log"}
EXCLUDED_FILES = {
    "package_project.py",
    "backend/worksync.db",
    "backend/worksync.db-wal",
    "backend/worksync.db-shm",
    "backend/test_worksync.db",
    "frontend/package-lock.json.tmp",
}

# The frontend build is included so the static preview works immediately.
# Source remains authoritative and can be rebuilt with `npm run build`.
INCLUDED_ARTIFACTS = {
    "artifacts/evaluation.json",
    "artifacts/reproducibility.json",
}


def is_excluded(relative: Path) -> bool:
    if relative.as_posix() in EXCLUDED_FILES:
        return True
    if relative.suffix in EXCLUDED_SUFFIXES:
        return True
    if relative.parts and relative.parts[0] == "artifacts":
        return relative.as_posix() not in INCLUDED_ARTIFACTS
    return any(part in EXCLUDED_DIRS for part in relative.parts)


def main() -> int:
    if not PROJECT.is_dir():
        raise SystemExit(f"Project directory not found: {PROJECT}")
    if OUTPUT.exists():
        OUTPUT.unlink()

    files = [
        path for path in sorted(PROJECT.rglob("*"))
        if path.is_file() and not is_excluded(path.relative_to(PROJECT))
    ]

    with zipfile.ZipFile(OUTPUT, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in files:
            relative = path.relative_to(PROJECT)
            archive.write(path, (Path("WorkSyncAI") / relative).as_posix())

    with zipfile.ZipFile(OUTPUT) as archive:
        bad = archive.testzip()
        if bad:
            raise SystemExit(f"Corrupt zip member: {bad}")
        names = archive.namelist()

    digest = hashlib.sha256(OUTPUT.read_bytes()).hexdigest()
    size_mb = OUTPUT.stat().st_size / 1024 / 1024
    print(f"Created {OUTPUT}")
    print(f"Files: {len(names)}")
    print(f"Size: {size_mb:.2f} MB")
    print(f"SHA256: {digest}")
    print("Top-level entries:")
    for name in sorted({name.split("/")[0] + "/" for name in names}):
        print(" ", name)
    for forbidden in ("node_modules", ".venv", "worksync.db", "__pycache__", ".pytest_cache"):
        if any(forbidden in name for name in names):
            print(f"WARNING: zip contains {forbidden}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

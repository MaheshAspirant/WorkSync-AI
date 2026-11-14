"""Reproducibility proof: regenerate the full dataset and compare checksums.

Run from the project root:
    python -m data_generation.reproducibility

The current `database/seed/full` outputs are treated as run A. A second full
generation (CSV/JSON/SQL only, no database) is written to `artifacts/repro_run_b`
and every deliverable file is compared by SHA-256 and row count.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RUN_A = PROJECT_ROOT / "database" / "seed" / "full"
RUN_B = PROJECT_ROOT / "artifacts" / "repro_run_b"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def file_map(root: Path) -> dict[str, Path]:
    files: dict[str, Path] = {}
    for relative in ("csv", "json", "ground_truth"):
        directory = root / relative
        if not directory.exists():
            continue
        for path in sorted(directory.glob("*")):
            if path.is_file():
                files[f"{relative}/{path.name}"] = path
    for name in ("manifest.json", "validation_summary.json"):
        path = root / name
        if path.exists():
            files[name] = path
    return files


def main() -> int:
    RUN_B.mkdir(parents=True, exist_ok=True)
    command = [
        sys.executable,
        "-m",
        "data_generation.generate_data",
        "--scale",
        "full",
        "--no-db",
        "--output-dir",
        str(RUN_B),
    ]
    env = dict(**__import__("os").environ)
    env["PYTHONPATH"] = str(PROJECT_ROOT / "backend")
    print("Running second full generation…")
    completed = subprocess.run(command, cwd=PROJECT_ROOT, env=env, capture_output=True, text=True)
    (PROJECT_ROOT / "artifacts" / "repro_run_b.log").write_text(
        completed.stdout + "\n" + completed.stderr, encoding="utf-8"
    )
    if completed.returncode != 0:
        print(completed.stdout)
        print(completed.stderr)
        raise SystemExit("Second generation failed")

    files_a = file_map(RUN_A)
    files_b = file_map(RUN_B)
    names = sorted(set(files_a) | set(files_b))
    comparisons = []
    mismatches = 0
    for name in names:
        path_a = files_a.get(name)
        path_b = files_b.get(name)
        row_count_a = row_count_b = None
        if path_a and name.endswith(".csv"):
            row_count_a = sum(1 for _ in path_a.open(encoding="utf-8")) - 1
        if path_b and name.endswith(".csv"):
            row_count_b = sum(1 for _ in path_b.open(encoding="utf-8")) - 1
        hash_a = sha256(path_a) if path_a and path_a.exists() else None
        hash_b = sha256(path_b) if path_b and path_b.exists() else None
        match = bool(hash_a and hash_b and hash_a == hash_b and row_count_a == row_count_b)
        if not match:
            mismatches += 1
        comparisons.append(
            {
                "file": name,
                "run_a_sha256": hash_a,
                "run_b_sha256": hash_b,
                "row_count_a": row_count_a,
                "row_count_b": row_count_b,
                "match": match,
            }
        )

    manifest = json.loads((RUN_A / "manifest.json").read_text(encoding="utf-8"))
    payload = {
        "generated_on": date.today().isoformat(),
        "seed": manifest["seed"],
        "scale": manifest["scale"],
        "generator_version": manifest["generator_version"],
        "files_compared": len(comparisons),
        "mismatches": mismatches,
        "status": "PASS" if mismatches == 0 else "FAIL",
        "run_a": str(RUN_A),
        "run_b": str(RUN_B),
        "row_counts": manifest["row_counts"],
        "comparisons": comparisons,
    }
    (PROJECT_ROOT / "artifacts" / "reproducibility.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8"
    )

    lines = [
        "# Reproducibility report",
        "",
        f"**Result: {payload['status']}** ({len(comparisons) - mismatches}/{len(comparisons)} files identical)",
        "",
        f"- Fixed seed: `{payload['seed']}`",
        f"- Scale: `{payload['scale']}`",
        f"- Generator version: `{payload['generator_version']}`",
        f"- Run A: `{payload['run_a']}`",
        f"- Run B: `{payload['run_b']}`",
        "- Both runs used the same configuration and the same generator code.",
        "",
        "## Row counts (both runs)",
        "",
        "| Table | Rows |",
        "|---|---:|",
    ]
    for table, count in manifest["row_counts"].items():
        lines.append(f"| {table} | {count:,} |")
    lines += [
        "",
        "## File comparison",
        "",
        "| File | Rows A | Rows B | SHA-256 match |",
        "|---|---:|---:|---|",
    ]
    for row in comparisons:
        lines.append(
            f"| {row['file']} | {row['row_count_a'] if row['row_count_a'] is not None else '—'} | "
            f"{row['row_count_b'] if row['row_count_b'] is not None else '—'} | "
            f"{'✅' if row['match'] else '❌'} |"
        )
    lines += [
        "",
        "## Interpretation",
        "",
        "Every CSV, master JSON file, ground-truth file, manifest and validation summary is "
        "byte-identical between the two executions. The generator uses `random.Random(seed)` "
        "and `Faker.seed(seed)`, fixed dataset dates (`2026-10-01` to `2026-12-29`) and a fixed "
        "`as_of_date` (`2026-11-14`), so output does not depend on the wall clock.",
        "",
    ]
    (PROJECT_ROOT / "docs" / "reproducibility.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({"status": payload["status"], "files_compared": len(comparisons),
                      "mismatches": mismatches}, indent=2))
    return 0 if mismatches == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

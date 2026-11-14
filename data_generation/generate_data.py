"""CLI for the WorkSync AI synthetic dataset generator.

Examples
--------
    python -m data_generation.generate_data --scale full
    python -m data_generation.generate_data --scale starter --no-db
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import replace
from pathlib import Path

from data_generation.config import preset
from data_generation.generator import DataGenerator


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate the WorkSync AI synthetic dataset")
    parser.add_argument("--scale", choices=["full", "starter"], default="full")
    parser.add_argument("--seed", type=int, default=20261022)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--database-url", type=str, default=None,
                        help="Override the target database (default: backend/worksync.db)")
    parser.add_argument("--no-db", action="store_true",
                        help="Write CSV/JSON/SQL only; do not create the SQLite database")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    config = preset(args.scale, write_db=not args.no_db, output_dir=args.output_dir,
                    database_url=args.database_url)
    if args.seed != config.seed:
        config = replace(config, seed=args.seed)
    generator = DataGenerator(config)
    result = generator.run()
    manifest = result["manifest"]
    summary = {
        "scale": config.scale,
        "seed": config.seed,
        "output_dir": str(config.output_dir),
        "rows": manifest["row_counts"],
        "validation_status": result["validation"]["status"],
        "baseline_failures": result["validation"]["baseline"]["failures"],
        "anomalies": result["validation"]["anomalies"],
        "unfilled_baseline_shifts": len(result["unfilled_shifts"]),
        "ground_truth_rows": len(result["ground_truth"]),
        "database": "written" if config.write_db else "skipped",
    }
    print(json.dumps(summary, indent=2, default=str))
    return 0 if result["validation"]["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())

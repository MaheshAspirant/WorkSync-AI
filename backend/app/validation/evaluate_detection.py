"""Evaluate the runtime exception detector against the isolated ground truth.

Usage (from the backend directory, PYTHONPATH=.):
    python -m app.validation.evaluate_detection --ground-truth ../ground_truth/ground_truth.csv

The detector never reads ground_truth.csv; this module is the only place that
joins the two, and it writes metrics to docs/evaluation_results.md.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

from app.core.config import PROJECT_ROOT
from app.db.session import SessionLocal
from app.models.enums import IssueType
from app.services import conflict_service

TARGET_TYPES = {
    "DOUBLE_BOOKING",
    "LEAVE_OVERLAP",
    "MISSING_SKILL",
    "OVERTIME_CAP",
    "UNAPPROVED_SWAP",
}


def load_ground_truth(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _matches(truth: dict, issue: dict) -> bool:
    kind = truth["issue_type"]
    if kind != issue["issue_type"].value:
        return False
    if kind in {"DOUBLE_BOOKING", "LEAVE_OVERLAP"}:
        return (
            (truth.get("employee_id") or None) == issue.get("employee_id")
            and truth.get("shift_id") == issue.get("shift_id")
        )
    if kind == "MISSING_SKILL":
        return (
            truth.get("shift_id") == issue.get("shift_id")
            and truth.get("secondary_entity_id") == issue.get("transaction_id")
        )
    if kind == "OVERTIME_CAP":
        return (
            truth.get("employee_id") == issue.get("employee_id")
            and truth.get("transaction_id") == issue.get("transaction_id")
        )
    if kind == "UNAPPROVED_SWAP":
        return truth.get("primary_entity_id") == issue.get("transaction_id")
    return False


def evaluate(truth_rows: list[dict], issues: list[dict]) -> dict:
    candidates = [issue for issue in issues if issue["issue_type"].value in TARGET_TYPES]
    used: set[int] = set()
    per_type = defaultdict(lambda: {"tp": 0, "fp": 0, "fn": 0})
    matched_truth_ids = set()
    for truth in truth_rows:
        if truth["issue_type"] not in TARGET_TYPES:
            continue
        match_index = None
        for index, issue in enumerate(candidates):
            if index in used:
                continue
            if _matches(truth, issue):
                match_index = index
                break
        if match_index is None:
            per_type[truth["issue_type"]]["fn"] += 1
        else:
            used.add(match_index)
            per_type[truth["issue_type"]]["tp"] += 1
            matched_truth_ids.add(truth["ground_truth_id"])
    for index, issue in enumerate(candidates):
        if index not in used:
            per_type[issue["issue_type"].value]["fp"] += 1

    overall_tp = sum(v["tp"] for v in per_type.values())
    overall_fp = sum(v["fp"] for v in per_type.values())
    overall_fn = sum(v["fn"] for v in per_type.values())
    precision = overall_tp / (overall_tp + overall_fp) if overall_tp + overall_fp else 0.0
    recall = overall_tp / (overall_tp + overall_fn) if overall_tp + overall_fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0

    by_kind = {}
    for kind in sorted(TARGET_TYPES):
        values = per_type[kind]
        p = values["tp"] / (values["tp"] + values["fp"]) if values["tp"] + values["fp"] else 0.0
        r = values["tp"] / (values["tp"] + values["fn"]) if values["tp"] + values["fn"] else 0.0
        by_kind[kind] = {
            **values,
            "precision": round(p, 4),
            "recall": round(r, 4),
            "f1": round(2 * p * r / (p + r), 4) if p + r else 0.0,
        }

    all_counts = Counter(issue["issue_type"].value for issue in issues)
    return {
        "ground_truth_rows": len(truth_rows),
        "target_detections": len(candidates),
        "all_detections": len(issues),
        "detections_by_type": dict(all_counts),
        "overall": {
            "tp": overall_tp,
            "fp": overall_fp,
            "fn": overall_fn,
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
        },
        "by_type": by_kind,
        "matched_truth_ids": sorted(matched_truth_ids),
        "other_findings": {
            kind: count for kind, count in all_counts.items() if kind not in TARGET_TYPES
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ground-truth", type=Path,
                        default=PROJECT_ROOT / "ground_truth" / "ground_truth.csv")
    parser.add_argument("--start", type=date.fromisoformat, default=None)
    parser.add_argument("--end", type=date.fromisoformat, default=None)
    parser.add_argument("--output", type=Path,
                        default=PROJECT_ROOT / "docs" / "evaluation_results.md")
    args = parser.parse_args(argv)

    truth = load_ground_truth(args.ground_truth)
    with SessionLocal() as db:
        issues = conflict_service.detect_issues(
            db, start=args.start, end=args.end, include_attendance=False
        )
    metrics = evaluate(truth, issues)
    payload = {
        "generated_at": date.today().isoformat(),
        "ground_truth_file": str(args.ground_truth),
        "note": "Detector output was produced without reading ground-truth labels.",
        **metrics,
    }
    json_path = PROJECT_ROOT / "artifacts" / "evaluation.json"
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    lines = [
        "# WorkSync AI detection evaluation",
        "",
        f"Ground truth: `{args.ground_truth}`  ",
        "The runtime detector was executed against the operational database **without reading** this file.",
        "",
        "## Overall (five required anomaly types)",
        "",
        "| Metric | Value |",
        "|---|---:|",
        f"| True positives | {payload['overall']['tp']} |",
        f"| False positives | {payload['overall']['fp']} |",
        f"| False negatives | {payload['overall']['fn']} |",
        f"| Precision | {payload['overall']['precision']:.2%} |",
        f"| Recall | {payload['overall']['recall']:.2%} |",
        f"| F1 | {payload['overall']['f1']:.2%} |",
        "",
        "## Per anomaly type",
        "",
        "| Issue type | TP | FP | FN | Precision | Recall | F1 |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for kind, row in payload["by_type"].items():
        lines.append(
            f"| {kind} | {row['tp']} | {row['fp']} | {row['fn']} | "
            f"{row['precision']:.2%} | {row['recall']:.2%} | {row['f1']:.2%} |"
        )
    lines += [
        "",
        "## Other legitimate findings",
        "",
        "Coverage gaps and rest/hour violations are separate operational findings and are not false positives "
        "for the five required anomaly classes. The detector reported:",
        "",
        "| Finding | Count |",
        "|---|---:|",
    ]
    for kind, count in sorted(payload["other_findings"].items()):
        lines.append(f"| {kind} | {count} |")
    lines += [
        "",
        "## Method",
        "",
        "1. Ground truth labels are written only by the anomaly injector, after valid baseline generation.",
        "2. Ground truth is never loaded into the application database or passed to the detector.",
        "3. Matching uses the documented affected-entity keys (employee + shift, shift + skill, employee + week, swap id).",
        "4. Each labelled scenario is matched at most once; unmatched detections of the same type are false positives.",
        "",
    ]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(payload["overall"], indent=2))
    print(f"Wrote {args.output} and {json_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# Evaluation methodology and results

## 1. Dataset quality evaluation

| Dimension | How it is measured | Result |
|---|---|---|
| Realistic distributions | Team sizes, skill combinations, preferences, leave mix, weekend/holiday variation, lateness/absence, overtime | Full dataset: 100 teams, 1,914 active employees, 27,000 shifts, 60,098 assignments, 5,000 leave requests |
| Consistent IDs / joins | Validator checks PK uniqueness and every FK pair | 0 failures |
| Dependency/lifecycle consistency | Parent-first generation, append-only history, leave/swap state transitions | 0 failures |
| Derived values / reconciliation | Leave working days, attendance hours, daily overtime, coverage counts, shift required staffing | 0 failures |
| Normal, boundary, failure, exception coverage | Baseline + five labelled anomaly classes with multiple instances | 34 labelled anomaly rows, all verified |
| Separate ground truth | Labels only in `ground_truth/` and dataset `ground_truth/`; never loaded into operational DB | Confirmed |
| Reproducibility | Full generation twice, SHA-256 of every deliverable file | 31/31 identical, 0 mismatches |
| Lawful provenance | Faker-generated synthetic identities; no external/confidential data | No external sources |

The only baseline warning is 126 of 27,000 shifts (0.47%) whose generated roster
is below the configured headcount. These are reported as `COVERAGE_GAP`
exceptions; they are legitimate operational findings, not false positives for
the five labelled anomaly classes.

## 2. Operational metrics

All values are computed from persisted records at request time.

### Coverage percentage

```
coverage = Σ min(active_assignments_on_shift, required_staff)
           ─────────────────────────────────────────────── × 100
                        Σ required_staff
```

### Skill coverage

```
skill_coverage = Σ min(qualified_assignees_skill, skill_min_staff)
                 ───────────────────────────────────────────── × 100
                            Σ skill_min_staff
```

### Schedule validity

```
validity = (period_active_assignments − assignment-level open exceptions)
           ──────────────────────────────────────────────────────────── × 100
                            period_active_assignments
```

Coverage gaps are shift-level and are reported separately from assignment-level
validity.

### Fairness score

For each dimension `d ∈ {night shifts, weekend shifts, overtime hours}` across
employees with assignments:

```
cv_d = population_stdev(d) / mean(d)
score_d = max(0, 1 − cv_d)                 (1 when mean = 0)
fairness = mean(score_night, score_weekend, score_overtime) × 100
```

A score of 100 means perfectly even distribution; a concentrated workload
approaches 0. The API exposes the component scores and the per-employee table.

### Overtime

```
daily_overtime   = max(0, actual_hours − daily_cap)
weekly_overtime  = max(0, weekly_actual_hours − weekly_cap)
cap_exceeded     = weekly_overtime > overtime_cap_weekly
```

### Absence rate

```
absence_rate = (ABSENT + NO_SHOW) ÷ attendance_events × 100
```

## 3. Detector evaluation (isolated ground truth)

The detector runs on the operational database first. Only the evaluation script
loads `ground_truth/ground_truth.csv` and joins the two by documented entity
keys. Matching rules:

| Anomaly | Match key |
|---|---|
| DOUBLE_BOOKING | employee_id + shift_id |
| LEAVE_OVERLAP | employee_id + shift_id |
| MISSING_SKILL | shift_id + skill_id |
| OVERTIME_CAP | employee_id + week_start |
| UNAPPROVED_SWAP | swap_id |

### Full dataset result

| Metric | Value |
|---|---:|
| Ground-truth anomalies | 34 |
| True positives | 34 |
| False positives (target classes) | 0 |
| False negatives | 0 |
| Precision | **100%** |
| Recall | **100%** |
| F1 | **100%** |

| Type | TP | FP | FN | Precision | Recall |
|---|---:|---:|---:|---:|---:|
| DOUBLE_BOOKING | 6 | 0 | 0 | 100% | 100% |
| LEAVE_OVERLAP | 6 | 0 | 0 | 100% | 100% |
| MISSING_SKILL | 10 | 0 | 0 | 100% | 100% |
| OVERTIME_CAP | 6 | 0 | 0 | 100% | 100% |
| UNAPPROVED_SWAP | 6 | 0 | 0 | 100% | 100% |

The detector also reports 126 `COVERAGE_GAP` findings on the full dataset; these
are separate legitimate operational exceptions and are deliberately excluded
from the five-class precision/recall calculation.

The generated evaluation report is in [`evaluation_results.md`](evaluation_results.md).
The machine-readable result is `artifacts/evaluation.json`.

## 4. Automated tests

`pytest` covers:

- authentication, JWT/me, invalid credentials
- RBAC and team-scoped employee/team access
- leave submit/approve/reject/cancel, overlap, self-approval, balances
- schedule generation, leave exclusion, decision explanations, infeasibility gaps
- swap target agreement, manager approval, applied assignment history, refusal of
  unapproved application
- attendance derivation, duplicate prevention, correction, summary/overtime
- all five required anomaly detections plus resolution workflow
- analytics calculations and admin validation report

Latest run: **25 passed** (`pytest tests -q`). See `README.md` for the command.

## 5. Reproducibility

Full generation was run twice with seed `20261022`. All 31 deliverable files
(17 CSVs, 10 master JSON files, ground truth CSV/JSON, manifest, validation
summary, schema) are byte-identical. See [`reproducibility.md`](reproducibility.md)
and `artifacts/reproducibility.json`.

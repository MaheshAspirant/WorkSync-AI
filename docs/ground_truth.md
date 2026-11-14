# Ground-truth methodology

## Principle

Ground truth is produced **after** valid baseline generation. It is stored only
in `ground_truth/ground_truth.csv` and `ground_truth/ground_truth.json` (and a
copy under `database/seed/full/ground_truth/`). The operational database
contains the affected records but **no labels**; the detector and scheduler
never receive the ground-truth file.

## Injection sequence

1. Generate a valid baseline: teams, skills, employees, availability, leave,
   shifts, assignments, attendance, swaps.
2. Validate the baseline (PK/FK, dates, arithmetic, lifecycle, rest, hours).
3. Inject six instances of each required anomaly class using valid parent IDs.
4. Re-verify that each labelled condition exists in the final operational data.
5. Write the separate ground-truth files.
6. Export CSV/JSON/SQL and build the seed database.

## Labelled scenarios (full dataset)

| Scenario | Instances | Injection rule | Expected detection | Expected action | Severity |
|---|---:|---|---|---|---|
| Employee double-booked | 6 | Add a second active assignment to another team's shift at the same start/end time | `DOUBLE_BOOKING` on employee + shift | Remove one overlapping assignment; notify manager | CRITICAL |
| Approved leave overlaps assigned shift | 6 | Add an assignment on a date inside an approved leave, rest-safe against other shifts | `LEAVE_OVERLAP` on employee + shift + leave | Reassign the shift; leave takes priority | HIGH |
| Required skill absent | 10 rows / 6 shifts | Replace **all** qualified assignees on a shift with unqualified staff while preserving headcount; label every resulting skill deficit | `MISSING_SKILL` on shift + skill | Assign a qualified employee or arrange training coverage | HIGH |
| Overtime cap exceeded | 6 | Extend an existing attendance checkout so weekly actual hours exceed 40 + overtime cap | `OVERTIME_CAP` on employee + week | Rebalance roster within cap | MEDIUM |
| Swap applied without approval | 6 | Create an `APPLIED` swap with no `APPROVED` history event and no manager actor | `UNAPPROVED_SWAP` on swap ID | Freeze swap, notify manager, restore original roster | CRITICAL |

The missing-skill count is 10 rather than 6 because cross-trained employees can
hold both required skills; replacing all qualified staff for one skill can
remove qualification for a second skill on the same shift. Every resulting
deficit is labelled rather than hidden.

## Label schema

`ground_truth.csv` columns:

- `ground_truth_id` — `GT-0001`…
- `scenario` — stable scenario name
- `issue_type` — detector issue type
- `primary_entity_type`, `primary_entity_id`
- `secondary_entity_type`, `secondary_entity_id`
- `employee_id`, `shift_id`, `transaction_id`
- `expected_detection`, `expected_action`, `severity`, `details`

`ground_truth.json` wraps the same rows with dataset/seed/as-of metadata and an
explicit methodology statement.

## Why this is not leakage

- The API/DB has no ground-truth table and no anomaly label column.
- Detection queries only operational entities: assignments, shifts, leave,
  employees, skills, attendance, swaps and approval history.
- The evaluation script is the only component that reads the labels.
- The generator writes anomalies with ordinary business fields; labels are never
  used as features or as an input to scheduling.

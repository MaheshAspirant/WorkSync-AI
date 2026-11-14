# Reproducibility report

**Result: PASS** (31/31 files identical)

- Fixed seed: `20261022`
- Scale: `full`
- Generator version: `1.0.0`
- Run A: `C:\Users\konda\OneDrive\Documents\deepseek-harness\default-workspace\WorkSyncAI\database\seed\full`
- Run B: `C:\Users\konda\OneDrive\Documents\deepseek-harness\default-workspace\WorkSyncAI\artifacts\repro_run_b`
- Both runs used the same configuration and the same generator code.

## Row counts (both runs)

| Table | Rows |
|---|---:|
| skills | 20 |
| teams | 100 |
| employees | 2,000 |
| employee_skills | 5,827 |
| team_managers | 100 |
| shift_templates | 3 |
| coverage_requirements | 2,700 |
| holiday_calendar | 5 |
| leave_policies | 5 |
| employee_availability | 14,000 |
| leave_requests | 5,000 |
| leave_approval_history | 9,049 |
| shifts | 27,000 |
| shift_assignments | 60,098 |
| attendance_events | 29,936 |
| swap_requests | 1,006 |
| swap_approval_history | 2,291 |

## File comparison

| File | Rows A | Rows B | SHA-256 match |
|---|---:|---:|---|
| csv/attendance_events.csv | 29936 | 29936 | ✅ |
| csv/coverage_requirements.csv | 2700 | 2700 | ✅ |
| csv/employee_availability.csv | 14000 | 14000 | ✅ |
| csv/employee_skills.csv | 5827 | 5827 | ✅ |
| csv/employees.csv | 2000 | 2000 | ✅ |
| csv/holiday_calendar.csv | 5 | 5 | ✅ |
| csv/leave_approval_history.csv | 9049 | 9049 | ✅ |
| csv/leave_policies.csv | 5 | 5 | ✅ |
| csv/leave_requests.csv | 5000 | 5000 | ✅ |
| csv/shift_assignments.csv | 60098 | 60098 | ✅ |
| csv/shift_templates.csv | 3 | 3 | ✅ |
| csv/shifts.csv | 27000 | 27000 | ✅ |
| csv/skills.csv | 20 | 20 | ✅ |
| csv/swap_approval_history.csv | 2291 | 2291 | ✅ |
| csv/swap_requests.csv | 1006 | 1006 | ✅ |
| csv/team_managers.csv | 100 | 100 | ✅ |
| csv/teams.csv | 100 | 100 | ✅ |
| ground_truth/ground_truth.csv | 34 | 34 | ✅ |
| ground_truth/ground_truth.json | — | — | ✅ |
| json/coverage_requirements.json | — | — | ✅ |
| json/employee_availability.json | — | — | ✅ |
| json/employee_skills.json | — | — | ✅ |
| json/employees.json | — | — | ✅ |
| json/holiday_calendar.json | — | — | ✅ |
| json/leave_policies.json | — | — | ✅ |
| json/shift_templates.json | — | — | ✅ |
| json/skills.json | — | — | ✅ |
| json/team_managers.json | — | — | ✅ |
| json/teams.json | — | — | ✅ |
| manifest.json | — | — | ✅ |
| validation_summary.json | — | — | ✅ |

## Interpretation

Every CSV, master JSON file, ground-truth file, manifest and validation summary is byte-identical between the two executions. The generator uses `random.Random(seed)` and `Faker.seed(seed)`, fixed dataset dates (`2026-10-01` to `2026-12-29`) and a fixed `as_of_date` (`2026-11-14`), so output does not depend on the wall clock.

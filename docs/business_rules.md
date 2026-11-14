# Business rules

## Master data and identifiers

1. Master data is created in dependency order: Team, Skill, ShiftTemplate,
   Employee, EmployeeSkill, TeamManager, CoverageRequirement, HolidayCalendar,
   LeavePolicy; then transaction/event data: LeaveRequest, Shift, ShiftAssignment,
   AttendanceEvent, SwapRequest, SchedulingRun/Decision/Exception, AuditLog.
2. Every identifier is deterministic, zero-padded and immutable. Counters live
   in `id_counters`; IDs are never reused or renumbered.
3. Every child record references a valid parent ID. Foreign keys are enforced by
   the database and validated again by the dataset validator.
4. Historical rows are never deleted to represent a state change. Leave, swap,
   assignment and schedule state changes append history and/or preserve the old
   row with a terminal status (`SWAPPED_OUT`, `CANCELLED`, etc.).

## Teams, skills and coverage

- An employee belongs to one team at a time; manager history is effective-dated.
- A coverage requirement defines a minimum headcount, optionally per skill and
  day type (weekday/weekend/holiday), with effective dates. The latest effective
  version wins.
- `Shift.required_staff` is the total headcount for that dated shift; skill
  minima are additional qualified-employee requirements.
- Coverage percentage = filled required positions ÷ total required positions.
  A position is filled when an active assignment exists; overstaffing does not
  increase the numerator above demand.
- Skill coverage = qualified fills of skill-specific minima ÷ total skill minima.
- If demand cannot be met, the system reports an explicit `COVERAGE_GAP` /
  `MISSING_SKILL` exception. It never silently hides a shortage.

## Scheduling hard constraints

A generated plan must never violate:

1. No employee is assigned to overlapping shifts.
2. No employee is assigned during approved leave.
3. An employee is assigned only to their own team's shifts.
4. The employee possesses at least one skill required by the shift, and
   skill-specific coverage is filled by qualified employees.
5. Availability day/time windows are respected (no effective row means
   unrestricted, as documented).
6. Minimum rest hours between an employee's shifts are respected.
7. Weekly scheduled hours do not exceed `weekly_hours_cap + overtime_cap_weekly`.
8. The employee's status is `ACTIVE`.
9. Covered shifts receive no more than the required staffing unless needed to
   satisfy a skill minimum; unnecessary overstaffing is penalised.

## Scheduling soft constraints

The CP-SAT objective balances:

- minimise overtime minutes above the weekly standard
- flatten night, evening and morning shift counts across eligible employees
- reward assignment to the employee's preferred shift
- keep staffing close to requirement
- preserve feasibility first; soft score is reported separately from hard
  violations

If the hard model is infeasible, the engine re-solves with coverage as a soft
penalty. The run becomes `PARTIAL`, lists each gap, and does not claim validity.
A fully infeasible result is `INFEASIBLE`.

## Explainability

Every generated assignment stores a `SchedulingDecision` with:

- run ID, shift ID, employee ID, assignment ID
- human-readable reason
- skill match and skills held
- availability result
- leave eligibility/check
- weekly-hours-before, caps and rest requirement
- preference match and coverage role
- constraint evaluation JSON and optimization score

## Leave rules

Lifecycle: `PENDING → APPROVED / REJECTED / CANCELLED`.

- Employee must exist and be active.
- `end_date ≥ start_date`; the range must contain at least one working day
  (weekends and public holidays excluded).
- Calendar duration must not exceed the policy `max_consecutive_days`.
- Notice days apply to forward-dated annual/unpaid requests; sick leave is
  exempt.
- Annual balance = entitlement − approved − pending annual days for the year.
- Overlapping PENDING/APPROVED leave for the same employee is rejected.
- A manager may decide only for their team; HR/Admin may decide any; nobody may
  approve their own leave.
- Rejection requires a comment.
- Employees may cancel their own pending leave; HR/Admin may cancel approved
  leave. Every transition appends history and audit.
- Approved leave is a hard scheduling exclusion. Existing assignments that
  overlap approved leave are reported as `LEAVE_OVERLAP`.

## Shift swap rules

Lifecycle: `REQUESTED → APPROVED / REJECTED / CANCELLED → APPLIED`.

- Requester and target are distinct employees with distinct active assignments.
- The target employee must explicitly agree.
- A manager (not a participant, and managing both teams) or HR/Admin must
  approve.
- Validation covers: skill compatibility in both directions, approved leave,
  availability, weekly hours cap + overtime allowance, minimum rest, assignment
  activity and team eligibility.
- A swap is applied **only** from `APPROVED`. Applying is refused otherwise.
- Application marks both original assignments `SWAPPED_OUT` and creates two new
  `SWAPPED_IN` assignments; all history remains.
- Applying to a past shift is refused.
- A swap that is `APPLIED` with no `APPROVED` event is a detected
  `UNAPPROVED_SWAP` exception.

## Attendance rules

- Attendance references an active assignment; one event per assignment.
- Scheduled start/end come from the shift.
- Actual hours and overtime are derived, never supplied as business outputs.
- Status is derived: no check-in → `ABSENT`; late > grace → `LATE`; checkout
  before scheduled end → `EARLY_DEPARTURE`; otherwise `PRESENT`.
- Reconciliation compares event employee/shift with the assignment; a swapped-out
  assignment yields `MISMATCH`.
- Corrections create audit entries with previous/new values.
- Absence rate = (ABSENT + NO_SHOW) ÷ attendance events.

## Overtime rules

- Daily overtime = max(0, actual hours − daily hours cap).
- Weekly overtime = max(0, weekly actual hours − weekly standard cap), derived
  from attendance and assignments.
- Overtime cap is per employee per week. `cap_exceeded` when weekly overtime is
  greater than the employee's cap.
- No overtime value is independently randomised or manually fabricated as a
  business output.

## Conflict detection rules

Detected issue types:

| Type | Detection |
|---|---|
| `DOUBLE_BOOKING` | same employee, overlapping active shift intervals |
| `LEAVE_OVERLAP` | active assignment whose shift date falls inside approved leave |
| `MISSING_SKILL` | assigned qualified headcount below a skill-specific minimum |
| `OVERTIME_CAP` | weekly attendance overtime above the employee's cap |
| `UNAPPROVED_SWAP` | swap status `APPLIED` without an `APPROVED` history event |
| `COVERAGE_GAP` | active assignment count below `required_staff` |
| `REST_VIOLATION` | gap between active assignments below minimum rest |
| `HOURS_CAP` | weekly scheduled hours above cap + overtime allowance |
| `ATTENDANCE_MISMATCH` | attendance/assignment inconsistency (optional check) |

Each exception stores an immutable issue ID, type, affected employee/shift/
assignment/transaction, severity, description, detection timestamp and source.
A fingerprint prevents duplicate open issues. Resolution records actor, status,
note and timestamp, and is audit-logged.

## Security and access

- JWT bearer authentication; bcrypt password hashing; no password or hash in
  responses.
- Role-based access control: ADMIN, HR, MANAGER, EMPLOYEE.
- Employees see only their own records; managers are scoped to managed teams;
  HR sees people/reporting; Admin manages users/config and can see all.
- Input validation is performed by Pydantic and service rules; SQL injection is
  prevented by SQLAlchemy parameterisation.
- CORS is explicitly configured; secrets come from environment variables.
- All sensitive mutations write an audit event with actor, previous/new state and
  reason.

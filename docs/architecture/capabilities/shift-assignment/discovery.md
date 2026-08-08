# Shift Assignment — Discovery

**Status:** Complete

**Capability:** Shift Assignment (candidate — validity as an independent capability not yet established)

**Owner:** EOP Architecture Governance

---

# Purpose

This document determines whether Shift Assignment is an independent architectural capability, using repository evidence only. It follows the same methodology already used for every prior capability discovery in this governance trail: observation only, no architecture chosen, no schema authored, no concept invented. Every statement is labeled **Repository Evidence**, **Logical Consequence**, or **Unknown**. No conclusion from any prior governance document is assumed — every finding below was re-derived from a fresh read of current repository state.

---

# Discovery Scope

Full file reads unless noted. All searches run fresh for this discovery.

- Full read of `models/shift.py`, `models/hr_employee.py`, `models/assignment.py`, `models/attendance_event.py`.
- Full read of `repositories/shift.py`, `services/shift.py`, `api/shifts.py`, `services/assignment.py`.
- Repository-wide grep for `shift_id|shift\.id|Shift\b` across `services/api/src` — 15 files matched, every match read in context.
- Repository-wide grep for `effective_from|effective_to|valid_from|valid_to|effective_date` across `services/api/src` — zero matches.
- Repository-wide grep for `schedule_id|roster_id|assignment_id|work_pattern|working_hours|roster|Roster` across `services/api/src` — zero matches.
- Repository-wide grep for `reassign|transfer|replacement|activation|deactivat` across `services/api/src` — 5 files matched, every match read in context.
- Repository-wide grep for `Assignment|Membership|Mapping|Link|Association` across `services/api/src/eop_api/models` — 5 files matched (one real entity, the rest incidental references to it).
- Grep for `class \w*(History|Snapshot|Revision)\b` across `services/api/src/eop_api/models` — zero matches.
- Grep for `is_active` across every model file — 1 match (`User`).
- Grep for "shift" across every authorization-related service file (`authorization_evaluator.py`, `authorization_request.py`, `authorization_decision.py`, `authorization.py`, `approval_authorization.py`, `leave_authorization.py`, `attendance_authorization.py`) — zero matches.
- Grep for "shift assignment" and "assign.*shift" (case-insensitive) across all of `docs/` — matches read in full context.
- Alembic migration filenames for `shift`/`hr_employee` — read directly, not inferred.
- `docs/architecture/10-reference/CAPABILITY_CATALOG.md`, `REPOSITORY_CENSUS.md`, `ARCHITECTURE_INVENTORY.md`, `MASTER_ARCHITECTURE_ROADMAP.md`, `LEAVE_DESIGN.md`, `ATTENDANCE_DESIGN.md`, `TIMESHEET_DESIGN.md` — searched for "shift", matches read in context.

---

# 1. Existing Shift Usage

**Repository Evidence**: `Shift` (`models/shift.py`) is global HR master data — `code` (globally unique), `name`, `description`, `start_time`, `end_time`, `break_duration_minutes`, `grace_period_minutes`. Its own docstring states: *"assigning a shift to an employee, a work calendar, and rostering are all out of scope and belong to future modules."* `ShiftRepository`/`ShiftService`/`api/shifts.py` (`/hr/shifts`) implement plain CRUD, mirroring `EmploymentType`/`JobGrade`/`Holiday`. Tests exist: `test_shift_repository.py`, `test_shift_service.py`, `test_shifts_api.py`.

Exactly two entities hold a direct foreign key to `shifts.id` today:
- `HrEmployee.shift_id` — required (non-nullable), `ON DELETE RESTRICT`, indexed (`ix_hr_employees_shift_id`).
- `AttendanceEvent.shift_id` — required (non-nullable), `ON DELETE RESTRICT`, indexed (`ix_attendance_events_shift_id`).

**Note on a prior governance document**: `docs/architecture/capabilities/payroll/discovery.md` (authored earlier in this same governance trail) states *"shift | Yes (template only) ... not assigned to any employee, calendar, or roster."* This does not match the repository state read directly for this discovery — `HrEmployee.shift_id` is a required FK, confirmed by direct model read and by the migration `e7a8ed87ea45_add_shift_id_to_hr_employees.py`. This discrepancy is stated as observed, not resolved; per instruction, this document does not assume prior governance conclusions and relies only on the fresh read above.

**Logical Consequence**: `Shift` currently has two real, code-level consumers, both via a plain FK column on the consuming entity — not through any dedicated join, assignment, or history entity.

**Unknown**: None — searched exhaustively.

---

# 2. Employee Relationship

**Repository Evidence**: `HrEmployee.shift_id` exists, is required, is `ON DELETE RESTRICT`, and is indexed. It was added via its own dedicated migration (`20260803_1300-e7a8ed87ea45_add_shift_id_to_hr_employees.py`), after `Shift`'s own table migration (`20260803_1200-c4a9d3e17f56_create_shifts_table.py`) — the same incremental-FK-addition pattern used for `job_grade_id`, `employment_type_id`, `employment_status_id`, and `user_id` on the same entity (confirmed directly by migration filenames, and cross-referenced in `TIMESHEET_DESIGN.md`'s own citation of the same sequence).

A full read of `HrEmployee`'s complete field list finds no `schedule_id`, `roster_id`, `assignment_id`, `work_pattern`, `working_hours`, or any equivalent field. The complete field set is: `employee_number`, `first_name`, `last_name`, `full_name`, `email`, `phone`, `organization_id`, `department_id`, `position_id`, `team_id`, `location_id`, `manager_id`, `job_grade_id`, `employment_type_id`, `employment_status_id`, `shift_id`, `user_id`, `hire_date`, `employment_status`, `notes`.

`HrEmployeeService.create`/`update` validate only `shift_id`'s *existence* (`ShiftRepository(uow.session).exists(shift_id)`) — no other shift-specific logic exists in the service.

**Logical Consequence**: `HrEmployee` already has a direct, current-value shift relationship — but it is a single plain FK (one shift per employee, at all times, overwritten on update), not a dated, historical, or multi-shift structure of any kind.

**Unknown**: None regarding existence. Whether a single current-value FK is sufficient for any future need is a design question, out of scope for discovery.

---

# 3. Assignment Precedent

**Repository Evidence**: Exactly one entity named `Assignment` exists in the repository (`models/assignment.py`), in the Project Tracking bounded context — linking Project Tracking's own `Employee` (explicitly distinct from `HrEmployee`, per `HrEmployee`'s own docstring: *"share no foreign key relationship"*) to `Project`, via `employee_id`/`project_id`, both `ON DELETE CASCADE`. It carries its own `role` (free-text `String(100)`), `start_date` (required `Date`), `end_date` (nullable `Date`), and `UniqueConstraint("employee_id", "project_id")`.

No entity named `Membership`, `Mapping`, `Link`, or `Association` exists anywhere in the repository — confirmed by grep across `services/api/src/eop_api/models`.

`AssignmentService` implements ordinary CRUD (`create`/`get`/`list`/`update`/`delete`) plus two additional checks: existence of both referenced aggregates, and an `OrganizationMismatchError` cross-aggregate consistency check (employee and project must share `organization_id`). "Reassignment" is performed by calling `update()` with new `employee_id`/`project_id` values — no dedicated reassignment or transfer method exists.

**Logical Consequence**: `Assignment` is the repository's one and only precedent for modeling a relationship between two aggregates as a first-class entity of its own, rather than as a plain FK column on one side. It carries a date range and a role, and enforces one-active-pair-at-a-time via a plain (not date-scoped) unique constraint — a second row for the same pair cannot exist even after the first's `end_date` has passed, since the constraint does not account for dates.

**Unknown**: Whether this precedent would extend to a Shift↔Employee relationship — not decided; comparison only, per instruction.

---

# 4. Effective Dating

**Repository Evidence**: Repository-wide, case-insensitive grep for `effective_from|effective_to|valid_from|valid_to|effective_date` across `services/api/src` returns **zero matches**. No entity anywhere uses this terminology or an equivalent field.

The closest related patterns found: `Assignment.start_date`/`end_date` (§3) — a date range scoped to one specific association aggregate, not a generalized effective-dating mechanism. `LeaveBalance.period_year` — a bare `Integer` year partition, not a date range; its own docstring describes it as *"persistence-shaped, not calculation/ledger shaped,"* with *"synchronization with LeaveRequest"* explicitly listed as a future, out-of-scope concern.

A fresh, repository-wide search for `class \w*(History|Snapshot|Revision)\b` across `services/api/src/eop_api/models` returns zero matches — no historical-record entity of any kind exists anywhere.

**Logical Consequence**: No general effective-dating or historical-assignment mechanism exists anywhere in this repository. The one date-range precedent (`Assignment`) is scoped to a single, specific relationship, not a reusable pattern extended to any other entity.

**Unknown**: None — searched exhaustively, per instruction not to infer.

---

# 5. Current Ownership

**Repository Evidence**: No entity, service, or module named `Roster`, `Schedule`, or `WorkCalendar` exists anywhere — confirmed by zero matches for `schedule_id`/`roster_id`/`work_pattern`/`working_hours`/`Roster`. `Shift`'s own docstring explicitly disclaims ownership: *"assigning a shift to an employee, a work calendar, and rostering are all out of scope and belong to future modules."*

`HrEmployee.shift_id` is validated only for existence by `HrEmployeeService` (§2) — no assignment-specific logic exists there. `AttendanceEvent.shift_id` is a separate, independently-validated, required FK (§1) — `AttendanceEventService` validates only its existence (`ShiftRepository(uow.session).exists(data.shift_id)`), with no cross-check against `HrEmployee.shift_id`. `ATTENDANCE_DESIGN.md` (a prior design document) explicitly flags this as unconfirmed: *"Whether `shift_id`, if provided, must belong to the same employee's currently-assigned shift... is unconfirmed."*

**Logical Consequence**: No existing capability owns "employee → shift" as a first-class relationship. It exists today only as an incidental byproduct of two independent, plain FK columns (`HrEmployee.shift_id`, `AttendanceEvent.shift_id`), neither validated against the other.

**Unknown**: None regarding ownership — the absence is total and consistent across every candidate named in this investigation (Shift, HrEmployee, Attendance, Timesheet, HR Master Data all either explicitly disclaim it or simply contain nothing addressing it beyond the plain FKs described above).

---

# 6. Lifecycle

**Repository Evidence**: Grep for `reassign|transfer|replacement|activation|deactivat` across `services/api/src` returns matches only in `services/hr_employee.py`, `services/team.py`, `services/department.py`, `models/department.py`, and `models/location.py` — every match describes ordinary FK-field overwrite via `update()` (e.g., *"Reassigning `organization_id` or `department_id` never touches other rows... Callers who reassign a team are responsible for reconciling its children themselves"*), not a dedicated reassignment mechanism, event, or entity.

`User.is_active` (`Mapped[bool]`, `default=True`) is the only activation/deactivation-shaped field found anywhere in the repository — confirmed by a full-model-file grep for `is_active`. It belongs to `User` (authentication), not to any HR or assignment-shaped entity.

**Logical Consequence**: The repository's only "lifecycle" precedent for any FK relationship, anywhere, is ordinary field update (overwrite in place, no before/after record). No capability models reassignment as a distinct, trackable event.

**Unknown**: None — searched exhaustively. Whether a dedicated lifecycle would be needed for Shift Assignment is a design question, out of scope here.

---

# 7. Authorization

**Repository Evidence**: Grep for "shift" (case-insensitive) across every authorization-related service file (`authorization_evaluator.py`, `authorization_request.py`, `authorization_decision.py`, `authorization.py`, `approval_authorization.py`, `leave_authorization.py`, `attendance_authorization.py`) returns **zero matches**. No authorization policy anywhere references `Shift` or a shift assignment.

**Logical Consequence**: Consistent with every other capability's own Authorization finding in this governance trail — no resource or Service exists for `AuthorizationRequest.resource` to resolve against, since no Shift Assignment entity or service exists at all.

**Unknown**: None.

---

# 8. Downstream Consumers

**Repository Evidence**: Exactly two entities hold a direct FK to `shifts.id` today — `HrEmployee` and `AttendanceEvent` (§1). No other entity, service, or governance document references `Shift` as a consumer.

`LEAVE_DESIGN.md` (a prior design document, predating this governance trail) states, under "Shift changes": *"`HrEmployee.shift_id` is mandatory, but whether a `LeaveRequest` needs to account for shift hours (for partial-day math) or shift reassignment mid-request is unconfirmed."* This names `LeaveRequest` as a documented-but-unconfirmed candidate future consumer of shift-assignment information — not a present one.

No other capability's governance documents in this trail (Payroll, Payslip, Payroll Calculation, Compensation, Monetary Representation, Timesheet) name Shift Assignment as a consumer or dependency anywhere.

**Logical Consequence**: Two entities are current, code-level consumers of `Shift` itself via plain FK, not of a distinct "Shift Assignment" concept (which does not exist as a separate thing to consume). One additional capability (`LeaveRequest`) has a documented but explicitly unconfirmed future interest.

**Unknown**: Whether other capabilities would consume a Shift Assignment concept if one existed — not addressed, per instruction not to invent future consumers.

---

# 9. Architectural Pattern

Comparison only, per instruction — no selection made.

| Pattern | Repository Precedent | Structural Similarity |
|---|---|---|
| Master data | `Shift`, `JobGrade`, `EmploymentType`, `Holiday` — `code`/`name`/`description`, zero FK, plain CRUD | Describes `Shift` itself, not a relationship. A Shift↔Employee relationship, if it became its own entity, would not be standalone reference data the way these are. |
| Transactional aggregate | `AttendanceEvent`, `LeaveRequest`, `OvertimeRequest`, `Timesheet`, `Payslip` — employee-scoped, `RESTRICT` FK, own status/lifecycle | Shares the employee-scoped-FK shape, but every existing transactional aggregate records a discrete fact or event, not a standing relationship between two aggregates. |
| Association aggregate | `Assignment` — two FKs to two independent aggregates, a role/date-range payload, pair-uniqueness constraint | **Closest structural match** — a Shift↔Employee relationship is, like Employee↔Project, a link between two independently-owned aggregates, not a fact about one alone. |
| Process | `ApprovalService`, `ReconciliationService` — no owned table, orchestrates reads/writes across other repositories | No resemblance — a shift-assignment relationship is a standing fact, not an orchestration invoked per-request. |
| Projection | No read-model, projection, or materialized-view pattern found anywhere in the repository | No resemblance — no example exists anywhere to compare against. |

**Logical Consequence**: Of the five patterns, "association aggregate" (`Assignment`'s shape) is the closest by direct structural comparison; "master data" already describes `Shift` itself, not the relationship in question; "transactional aggregate" and "process" do not match; "projection" has no repository precedent to compare against at all.

**Unknown**: Whether the resemblance to `Assignment` is close enough to warrant the same shape for Shift Assignment — not decided here.

---

# 10. Repository Gaps

Everything confirmed completely absent, distinguished by label:

**Repository Evidence** (confirmed absent by direct search):
- No `EmployeeShift`/`ShiftAssignment`/`Roster`/`Schedule`/`WorkCalendar` entity, table, migration, repository, service, or API exists anywhere.
- No effective-dating field (`effective_from`/`effective_to`/`valid_from`/`valid_to`) exists anywhere, on any entity.
- No `*History`/`*Snapshot`/`*Revision` entity exists anywhere.
- No authorization policy references `Shift` or shift assignment anywhere.
- No dedicated reassignment/transfer/activation/deactivation mechanism exists for any FK relationship anywhere — only plain field overwrite via `update()`.
- No cross-column invariant enforces that `AttendanceEvent.shift_id` matches `HrEmployee.shift_id` — the two FKs are independent today, and this is explicitly flagged as unconfirmed in `ATTENDANCE_DESIGN.md`, a prior design document.

**Logical Consequence**: Today, "employee → shift" exists only as two independent, unvalidated-against-each-other, plain FK columns. No distinct capability, entity, history, lifecycle, or authorization surrounds this relationship anywhere in the repository.

**Unknown**:
- Whether `Assignment`'s association-aggregate shape (§3, §9) is the correct precedent to follow, if this capability is ever built.
- Whether `LeaveRequest`'s documented-but-unconfirmed interest in shift reassignment (§8) would become a real consumer.
- Whether the discrepancy between this discovery's direct findings and `payroll/discovery.md`'s earlier claim (§1) reflects staleness in that document or an oversight — not resolved here.

---

# Recommended Next Step

```
Continue Governance
```

A minimal, functioning employee→shift relationship already exists in the repository (`HrEmployee.shift_id`, required FK), consumed independently by one additional entity (`AttendanceEvent.shift_id`) — this is real evidence, not a blank slate. `Shift`'s own docstring explicitly anticipates assignment/rostering as a distinct future concern, and one sibling capability's own design document (`LEAVE_DESIGN.md`) independently flags shift reassignment as an unconfirmed but named future question. A direct architectural precedent for how the repository would model such a relationship as its own entity (`Assignment`) exists and was compared, not adopted. This combination — real current evidence, explicit forward anticipation in existing docstrings/design docs, and an available structural precedent — matches the pattern this governance trail has used elsewhere to proceed to a Capability Decision, not the pattern used where a capability was found entirely unsupported by any evidence.

---

# References

- `services/api/src/eop_api/models/shift.py`, `hr_employee.py`, `assignment.py`, `attendance_event.py`
- `services/api/src/eop_api/services/shift.py`, `hr_employee.py`, `assignment.py`, `attendance_event.py`
- `services/api/alembic/versions/20260803_1200-c4a9d3e17f56_create_shifts_table.py`, `20260803_1300-e7a8ed87ea45_add_shift_id_to_hr_employees.py`
- `docs/architecture/LEAVE_DESIGN.md` ("Shift changes"), `ATTENDANCE_DESIGN.md` (§5, §9, §11), `TIMESHEET_DESIGN.md` (§ future)
- `docs/architecture/capabilities/payroll/discovery.md` (cited §1 for the observed discrepancy)

# PR-039 — Attendance Architecture Discovery

Status: **Discovery only. No code, no migrations. Awaiting approval.**

---

## 0. What was reviewed

**HR module** (`services/api/src/eop_api/{models,repositories,services,api,schemas}`):
`HrEmployee`, `Shift`, `JobGrade`, `EmploymentType`, `EmploymentStatus`, `Organization`,
`Department`, `Position`, `Team`, `Location`.

**Project Tracking module**: `Employee`, `Assignment`, `Task`, `Project`.

**Repository/UoW foundation**: `BaseRepository`, `AbstractUnitOfWork`, `SQLAlchemyUnitOfWork`,
`BaseEntity` (`UUIDMixin`, `TimestampMixin`, `AuditMixin`, `SoftDeleteMixin`, `VersionMixin`).

**Master-data reference implementations**: `Shift` (model, repo, service, api, schema, migration
`c4a9d3e17f56`, tests `test_shift_repository.py` / `test_shift_service.py` / `test_shifts_api.py`),
plus `JobGrade`, `EmploymentType`, `EmploymentStatus` for the simpler global-lookup shape.

**Also reviewed**: `User` (auth identity, `dependencies/auth.py`), and
`docs/product/06_PRODUCT_ROADMAP.md`.

---

## Confirmed dependency findings

1. **`HrEmployee` and Project Tracking `Employee` are already confirmed independent.**
   This is not an inference — it's stated in `HrEmployee`'s own docstring
   (`services/api/src/eop_api/models/hr_employee.py:20-33`): "Deliberately independent from the
   Project Tracking `Employee`... the two model different concepts under the same business word
   'Employee' and share no foreign key relationship." `Assignment` and `Task` both FK to
   `employees.id` (Project Tracking), never to `hr_employees.id`.

2. **There is a third, separate identity: `User`** (`models/user.py`), the authentication
   principal (email/password/roles), used for `CurrentUser` in every API route. **`User` has no
   foreign key to `HrEmployee`** anywhere in the codebase. This means: today, nothing in the
   system says "this logged-in `User` corresponds to that `HrEmployee` row." This is flagged in
   §11 (Ambiguities) — it's load-bearing for who/what an attendance record is actually for.

3. **Roadmap context** (`docs/product/06_PRODUCT_ROADMAP.md`): Attendance is Phase 4 ("Field
   Operations"), listed alongside Check In / Check Out / Mission / Visit / Survey / **GPS** /
   Photo, and is part of the MVP. This suggests attendance was originally scoped as a
   field-operations/mobile-GPS concept (sales-rep-in-the-field style check-in), not necessarily
   an office badge-in/badge-out system. The current codebase (HR module, Shift master data) is
   clearly building the office/workforce HR variant instead. **Which of these two product visions
   Attendance is meant to serve is itself an open question** — see §11.

---

## 1. Aggregate Definition

**Recommendation: the aggregate root is one clock transaction — an `AttendanceEvent`.**

Evaluated options:

| Candidate | Verdict |
|---|---|
| One attendance event (clock-in *or* clock-out as a discrete row) | **Recommended** |
| One employee-day (a row per employee per calendar date, holding computed totals) | Rejected as the *aggregate root* — see below |
| Clock transaction | Same as "attendance event"; naming variant |
| Attendance summary | Rejected as an aggregate — this is a read model/projection, not a source of truth |

**Why an event, not a day-summary:**

- An employee-day summary requires deciding, up front, how many clock-ins per day are legal, how
  overnight shifts roll up to "a day," and how corrections are represented — none of which can be
  answered from the current codebase (see §11). Modeling the *event* first avoids baking an
  unconfirmed business rule into the schema.
- Raw events are the append-mostly source of truth; anything aggregate/derived (hours worked,
  lateness, daily summary) is a computation *over* events, not a replacement for them. This keeps
  Attendance in the same shape as an audit-log/ledger: cheap to append, cheap to reason about,
  and it lets Leave/Overtime/Payroll/Analytics (§9) each build their own projection over the same
  raw facts instead of contending over one mutable summary row.
- This mirrors the only precedent in the codebase for "something that happens at a point in
  time tied to an employee": there isn't one yet in HR (all HR master data reviewed is
  slowly-changing reference data, not event data). The closest structural analogy is
  `AuditLog`-style append-only records, not the CRUD master-data pattern of `Shift`/`JobGrade`/etc.
- A single "employee-day" row invites read-modify-write races the moment there's more than one
  clock action per day (a break, a correction, a second shift) — an event row sidesteps that by
  construction.

This does **not** rule out an `AttendanceDailySummary` as a *second*, derived aggregate later
(needed by Payroll/Timesheet) — but that's an additive future step, not part of this recommendation,
and not something to decide now (§11).

---

## 2. Entity Fields

Only fields directly implied by "one clock transaction" and by patterns already established in
the codebase are proposed. Anything requiring an unconfirmed business rule is deliberately
omitted and listed in §11 instead of guessed.

| Field | Type | Nullable | Purpose | Why required |
|---|---|---|---|---|
| `id` | UUID | No | Primary key | `UUIDMixin`, identical to every other entity reviewed |
| `hr_employee_id` | UUID (FK) | No | Whose attendance this event belongs to | The entire point of the record; every reviewed master-data child (e.g. `HrEmployee.department_id`) is non-nullable when the relationship is mandatory |
| `event_type` | string/enum | No | Distinguishes clock-in vs clock-out (and, if confirmed, break-start/break-end) | An event-based aggregate is meaningless without knowing what kind of event it is |
| `event_time` | timestamptz | No | When the clock action occurred | Core fact being recorded; `timestamptz` matches `TimestampMixin`'s existing convention (`DateTime(timezone=True)`) so it survives timezone ambiguity at the DB layer — see §10 for whether that's sufficient |
| `shift_id` | UUID (FK, nullable) | Yes | Which shift template this event is being measured against | Nullable because whether attendance always occurs against an assigned shift, or can happen with no shift, is unconfirmed (§11) |
| `source` | string/enum | Unconfirmed | How the event was captured (web, mobile, biometric device, manual) | Every risk in §10 (GPS, biometric devices, manual correction) implies this matters, but no capture-channel model exists in the codebase to confirm the enum values against — see §11 |
| `notes` | string, nullable | Yes | Free-text annotation | Direct precedent: `Shift.description`, `HrEmployee.notes` are optional free text on every reviewed entity |
| `created_at` / `updated_at` | timestamptz | No | Audit timestamps | `TimestampMixin`, applied uniformly to every `BaseEntity` |
| `created_by` / `updated_by` | UUID, nullable | Yes | Who/what performed the write | `AuditMixin`, applied uniformly — but note this is the acting `User`, not the `HrEmployee` the event is about, and those two are unlinked (§11) |
| `deleted_at` / `is_deleted` | timestamptz / bool | Yes / No | Soft-delete bookkeeping | `SoftDeleteMixin`, applied uniformly — **but see §10/§11: `BaseRepository.delete()` currently performs a hard `session.delete()`, not a soft delete, so this mixin is inherited but not actually honored by the shared repository today.** Whether Attendance needs real soft-delete (audit trail for corrections) or the inherited-but-unused columns are fine as-is is a business-rule question, not an architectural one. |
| `version` | int | No | Optimistic concurrency | `VersionMixin`, applied uniformly |

**Deliberately not proposed** (would require inferring an unconfirmed business rule):
`location`/GPS coordinates, `device_id`/biometric identifiers, `correction_of_id` (link to an
original event a correction amends), `is_manual_correction`, `approved_by`/approval workflow
fields, `latitude`/`longitude`, `photo_url`. Each maps to a §10 risk with no existing model to
confirm structure or naming against.

---

## 3. Relationships

| Relationship | Cardinality | ON DELETE | Explanation |
|---|---|---|---|
| `AttendanceEvent.hr_employee_id → HrEmployee.id` | many-to-one | **Candidate: RESTRICT**, matching every other FK *into* `HrEmployee` from HR master data. But `HrEmployee` is a person record, and attendance is transactional history *about* that person — RESTRICT would mean an employee can never be deleted while any attendance history exists, which may be exactly right (history must be preserved) or may be wrong (need to purge on offboarding). Not decidable from the codebase — see §11. | The mandatory link; without it the event is orphaned data |
| `AttendanceEvent.shift_id → Shift.id` | many-to-one, nullable | Candidate: RESTRICT (consistent with `HrEmployee.shift_id`'s own FK), if the field exists at all | Ties the event to the shift template it's measured against, for lateness/overtime calculations later — contingent on §11 confirming shift is always known at clock-time |

**Not** a relationship: `AttendanceEvent` to Project Tracking `Employee`, `Assignment`, or `Task`.
No dependency currently exists between HR and Project Tracking (confirmed in §0), and nothing
in this discovery implies Attendance should be the entity that bridges them.

**Also not modeled** (pending §11): a link from `AttendanceEvent` back to the acting `User`
(distinct from `hr_employee_id`), because `User ↔ HrEmployee` itself has no existing link to
build on.

---

## 4. REST API

Proposed, following the exact router/prefix/dependency shape of `api/shifts.py`
(`APIRouter(prefix="/hr/...", tags=[...])`, `CurrentUser` on every route, service injected via a
`Depends`-wrapped factory):

| Method | Path | Why |
|---|---|---|
| `POST` | `/hr/attendance` | Record a single event (clock-in/out). Mirrors `POST /hr/shifts` — one write endpoint, not separate `/clock-in` and `/clock-out` routes, since both are the same aggregate differentiated only by `event_type` (§1). Whether this needs to be split into distinct endpoints depends on §11 (e.g. if clock-out must validate against an open clock-in, a dedicated endpoint might be clearer than a generic POST) |
| `GET` | `/hr/attendance/{event_id}` | Single-record fetch, same shape as every reviewed master-data `GET /{id}` |
| `GET` | `/hr/attendance` | Plain list, matching `GET /hr/shifts` |
| `GET` | `/hr/attendance/paginated` | Paginated + searchable list, matching `GET /hr/shifts/paginated`. Filterable fields would include `hr_employee_id` and a date range — both require confirming the repository's `paginate()` filter mechanics support range filters, which today only supports equality (`BaseRepository._apply_filters`, `column == value`) — a range filter is new capability, not a copy of the existing pattern |
| `PUT` | `/hr/attendance/{event_id}` | Correction/edit of an existing event — contingent entirely on §11 confirming corrections are in scope and how they should be represented (in-place edit vs. append-only compensating event) |
| `DELETE` | `/hr/attendance/{event_id}` | Present for pattern-consistency with every other reviewed entity, but whether attendance history should ever be deletable (vs. append-only, correction-only) is itself a §10/§11 open question |

**Explicitly not proposed yet**, because each depends on an aggregate decision this document
does not make: `POST /hr/attendance/clock-in` + `/clock-out` as distinct actions, any
`/hr/attendance/summary` or per-employee-day rollup endpoint (that's the future
`AttendanceDailySummary` projection, §1/§9), and anything biometric-device or GPS-specific.

---

## 5. Business Rules

**Required** (follow directly from the aggregate definition in §1, no inference beyond it):
- An `AttendanceEvent` must belong to exactly one `HrEmployee` that exists.
- `event_time` must be set (a clock action has to have happened at some point).

**Optional** (plausible, but the codebase gives no basis to include or exclude them — flagged,
not decided):
- Whether an `HrEmployee` must exist to have an active/effective `employment_status` at the time
  of the event (i.e., can a terminated employee have a new attendance event recorded).
- Whether `shift_id`, if provided, must belong to the same employee's currently-assigned shift
  (`HrEmployee.shift_id`), the same cross-column-invariant pattern used for
  `HrEmployee.team_id`/`department_id` in `HrEmployeeService`.
- Whether duplicate/rapid-fire clock-ins within some time window should be rejected at the
  service layer (mirrors `ShiftService`'s `InvalidShiftTimeError`-style validation, but the
  threshold and exact rule are unconfirmed).

**Future** (explicitly out of scope for this discovery, likely owned by consumer modules per
§9, not by Attendance itself):
- Overtime threshold calculation.
- Leave-day reconciliation (an approved leave day suppressing an "absent" read on that date).
- Payroll hour aggregation and rounding rules.
- Approval workflows for manual corrections.

---

## 6. Service Responsibilities

**Belongs in `AttendanceService`** (mirrors `ShiftService`/`HrEmployeeService`'s division of
labor — service owns the UoW/transaction boundary and cross-entity validation; repository stays
dumb):
- Owning the transaction boundary via `uow_factory`, exactly like every reviewed service.
- Validating `hr_employee_id` (and `shift_id`, if kept) exist before insert — same
  existence-check pattern as `HrEmployeeService.create`'s `OrganizationRepository(...).exists(...)`
  calls.
- Any cross-column invariant that turns out to be required (§5 "optional" bullets) once
  confirmed — e.g., "event's shift must match the employee's assigned shift," mirroring
  `HrEmployeeService`'s department/position/team-must-match-organization checks.
- Expunge-on-return and refresh-before-expunge-on-update, identical to every reviewed service,
  for the same session-lifecycle reason documented in `ShiftService`'s docstring.

**Must NOT belong in `AttendanceService`**:
- Overtime/payroll/leave computation — those are downstream consumers (§9), not Attendance's
  own responsibility, the same way `Shift` knows nothing about the `HrEmployee` rows that
  reference it.
- GPS/geofence validation, biometric device integration, or any capture-channel-specific logic —
  if `source` (§2) is confirmed as in-scope, the service validates that a value was provided, not
  the semantics of what a "biometric" reading means.
- Any notion of `User` identity/permissions beyond what `CurrentUser` already provides at the API
  layer — same boundary every reviewed service respects today.

---

## 7. Repository Responsibilities

**Yes — `AttendanceRepository` should remain persistence-only**, subclassing `BaseRepository[AttendanceEvent]`
exactly like `ShiftRepository` subclasses `BaseRepository[Shift]`. Concretely:

- No commits, no rollbacks — inherited from `BaseRepository`'s documented contract ("Never
  commits: callers own the transaction boundary").
- Query helpers only (e.g. a `list_by_employee_and_range(employee_id, start, end)`, mirroring
  `ShiftRepository.get_by_code`) — no business-rule branching, no exception-raising for
  invalid states (that's the service's job, per §6).
- `paginate()` reused/extended from `BaseRepository`, following `ShiftRepository.paginate`'s
  override shape (supplying `SEARCHABLE_FIELDS` and, once needed, employee/date filters).

One open question that belongs here, not decided: whether a date-range filter needs to be added
to `BaseRepository._apply_filters`/`paginate` generically (today it only does equality — §4),
or whether `AttendanceRepository` should implement range queries itself outside the shared
`paginate()` path. That's an implementation-time decision, not an architectural one, and is
noted rather than resolved.

---

## 8. Migration Strategy

**Recommendation: staged — standalone table first, integrated by foreign key only, no
`HrEmployee` schema changes.**

- **Standalone-but-linked** (not fully standalone, not "immediately integrated" in the sense of
  reshaping other tables): the migration creates one new `attendance_events` table with a FK to
  `hr_employees.id` (and optionally `shifts.id`), following the exact shape of migration
  `c4a9d3e17f56` (`create_shifts_table`) — full `BaseEntity` column set
  (`id`/`created_at`/`updated_at`/`created_by`/`updated_by`/`deleted_at`/`is_deleted`/`version`),
  autogenerated `upgrade`/`downgrade`, chained off the current alembic head.
- This is "staged" rather than "immediately integrated" because it deliberately does **not**
  touch `HrEmployee` (no new column added there, unlike how `shift_id` was added to
  `hr_employees` in migration `e7a8ed87ea45` after `Shift` itself landed in `c4a9d3e17f56`). That
  precedent — master data lands standalone first, gets wired into `HrEmployee` in a *second*,
  later migration once the relationship is confirmed — is exactly the shape recommended here,
  except Attendance is event data referencing `HrEmployee`, not the reverse, so there may never
  need to be a second "wiring" migration on `HrEmployee` at all.
- Not "immediately integrated" with Leave/Overtime/Payroll/Timesheet in this same PR — those
  don't exist yet, so there's nothing to integrate with. §9 addresses how the schema stays open
  to them without a future rewrite.

---

## 9. Future Dependencies

How an event-shaped `AttendanceEvent` (§1) avoids forcing a refactor for each consumer:

- **Leave**: reads attendance events (or absence of them) over a date range per employee to
  reconcile against approved leave days. Because Attendance only records *what happened* and
  makes no judgment about *why* a day has no events, Leave can layer its own interpretation on
  top without Attendance needing to know about leave types.
- **Overtime**: computed by a consumer that reads ordered events per employee-day and compares
  elapsed time against `Shift` (via `shift_id`, if confirmed) — Attendance supplies raw
  timestamps, Overtime owns the threshold math (§5 "future", §6 "must not").
- **Payroll**: consumes the same raw events (or a derived `AttendanceDailySummary` projection,
  §1) to compute payable hours. Because raw events remain the source of truth, Payroll's
  rounding/rounding-rule choices don't require mutating Attendance's own schema.
- **Timesheet**: is essentially a per-employee, per-period *view* over the same event stream —
  a read model, not a new write path, so it doesn't require Attendance to add timesheet-specific
  columns.
- **Workforce Analytics**: aggregates across employees/departments/locations over time — every
  dimension it needs (`hr_employee_id → department_id/location_id/team_id` via the existing
  `HrEmployee` relationships already reviewed in §0) is already reachable by joining
  `AttendanceEvent → HrEmployee` without Attendance needing to denormalize any of that onto
  itself.

The common thread: **all five consumers read the event stream and compute their own derived
view; none of them require a schema change to `AttendanceEvent` itself** — which is the main
argument for the event-aggregate choice in §1 over a mutable day-summary row that each consumer
would otherwise need to renegotiate the shape of.

---

## 10. Risks

Identified, not solved:

- **Overnight shifts.** `Shift` already explicitly allows `start_time > end_time`
  (`ShiftService`'s `InvalidShiftTimeError` docstring: "Overnight shifts... are valid and
  intentionally not rejected"). An attendance event's "day" attribution for an overnight shift is
  ambiguous (clock-in 22:00 / clock-out 06:00 next day — which calendar date does it belong to?).
- **Multiple clock-ins per day.** No rule confirms whether more than one clock-in/out pair per
  day is expected (e.g. lunch break, split shift) or should be rejected.
- **Timezone.** `TimestampMixin` stores `DateTime(timezone=True)`, which handles *storage*
  correctly, but says nothing about which timezone a field employee's clock action should be
  *interpreted* in relative to their assigned `Location` — Location itself has no timezone field
  today (reviewed in §0; `Location` has no `timezone` column).
- **Mobile GPS.** Roadmap context (§0) places GPS alongside Attendance/Check-In/Check-Out as a
  Phase 4 deliverable, but no GPS/geolocation model exists anywhere in the reviewed codebase to
  confirm whether it's a field on the event itself, a separate aggregate, or out of scope for
  this PR.
- **Manual correction.** No existing entity in the codebase models "this record amends/replaces
  that record" (no precedent for a self-referential correction chain, distinct from
  `HrEmployee.manager_id`'s simple self-reference, which is a *current-state* pointer, not a
  *historical-amendment* pointer).
- **Biometric devices.** No device/integration model exists to confirm what a `source`/device
  identifier field should look like, or whether device trust/verification is in scope.
- **Duplicate attendance.** Closely related to "multiple clock-ins" above — whether the same
  employee clocking in twice within a short window is a duplicate to reject or a legitimate
  break/re-entry is unconfirmed.
- **Soft-delete vs. hard-delete mismatch.** `BaseEntity` gives every entity `SoftDeleteMixin`
  columns, but `BaseRepository.delete()` performs a real `session.delete()` (hard delete) — none
  of the reviewed services or repositories actually branch on `is_deleted`/query-filter it out.
  For an audit-sensitive aggregate like Attendance, inheriting columns that the shared repository
  doesn't honor is a risk worth surfacing before relying on them for compliance/correction history.
- **`User` ↔ `HrEmployee` gap.** Every API route authenticates a `User` (§0), but nothing links
  `User` to `HrEmployee`. If attendance is meant to be self-service (an employee clocking
  themselves in via the app they're logged into), the system currently has no way to resolve
  "this authenticated `User` is this `HrEmployee`."
- **Cross-organization/consistency scope.** Unlike `HrEmployee`'s department/position/team,
  which are all validated to share one `organization_id`, it's unconfirmed whether an
  `AttendanceEvent`'s `shift_id` needs any such cross-check against the employee's own
  organization/department/location.

---

## 11. Ambiguities

Per instructions, these are listed, not guessed at. Implementation should not proceed until they
are resolved:

1. **What "one attendance event" actually is, product-wise.** Roadmap context (§0) suggests
   Attendance may originally have meant field-rep GPS check-in/check-out (Phase 4, alongside
   Mission/Visit/Survey/GPS/Photo), while the current codebase (HR module, `Shift` master data)
   points toward an office/workforce clock-in system. These are materially different products
   with different required fields (GPS + photo vs. shift/grace-period matching). Which one this
   aggregate is being built for is not decidable from the code.
2. **`User` vs. `HrEmployee` identity.** No FK links the authenticated `User` to an `HrEmployee`
   row anywhere in the codebase. If self-service clock-in is intended, this link must exist
   *before* Attendance can resolve "who is clocking in" from an authenticated request — and its
   absence is a gap in the HR module, not something Attendance can work around.
3. **Whether `shift_id` is mandatory, optional, or absent** on the event. `HrEmployee.shift_id`
   is already mandatory on the employee — but whether every attendance event must reference a
   shift, may optionally override the employee's default shift, or shouldn't reference one at
   all, is unconfirmed.
4. **Correction semantics.** Is a correction an in-place edit (`PUT`, losing the original value),
   an append-only compensating event (new row, `correction_of_id` link), or an approval-gated
   workflow? No precedent exists in the codebase for any of the three.
5. **Delete semantics.** Should `DELETE` ever be exposed for attendance history at all, given
   it's likely audit-sensitive? If yes, does it need to honor `SoftDeleteMixin` in a way
   `BaseRepository.delete()` currently doesn't (§10)?
6. **Multiple-events-per-day cardinality.** Is more than one clock-in/out pair per employee per
   day valid (breaks, split shifts), and if so, how are they paired for hour calculation? Not
   answerable from `Shift` alone (`break_duration_minutes` is a fixed template value, not a
   record of an actual break taken).
7. **Timezone attribution.** Given `Location` has no timezone field, what timezone should an
   event's calendar-day attribution use — server UTC, employee's `Location`, or device-reported
   local time?
8. **GPS/photo/biometric fields.** Entirely unconfirmed whether any of these are in scope for
   this aggregate or a separate future aggregate/module.
9. **Cross-employee consistency rules.** Whether `shift_id` (if present) must match the
   employee's currently-assigned `HrEmployee.shift_id`, mirroring the
   department/position/team-must-match-organization pattern already enforced in
   `HrEmployeeService`.
10. **Retention/purge on employee offboarding.** Whether `hr_employee_id`'s FK should be
    `RESTRICT` (preserve history forever, block employee deletion) or something else — no
    existing precedent in the codebase deletes an `HrEmployee` at all today, so there's no
    established behavior to follow.

**Stopping here per instructions.** No aggregate has been implemented, no migration has been
written, no code has been changed. Awaiting direction on the ambiguities above before proceeding.

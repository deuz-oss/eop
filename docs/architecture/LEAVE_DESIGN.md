# PR-040 — Leave Architecture Discovery

Status: **Discovery only. No code, no migrations. Awaiting approval.**

---

## 1. Architecture Summary

**Reviewed** (`services/api/src/eop_api/{models,repositories,services,api,schemas}`):

- **HR**: `HrEmployee`, `Shift`, `AttendanceEvent`, `JobGrade`, `EmploymentType`,
  `EmploymentStatus`, `Organization`, `Department`, `Position`, `Team`, `Location`.
- **Project Tracking**: `Employee`, `Assignment`, `Project`, `Task`.
- **Foundation**: `BaseEntity`/mixins (`db/base.py`, `db/mixins.py`), `BaseRepository`
  (`repositories/base.py`), `AbstractUnitOfWork`/`SQLAlchemyUnitOfWork` (`uow/`),
  `FilterParams`/`SearchParams`/`Page`/`PaginationParams` (`schemas/`),
  `CurrentUser`/`RequireRole` (`dependencies/auth.py`, `dependencies/rbac.py`).
- **Migrations**: every `alembic/versions/*` file, in order, through
  `1c4f19907e49_create_attendance_events_table` (current head).
- **Tests**: `test_shift_{repository,service}.py`, `test_shifts_api.py`,
  `test_attendance_event_*`, `test_job_grade_*` — establishing the three-tier test pattern.
- **Also reviewed**: `docs/architecture/ATTENDANCE_DESIGN.md` (the PR-039 discovery doc for
  `AttendanceEvent` — same exercise, one module earlier), `docs/product/06_PRODUCT_ROADMAP.md`.

### Confirmed dependency findings

1. **HR and Project Tracking remain independent bounded contexts.** `HrEmployee`'s own
   docstring (`models/hr_employee.py:20-33`) states it is "deliberately independent from the
   Project Tracking `Employee`." Nothing reviewed for Leave changes this: `Assignment`/`Task`
   FK into Project Tracking's `Employee`, never into `HrEmployee`. This finding is inherited
   unchanged from `ATTENDANCE_DESIGN.md` §0 and re-confirmed here independently.
2. **The `User` ↔ `HrEmployee` gap still exists.** No FK anywhere links the authenticated
   `User` (`models/user.py`, used as `CurrentUser` on every route) to an `HrEmployee` row. This
   was flagged as load-bearing for Attendance's self-service question in
   `ATTENDANCE_DESIGN.md` §11, and it is equally load-bearing here — see §12.
3. **Leave does not appear in the product roadmap.** `docs/product/06_PRODUCT_ROADMAP.md`
   enumerates Phase 4 ("Field Operations": Attendance, Check In, Check Out, Mission, Visit,
   Survey, GPS, Photo) and the MVP list (Authentication, Organization, Employee, Store,
   Attendance, Visit, Mission, Dashboard). **"Leave" is not named in any phase or in the MVP.**
   Unlike Attendance, which had roadmap context to (partially) triangulate against, Leave has
   none. This is the single biggest ambiguity in this discovery — see §12.1.
4. **No `LeaveType`-equivalent master data exists.** Every prior master-data-backed entity
   (`AttendanceEvent` → `Shift`/`HrEmployee`) referenced tables that already existed before it
   landed. There is no comparable pre-existing table for a leave "type" (annual, sick,
   unpaid, ...) to reference. See §3 and §12.2.

### Patterns identified (from `Shift`, `JobGrade`, `EmploymentType`, `EmploymentStatus`, `AttendanceEvent`)

- **Model pattern**: subclass `BaseEntity` (`UUIDMixin` + `TimestampMixin` + `AuditMixin` +
  `SoftDeleteMixin` + `VersionMixin`). Global/simple master data (`JobGrade`,
  `EmploymentType`, `EmploymentStatus`) is flat: `code` (globally unique), `name`,
  `description | None`. Transactional/event data (`AttendanceEvent`) adds mandatory FKs
  (`ON DELETE RESTRICT`), a `datetime` fact column, `sa.Enum(..., native_enum=False)` for
  closed-vocabulary fields backed by a `StrEnum` in `core/`, and a nullable free-text field
  (`remarks`/`notes`/`description`). Every FK from HR data into other HR master data observed
  is `RESTRICT`. Lifecycle/status-bearing entities in the *other* reviewed module
  (`Project.status`, `Task.status`) use a **plain `String` column with a default**, not an enum
  and not a workflow/state-machine abstraction.
- **Repository pattern**: subclass `BaseRepository[Model]`. Never commits. Declares
  module-level `SEARCHABLE_FIELDS` (free-text `ilike` search) and `FILTERABLE_FIELDS`
  (equality-only allowlist) tuples/mappings, and overrides `paginate()` purely to supply
  defaults for those two. Adds narrow `get_by_x` helpers only. `BaseRepository._apply_filters`
  only supports equality — no range/date-span filtering exists anywhere yet.
- **Service pattern**: owns the transaction boundary via an injected `uow_factory`. Validates
  referenced-entity existence via `OtherRepository(uow.session).exists(...)`/`.get(...)` before
  writing, raises local, typed `Exception` subclasses (not HTTP-aware) for every violation, and
  — for cross-column invariants like "department must belong to employee's organization" — does
  the check itself, since it isn't expressible as a plain FK. Every read/write path ends with
  `uow.session.expunge(...)`/`expunge_all()`; `update()` additionally does
  `await uow.session.refresh(updated)` before expunging, to pick up the server-side
  `onupdate=func.now()` on `updated_at`.
- **API pattern**: `APIRouter(prefix="/hr/...", tags=[...])`. Every route takes `CurrentUser`
  (authentication only — no route observed uses `RequireRole`, so no HR/Attendance endpoint
  today is role-gated beyond "authenticated"). Service exceptions are caught per-route and
  mapped to HTTP status (404 not-found, 409 duplicate, 422 invalid-value). Standard route set:
  `POST ""`, `GET ""`, `GET "/paginated"`, `GET "/{id}"`, `PUT "/{id}"`, `DELETE "/{id}"` (204).
  Equality filters for `paginated` are exposed as individual `Query()` params assembled into a
  `FilterParams` via a small `get_x_filters` dependency.
- **Migration pattern**: one Alembic revision per entity, `op.create_table` with the full
  explicit `BaseEntity` column set (`id`, `created_at`, `updated_at`, `created_by`, `updated_by`,
  `deleted_at`, `is_deleted`, `version`), FK constraints inline, indexes created after the table,
  chained via `down_revision` off the current head. Nothing is squashed into an earlier
  migration; master data that gets referenced later (e.g. `Shift` from `HrEmployee`) is wired in
  by a *separate*, later migration on the referencing table, not by editing the original.
- **Testing pattern**: three tiers per entity — repository tests (real, migration-created
  tables, one connection/one transaction rolled back per test), service tests (real tables,
  `TRUNCATE ... CASCADE` teardown, service constructed with an injected `uow_factory`), API
  tests (`TestClient` against the real `app`, `TRUNCATE` teardown, an authenticated-user fixture,
  explicit "requires authentication" 401 tests for every route, then full create/read/update/
  delete/paginate/search coverage including validation-failure and duplicate-conflict cases).

**Conclusion: Leave should follow the `AttendanceEvent` reference shape** (transactional/event
entity with mandatory FKs into HR master data), not the `JobGrade`/`EmploymentType` flat-lookup
shape — Leave is inherently about a specific employee and a specific span of time, not a
reusable global code table.

---

## 2. Proposed Aggregate

**Recommendation: the aggregate root is `LeaveRequest`** — one employee's ask to be away for a
contiguous date span, together with the decision made on that ask.

Evaluated options:

| Candidate | Verdict |
|---|---|
| Leave request (the ask + its lifecycle status, one row per span) | **Recommended** |
| Approved leave (only records already-decided/approved leave, no lifecycle) | Rejected — see below |
| Leave period (an entitlement/balance allocation, e.g. "12 days annual leave for 2026") | Rejected as the aggregate root |
| Leave transaction (a ledger debit/credit against a balance) | Rejected — nothing to post against |

**Why a request, not a balance/period/ledger:**

- A "leave period" or "leave transaction" both presuppose an **entitlement/balance** concept
  (how many days of what type an employee is allowed) that has no existing model anywhere in
  the codebase to build on — there is no `LeaveType`, `LeaveEntitlement`, or `LeaveBalance`
  table today (§1, §12.2). Modeling a ledger before the thing it's a ledger *of* exists would be
  guessing at unconfirmed structure, which these instructions explicitly prohibit.
- "Approved leave" (recording only decided leave, with no pending/rejected state) discards the
  ask itself — but a leave *request* system with no way to represent "submitted, not yet
  decided" doesn't match the plain-English meaning of "request," and every lifecycle-bearing
  entity reviewed in the codebase (`Project.status`, `Task.status`) models the full lifecycle
  in one row via a status column, not by only persisting the terminal state.
- This mirrors `ATTENDANCE_DESIGN.md`'s own reasoning for choosing the raw event over a derived
  summary: model the fact-recording concept that has to exist regardless of which future
  business rules get layered on, not the derived/computed concept (balance, summary) that
  depends on rules this discovery cannot confirm.
- A `LeaveRequest` is naturally the unit `Attendance`'s own future-dependencies section already
  anticipated: `ATTENDANCE_DESIGN.md` §9 states Leave will "read attendance events... to
  reconcile against approved leave days" — i.e. Attendance already expects to consume a leave
  concept shaped as discrete, dated, employee-scoped, status-bearing records. `LeaveRequest`
  is exactly that shape.

This does **not** rule out a future `LeaveBalance`/`LeaveEntitlement` aggregate — that is an
additive step once the underlying business rules (accrual, carry-over, per-type limits) are
confirmed, not part of this recommendation (§10, §12).

---

## 3. Proposed Entity

Only fields directly implied by "one employee's request for a dated span, with a decision
outcome" and by patterns already established in the codebase are proposed. Anything requiring
an unconfirmed business rule is deliberately omitted and listed in §12 instead of guessed.

| Field | Type | Nullable | Purpose | Why required |
|---|---|---|---|---|
| `id` | UUID | No | Primary key | `UUIDMixin`, identical to every entity reviewed |
| `hr_employee_id` | UUID (FK) | No | Whose leave request this is | The entire point of the record; mirrors `AttendanceEvent.employee_id` — mandatory, non-nullable, exactly like every mandatory child FK into `HrEmployee` |
| `start_date` | Date | No | First day of the requested span | Core fact being recorded; `Date` (not `DateTime`) matches `Assignment.start_date`/`Project.start_date`/`HrEmployee.hire_date` — every existing date-only business field in the codebase uses `Date`, not `DateTime` |
| `end_date` | Date | No | Last day of the requested span | Same rationale as `start_date`; `Assignment.end_date`/`Project.end_date` are the direct precedent for a nullable-vs-required end date — here it's required because an open-ended leave span has no precedent to justify defaulting to nullable |
| `status` | string | No | Current lifecycle state of the request | Direct precedent: `Project.status: Mapped[str] = mapped_column(String(50), default="active")` and `Task.status: Mapped[str] = mapped_column(String(50), default="todo")` — plain string with a default, not an enum-mixin, not a workflow engine. The *set of valid values* and *who may transition it* are unconfirmed — see §6, §12.3 |
| `leave_type` | string, unconfirmed | Unconfirmed | Category of leave (e.g. annual, sick, unpaid) | Plausible on its face, but no existing master-data table to reference (unlike `Shift`/`JobGrade` pre-existing `AttendanceEvent`) and no precedent for a plain free-text category field of this kind either — genuinely unconfirmed whether this should be a `String` column (à la `EmploymentStatus.code`) or a not-yet-built FK. **Not proposed as a concrete column here; flagged instead in §12.2** |
| `reason` | string, nullable | Yes | Free-text justification for the request | Direct precedent: `Shift.description`, `HrEmployee.notes`, `AttendanceEvent.remarks` — every reviewed entity carries one optional free-text field |
| `created_at` / `updated_at` | timestamptz | No | Audit timestamps; `created_at` also doubles as "submitted at" | `TimestampMixin`, applied uniformly |
| `created_by` / `updated_by` | UUID, nullable | Yes | Who/what performed the write | `AuditMixin`, applied uniformly — but same caveat as Attendance: this is the acting `User`, not necessarily the `HrEmployee` the request is about, and the two are unlinked (§12.5) |
| `deleted_at` / `is_deleted` | timestamptz / bool | Yes / No | Soft-delete bookkeeping | `SoftDeleteMixin`, applied uniformly — but see §11/§12.11: `BaseRepository.delete()` hard-deletes, so this mixin is inherited but not actually honored today, same gap already flagged in `ATTENDANCE_DESIGN.md` |
| `version` | int | No | Optimistic concurrency | `VersionMixin`, applied uniformly — but note no reviewed service actually branches on `.version` for conflict detection (§11) |

**Deliberately not proposed** (would require inferring an unconfirmed business rule):
`leave_type_id`/`leave_type` (§12.2), `is_half_day`/`half_day_period`/`partial_hours`,
`shift_id`, `approved_by`/`decided_by`/`decided_at`/`decision_notes`, `is_paid`,
`balance_days_used`, `attachment_id`/`document_url`, `cancelled_at`, `duration_days` (computed
vs. stored — unconfirmed whether weekends/holidays are excluded, see §11). Each maps to a §11
risk or §12 ambiguity with no existing model to confirm structure or naming against.

---

## 4. Relationships

| Relationship | Cardinality | ON DELETE | Explanation |
|---|---|---|---|
| `LeaveRequest.hr_employee_id → HrEmployee.id` | many-to-one | **Candidate: RESTRICT**, matching every FK into `HrEmployee` from HR data (`AttendanceEvent.employee_id`, `HrEmployee.manager_id`, etc.) | The mandatory link; without it the request is orphaned data. Same unresolved retention question as Attendance's own §11 (RESTRICT blocks employee deletion forever) — not decidable from the codebase, see §12.9 |

**Not** a relationship: `LeaveRequest.shift_id → Shift.id`. Evaluated and rejected for this
discovery: a `Shift` is a time-of-day template, not something a multi-day date-span request
inherently needs to reference. It would only become relevant if partial-day leave needs to be
measured in shift-hours — an unconfirmed rule (§11, §12.6) — so adding the FK now would be
inferring a business rule this document is instructed not to guess.

**Not** a relationship: `LeaveRequest` to `AttendanceEvent`. No FK is proposed in either
direction. `ATTENDANCE_DESIGN.md` §9 already anticipated this exact boundary: Leave and
Attendance are meant to be reconciled by a *consumer* reading both by `hr_employee_id` +
date range, not by one holding a foreign key into the other. Adding an FK now would
pre-empt that reconciliation design before it's been discovered.

**Not** a relationship: `LeaveRequest` to Project Tracking (`Employee`, `Assignment`, `Project`,
`Task`). Confirmed independent bounded contexts (§1); nothing in this discovery implies Leave
should bridge them, and no existing code does.

**Also not modeled** (pending §12): a link from `LeaveRequest` to the acting `User` as a
business-meaningful "approver" field, distinct from the generic `AuditMixin.updated_by` —
because `User ↔ HrEmployee` itself has no existing link to build on (§1 finding 2).

---

## 5. REST API

Proposed, following the exact router/prefix/dependency shape of `api/attendance_events.py`
(`APIRouter(prefix="/hr/...", tags=[...])`, `CurrentUser` on every route, service injected via a
`Depends`-wrapped factory):

| Method | Path | Why |
|---|---|---|
| `POST` | `/hr/leave-requests` | Submit a request. Mirrors `POST /hr/attendance-events` — one write endpoint, `status` defaults to whatever the initial value is confirmed to be (§12.3) |
| `GET` | `/hr/leave-requests/{id}` | Single-record fetch, same shape as every reviewed entity |
| `GET` | `/hr/leave-requests` | Plain list, matching `GET /hr/shifts` / `GET /hr/attendance-events` |
| `GET` | `/hr/leave-requests/paginated` | Paginated + searchable list, matching the `AttendanceEvent` shape. Filterable fields would include `hr_employee_id` and `status` (both equality — directly supported by `BaseRepository._apply_filters` today) and a start/end date range (**not** supported today — same gap already flagged in `ATTENDANCE_DESIGN.md` §4/§7: `_apply_filters` only does equality) |
| `PUT` | `/hr/leave-requests/{id}` | Edit request details and/or change `status` — **contingent on §12.3/§12.10**: whether "edit the request" and "record a decision" should be the same generic endpoint (mirroring how `Project`/`Task` mutate `status` via plain `PUT`) or split into dedicated action endpoints. No existing entity in the codebase has a lifecycle-transition endpoint to copy either way |
| `DELETE` | `/hr/leave-requests/{id}` | Present for pattern-consistency with every other reviewed entity, but whether a *decided* (approved/rejected) request should ever be hard-deletable is a §11/§12.11 open question, exactly as flagged for `AttendanceEvent` |

**Explicitly not proposed yet**, because each depends on a decision this document does not make:
`POST /hr/leave-requests/{id}/approve` + `/reject` as distinct action endpoints (would require
confirming §12.3/§12.10 first, and per this PR's constraints, no Approval Engine is being
designed), any `/hr/leave-requests/balance` or entitlement-summary endpoint (that presupposes
the not-yet-existing balance concept, §2/§12.2), and anything self-service-scoped (e.g. "my
leave requests" resolved from the authenticated `User`) — blocked on the `User`↔`HrEmployee`
gap (§12.5).

---

## 6. Business Rules

**Mandatory** (follow directly from the aggregate definition in §2, or are the same class of
structural-validity check `ShiftService.InvalidShiftTimeError` already applies to `Shift`):
- A `LeaveRequest` must belong to exactly one `HrEmployee` that exists.
- `start_date` and `end_date` must both be set.
- `end_date` must not be earlier than `start_date` — a direct structural-integrity check, the
  same category as `Shift`'s existing start/end validation, not a policy choice about how many
  days may be requested.

**Optional** (plausible, but the codebase gives no basis to include or exclude them — flagged,
not decided):
- Whether an `HrEmployee` must have an active `employment_status` to submit a request (mirrors
  the identical "optional" bullet already flagged for Attendance in `ATTENDANCE_DESIGN.md` §5).
- Whether overlapping `LeaveRequest`s for the same employee should be rejected — requires a
  date-range query the repository foundation does not support today (§5, §7).
- Whether `status` transitions must follow an enforced sequence (e.g.
  `PENDING → APPROVED/REJECTED`, then optionally `→ CANCELLED`) versus free-form updates, and
  who (which role) may perform which transition — ties to `RequireRole`, which exists but is
  unused by any HR/Attendance endpoint reviewed (§1).
- Whether `leave_type` (§3, §12.2) constrains any other field (e.g. only certain types allow
  half-days).

**Future** (explicitly out of scope for this discovery, likely owned by consumer modules per
§10, not by Leave itself):
- Leave balance/entitlement accrual, carry-over, and deduction.
- Leave-vs-Attendance reconciliation (an approved `LeaveRequest` suppressing an "absent" read on
  an `AttendanceEvent` gap) — already anticipated in `ATTENDANCE_DESIGN.md` §9, not yet built on
  either side.
- Public-holiday and weekend exclusion from day-count calculations.
- Notification dispatch to a manager/HR on submission or decision.
- Multi-level or role-gated approval routing (explicitly excluded by this PR's own constraints).

---

## 7. Service Responsibilities

**Belongs in `LeaveRequestService`** (mirrors `AttendanceEventService`/`ShiftService`'s division
of labor — service owns the UoW/transaction boundary and cross-entity validation; repository
stays dumb):
- Owning the transaction boundary via `uow_factory`, exactly like every reviewed service.
- Validating `hr_employee_id` exists before insert — same existence-check pattern as
  `AttendanceEventService.create`'s `HrEmployeeRepository(...).exists(...)` call.
- The `end_date >= start_date` structural check (§6).
- Any status-transition validation that turns out to be required (§6 "optional" bullets) once
  confirmed.
- Expunge-on-return and refresh-before-expunge-on-update, identical to every reviewed service.

**Must NOT belong in `LeaveRequestService`**:
- Leave balance/entitlement math or payroll deduction — those are downstream consumers (§10),
  not Leave's own responsibility, the same way `Shift` knows nothing about the `HrEmployee`
  rows that reference it.
- Attendance reconciliation logic — Leave supplies the "approved, dated" fact; Attendance (or a
  future reconciliation consumer) does the join and interpretation, mirroring the boundary
  `ATTENDANCE_DESIGN.md` §6 already drew from the other side.
- Notification/email dispatch on submission or decision.
- Multi-level approval routing or any generalized workflow/state-machine abstraction (excluded
  by this PR's constraints).
- Any notion of `User` identity/permissions beyond what `CurrentUser`/`RequireRole` already
  provide at the API layer — same boundary every reviewed service respects today.

---

## 8. Repository Responsibilities

**Yes — `LeaveRequestRepository` should remain persistence-only**, subclassing
`BaseRepository[LeaveRequest]` exactly like `AttendanceEventRepository` subclasses
`BaseRepository[AttendanceEvent]`. Concretely:

- No commits, no rollbacks — inherited from `BaseRepository`'s documented contract.
- Query helpers only (e.g. a `list_by_employee_and_range(hr_employee_id, start, end)`, mirroring
  the kind of helper `ATTENDANCE_DESIGN.md` §7 already anticipated `AttendanceRepository` would
  need) — no business-rule branching, no exception-raising for invalid states (that's the
  service's job, per §7).
- `paginate()` reused/extended from `BaseRepository`, supplying `SEARCHABLE_FIELDS` (candidate:
  `reason`, mirroring `AttendanceEvent.remarks`) and `FILTERABLE_FIELDS` (candidate:
  `hr_employee_id`, `status` — both equality, both directly supported today).

Same open question already on record for Attendance, restated here rather than resolved: a
date-range filter (for both `paginate()`'s `start_date`/`end_date` filtering and any future
overlap check) is not something `BaseRepository._apply_filters` supports today (equality only)
— whether to generalize the shared foundation or implement range queries locally in
`LeaveRequestRepository` is an implementation-time decision, not an architectural one.

---

## 9. Migration Strategy

**Recommendation: staged — standalone table first, integrated by foreign key only, no
`HrEmployee` schema changes.** Identical reasoning to `ATTENDANCE_DESIGN.md` §8, restated for
Leave:

- **Standalone-but-linked**: the migration creates one new `leave_requests` table with a FK to
  `hr_employees.id`, following the exact shape of migration `1c4f19907e49`
  (`create_attendance_events_table`) — full `BaseEntity` column set, autogenerated
  `upgrade`/`downgrade`, chained off the current alembic head (`1c4f19907e49`).
- This is "staged" rather than "immediately integrated" because it deliberately does **not**
  touch `HrEmployee` — no new column added there. The established precedent in this codebase is
  that a referencing entity lands standalone first, and `HrEmployee` only gets a new column in a
  *second*, later migration if a "current/effective" pointer back is ever confirmed as needed
  (as happened for `shift_id` in `e7a8ed87ea45`, after `Shift` itself landed in `c4a9d3e17f56`).
  Because Leave is transactional/historical data referencing `HrEmployee` (like
  `AttendanceEvent`), not the reverse, there may never need to be such a second migration at all.
- Not "immediately integrated" with a future `LeaveBalance`/`LeaveType` module in this same PR —
  those don't exist, so there's nothing to integrate with yet. §10 addresses how the schema
  stays open to them without a future rewrite.

---

## 10. Future Readiness

How a request-shaped `LeaveRequest` (§2) avoids forcing a refactor for each future consumer:

- **Attendance**: reads `LeaveRequest` rows (`status = APPROVED`, per employee, over a date
  range) to reconcile against gaps in the `AttendanceEvent` stream — exactly the direction
  `ATTENDANCE_DESIGN.md` §9 already committed to from the Attendance side. Because Leave only
  records the request and its decision, and makes no judgment about attendance itself, this
  reconciliation can be built entirely as a read over both streams without either module
  changing shape.
- **Overtime**: has no direct dependency on Leave identified in this discovery; the main
  requirement is that Leave not need to change shape once Overtime exists, which holds as long
  as Leave doesn't try to pre-compute hours/day-counts itself now (§6 "future").
- **Payroll**: consumes `APPROVED` `LeaveRequest`s (once a paid/unpaid distinction is confirmed,
  §3/§12.7) to compute deductions or paid-leave pay. Because the request record stays the source
  of truth for "what was asked for and decided," Payroll's own rounding/rate rules don't require
  mutating `LeaveRequest`'s schema.
- **Timesheet**: a per-employee, per-period *view* combining `LeaveRequest` and
  `AttendanceEvent` — a read model, not a new write path, so no timesheet-specific columns are
  needed on `LeaveRequest` itself.
- **Analytics**: aggregates across employees/departments/locations/time; every dimension it
  needs is reachable by joining `LeaveRequest → HrEmployee` (already reviewed relationships:
  `department_id`/`location_id`/`team_id`) without `LeaveRequest` needing to denormalize any of
  that onto itself — the same argument `ATTENDANCE_DESIGN.md` §9 made for `AttendanceEvent`.

The common thread, carried over from Attendance's own precedent: **all five consumers read the
request stream and compute their own derived view; none of them require a schema change to
`LeaveRequest` itself** — which is the main argument for the request-aggregate choice in §2 over
a mutable balance/summary row each consumer would otherwise need to renegotiate the shape of.

---

## 11. Risks

Identified, not solved:

- **Overlapping leave.** No rule confirms whether an employee may have two `LeaveRequest`s with
  overlapping date spans, or whether the system should reject a second request that overlaps an
  already-approved (or even already-pending) one.
- **Partial-day / half-day leave.** No fractional-day precedent exists anywhere in the reviewed
  codebase — `Shift.break_duration_minutes` is a fixed template value, not a record of a
  variable actual duration, so there's nothing to model half-day leave against.
- **Holidays and weekends.** Whether `end_date - start_date` counts calendar days or working
  days (excluding weekends/public holidays) is unconfirmed, and no `Holiday`/`WorkCalendar`
  entity exists in the codebase to resolve it.
- **Timezone.** Same gap already flagged in `ATTENDANCE_DESIGN.md` §10: `Location` has no
  timezone field, so which timezone a "day" boundary is interpreted in in relation to a
  field employee's location is unresolved — directly relevant here since `start_date`/`end_date`
  are calendar dates.
- **Shift changes.** `HrEmployee.shift_id` is mandatory, but whether a `LeaveRequest` needs to
  account for shift hours (for partial-day math) or shift reassignment mid-request is
  unconfirmed (§4, §12.6).
- **Attendance reconciliation.** No code exists yet on either side to actually perform the
  Leave↔Attendance join `ATTENDANCE_DESIGN.md` §9 anticipated — both are new, so the
  reconciliation consumer itself doesn't exist and its exact matching logic (day-boundary rules,
  precedence when both a leave day and an attendance event exist) is undefined.
- **Payroll interaction.** Paid-vs-unpaid leave is not modeled (§3); without it, Payroll cannot
  distinguish which `LeaveRequest`s affect pay.
- **Retroactive edits.** No precedent exists in the codebase for amending a decided record (same
  gap `ATTENDANCE_DESIGN.md` §10 flagged for attendance corrections) — editing an already
  `APPROVED`/`REJECTED` `LeaveRequest` has no defined semantics here either.
- **Status-transition races.** `VersionMixin` gives every entity a `version` column, but no
  reviewed service actually checks it for optimistic-concurrency conflicts on update — two
  concurrent decisions on the same request (e.g. an approve and a cancel racing) would not be
  detected today.
- **Soft-delete vs. hard-delete mismatch.** Same inherited-but-unused gap as every entity:
  `BaseRepository.delete()` performs a real `session.delete()`, not a soft delete, despite
  `SoftDeleteMixin` columns being present.
- **`User` ↔ `HrEmployee` gap.** If self-service leave submission is intended (an employee
  requesting leave for themselves via the app they're logged into), the system has no way to
  resolve "this authenticated `User` is this `HrEmployee`" — identical to the gap
  `ATTENDANCE_DESIGN.md` §10 flagged for self-service clock-in.
- **No approver identity.** Relatedly, if a manager/HR admin approves a request, nothing in the
  schema proposed here (§3) records *who* decided it as a business-meaningful field, only the
  generic `AuditMixin.updated_by`.

---

## 12. Ambiguities

Per instructions, these are listed, not guessed at. Implementation should not proceed until
they are resolved:

1. **Leave is not in the product roadmap.** `docs/product/06_PRODUCT_ROADMAP.md` names
   Attendance, Check In, Check Out, Mission, Visit, Survey, GPS, and Photo for Phase 4, and
   Authentication/Organization/Employee/Store/Attendance/Visit/Mission/Dashboard for the MVP —
   "Leave" appears nowhere. Unlike Attendance, which at least had roadmap phrasing to partially
   triangulate against, there is no documented product intent for Leave to check this design
   against at all. This is the most significant open question in this discovery.
2. **`leave_type` structure.** Is leave categorized at all (annual/sick/unpaid/etc.), and if so,
   is it a plain string (à la `EmploymentStatus.code`) or a foreign key to a not-yet-built
   `LeaveType` master-data table? No precedent table exists to confirm either shape, unlike
   `Shift`/`JobGrade` which already existed before `AttendanceEvent` referenced them.
3. **`status` values and transition rules.** What are the valid values (`PENDING`, `APPROVED`,
   `REJECTED`, `CANCELLED`, others?), is a strict transition sequence enforced, and by whom?
   `RequireRole` exists in the codebase but is unused by any HR/Attendance endpoint today, so
   there's no precedent for how role-gating a transition would actually be wired.
4. **Approver identity.** If a decision requires a specific person/role, should that be recorded
   as a business-meaningful field (distinct from generic `AuditMixin.updated_by`)? This is
   downstream of the `User`↔`HrEmployee` gap (#5 below) — if approvers are `HrEmployee`s (e.g.
   a manager), there's currently no way to resolve which authenticated `User` corresponds to
   which `HrEmployee` approver either.
5. **`User` vs. `HrEmployee` identity.** No FK links the authenticated `User` to an `HrEmployee`
   row anywhere in the codebase (inherited unresolved from `ATTENDANCE_DESIGN.md` §11). If
   self-service submission or approval is intended, this link must exist before Leave can
   resolve "who is this" from an authenticated request.
6. **Whether `shift_id` is referenced at all.** Unconfirmed whether partial-day leave
   calculations (if in scope) need to measure against the employee's shift hours, making a
   `shift_id` FK relevant, or whether Leave should stay entirely shift-agnostic.
7. **Paid vs. unpaid, and entitlement/balance dependency.** No `LeaveBalance`/`LeaveEntitlement`
   concept exists anywhere in the codebase to confirm whether `LeaveRequest` needs to reference
   one, defer to one, or exist independently of one for this PR.
8. **Overlap detection.** Should the system reject a new request that overlaps an existing one
   for the same employee, and does `BaseRepository` need a new range/overlap-query capability
   (today `_apply_filters` is equality-only) to support it?
9. **Retention/purge on employee offboarding.** Whether `hr_employee_id`'s FK should be
   `RESTRICT` (preserve history forever, block employee deletion) or something else — same
   unresolved question already on record for `AttendanceEvent.hr_employee_id` in
   `ATTENDANCE_DESIGN.md` §11; no existing code deletes an `HrEmployee` today, so there's no
   established behavior to follow either way.
10. **Approve/reject endpoint shape.** Should a decision be recorded via a generic `PUT` with a
    `status` field (mirroring how `Project`/`Task` mutate `status` today) or via dedicated
    action endpoints (`POST .../approve`, `.../reject`)? No lifecycle-transition endpoint exists
    anywhere in the reviewed codebase to copy either pattern from.
11. **Delete semantics.** Should `DELETE` ever be exposed for a *decided* leave request, given
    it's likely audit-sensitive? If yes, does it need to honor `SoftDeleteMixin` in a way
    `BaseRepository.delete()` currently doesn't (§11) — same open question already on record for
    `AttendanceEvent`?
12. **Day-count semantics.** Does `end_date - start_date` represent calendar days or working
    days (excluding weekends/holidays)? No `Holiday`/`WorkCalendar` entity exists to resolve
    this, and no precedent field anywhere computes or stores a duration this way.

**Stopping here per instructions.** No aggregate has been implemented, no migration has been
written, no code has been changed. Awaiting direction on the ambiguities above — particularly
§12.1 (Leave's absence from the roadmap) — before proceeding.

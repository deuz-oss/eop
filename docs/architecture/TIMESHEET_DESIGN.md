# PR-045 — Timesheet Architecture Discovery

Status: **Discovery only. No code, no migrations. Awaiting approval.**

---

## 1. Executive Summary

**Recommendation: `Timesheet` is a new, persisted aggregate — one `HrEmployee`'s submission
for one arbitrary contiguous date span, holding only the submission/decision fact (span +
status), never the computed hour totals.** It follows the same "request-shaped" pattern already
used for `LeaveRequest` and `OvertimeRequest`, not the day/week/month/pay-period bucket shape the
PR title suggests as an open question.

The single most load-bearing finding of this discovery is that **three independent prior
discovery documents have already, unprompted, characterized "Timesheet" as a pure read
model**:

- `ATTENDANCE_DESIGN.md` §9: *"Timesheet: is essentially a per-employee, per-period view over
  the same event stream — a read model, not a new write path, so it doesn't require Attendance
  to add timesheet-specific columns."*
- `LEAVE_DESIGN.md` §10: *"Timesheet: a per-employee, per-period view combining `LeaveRequest`
  and `AttendanceEvent` — a read model, not a new write path, so no timesheet-specific columns
  are needed on `LeaveRequest` itself."*
- `HOLIDAY_CALENDAR_DESIGN.md` §8: *"Timesheet: a per-employee, per-period view that would
  overlay holiday dates as a classification/display concern — pure read, no write path, no
  schema dependency."*

This discovery does **not** contradict that finding for the *hour totals* — they remain
computed, never stored, exactly as those three documents anticipated. But it does find one gap
in that framing: a "read model" has no place to record the *business action* of submitting and
approving a period, the same way a `LeaveRequest` is not just a computed day-count but a
persisted ask-and-decision. Recommendation: `Timesheet` persists the ask-and-decision
(employee, span, status) and computes everything else on read, mirroring `LeaveRequest`'s own
split between what is stored (`start_date`/`end_date`/`status`) and what is deliberately left
uncomputed (day-count, `LEAVE_DESIGN.md` §3/§11).

Timesheet is the first HR aggregate in this codebase whose core read path spans four other
entities (`AttendanceEvent`, `LeaveRequest`, `OvertimeRequest`, `Holiday`). Earlier drafts of
this discovery treated the equality-only nature of `BaseRepository._apply_filters` as the
central architectural blocker for that read path. **On review, that conclusion is not supported
by the evidence and has been withdrawn** (§6): a single new consumer needing a capability the
shared foundation doesn't have is not, by itself, evidence that the foundation should change —
every prior discovery in this codebase has consistently declined to generalize shared
infrastructure ahead of a second confirmed need, and this document now holds Timesheet to that
same standard. The real open question is narrower and more structural: **where should a
query that reads and combines multiple aggregates live, given that every repository reviewed is
scoped to exactly one model?** That question is analyzed on its own in §7 and left as an
explicit architectural ambiguity, not resolved by inventing a new abstraction.

Like `LeaveRequest` (`LEAVE_DESIGN.md` §12.1) and `Holiday`
(`HOLIDAY_CALENDAR_DESIGN.md` §10.8) before it, **"Timesheet" and "Payroll" appear nowhere in
`docs/product/06_PRODUCT_ROADMAP.md`** — this is now the third consecutive HR module with no
roadmap grounding, and the first with no `PayPeriod`/`Payroll` concept anywhere to anchor its
period boundary against either.

---

## 2. Evidence Reviewed

**HR module** (`services/api/src/eop_api/{models,repositories,services,api,schemas}`):
`HrEmployee` (`models/hr_employee.py`), `Shift` (`models/shift.py`), `AttendanceEvent`
(`models/attendance_event.py`, `core/attendance.py`), `LeaveRequest` (`models/leave_request.py`),
`LeaveBalance` (`models/leave_balance.py`, `repositories/leave_balance.py`,
`services/leave_balance.py`), `Holiday` (`models/holiday.py`), `OvertimeRequest`
(`models/overtime_request.py`, `repositories/overtime_request.py`,
`services/overtime_request.py`, `api/overtime_requests.py`).

**Foundation**: `Base`/`BaseEntity` (`db/base.py`), mixins (`db/mixins.py`:
`UUIDMixin`/`TimestampMixin`/`AuditMixin`/`SoftDeleteMixin`/`VersionMixin`), `BaseRepository`
(`repositories/base.py`), `AbstractUnitOfWork`/`SQLAlchemyUnitOfWork` (`uow/base.py`,
`uow/sqlalchemy.py`), `PaginationParams`/`Page` (`schemas/pagination.py`),
`FilterParams`/`SearchParams` (`schemas/search.py`), `Pagination` dependency
(`dependencies/pagination.py`). Also reviewed the full top-level `eop_api` package layout
(`models`, `repositories`, `services`, `api`, `schemas`, `core`, `db`, `uow`, `dependencies`,
`exceptions`, `events`, `jobs`, `middleware`, `notifications`, `storage`) — confirmed there is no
`queries/`, `read_models/`, or `projections/`-style directory or module anywhere in the codebase
(§7).

**Previous discovery documents**: `ATTENDANCE_DESIGN.md` (PR-039), `LEAVE_DESIGN.md` (PR-040),
`HOLIDAY_CALENDAR_DESIGN.md` (PR-041). No `OVERTIME_REQUEST_DESIGN.md` or
`TIME_MANAGEMENT_DOMAIN.md` exist in the repository or in `git log --all` history for
`docs/architecture/` — only three discovery docs were ever committed
(`d3067f0`, `0b7c15d`, `120c639` added `HOLIDAY_CALENDAR_DESIGN.md`, `LEAVE_DESIGN.md`,
`ATTENDANCE_DESIGN.md` respectively). `OvertimeRequest` and `LeaveBalance` both landed
(`44ec2ff`, `f533172`) with **no accompanying discovery document at all** — this is a break from
the pattern the first two modules established, and means this discovery has no prior-art
document to check `OvertimeRequest`'s or `LeaveBalance`'s own design reasoning against, only
their resulting code.

**Also reviewed**: `docs/product/06_PRODUCT_ROADMAP.md` (full file), every file in
`alembic/versions/` (23 migrations, current head `6a370704cee5` /
`create_leave_balances_table`, chained off `092c2a938797`), `models/user.py` (grepped for any
`HrEmployee` reference — none found, confirming the `User` ↔ `HrEmployee` gap first flagged in
`ATTENDANCE_DESIGN.md` §11 still holds), `dependencies/rbac.py`/`api/roles.py` (confirmed
`RequireRole` is used only by `roles.py`; no HR/Attendance/Leave/Overtime endpoint is role-gated).

---

## 3. Aggregate Analysis

**Question: what is the aggregate root, and does it represent one employee-day, employee-week,
employee-month, pay period, or something else?**

| Candidate | Verdict |
|---|---|
| One employee-day | Rejected |
| One employee-week | Rejected |
| One employee-month | Rejected |
| One pay period | Rejected |
| One employee, one arbitrary contiguous date span, submission + decision | **Recommended** |

**Why not employee-day:** this is precisely the concept `ATTENDANCE_DESIGN.md` §1 already
evaluated and rejected as `AttendanceEvent`'s own aggregate root ("`AttendanceDailySummary`...
an additive future step, not part of this recommendation"). A day-level `Timesheet` would just be
that already-rejected `AttendanceDailySummary` concept under a new name. Nothing in the codebase
has changed since that rejection to justify reviving it now.

**Why not week/month:** no entity anywhere in the codebase buckets by a fixed calendar unit.
`Shift` is a time-of-day template (`start_time`/`end_time`, `models/shift.py:30-31`), not a
weekly schedule. `LeaveRequest` and `OvertimeRequest` both use arbitrary `start_date`/`end_date`
(`overtime_date` for the latter — a single date, not a span) rather than being bucketed to
calendar weeks or months. There is no `WeekPeriod`/`MonthPeriod`/calendar-bucket precedent to
build on; inventing one now would be guessing at unconfirmed structure.

**Why not pay period:** there is no `PayPeriod`/`Payroll` concept anywhere in the codebase or in
`docs/product/06_PRODUCT_ROADMAP.md` (Phase 5 "Performance" lists KPI/Target/Achievement/
Dashboard/Reporting — no payroll). This is the least-grounded of the four named candidates: unlike
week/month, which are at least generic calendar concepts, "pay period" presupposes a payroll
cadence (weekly? bi-weekly? monthly?) that nothing in this codebase defines.

**Why "something else" — an arbitrary date-span request, mirroring `LeaveRequest`:**
`LeaveRequest` (`models/leave_request.py:12-28`) is already exactly this shape: "one employee's
request to be away for a dated span," `start_date`/`end_date` as plain `Date` columns with no
fixed bucket width, plus a storage-only `status` string. A `Timesheet` submission has the
identical shape — one employee, one dated span (whatever span the caller submits it for), one
decision (`status`). Recommending this shape over inventing a week/month/pay-period bucket avoids
the exact category of error `LEAVE_DESIGN.md` §2 itself warned against: modeling a derived/bucketed
concept before the business rule that defines its width is confirmed.

This does not resolve *what span* a Timesheet is submitted for in practice (a week, a month, a
pay period) — that remains a genuine ambiguity (§13.1), but it is the *caller's* choice of
`start_date`/`end_date`, not a schema-level bucket the aggregate itself enforces. This is a
deliberate parallel to how `LeaveRequest` does not enforce any particular span length either.

---

## 4. Entity Analysis

**Question: which data belongs inside the aggregate, which should remain a projection, which
fields should be stored, and which values should always be computed?**

| Field | Belongs in aggregate? | Why |
|---|---|---|
| `id` (UUID) | Yes | `UUIDMixin`, universal |
| `employee_id` (UUID, FK) | Yes | The entire point of the record; matches the exact column name (`employee_id`, not `hr_employee_id`) used by `AttendanceEvent.employee_id` (`models/attendance_event.py:44`), `LeaveRequest.employee_id` (`models/leave_request.py:36`), `OvertimeRequest.employee_id` (`models/overtime_request.py:37`), and `LeaveBalance.employee_id` (`models/leave_balance.py:31`) — every FK into `HrEmployee` from a transactional/request entity uses this name, not the longer form the earlier `ATTENDANCE_DESIGN.md` draft proposed before implementation |
| `start_date` / `end_date` (Date) | Yes | Direct precedent: `LeaveRequest.start_date`/`end_date` (`models/leave_request.py:39-40`) — `Date`, not `DateTime`, matches every whole-day business field reviewed |
| `status` (String, default) | Yes | Direct precedent: `LeaveRequest.status`/`OvertimeRequest.status`, both `String(50)`, both `default="pending"`, both explicitly "storage only -- no transition validation" (`models/leave_request.py:41-43`, `models/overtime_request.py:43-45`) |
| `reason`/notes (String, nullable) | Unconfirmed | Plausible free-text precedent exists on every reviewed entity (`Shift.description`, `LeaveRequest.reason`, `OvertimeRequest.reason`), but whether a Timesheet submission needs employee-facing comments has no basis to confirm either way — not proposed as a certain column, flagged in §13.4 |
| `created_at`/`updated_at` | Yes | `TimestampMixin`, universal; `created_at` can double as "submitted at," mirroring `LEAVE_DESIGN.md` §3's identical reasoning for `LeaveRequest.created_at` |
| `created_by`/`updated_by` | Yes | `AuditMixin`, universal — same caveat as every prior entity: this is the acting `User`, unlinked from `HrEmployee` (§2) |
| `deleted_at`/`is_deleted` | Yes (inherited, not honored) | `SoftDeleteMixin`, universal — but `BaseRepository.delete()` performs a hard `session.delete()` (`repositories/base.py:59-66`), so this is inherited-but-unused for every entity reviewed, Timesheet included |
| `version` | Yes (inherited, not checked) | `VersionMixin`, universal — no reviewed service branches on it for optimistic-concurrency conflicts, same systemic gap noted in every prior discovery |

**Computed, never stored** (projections from other aggregates, read at query time, not persisted
on `Timesheet`):

- **Worked hours** — projected from `AttendanceEvent` rows (`event_type`/`event_time`,
  `core/attendance.py:4-10`) matching `employee_id` within `[start_date, end_date]`.
- **Overtime hours** — projected from `OvertimeRequest` rows (`start_time`/`end_time`,
  `models/overtime_request.py:41-42`) matching `employee_id` within the span.
- **Leave days** — projected from `LeaveRequest` rows (`status`, `start_date`/`end_date`)
  overlapping the span.
- **Holiday days** — projected from `Holiday.holiday_date` (`models/holiday.py:29`) within the
  span.
- **Remaining leave balance context** (if surfaced at all) — projected from `LeaveBalance`
  (`allocated_days`/`used_days`/`remaining_days`, `models/leave_balance.py:35-37`) for the
  employee's `period_year`.

This split (store the ask-and-decision, compute everything else) is not a new idea invented for
this document — it is the same boundary `AttendanceEvent`/`LeaveRequest`/`OvertimeRequest` each
already draw between themselves and *their own* future consumers (§6/§7/§9 of each respective
prior doc: "the source of truth stays raw, consumers compute their own derived view"). Applying
it to Timesheet's *own* internal fields (store the request, compute the totals) is the direct
continuation of that same principle, not a deviation from it. *How* that computation is actually
executed against five separate aggregates is a distinct question, addressed on its own in §7.

**Deliberately not proposed**: `total_worked_hours`, `total_overtime_hours`, `total_leave_days`,
`net_pay_amount`, `approved_by` (business-meaningful, distinct from `updated_by`),
`submitted_at` (distinct from `created_at`), `pay_period_id`. Each would require either inferring
an unconfirmed business rule (whether a snapshot must be frozen at approval time, §12) or a
not-yet-built entity (`PayPeriod`) to reference.

---

## 5. Relationship Analysis

**Required:**

| Relationship | Cardinality | ON DELETE | Why |
|---|---|---|---|
| `Timesheet.employee_id → HrEmployee.id` | many-to-one | RESTRICT | Matches every mandatory FK into `HrEmployee` from HR transactional data (`AttendanceEvent.employee_id`, `LeaveRequest.employee_id`, `OvertimeRequest.employee_id`, `LeaveBalance.employee_id` — all `ondelete="RESTRICT"`). Same unresolved retention question as every prior entity: no code anywhere deletes an `HrEmployee`, so there is no established precedent to confirm RESTRICT is definitely correct forever, only that it is consistent with 100% of existing precedent |

**Forbidden (explicitly not modeled, by direct precedent):**

- **`Timesheet` → `AttendanceEvent`/`LeaveRequest`/`OvertimeRequest`/`Holiday`/`LeaveBalance` —
  no foreign key in either direction.** This is the single clearest precedent in the entire
  codebase: `ATTENDANCE_DESIGN.md` §3 explicitly rejected an FK to Leave (reconciliation is "a
  consumer reading both by `hr_employee_id` + date range, not by one holding a foreign key into
  the other"); `LEAVE_DESIGN.md` §4 explicitly rejected an FK to `AttendanceEvent` for the
  identical reason; `HOLIDAY_CALENDAR_DESIGN.md` §3 rejected FKs to both, again for the same
  reason ("reconciliation is a read, not a foreign key"). A Timesheet joining across *five*
  entities by `employee_id` + date range, with zero FKs among them, is the direct continuation of
  a pattern established three times over, not a new decision. *How* that join is physically
  executed, given every repository is single-model, is the open question in §7 — the absence of
  an FK is settled; the mechanics of the read are not.
- **`Timesheet` → Project Tracking (`Employee`/`Assignment`/`Project`/`Task`)** — confirmed
  independent bounded context, restated identically in all three prior docs' §0/§1 findings, and
  reconfirmed here: nothing reviewed in this discovery introduces a dependency between HR and
  Project Tracking.
- **`Timesheet` → `User` beyond `AuditMixin`** — no business-meaningful "submitted by"/"approved
  by" field distinct from generic `created_by`/`updated_by`, because `User` ↔ `HrEmployee` itself
  has no link to build on (confirmed via grep, §2). Same gap flagged unresolved in every prior
  discovery.

---

## 6. Repository Boundary

**`TimesheetRepository(BaseRepository[Timesheet])`** — persistence-only, matching every reviewed
repository (`repositories/leave_balance.py`, `repositories/overtime_request.py`):

- No commits, no rollbacks (`repositories/base.py:18-19`'s documented contract).
- `SEARCHABLE_FIELDS`: none proposed, unless a `reason` field is confirmed (§13.4) — mirrors
  `LeaveBalanceRepository`'s `SEARCHABLE_FIELDS: Sequence[...] = ()` (`repositories/leave_balance.py:14`),
  which also has no free-text field.
- `FILTERABLE_FIELDS`: `{"employee_id": ..., "status": ...}` — both equality, both directly
  supported by `BaseRepository._apply_filters` today (`repositories/base.py:100-124`), mirroring
  `OvertimeRequestRepository.FILTERABLE_FIELDS` exactly (`repositories/overtime_request.py:15-19`).
- `get_by_employee(employee_id)` helper — mirrors `LeaveBalanceRepository.get_by_employee`
  (`repositories/leave_balance.py:27-30`) and `OvertimeRequestRepository.get_by_employee`
  (`repositories/overtime_request.py:28-31`) exactly.

**Explicitly not the repository's job**: computing worked/overtime/leave/holiday totals. That
would require reading across four *other* repositories (`AttendanceEventRepository`,
`LeaveRequestRepository`, `OvertimeRequestRepository`, `HolidayRepository`), which is
cross-aggregate orchestration, not persistence — no reviewed repository does this today (every
repository is scoped to exactly one model). This is analyzed in its own right in §7, rather than
folded into ordinary CRUD repository responsibilities here.

**On the equality-only nature of `BaseRepository._apply_filters` — reclassified as an
implementation consideration, not an architectural blocker.** `_apply_filters`
(`repositories/base.py:100-124`) only supports equality; there is no `BETWEEN`/date-range query
capability anywhere in the foundation. Every prior discovery flagged this as an open question for
its *own* date-range needs (Attendance's employee+range list, Leave's overlap detection,
Holiday's "holidays in this period"), and each one declined to generalize the shared foundation on
the strength of its own single use case — `HOLIDAY_CALENDAR_DESIGN.md` §4 explicitly left this
"an implementation-time decision, not an architectural one," and `LEAVE_DESIGN.md` §8 restated the
same conclusion rather than resolving it. **Timesheet does not meet a higher bar than those
modules did.** One new consumer needing range queries is not, by itself, evidence that
`BaseRepository` should change — it is evidence that a range-scoped query needs to be written
*somewhere*, which is a narrower and more local problem than "the foundation is inadequate." This
document explicitly does **not** recommend adding generic date-range filtering to
`BaseRepository`, and holds that the shared repository foundation should not be generalized until
multiple real, concrete consumers are shown to need the same capability — Timesheet alone is one
consumer, not a pattern. Where the range-scoped, multi-table read for Timesheet specifically
should live is addressed in §7.

---

## 7. Query Orchestration Analysis

**Question: Timesheet is the first module expected to read and combine data from multiple
aggregates — `AttendanceEvent`, `LeaveRequest`, `Holiday`, `OvertimeRequest`, and
`LeaveBalance`. Does the existing repository/service pattern support this naturally, should
`TimesheetRepository` own specialized projection queries, and would a new shared abstraction be
premature?**

**What the codebase establishes about repository scope.** `BaseRepository`'s own docstring
describes it as a "generic, model-agnostic data access layer" that gives a subclass "typed CRUD
access" (`repositories/base.py:14-19`) — the type parameter `ModelT` is singular, and every method
on it (`get`, `get_by`, `list`, `create`, `update`, `delete`, `exists`, `count`, `paginate`)
operates against `self.model`, one table. Every concrete repository reviewed —
`ShiftRepository`, `HrEmployeeRepository`, `LeaveBalanceRepository`, `OvertimeRequestRepository`,
and by extension `AttendanceEventRepository`/`LeaveRequestRepository`/`HolidayRepository` —
subclasses `BaseRepository[SingleModel]` and only ever issues `select(self.model)`-rooted queries
against that one table. None reviewed accepts another repository, another model, or joins across
tables. **A `TimesheetRepository` method that also queried `attendance_events`, `leave_requests`,
`overtime_requests`, or `holidays` directly would be the first repository in the codebase to read
outside its own model's table** — a deviation from the single-model contract every other
repository observes, not an extension of it.

**What the codebase establishes about where cross-entity reads currently happen.** They already
happen — but only as narrow existence checks, never as data composition. Every service reviewed
(`LeaveBalanceService.create`, `OvertimeRequestService.create`, and by the same pattern
`LeaveRequestService`/`AttendanceEventService`) instantiates a *second* repository against the
same `uow.session` purely to call `.exists(...)` before writing (e.g.
`services/leave_balance.py:55`: `HrEmployeeRepository(uow.session).exists(data.employee_id)`).
This confirms the `SQLAlchemyUnitOfWork`'s shared-session mechanism (`uow/sqlalchemy.py:26-30`)
already supports multiple repositories being instantiated side by side within one unit of work —
but every observed use of that mechanism stops at a boolean existence check. **No service
anywhere composes the *results* of multiple repositories into a single computed value or
combined read model.** Whether that same shared-session mechanism is an adequate basis for a
service to read from four other repositories and compute a Timesheet's totals, or whether that
kind of composition needs its own layer, is not something the existing precedent settles either
way — it only tells us the mechanism *could* be reused for more than an existence check, not that
doing so is the intended or proven pattern.

**Whether a new shared abstraction would be premature.** By the same standard this codebase's own
discovery documents have applied at every prior step — decline to build shared/general
infrastructure until a second concrete consumer confirms the shape it should take
(`HOLIDAY_CALENDAR_DESIGN.md` §1 declined to build a `HolidayCalendar` container before an
assignment mechanism existed; `LEAVE_DESIGN.md` §2 declined to build a balance/ledger aggregate
before an entitlement concept existed) — introducing a new "query object," "read model," or
cross-aggregate query layer now, on the strength of exactly one consumer (Timesheet), would repeat
the same mistake those documents were each careful to avoid. A repo-wide search for any
`queries/`, `read_models/`, or `projections/`-style module turned up nothing (§2) — there is no
existing seam to extend, only a choice about where to place a first instance of something new.
Building that shared abstraction now would be speculative in exactly the way this discovery
methodology has consistently declined to be.

**Conclusion: this is an open architectural ambiguity, not a resolved design.** The evidence is
sufficient to rule two things out — (a) `TimesheetRepository` reaching into other models' tables
would break the single-model repository contract every other repository observes, and (b)
inventing a new shared cross-aggregate query abstraction before a second real consumer needs one
would be premature by this codebase's own established standard. The evidence is **not**
sufficient to confirm a positive answer. Plausible, evidence-consistent options that remain
un-adjudicated:

- `TimesheetService` directly instantiates `AttendanceEventRepository`/`LeaveRequestRepository`/
  `OvertimeRequestRepository`/`HolidayRepository` against its own `uow.session` and composes their
  results itself — consistent with the existing precedent that services already juggle multiple
  repositories per unit of work, but that precedent has only ever been exercised for existence
  checks, never for combining query results, so extending it to full data composition is an
  interpretation of the pattern, not a confirmed instance of it.
- A `TimesheetRepository` method queries `Timesheet`'s own table only, and a *separate*,
  not-yet-precedented component (a "query service," "reporting service," or similar) is
  responsible for the multi-aggregate composition — structurally cleaner, but introduces a kind
  of component that does not exist anywhere in this codebase today.
- Some other placement not yet named.

No option above is confirmed by the codebase as reviewed. This ambiguity is carried forward
explicitly into §13 and §14 rather than resolved here.

---

## 8. Service Boundary

**Belongs in `TimesheetService`** (mirrors `LeaveRequestService`/`OvertimeRequestService`'s
division of labor):

- Owning the transaction boundary via `uow_factory`, identical to every reviewed service.
- Validating `employee_id` exists via `HrEmployeeRepository(...).exists(...)` before insert —
  same pattern as `LeaveBalanceService.create`/`OvertimeRequestService.create`.
- The `end_date >= start_date` structural check, mirroring `LeaveRequestService`'s identical
  check on `LeaveRequest` (per `LEAVE_DESIGN.md` §6/§7).
- Expunge-on-return, refresh-before-expunge-on-update — identical to every reviewed service, for
  the identical reason documented in `LeaveBalanceService`'s and `OvertimeRequestService`'s own
  docstrings (`services/leave_balance.py:37-43`, `services/overtime_request.py:37-42`).

**Whether `TimesheetService` (or some other, not-yet-named component) is also responsible for
computing the period totals by orchestrating reads across four other repositories is the same
open question analyzed in full in §7, and is not re-litigated here.** What can be said at the
service-boundary level specifically: no reviewed service today reads and aggregates across more
than one *other* entity type (every existence check touches exactly one other repository), so
whichever placement §7's ambiguity resolves to, it would be new territory for the service layer
either way, not a copy of an established pattern.

**Must NOT belong in `TimesheetService`**:

- Payroll pay-rate/deduction computation — same boundary every reviewed service draws around its
  own downstream consumers.
- Approval-workflow role gating — `RequireRole` exists (`dependencies/rbac.py`) but is used only
  by `roles.py` (confirmed by grep, §2); no HR/Attendance/Leave/Overtime service reviewed does
  role-gated business logic, so Timesheet would be the first, which this discovery does not
  recommend inventing without product direction.
- Notification dispatch on submission/decision — same boundary drawn in both `LEAVE_DESIGN.md` §7
  and the `OvertimeRequestService` docstring.
- Correction/recompute logic for already-submitted timesheets when underlying `AttendanceEvent`/
  `LeaveRequest`/`OvertimeRequest` rows change after the fact — no precedent exists for amending a
  decided record in this codebase at all (`ATTENDANCE_DESIGN.md` §11.4, `LEAVE_DESIGN.md` §12.11
  both flag this, unresolved, for their own entities).

---

## 9. API Boundary

Proposed, following the exact router/prefix/dependency shape of `api/overtime_requests.py`
(`APIRouter(prefix="/hr/...", tags=[...])`, `CurrentUser` on every route, service injected via a
`Depends`-wrapped factory):

| Method | Path | Why |
|---|---|---|
| `POST` | `/hr/timesheets` | Submit a timesheet for an employee + date span. Mirrors `POST /hr/overtime-requests` |
| `GET` | `/hr/timesheets/{id}` | Single-record fetch, same shape as every reviewed entity |
| `GET` | `/hr/timesheets` | Plain list, matching every reviewed entity's unfiltered list route |
| `GET` | `/hr/timesheets/paginated` | Paginated list, filterable by `employee_id`/`status` (both equality, both supported today) |
| `PUT` | `/hr/timesheets/{id}` | Edit span/status — same open question `LEAVE_DESIGN.md` §12.10 already left unresolved for `LeaveRequest`: generic `PUT` vs. dedicated `approve`/`reject` action endpoints. No lifecycle-transition endpoint exists anywhere in the codebase to copy either pattern from |
| `DELETE` | `/hr/timesheets/{id}` | Present for pattern-consistency; whether a decided timesheet should ever be hard-deletable is the same open question flagged for `LeaveRequest`/`AttendanceEvent` |

**Explicitly not proposed**, because each presupposes a decision this document does not make:

- `GET /hr/timesheets/{id}/summary` or `/compute` — presupposes resolving the query-orchestration
  ambiguity in §7.
- `POST /hr/timesheets/{id}/submit` / `/approve` / `/reject` — presupposes resolving §13.2
  (status/transition rules) and §13.3 (approver identity), neither of which any reviewed endpoint
  has precedent for.
- Any self-service "my timesheets" endpoint resolved from the authenticated `User` — blocked by
  the confirmed-still-open `User` ↔ `HrEmployee` gap (§2, §13.7).
- `GET /hr/timesheets/{employee_id}/range?start=&end=` as a bespoke range endpoint — would sit
  directly on top of the unresolved §7 ambiguity, and every prior doc that considered a similar
  endpoint (`ATTENDANCE_DESIGN.md` §4, `HOLIDAY_CALENDAR_DESIGN.md` §6) explicitly declined to
  propose one until the underlying read path is settled.

---

## 10. Migration Strategy

**Recommendation: staged — one standalone new table, `timesheets`, FK-only, no changes to any
existing table.** Identical reasoning to every prior module's migration strategy
(`ATTENDANCE_DESIGN.md` §8, `LEAVE_DESIGN.md` §9, and the actual `leave_requests`/
`overtime_requests`/`leave_balances` migrations as built):

- Full explicit `BaseEntity` column set (`id`, `created_at`, `updated_at`, `created_by`,
  `updated_by`, `deleted_at`, `is_deleted`, `version`), matching every migration reviewed.
- `employee_id` FK → `hr_employees.id`, `ondelete="RESTRICT"` — matching
  `leave_requests`/`overtime_requests`/`leave_balances`' own migrations exactly.
- `start_date`, `end_date` (`Date`, not null), `status` (`String(50)`, default `"pending"`).
- Indexes on `employee_id` and `status`, matching `ix_leave_requests_employee_id`/
  `ix_leave_requests_status` and `ix_overtime_requests_employee_id`.
- Chained off the current alembic head, `6a370704cee5` (`create_leave_balances_table`).

**Should NOT contain**:

- **No unique constraint on `(employee_id, start_date, end_date)`.** Whether overlapping or
  duplicate timesheet periods for the same employee should be rejected is unconfirmed — same
  category of open question `LEAVE_DESIGN.md` §12.8 already left unresolved for `LeaveRequest`
  overlap detection, and no existing table in this codebase enforces a date-range uniqueness
  constraint at all.
- **No FK to `AttendanceEvent`/`LeaveRequest`/`OvertimeRequest`/`Holiday`/`LeaveBalance`** — none
  justified (§5).
- **No changes to `hr_employees`, `attendance_events`, `leave_requests`, `overtime_requests`,
  `leave_balances`, or `holidays`.** This continues the same isolation pattern every prior HR
  migration has followed: the referencing table lands standalone, the referenced tables are never
  retroactively edited.

---

## 11. Future Compatibility

- **Payroll** (if it materializes as a future module): would read `Timesheet` rows by `status`
  (e.g. `APPROVED`) and independently recompute or reuse whatever query mechanism Timesheet's own
  §7 ambiguity resolves to — because Timesheet stores only the ask-and-decision (§4), Payroll's
  own rate/deduction logic doesn't require a Timesheet schema change.
- **Analytics/Reporting** (Phase 5 of the roadmap): would aggregate `Timesheet` submission/approval
  rates across employees/departments — reachable via the existing `HrEmployee` relationship graph
  (`department_id`/`location_id`/`team_id`) already established as sufficient for this purpose in
  every prior doc's own "Future Dependencies" section.
- **A future `PayPeriod`/`Payroll` module**, if it materializes, would be additive — a new table
  plus an optional FK added to `Timesheet` later, following the exact incremental-FK precedent
  already used three times in this codebase (`shift_id` added to `hr_employees` in `e7a8ed87ea45`
  after `Shift` landed in `c4a9d3e17f56`; `job_grade_id`/`employment_type_id`/
  `employment_status_id` added the same way). Not something to build now on speculation.

**Flagged as a point of likely future churn, not a blocker**: if a second consumer ever needs
the same range-scoped, multi-table read Timesheet needs (§7), that would be the point at which
generalizing part of the repository foundation becomes evidence-backed rather than speculative.
Until then, whatever Timesheet-specific approach §7's ambiguity resolves to should be expected to
possibly be revisited later — that is foreseeable, ordinary schema/architecture evolution, not a
sign that the current approach is wrong.

---

## 12. Risks

Identified, not solved:

- **Computed-vs-stored hours tension.** The codebase-wide precedent (§4) says compute, don't
  store — but once a `Timesheet` is approved, payroll-adjacent business reality often wants a
  frozen snapshot immune to later corrections of the underlying `AttendanceEvent`/`LeaveRequest`/
  `OvertimeRequest` rows. No entity in this codebase has ever needed to reconcile "compute live"
  vs. "freeze at approval" before; Timesheet is the first, and there is no precedent to resolve it
  either way.
- **Correction propagation.** If an `AttendanceEvent` that was already included in an
  approved `Timesheet` is later corrected (itself an unresolved mechanism per
  `ATTENDANCE_DESIGN.md` §11.4), nothing defines whether/how that correction should invalidate or
  update the Timesheet. Timesheet inherits this unresolved ambiguity from Attendance, compounded
  by the identical unresolved ambiguity already flagged for `LeaveRequest` corrections
  (`LEAVE_DESIGN.md` §12.11) and `OvertimeRequest`'s complete absence of any correction/overlap
  logic (confirmed by reading `services/overtime_request.py` directly — only existence and
  `end_time > start_time` are validated).
- **Period-granularity ambiguity.** Whether a Timesheet is meant to be submitted weekly, monthly,
  per pay-period, or genuinely arbitrary has no basis for resolution in the codebase or the
  roadmap (§3, §13.1).
- **Overlap/duplicate periods.** No constraint proposed prevents two `Timesheet` rows for the
  same employee covering overlapping spans (§10), the same open question already left unresolved
  for `LeaveRequest` (`LEAVE_DESIGN.md` §12.8).
- **Status-transition and approver-identity gap.** `status` is storage-only by direct precedent
  (§4), so approval workflow, valid-value enumeration, and role-gating are all unconfirmed — same
  gap `LEAVE_DESIGN.md` §12.3/§12.4 already left open for `LeaveRequest`, now compounded by a
  second module inheriting it unresolved.
- **`User` ↔ `HrEmployee` gap** (confirmed still open, §2). Blocks any self-service "submit my own
  timesheet" flow and blocks recording a business-meaningful approver identity.
- **Systemic soft-delete/version gap.** `BaseRepository.delete()` hard-deletes despite
  `SoftDeleteMixin`; no service checks `.version` for concurrency conflicts. Flagged in every
  prior discovery as codebase-wide, not Timesheet-specific, but especially relevant for an
  aggregate that represents a payroll-adjacent approval decision.
- **Query-orchestration placement is unresolved (§7).** This is an architectural open question,
  not a foundation-level blocker: the codebase gives no precedent either for a repository
  reading outside its own table or for a service composing multiple repositories' results into
  one computed value. Implementation should not proceed by guessing at a placement; it should be
  confirmed first (§14).
- **Roadmap silence.** Neither "Timesheet" nor "Payroll" appears anywhere in
  `docs/product/06_PRODUCT_ROADMAP.md` — the same absence already flagged for Leave and Holiday,
  now true for a third consecutive module, with no `PayPeriod`/Payroll concept anywhere to anchor
  against either.
- **No accompanying discovery doc for `OvertimeRequest`/`LeaveBalance`.** Both modules were
  implemented without a discovery document (§2), meaning this Timesheet discovery cannot check
  its assumptions about their design intent against anything but their resulting code — a gap in
  process precedent, not in code, but one that increases the risk that this discovery is
  reconstructing intent rather than confirming it.

---

## 13. Ambiguities

Per instructions, these are listed, not guessed at. Implementation should not proceed until they
are resolved:

1. **Period granularity.** Is a Timesheet meant to be submitted for a week, a month, a pay
   period, or a genuinely arbitrary span chosen by the caller? No `PayPeriod`/`Payroll`/
   calendar-bucket concept exists anywhere to confirm this (§3, §12).
2. **`status` values and transition rules.** What are the valid values (`pending`, `submitted`,
   `approved`, `rejected`, others?), and is a strict transition sequence enforced? `RequireRole`
   exists but is used by no HR/Attendance/Leave/Overtime endpoint (§2, §8).
3. **Approver identity.** Should a decision record a business-meaningful approver, distinct from
   generic `AuditMixin.updated_by`? Downstream of the `User` ↔ `HrEmployee` gap (#7 below).
4. **Whether a free-text `reason`/comments field is needed** on submission (§4) — plausible by
   precedent, not confirmed.
5. **Where cross-aggregate query composition should live.** Analyzed in full in §7: the evidence
   rules out `TimesheetRepository` reaching into other models' tables and rules out inventing a
   new shared abstraction on the strength of one consumer, but does not confirm a positive
   placement (service-level composition across multiple repositories vs. a new, not-yet-precedented
   component). **This is the central unresolved architectural question in this discovery** and is
   restated as the key implementation-readiness blocker in §14.
6. **Frozen snapshot vs. live recompute.** Once approved, should a Timesheet's hour totals be
   frozen against later corrections to the underlying event/request streams, or always
   recomputed live? No precedent addresses this anywhere (§12).
7. **`User` vs. `HrEmployee` identity** — inherited unresolved from every prior discovery; still
   confirmed absent by direct inspection of `models/user.py` in this discovery (§2).
8. **Overlap/duplicate detection.** Should two `Timesheet` rows for the same employee with
   overlapping spans be rejected? Same unresolved question already on record for `LeaveRequest`
   (§10, §12).
9. **Whether `BaseRepository` should ever gain a generic date-range capability.** Downgraded from
   an architectural blocker to a longer-term, secondary question (§6): not resolved here, and
   explicitly not recommended for this PR. Should only be revisited once a *second* concrete
   consumer, beyond Timesheet, is shown to need the same capability — a single new consumer is not
   sufficient justification on its own.
10. **Retention/purge on employee offboarding.** Whether `employee_id`'s FK should be `RESTRICT`
    forever — same unresolved question on record for every prior HR transactional entity (§5); no
    code anywhere deletes an `HrEmployee` today.
11. **Delete/soft-delete semantics** for a decided (approved/rejected) Timesheet — same open
    question already on record for `LeaveRequest`/`AttendanceEvent` (§12).
12. **Product intent.** Neither "Timesheet" nor "Payroll" is named anywhere in
    `docs/product/06_PRODUCT_ROADMAP.md`. Is this a confirmed, prioritized module, or exploratory
    work ahead of product scoping — the same question already raised, unresolved, for both Leave
    and Holiday before it?

---

## 14. Implementation Readiness

**Not ready.** This is the most cross-cutting discovery of the four conducted so far: Timesheet's
entire value proposition is a rollup across `AttendanceEvent`, `LeaveRequest`, `OvertimeRequest`,
`Holiday`, and `LeaveBalance`, which means it inherits every one of those modules' own unresolved
ambiguities simultaneously (overnight-shift day-attribution, leave day-count semantics, overtime
overlap detection, holiday scoping) *in addition to* the ambiguities specific to Timesheet itself.

The document previously identified the equality-only nature of `BaseRepository._apply_filters` as
the reason implementation could not proceed. **That framing has been withdrawn.** The lack of
generic date-range filtering is, at most, an implementation-level inconvenience that a
Timesheet-scoped query can work around locally (§6) — it does not, by itself, block
implementation, and it is not evidence that the shared repository foundation needs to change.

**The real unresolved architectural question is narrower and is the one that actually blocks
implementation:**

> How should complex projection queries spanning multiple aggregates be implemented while
> preserving the existing repository architecture?

This is distinct from ordinary CRUD repository work in a specific, evidenced way: every repository
reviewed in this codebase (§7) is scoped to exactly one model and every service reviewed composes
at most a boolean existence check from a second repository — nothing reviewed reads and combines
the *data* of multiple aggregates into one computed result. Timesheet cannot be implemented
without answering this, because its core feature (period totals across five aggregates) is
exactly that kind of query, and the codebase currently offers no confirmed place for it to live
(§7, §13.5).

Concrete decisions required before implementation can begin:

1. **Query-orchestration placement (§7, §13.5)** — the central blocker. Must be resolved before
   `TimesheetService`/`TimesheetRepository` can be designed at all, since it determines which
   component is responsible for reading `AttendanceEvent`/`LeaveRequest`/`OvertimeRequest`/
   `Holiday`/`LeaveBalance` and how.
2. Period granularity (§13.1) — affects the practical meaning of `start_date`/`end_date`, though
   not the literal schema (§3/§4 already resolve the schema question independent of this).
3. `status` values, transition rules, and approver identity (§13.2, §13.3) — blocks §9's `PUT`
   vs. dedicated-action-endpoint decision.
4. Frozen-snapshot vs. live-recompute semantics (§13.6) — blocks whether any computed total is
   ever persisted, even as a cache, which would change §4's "compute, never store" recommendation,
   and is entangled with the §7 placement decision.
5. Overlap/duplicate-period policy (§13.8) — blocks §10's migration constraint design.
6. Confirmation that no roadmap/product decision supersedes this discovery (§13.12), given
   "Timesheet"/"Payroll" appears nowhere in `docs/product/06_PRODUCT_ROADMAP.md`.

**Stopping here per instructions.** No aggregate has been implemented, no migration has been
written, no code has been changed. Awaiting direction on the ambiguities above — particularly
§13.5/§7 (query-orchestration placement) and §13.1 (period granularity) — before proceeding.

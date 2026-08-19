# PR-041 — HolidayCalendar Architecture Discovery

Status: **Discovery only. No code, no migrations. Awaiting approval.**

---

## 0. What was reviewed

**HR module** (`services/api/src/eop_api/{models,repositories,services,api,schemas}`):
`JobGrade`, `EmploymentType`, `EmploymentStatus`, `Shift`, `HrEmployee`, `AttendanceEvent`,
`LeaveRequest`, `Organization`, `Department`, `Position`, `Team`, `Location`.

**Project Tracking module**: `Employee`, `Assignment`, `Project`, `Task`.

**Foundation**: `BaseEntity`/mixins (`db/base.py`, `db/mixins.py`), `BaseRepository`
(`repositories/base.py`), `AbstractUnitOfWork`/`SQLAlchemyUnitOfWork` (`uow/`),
`FilterParams`/`SearchParams`/`Page`/`PaginationParams` (`schemas/`), `CurrentUser`/`RequireRole`
(`dependencies/auth.py`, `dependencies/rbac.py`).

**Migrations**: every `alembic/versions/*` file, in order, through
`1c4f19907e49_create_attendance_events_table` (current head).

**Also reviewed**: `docs/architecture/ATTENDANCE_DESIGN.md` (PR-039), `docs/architecture/LEAVE_DESIGN.md`
(PR-040) — the two prior discovery exercises for this same codebase — and
`docs/product/06_PRODUCT_ROADMAP.md`.

### Confirmed dependency findings

1. **No `Holiday`/`Calendar`/`WorkCalendar` concept exists anywhere in the codebase today.**
   A repo-wide search for "holiday" and "calendar" turns up nothing except: incidental phrases
   like "calendar date" inside `Shift`/`AttendanceEvent` docstrings (referring to a generic date,
   not an entity), and the *prior* discovery docs themselves, which already flagged this gap —
   `LEAVE_DESIGN.md` §11/§12.12 explicitly states day-count math is unconfirmed "and no
   `Holiday`/`WorkCalendar` entity exists in the codebase to resolve it." **This PR has zero
   existing structure to build on** — a stronger version of the gap Leave itself faced (Leave at
   least had `Project.status`/`Task.status` as a status-column precedent; Holiday has no
   precedent for any of its distinguishing concerns: scope, recurrence, or category).
2. **`docs/product/06_PRODUCT_ROADMAP.md` names neither "Holiday" nor "Calendar" in any phase or
   in the MVP.** Phase 4 ("Field Operations") lists Attendance, Check In, Check Out, Mission,
   Visit, Survey, GPS, Photo. The MVP list is Authentication, Organization, Employee, Store,
   Attendance, Visit, Mission, Dashboard. Exactly as `LEAVE_DESIGN.md` §12.1 already found for
   Leave, there is no documented product intent to validate this design against — see §10.
3. **The four existing global-lookup entities (`JobGrade`, `EmploymentType`, `EmploymentStatus`,
   `Shift`) are the only precedent in the codebase for reference data with zero outbound foreign
   keys.** Each one's own docstring states, nearly verbatim: "Deliberately independent of
   Organization, Department, Team, and Position — it has no hierarchy, no parent, and is not
   scoped to any of them." This is the closest existing shape to what "holiday" reference data
   would need — see §1, §3.
4. **The `User` ↔ `HrEmployee` gap still exists** (no FK anywhere links the authenticated `User`
   to an `HrEmployee` row) — inherited unresolved from both prior discoveries. It is not
   load-bearing for Holiday the way it was for Attendance/Leave self-service, since nothing about
   a holiday calendar is employee-specific, but it's restated here for completeness (§3).
5. **`BaseRepository._apply_filters` is equality-only** — no range/date-span (`BETWEEN`) query
   capability exists anywhere in the foundation. Both prior discoveries flagged this as an open
   question for their own date-range needs (Attendance's employee+date-range list, Leave's
   overlap detection); it resurfaces again here, arguably more centrally, since "holidays between
   two dates" is Holiday's single most obviously useful query — see §4.

### Patterns identified (from `JobGrade`, `EmploymentType`, `EmploymentStatus`, `Shift`, `AttendanceEvent`, `LeaveRequest`)

- **Model pattern**: subclass `BaseEntity` (`UUIDMixin` + `TimestampMixin` + `AuditMixin` +
  `SoftDeleteMixin` + `VersionMixin`). Two distinct existing shapes: (a) flat global master data
  (`JobGrade`, `EmploymentType`, `EmploymentStatus`, `Shift`) — no employee FK, no org FK, a
  unique `code`, a `name`, an optional `description`; (b) employee-scoped transactional/event data
  (`AttendanceEvent`, `LeaveRequest`) — mandatory `hr_employee_id` FK (`RESTRICT`), date/time fact
  columns, an optional free-text field. Holiday matches neither shape exactly — see §1.
- **Repository pattern**: subclass `BaseRepository[Model]`. Never commits. Declares module-level
  `SEARCHABLE_FIELDS` (free-text `ilike`, always `code`/`name` only — never `description`, even
  though every entity has one) and `FILTERABLE_FIELDS` (equality-only allowlist). Adds narrow
  `get_by_x` helpers only (`get_by_code`, `get_by_email`, `get_by_employee_number`) — never a
  range helper, because none exists yet.
- **Service pattern**: owns the transaction boundary via an injected `uow_factory`. Validates
  referenced-entity existence and uniqueness constraints (`Duplicate<X>CodeError`-style local
  exceptions defined at the top of the service module, not in `exceptions/`). Ends every
  read/write path with `expunge`/`expunge_all`, and `refresh` before expunge on update.
- **API pattern**: `APIRouter(prefix="/hr/...", tags=[...])`. Every route takes `CurrentUser` only
  — no HR/Attendance/Leave endpoint uses `RequireRole`, despite it existing. Standard six-route
  set: `POST ""`, `GET ""`, `GET "/paginated"`, `GET "/{id}"`, `PUT "/{id}"`, `DELETE "/{id}"`
  (204). No bulk/import/action-specific endpoints exist anywhere in the reviewed codebase.
- **Migration pattern**: one Alembic revision per table, full explicit `BaseEntity` column set,
  FK constraints inline, indexes after the table, chained via `down_revision`. Entities with no
  natural relationship (the four global-lookup tables) carry no FK columns at all. Where a later
  relationship *is* confirmed, it is wired in by a **separate, later** migration on the
  referencing table (e.g. `shift_id` added to `hr_employees` in `e7a8ed87ea45`, after `Shift`
  itself landed in `c4a9d3e17f56`) — the original table is never edited retroactively.

---

## 1. Aggregate

**Recommendation: `Holiday`** — one row per named non-working calendar date.

Evaluated options:

| Candidate | Verdict |
|---|---|
| `Holiday` (one date + label, flat reference row) | **Recommended** |
| `HolidayCalendar` (a named container that owns many `Holiday` child rows, e.g. "Indonesia 2027") | Rejected as the aggregate root for *this* PR — see below |
| `CalendarDay` (one row per calendar day of the year, working/non-working/holiday flag) | Rejected |
| `WorkCalendar` (synonym for the container concept) | Same objection as `HolidayCalendar` |

**Why `Holiday`, not `HolidayCalendar`:**

- `HolidayCalendar`-as-container presupposes that multiple, distinct named calendars need to
  coexist and that some other entity gets *assigned* to one of them (e.g. an organization, a
  location, or a country picks "which calendar applies to it"). **No assignment mechanism exists
  anywhere in the codebase to hang that off of** — `HrEmployee` has no `calendar_id`, `Location`
  has no `calendar_id`, `Organization` has no `calendar_id`. Modeling the container before the
  thing that would select between containers is exactly the kind of unconfirmed structure this
  discovery is instructed not to invent (mirrors `LEAVE_DESIGN.md`'s own reasoning for rejecting a
  balance/ledger aggregate before an entitlement concept exists to be a ledger *of*).
- `CalendarDay` (a full date-dimension table, one row per day of the year regardless of whether
  it's a holiday) is a much larger, denormalized concept with zero precedent — every other date
  field in the codebase (`LeaveRequest.start_date`/`end_date`, `HrEmployee.hire_date`) is a plain
  `Date` column, never a lookup into a per-day dimension table.
- `Holiday` matches the **shape**, not just the name, of the codebase's existing "flat global
  reference data" group (`JobGrade`, `EmploymentType`, `EmploymentStatus`, `Shift`, §0 finding 3):
  no employee dimension, no org dimension, a small number of descriptive fields, referenced by
  *other* future modules rather than referencing anything itself. It does not fit the
  transactional/event shape (`AttendanceEvent`, `LeaveRequest`) because a holiday is not something
  that happens *to* a specific employee.

**Naming tension worth surfacing explicitly**: this PR is titled "HolidayCalendar Aggregate," but
the evidence supports a flatter `Holiday` entity today. This does not rule out a future
`HolidayCalendar` container once a scoping/assignment mechanism is confirmed (§10) — that would be
an additive step (a new parent table + a FK added to `Holiday`, following the exact incremental-FK
precedent already established for `job_grade_id`/`employment_type_id`/`employment_status_id`/
`shift_id` on `hr_employees`), not something to build now on speculation.

---

## 2. Entity Shape

Only fields directly implied by "one named non-working calendar date" and by patterns already
established in the codebase are proposed. Anything requiring an unconfirmed business rule is
listed in §10 instead of guessed.

| Field | Belongs? | Computed? | Future concern? | Deferred? |
|---|---|---|---|---|
| `id` (UUID) | Yes — universal PK, `UUIDMixin` on every entity reviewed | No | No | No |
| `date` (Date) | Yes — the entire point of the record; `Date` (not `DateTime`) matches every existing whole-day business field (`LeaveRequest.start_date`/`end_date`, `HrEmployee.hire_date`) | No | Scoping/uniqueness of `date` is a future concern (§10) — the field itself is not | No |
| `name` (String) | Yes — human label, matches `JobGrade.name`/`Shift.name`/`EmploymentType.name` (non-nullable everywhere) | No | No | No |
| `description` (String, nullable) | Yes — direct precedent: `Shift.description`, `JobGrade.description`, `HrEmployee.notes` are optional free text on every reviewed entity | No | No | No |
| `code` (String, unique) | **No** — `JobGrade`/`EmploymentType`/`EmploymentStatus`/`Shift` all have a `code` because *other rows reference them by a stable string key* (`get_by_code`); nothing references `Holiday` by any key today, and `date` is already a sufficient natural identifier | No | N/A | Deferred until a consumer needs a stable non-date key |
| `is_recurring` / recurrence rule | No — plausible (most public holidays repeat yearly) but zero recurrence precedent exists anywhere in the codebase, including `Shift` (a "template" entity that still has no day-of-week/recurrence field) | N/A | Yes — the biggest future-schema risk (§8, §9) | Deferred, unconfirmed |
| `organization_id` | No — the only precedent group for this shape (`JobGrade`/`EmploymentType`/`EmploymentStatus`/`Shift`) explicitly documents itself as *not* org-scoped; but holidays plausibly do vary by country/organization in reality | N/A | Yes | Deferred — genuine ambiguity, not a guessable default either way (§10) |
| `location_id` | No — same reasoning as `organization_id`, no precedent for scoping this class of entity by `Location` either | N/A | Yes | Deferred (§10) |
| `holiday_type` / category (public, company, religious, etc.) | No — no precedent field of this kind anywhere; mirrors `LeaveRequest`'s own unresolved `leave_type` ambiguity (`LEAVE_DESIGN.md` §12.2) | N/A | Yes — Payroll/Overtime premium-pay rules plausibly depend on this | Deferred (§10) |
| `is_paid` / pay multiplier | No — same class of deferred concern as `LeaveRequest`'s unmodeled paid/unpaid flag | N/A | Yes — Payroll concern | Deferred (§8, §10) |
| `year` (denormalized int) | No — fully derivable from `date`; storing it would be redundant, not a new fact | Yes (computed) | No | Rejected outright, not just deferred |

**Deliberately not proposed** (would require inferring an unconfirmed business rule): `code`,
`is_recurring`/recurrence fields, `organization_id`, `location_id`, `holiday_type`, `is_paid`,
`shift_id`. Each maps to a §9 risk or §10 ambiguity with no existing model to confirm structure or
naming against.

**Net proposed business fields**: `date`, `name`, `description` — plus the standard `BaseEntity`
mixin columns (`id`, `created_at`, `updated_at`, `created_by`, `updated_by`, `deleted_at`,
`is_deleted`, `version`) applied uniformly to every entity reviewed. This is deliberately thinner
than any other entity in the HR module.

---

## 3. Relationships

| Candidate | Recommendation | Why |
|---|---|---|
| `Organization` | **Not modeled** | The only shape-precedent group (`JobGrade`/`EmploymentType`/`EmploymentStatus`/`Shift`) is explicitly documented as *not* org-scoped; adding this FK now would contradict the one precedent that exists, on the basis of a real-world assumption the codebase gives no way to confirm (§10) |
| `HrEmployee` | **Not modeled** | Holiday is not "about" a specific employee the way `AttendanceEvent`/`LeaveRequest` are — it is shared context every employee's records get evaluated *against*, not a per-employee fact |
| `Shift` | **Not modeled** | No shared dimension — `Shift` is a time-of-day template, `Holiday` is a whole-day fact; no existing relationship pattern connects the two kinds of concept |
| `AttendanceEvent` | **Not modeled** | Future consumer only, via a read-side join on `date` (mirrors the `AttendanceEvent`↔`LeaveRequest` boundary already established in `ATTENDANCE_DESIGN.md` §9/`LEAVE_DESIGN.md` §4 — reconciliation is a read, not a foreign key) |
| `LeaveRequest` | **Not modeled** | Same reasoning; `LEAVE_DESIGN.md` §11/§12.12 already anticipated needing holiday dates for day-count math, framed as something a future consumer reads, not something `LeaveRequest` references directly |
| Project Tracking (`Employee`/`Assignment`/`Project`/`Task`) | **Not modeled** | Confirmed independent bounded context (§0); nothing here implies Holiday should bridge them |
| `User` | **Not modeled** | Same boundary every reviewed entity respects — `AuditMixin.created_by`/`updated_by` is the only touchpoint, identical to every other entity |
| `Location` | **Not modeled** | Plausible if regional scoping is ever confirmed, but no existing precedent to build on now (§10) |

**Recommendation: `Holiday` should have zero foreign keys to any other entity.** This places it
alongside `JobGrade`/`EmploymentType`/`EmploymentStatus`/`Shift` as the fifth entity in the schema
with no outbound relationships at all — but it goes one step further than those four: it also has
no *inbound* relationships proposed in this PR (no other table gains a `holiday_id`/`calendar_id`
column), since no consuming module exists yet to wire it into (§8).

---

## 4. Repository Responsibilities

**`SEARCHABLE_FIELDS`**: `(Holiday.name,)` — matches the `(code, name)` pattern of
`JobGrade`/`EmploymentType`/`EmploymentStatus`/`Shift`, minus `code` since none is proposed (§2).
`description` is deliberately excluded, consistent with every reviewed repository (none of them
search their own free-text `description`/`notes`/`remarks` field either).

**`FILTERABLE_FIELDS`**: `{"date": Holiday.date}` — an exact-date equality filter ("is this
specific date a holiday?") is directly supported by `BaseRepository._apply_filters` today and is
the one filter every future consumer would need at minimum.

**Required query helper**: `get_by_date(date) -> Holiday | None` — mirrors the existing
`get_by_code` family exactly, and is the single most obviously justified helper given §1's
recommendation that `date` is Holiday's natural key.

**Not proposed, flagged instead**: a range helper (e.g. `list_between(start, end)`) would be the
single most valuable addition for every anticipated consumer (Attendance, Leave, Overtime,
Payroll, Timesheet all need "holidays in this period," not just "is this one date a holiday") —
but `BaseRepository._apply_filters` is equality-only, and no range/`BETWEEN` capability exists
anywhere in the foundation today (§0 finding 5, already flagged unresolved by both prior
discoveries). Whether to generalize the shared foundation or implement a local range query in
`HolidayRepository` outside the shared `paginate()` path is an implementation-time decision, not
an architectural one, and is noted here rather than resolved.

---

## 5. Service Responsibilities

**Persistence** (`HolidayRepository`, via `BaseRepository[Holiday]`): CRUD + `get_by_date` only,
no business-rule branching — identical contract to every reviewed repository.

**Validation** (`HolidayService`):
- `date` and `name` must be set — direct structural requirement, the same category as every
  reviewed service's non-nullable-field check.
- Uniqueness of `date` (a `DuplicateHolidayDateError`, mirroring `DuplicateJobGradeCodeError`/
  `DuplicateShiftCodeError`) is *plausible* but not decidable yet — it depends entirely on the
  unresolved scoping question (§10): unique globally, or unique only within an
  organization/location scope that doesn't exist in the schema proposed here. Not implemented in
  this discovery.

**Business rules**: **none invented.** No recurrence computation, no "is this a working day"
logic, no payroll/leave-exclusion logic. This mirrors the explicit boundary both prior services
drew for their own consumers (`ATTENDANCE_DESIGN.md` §6, `LEAVE_DESIGN.md` §7): Holiday supplies
the raw fact ("this date is a holiday, and here's its name"), consumers compute their own
derived interpretation of it.

**Future workflow**: **none exists to design.** Unlike `LeaveRequest`, `Holiday` has no
lifecycle/status field — a holiday is either recorded or not, with no pending/approved/rejected
state. This is a structural simplification, not an omission (§11).

---

## 6. REST API

Proposed, following the exact router/prefix/dependency shape of `api/shifts.py`
(`APIRouter(prefix="/hr/...", tags=[...])`, `CurrentUser` on every route):

| Method | Path | Why |
|---|---|---|
| `POST` | `/hr/holidays` | Record one holiday date. Mirrors `POST /hr/shifts` |
| `GET` | `/hr/holidays/{holiday_id}` | Single-record fetch, same shape as every reviewed entity |
| `GET` | `/hr/holidays` | Plain list, matching `GET /hr/shifts` |
| `GET` | `/hr/holidays/paginated` | Paginated + searchable (`name`) + filterable (`date`) list, matching `GET /hr/shifts/paginated` |
| `PUT` | `/hr/holidays/{holiday_id}` | Edit name/description/date of an existing record |
| `DELETE` | `/hr/holidays/{holiday_id}` | Present for pattern-consistency with every other reviewed entity |

**Explicitly should NOT exist in this PR**, because each presupposes a decision this document does
not make:

- `GET /hr/holidays/range` or `/between` — presupposes the range-query capability flagged as
  unresolved in §4; nothing today supports it, and adding a bespoke endpoint before the underlying
  capability exists would be building on sand.
- Any nested `/hr/holidays/{id}/holidays` or `/hr/holiday-calendars` collection endpoint —
  presupposes the `HolidayCalendar`-as-container model explicitly rejected in §1.
- `POST /hr/holidays/import` or any bulk-upload endpoint — no precedent for bulk operations
  anywhere in the reviewed codebase; every entity is single-record CRUD only.
- Any `/hr/holidays/{id}/assign` or organization/location-scoping endpoint — presupposes the
  unresolved scoping model (§3, §10).
- Any recurrence-expansion endpoint (e.g. "generate this holiday for the next N years") —
  presupposes the recurrence field explicitly deferred in §2.
- Any role-gated or self-service-scoped endpoint — `RequireRole` exists but is unused by every
  HR/Attendance/Leave endpoint reviewed; no basis for Holiday to be the first.

---

## 7. Migration

**Should contain**: one new table, `holidays`, following the exact shape of migration
`c4a9d3e17f56` (`create_shifts_table`) — the closest structural precedent (a global reference
table with no FK):

- Full `BaseEntity` column set: `id`, `created_at`, `updated_at`, `created_by`, `updated_by`,
  `deleted_at`, `is_deleted`, `version` — identical to every migration reviewed.
- `date` (`Date`, not null).
- `name` (`String(255)`, not null) — matching `JobGrade.name`/`Shift.name` column length.
- `description` (`String(1000)`, nullable) — matching `Shift.description`'s column length.
- An index on `date` (supports `get_by_date`/the equality filter in §4) and an index on `name`
  (matching the `ix_shifts_name`/`ix_job_grades_name` precedent).
- Chained off the current alembic head, `1c4f19907e49` (`create_attendance_events_table`).

**Should NOT contain**:
- **No unique constraint on `date`.** Whether uniqueness should be global or scoped to an
  organization/location that doesn't exist in this schema is unresolved (§10); adding a bare
  `UNIQUE(date)` constraint now risks having to walk it back the moment scoping is confirmed. This
  mirrors the "staged" migration philosophy both prior docs used — don't bake in a constraint that
  might need reversal.
- **No foreign key columns** — `organization_id`, `location_id`, `hr_employee_id`, `shift_id`: none
  justified (§3).
- **No recurrence, category/type, or `is_paid` columns** — none proposed (§2).
- **No changes to any existing table** — `hr_employees`, `shifts`, `attendance_events`,
  `leave_requests` are all untouched. This is a *stronger* isolation than either prior migration:
  Attendance and Leave each added exactly one FK into `hr_employees`'s referenced table; Holiday
  adds none, in either direction.

---

## 8. Future Compatibility

- **AttendanceEvent**: would read `Holiday` by `date` to help interpret gaps in the event stream
  (e.g. distinguishing "absent" from "non-working holiday") — a read-side join on `date`, no FK,
  matching the reconciliation pattern already anticipated between Attendance and Leave.
- **LeaveRequest**: `LEAVE_DESIGN.md` §11/§12.12 already flagged day-count semantics (calendar
  days vs. working days excluding holidays) as unresolved. `Holiday` directly supplies the missing
  input to that future calculation — again via a date-range read, not a schema relationship.
- **Overtime**: would need holiday dates to determine holiday-premium-pay eligibility — same
  read-by-date pattern as above.
- **Payroll**: would need to know whether a given pay-period date is a holiday, for rate
  multipliers — same read pattern, but Payroll would also need the not-yet-modeled `is_paid`/
  pay-multiplier concept (§2), which is explicitly out of scope here.
- **Timesheet**: a per-employee, per-period view that would overlay holiday dates as a
  classification/display concern — pure read, no write path, no schema dependency.

**Flagged as likely to force a future schema change**:
- **Scoping** (§10) is the single biggest risk. If holidays turn out to need to vary by
  organization, location, or country, that's an additive column/constraint (the same incremental
  pattern already used for `job_grade_id`/`shift_id` on `hr_employees`), not a full redesign — but
  it is real, foreseeable schema churn, not a hypothetical one.
- **Recurrence** (§2, §9) is the second likely churn point. If annual recurrence is required (most
  public holidays repeat every year), the one-row-per-occurrence model recommended here means every
  consumer must re-populate holiday rows yearly — an operational cost more than a breaking one, but
  worth flagging before it becomes an implicit yearly-maintenance surprise.

---

## 9. Risks

Identified, not solved:

- **Scoping unknown.** Global vs. organization vs. location vs. country — the single biggest
  structural risk, and the one place this design's default (follow the "no scoping" precedent of
  `JobGrade`/`EmploymentType`/`EmploymentStatus`/`Shift`) is least certain to be correct in
  practice, since holidays are a real-world concept that plausibly *does* vary by jurisdiction in a
  way license-plate-style master data does not.
- **No recurrence modeled.** Operational risk (every holiday needs manual yearly re-entry) if
  recurrence is never added; correctness/migration risk if a recurrence rule engine is bolted on
  later without reconciling historical one-off rows.
- **No uniqueness constraint on `date`.** Deferred pending scoping (§7) — until resolved, nothing
  at the database level prevents two rows for the same date.
- **No day-type/category distinction.** Payroll/Overtime plausibly need to distinguish public
  holidays from company-specific ones for premium-pay purposes; its absence here could force an
  urgent schema addition once a consumer actually needs it.
- **Systemic soft-delete/version gap.** `BaseEntity` gives every entity `SoftDeleteMixin`/
  `VersionMixin` columns, but `BaseRepository.delete()` performs a real `session.delete()` (hard
  delete) and no service checks `.version` for optimistic-concurrency conflicts. Already flagged in
  both prior discoveries as a codebase-wide gap, not specific to Holiday — but relevant here if a
  holiday is deleted after other modules' calculations have already relied on it.
- **No shared range-query capability.** Every anticipated consumer (Attendance, Leave, Overtime,
  Payroll, Timesheet) will independently want "holidays in this date range." Building that
  capability five separate times inside five separate future modules, instead of once in the
  shared foundation, risks inconsistent implementations.
- **No documented product intent.** Like Leave before it, "Holiday" and "Calendar" appear nowhere
  in `docs/product/06_PRODUCT_ROADMAP.md` — there is no roadmap language to validate this design
  against at all (§0 finding 2).

---

## 10. Ambiguities

Per instructions, these are listed, not guessed at. Implementation should not proceed until they
are resolved:

1. **Scoping model.** Global, per-organization, per-location, or per-country? The only shape
   precedent (`JobGrade`/`EmploymentType`/`EmploymentStatus`/`Shift`) says "no scoping," but that
   precedent was set for entities that are not inherently jurisdiction-dependent the way public
   holidays are. Not decidable from the code.
2. **Uniqueness of `date`.** Should two holidays ever share a date, and if not, unique at what
   scope? Directly downstream of #1.
3. **Recurrence.** Is annual repetition in scope for this PR, or is `Holiday` meant to be a
   one-off, manually-entered-every-year fact table? No precedent anywhere in the codebase
   (including `Shift`, itself a "template" entity) to resolve this either way.
4. **Day-type/category.** Should holidays be classified (public, company, religious, etc.), and if
   so, is it a plain string (à la `EmploymentStatus.code`) or a foreign key to a not-yet-built
   `HolidayType` table? Mirrors `LeaveRequest`'s own unresolved `leave_type` ambiguity
   (`LEAVE_DESIGN.md` §12.2) exactly.
5. **Paid/pay-multiplier concept.** Does Payroll need `Holiday` to carry any pay-rate information,
   or is that entirely Payroll's own future concern layered on top of a plain date fact?
6. **Container vs. flat entity.** Is a `HolidayCalendar`-as-container (multiple named calendars,
   assignable to organizations/locations) the actually intended long-term shape, in which case
   this PR's flatter `Holiday` recommendation (§1) would need revisiting once an
   assignment/selection mechanism is confirmed to exist?
7. **Range-query ownership.** Should a date-range query capability be added to
   `BaseRepository`/`_apply_filters` generically now, given how many future consumers will need
   it, or should each consumer (Attendance, Leave, Overtime, Payroll, Timesheet) build its own
   local range query against `HolidayRepository` independently? An implementation-time decision,
   not resolved here.
8. **Product intent.** "Holiday"/"Calendar" is named nowhere in
   `docs/product/06_PRODUCT_ROADMAP.md`. Is this a confirmed, prioritized module, or exploratory
   work ahead of product scoping? Not answerable from the repository.

---

## 11. Consistency Review

Compared against `Shift`, `AttendanceEvent`, `LeaveRequest`:

- **Like `Shift`/`JobGrade`/`EmploymentType`/`EmploymentStatus`**: flat, global reference data, no
  `hr_employee_id` FK, no status/lifecycle field, an optional free-text `description`.
  **Intentional deviation**: those four all have a unique `code` used as a stable lookup key by
  other referencing rows; `Holiday` does not, because nothing references it by key today and
  `date` is already sufficient as a natural identifier (§2). If a future consumer needs a
  non-date key, that would be an additive column, not a redesign.
- **Unlike `AttendanceEvent`/`LeaveRequest`**: no `hr_employee_id` FK at all.
  **Intentional deviation**: `Holiday` is not "about" an employee — it is shared context every
  employee's records get evaluated *against*. This makes `Holiday` the first entity in the HR
  module that is neither employee-scoped transactional data nor org-scoped hierarchy data; it is
  pure reference data with zero relationships in any direction, a shape not previously seen even
  among the four other global-lookup entities (which, while relationship-free themselves, are all
  still *referenced by* `HrEmployee`).
- **Unlike `LeaveRequest`**: no `status`/lifecycle field. **Intentional deviation, not an
  oversight** — a holiday is either recorded or it is not; there is no pending/approved/rejected
  state analogous to a leave request's decision workflow (§5).
- **Like every entity reviewed**: inherits the full `BaseEntity` mixin set (audit, soft-delete,
  versioning), consistent with the codebase-wide convention, even though soft-delete and version
  checks are not functionally honored by the shared repository today (§9) — a systemic gap, not a
  Holiday-specific one.
- **Unlike `Shift`'s `Time` columns**: `Holiday.date` uses `Date`, matching `LeaveRequest.start_date`/
  `end_date`/`HrEmployee.hire_date` instead. This is correct alignment, not a deviation — `Holiday`
  concerns whole calendar days, not times of day, so it belongs with the `Date`-typed group.

---

## 12. Implementation Readiness

**Not ready.** This is a thinner discovery than either prior one, but the open questions are more
foundational, not fewer: Attendance and Leave each had at least one directly analogous entity
shape to extend (`Shift`'s master-data pattern, `AttendanceEvent`'s event pattern respectively).
Holiday has no precedent for the two things that matter most to its correctness — scoping and
recurrence — and guessing either would mean baking an unconfirmed business rule directly into a
migration.

Concrete decisions required before implementation can begin:

1. Scoping model (§10.1) — blocks the migration's constraint design (§7) and the relationships
   decision (§3).
2. Whether `date` must be unique, and at what scope (§10.2) — directly downstream of #1.
3. Whether recurrence is in scope for this PR (§10.3) — blocks the entity shape (§2).
4. Whether a day-type/category concept is needed now or deferred entirely (§10.4).
5. Whether `Holiday` (flat) or `HolidayCalendar` (container) is the intended long-term shape
   (§10.6) — blocks the aggregate-naming decision (§1) and the migration table name (§7).
6. Confirmation that no roadmap/product decision supersedes this discovery (§10.8), given
   "Holiday"/"Calendar" appears nowhere in `docs/product/06_PRODUCT_ROADMAP.md`.

**Stopping here per instructions.** No aggregate has been implemented, no migration has been
written, no code has been changed. Awaiting direction on the ambiguities above before proceeding.

---

## 13. Addendum — Authorization Policy Reopened (CTO Decision H2)

**Status:** Accepted — CTO Decision

**Resolves:** the `CurrentUser`-only authorization decision recorded above (§0 "Patterns identified,"
line 76-77; "Explicitly should NOT exist," line 265-266) for this document's own aggregate and, by
the same reasoning this document originally applied, for the sibling family it named as precedent
(`JobGrade`, `EmploymentType`, `EmploymentStatus`, `Shift`).

This addendum does not reopen or modify §0-§12 above. All prior content is preserved verbatim as
the historical record of the original decision and its reasoning.

### Decision

The original decision — `CurrentUser`-only authorization for `Holiday`, following the precedent
already established by `JobGrade`/`EmploymentType`/`EmploymentStatus`/`Shift` — is explicitly
reopened and superseded for create/update/delete only. Read access is unchanged.

**Global HR master/reference data** (`Holiday`, `Shift`, `JobGrade`, `EmploymentType`,
`EmploymentStatus`) now requires:

- `POST` → `RequireRole("admin")`
- `GET` → `CurrentUser` (unchanged)
- `PUT` → `RequireRole("admin")`
- `DELETE` → `RequireRole("admin")`

This reuses the existing `RequireRole("admin")` mechanism already established for non-owner-scoped
data by `Location`, `LocationType`, `Store`, `StoreType`, and `PayrollRun` — no new authorization
framework, evaluator, or abstraction is introduced.

### Why the original decision is being revisited

The original reasoning (line 265-266: *"no basis for Holiday to be the first"*) was sound at the
time it was written, but rested on two premises that have since changed:

1. `Holiday` had no financial/payroll consumer when this document was written. It now does:
   `ReconciliationService.reconcile()` classifies a matching date as `"holiday"` before evaluating
   attendance, and `AttendanceLeaveDeductionCalculator` never deducts a `holiday`-classified day —
   for every employee reconciled on that date, not one individually.
2. This document's own §1 (line 49) named the missing `User` ↔ `HrEmployee` identity link as an
   open gap. That link has since been built (`ADR-006`, `hr_employees.user_id`,
   `EmployeeContextResolver`) and now underlies the Owner-Only authorization pattern used by five
   other HR-domain aggregates. The absence of any stronger-than-`CurrentUser` mechanism in the HR
   domain, part of the original reasoning, no longer holds.

### Scope of this addendum

Covers only the authorization dependency at the API layer for the five named aggregates. Does not
modify: models, schemas, repositories, migrations, `ReconciliationService`,
`AttendanceLeaveDeductionCalculator`, or any other business logic. Read access for all five
aggregates remains `CurrentUser`-only, unchanged by this addendum.

### LeaveBalance (recorded here for completeness, not part of this document's original scope)

**Status:** Accepted — CTO Decision (L2)

`LeaveBalance` (`docs/architecture/LEAVE_BALANCE_SYNCHRONIZATION_DESIGN.md`) had no prior governed
authorization model — a separate, distinct gap from Holiday's (which had an explicit decision,
now reopened). The CTO has decided `LeaveBalance` create/update/delete require `RequireRole("admin")`,
the same mechanism as above; `LeaveBalance` is explicitly **not** Owner-Only, and no
`LeaveBalanceAuthorizationEvaluator` is introduced. Read access remains `CurrentUser`-only. This
does not modify `LeaveBalance`'s existing integrity protection (`used_days`/`remaining_days` remain
excluded from all public schemas and writable only via `ApprovalService._sync_leave_balance`).

# PR-049 — Leave Balance Synchronization (Discovery)

Status: **Discovery only. No code, no migrations, no tests. Awaiting review.**

---

## 1. Executive Summary

**Repository evidence identifies Leave Balance Synchronization — the effect an approved
`LeaveRequest` has on its employee's `LeaveBalance` — as the most directly evidenced next PR.**
Both aggregates already exist, fully built (`models/leave_request.py`, `models/leave_balance.py`,
their repositories, services, schemas, and API routers). The component that makes leave
*decisions* (`ApprovalService`, `services/approval.py`, built PR-047) already exists and already
transitions `LeaveRequest.status` from `pending` to `approved`. What does **not** exist anywhere in
this codebase is any code path connecting the two: approving a `LeaveRequest` today changes exactly
one row, in one table (`leave_requests`), and has **zero** effect on any `LeaveBalance` row. This is
not an inferred gap — it is a gap the codebase names explicitly, in its own words, in five separate
places:

- `LeaveBalance`'s own model docstring (`models/leave_balance.py:14-17`): *"Accrual, deduction,
  carry-forward, expiration, and synchronization with LeaveRequest are all future concerns -- out
  of scope here."*
- `LeaveBalanceService`'s own docstring (`services/leave_balance.py:22-25`): *"Automatic
  remaining-days calculation, deduction, accrual, carry-forward, expiration, leave reconciliation,
  payroll synchronization, and duplicate-period prevention are all explicitly out of scope for this
  module and belong to future PRs."*
- `LEAVE_DESIGN.md` §6 (PR-040): *"Leave balance/entitlement math or payroll deduction... those are
  downstream consumers... not Leave's own responsibility."*
- `LEAVE_DESIGN.md` §9: *"Leave balance/entitlement accrual, carry-over, and deduction"* listed
  under **Future**, explicitly out of scope.
- `APPROVAL_WORKFLOW_DESIGN.md` §4 (PR-046): *"`LeaveBalance` was evaluated and rejected [as
  approval-decision owner]: it holds computed totals... and its own docstring explicitly defers
  'synchronization with `LeaveRequest`' as a future concern -- it is a **consumer** of an approved
  `LeaveRequest`, not a place to store the approval itself."*

**This is the same evidentiary shape that made Attendance Reconciliation (PR-048) the prior
discovery's chosen topic**: a gap named, in the same words, by every module whose boundary excludes
it, never picked up by any subsequent PR. The difference from Reconciliation is directional —
Reconciliation is unresolved **read**-composition across five aggregates; Leave Balance
Synchronization is unresolved **write**-composition across two, triggered by an existing decision
(`ApprovalService.approve_leave_request`) rather than computed on demand. No prior discovery
document has examined this specific gap as its primary subject; `TIMESHEET_DESIGN.md` and
`ATTENDANCE_RECONCILIATION_DESIGN.md` both name `LeaveBalance` only as a non-input, not as a
write-target (§3 below).

**Alternative candidates considered and set aside for insufficient repository grounding.**
`docs/product/06_PRODUCT_ROADMAP.md` Phase 3/4 name `Territory`, `Region`, `Area`, `Store`,
`Customer`, `Mission`, `Visit`, `Survey`, `GPS`, `Photo` as roadmap modules, and none of them exist
in the codebase yet. They were considered as candidates for this discovery and set aside: unlike
Leave Balance Synchronization, none of these has any existing model, repository, service, schema,
partial implementation, or prior discovery document to build evidence from — choosing one would
require inventing an aggregate shape from the roadmap's one-line module name alone, which is
exactly the kind of unevidenced architectural guess these instructions prohibit (§12, §13). Leave
Balance Synchronization instead extends two fully-built aggregates and one fully-built orchestration
service, with the specific gap named by the code itself.

**What this discovery does and does not resolve**: it establishes, from repository evidence, which
architectural boundaries the eventual synchronization logic must respect (§3–§7), and identifies
which business rules remain undetermined by the repository (§12). It does not choose a final
class/component (mirroring `ATTENDANCE_RECONCILIATION_DESIGN.md`'s own posture, §8, §13) where
evidence is insufficient, and does not resolve business rules the repository has no basis to answer.

---

## 2. Existing Architecture

**Repository evidence.** The codebase is a single FastAPI service
(`services/api/src/eop_api`) in a strict four-layer shape, observed without exception across all
34 reviewed modules (`models/`, `repositories/`, `services/`, `api/`):

- **Models** (`models/*.py`): SQLAlchemy 2.0 declarative classes, each subclassing `BaseEntity`
  (`db/base.py:15-22`), which composes `UUIDMixin`, `TimestampMixin`, `AuditMixin`,
  `SoftDeleteMixin`, and `VersionMixin` (`db/mixins.py`) — giving every entity a UUID PK,
  `created_at`/`updated_at`, `created_by`/`updated_by`, `deleted_at`/`is_deleted`, and a `version`
  integer (default `1`), regardless of whether any of those columns are actually used by the
  entity's repository or service (confirmed below, none currently are, for soft-delete or version).
- **Repositories** (`repositories/*.py`): each subclasses `BaseRepository[ModelT]`
  (`repositories/base.py:14-19`), generic over exactly **one** model. Every method
  (`get`, `get_by`, `list`, `create`, `update`, `delete`, `exists`, `count`, `paginate`) issues
  `select(self.model)`-rooted queries; `update()` (`repositories/base.py:47-55`) does a plain
  attribute `setattr` loop with **no version check or increment** — `VersionMixin.version`
  (`db/mixins.py:39-40`) exists on every entity but is dead weight; nothing in the reviewed
  codebase reads or writes it. `delete()` (`repositories/base.py:57-64`) performs a real
  `session.delete()` — a hard delete — despite `SoftDeleteMixin` existing on every entity;
  `is_deleted`/`deleted_at` are likewise unused columns.
- **Services** (`services/*.py`): each takes a `uow_factory: Callable[[], SQLAlchemyUnitOfWork]`
  constructor parameter (defaulting to `SQLAlchemyUnitOfWork`), opens one `uow` per public method,
  constructs the repositories it needs against `uow.session`, and owns the transaction boundary —
  `uow.commit()` is called only by mutating methods, never by `get`/`list`/`list_paginated`.
  `AbstractUnitOfWork` (`uow/base.py:6-14`) makes read-only-by-default safe by construction:
  *"exiting the context without an explicit commit rolls the transaction back."* Returned entities
  are `expunge`d before the `uow` closes (avoiding `DetachedInstanceError` on session close);
  `update` methods additionally `refresh()` before expunging, to pick up server-side `onupdate`
  values.
- **API** (`api/*.py`): `APIRouter(prefix=..., tags=[...])`, one `Depends()`-injected service per
  router via a `get_x_service()` factory function, `CurrentUser` (`dependencies/auth.py`) required
  on every route, domain exceptions translated to `HTTPException` at the route boundary (never
  inside the service).

**Two precedented exceptions to the one-service-per-entity default**, both directly relevant to
this discovery:

- **`ApprovalService`** (`services/approval.py`, built PR-047, per
  `APPROVAL_ORCHESTRATION_DESIGN.md`): owns no entity of its own. Constructs
  `LeaveRequestRepository`, `OvertimeRequestRepository`, or `TimesheetRepository` — **exactly one
  per call** — against a single `uow.session`, reads the row, checks `status == "pending"`
  (`ApprovalStatus`, `services/approval.py:17-21`), and writes `status`/`approved_by`/`approved_at`/
  `rejection_reason` via `BaseRepository.update(**values)` (`services/approval.py:168-174`). It is
  wired into `api/leave_requests.py`, `api/overtime_requests.py`, and `api/timesheets.py` via
  `POST .../approve` / `POST .../reject` routes (`api/leave_requests.py:151-181`), each of which
  passes `current_user.id` — a `User` id — directly as `approver_id`; no `HrEmployee` resolution is
  needed for the approver.
- **`ReconciliationService`** (`services/reconciliation.py`, built PR-048, per
  `ATTENDANCE_RECONCILIATION_DESIGN.md`): also owns no entity. Reads `HrEmployeeRepository`,
  `HolidayRepository`, `LeaveRequestRepository`, and `AttendanceEventRepository` — **multiple
  repositories per call**, against one `uow.session` — and combines them into a single computed,
  non-persisted result. It is the codebase's only precedent for **read**-composition across more
  than one repository; it never writes (`uow.commit()` is never called,
  `services/reconciliation.py` confirmed by full read).

**No service in the codebase currently performs write-composition across more than one
repository.** `ApprovalService` writes to exactly one repository per call (§ above).
`AttendanceEventService.create` reads two repositories (`HrEmployeeRepository`, `ShiftRepository`)
for existence checks but writes to exactly one (`attendance_events`). This is the precise
capability Leave Balance Synchronization would require: approving a `LeaveRequest` (a write to
`leave_requests`) needs to also produce a write to `leave_balances` — two tables, one business
event, in what would need to be one transaction for the two writes to stay consistent.

---

## 3. Aggregate Analysis

**Question: is Leave Balance Synchronization a new aggregate, a capability on an existing
aggregate's service, or an orchestration capability spanning two aggregates?**

| Candidate | Verdict |
|---|---|
| A new aggregate (e.g. a `LeaveTransaction`/ledger entity) | Not ruled out, but no repository evidence compels it over the simpler alternatives below (§8 Option D) |
| A capability added to `LeaveBalanceService` (recomputes on being told about an approval) | Evaluated in §8 Option B |
| A capability added to `ApprovalService` (writes `LeaveBalance` in the same transaction as the status change) | Evaluated in §8 Option A |
| A new dedicated orchestration service (mirroring `ReconciliationService`'s category) | Evaluated in §8 Option C |
| Compute `LeaveBalance.used_days`/`remaining_days` on read, storing nothing (mirrors Reconciliation's "compute, never store" pattern) | Evaluated in §8 Option E — not supported by current repository evidence, given the existing persisted-column shape |

**Why this is not already answered by `LEAVE_DESIGN.md` or `APPROVAL_WORKFLOW_DESIGN.md`.**
Both discovery documents name this gap (§1) but neither analyzes it as their primary subject:
`LEAVE_DESIGN.md` was scoped to `LeaveRequest`'s own shape, before `LeaveBalance` existed at all
(`LeaveBalance` landed in migration `6a370704cee5`, chained after `LeaveRequest`'s
`e16ad71281c6`); `APPROVAL_WORKFLOW_DESIGN.md` only considered `LeaveBalance` as a candidate
**owner of the approval decision itself** (§4, quoted §1) — a different, narrower question than
whether `LeaveBalance` should be a **consumer** of that decision, which it explicitly flagged as
out of scope rather than resolving.

**Why `LeaveBalance` is the write target, not `LeaveRequest`.** `LeaveRequest` already has a
complete, working lifecycle (`pending` → `approved`/`rejected`, `services/approval.py`) that
requires no further columns to represent "this request has been approved." `LeaveBalance`
(`allocated_days`/`used_days`/`remaining_days`, `models/leave_balance.py:35-37`) is the row whose
*values* are stale the moment an approval happens — `used_days` does not reflect the newly-approved
request, and nothing recomputes it. This is symmetric with how `ATTENDANCE_RECONCILIATION_DESIGN.md`
§4 already classified `LeaveBalance`: *"relevant to Payroll/HR entitlement tracking"* — a
downstream, computed-value consumer of decisions made elsewhere, not a source of decisions itself.

**Why not embedded in `LeaveRequestService` or `LeaveBalanceService` individually.**
`LeaveRequestService`'s own docstring (`services/leave_request.py:26-33`) states approval
orchestration is *"an intentionally unresolved architectural question... deferred to a future
PR"* — a question PR-047 answered by building `ApprovalService`, not by extending
`LeaveRequestService`. `LeaveBalanceService`'s docstring (§1) draws an equally explicit boundary
around deduction. Extending either service individually to reach into the other's repository is not
supported by current repository evidence — it would run counter to a boundary each service's own
current code still honors, the same class of argument `ATTENDANCE_RECONCILIATION_DESIGN.md` §3 used
to find no repository support for extending `AttendanceService`. Neither conclusion establishes that
such an extension could never be adopted by a future architectural evolution — only that the current
codebase gives no basis for it.

---

## 4. Repository Boundary

**Should either repository perform the synchronization, or read/write across both tables? No —
on the same structural grounds every prior discovery has already established for this codebase.**

`BaseRepository[ModelT]` (`repositories/base.py:14-19`) is generic over exactly one model; every
concrete repository reviewed — including `LeaveRequestRepository` and `LeaveBalanceRepository`
themselves — issues only same-table queries. A repository method that reads an approved
`LeaveRequest` and writes to `leave_balances` (or vice versa) would be the first repository in the
codebase to touch two tables, contradicting the single-model contract every repository in this
codebase observes without exception (`repositories/timesheet.py`'s own docstring draws this same
line explicitly, quoted in full by `ATTENDANCE_RECONCILIATION_DESIGN.md` §5).

**What each repository would plausibly need, mechanically — narrow, same-table additions only:**

- `LeaveBalanceRepository` currently exposes `get_by_employee(employee_id) -> Sequence[LeaveBalance]`
  (`repositories/leave_balance.py:27-30`) — filtered by employee only, **not** by `period_year`.
  Locating the *one* balance row a specific approved `LeaveRequest` should affect requires a
  narrower `get_by_employee_and_period(employee_id, period_year)`-shaped method, or filtering the
  existing sequence in the caller. Either is a same-table read, consistent with the repository
  boundary.
- No FK exists from `leave_balances` to `leave_requests` in either direction (confirmed by direct
  read of `models/leave_balance.py` and migration `6a370704cee5`) — the two tables are currently
  fully independent. Whether one should be added is a migration-level question (§9), not a
  repository-boundary one.
- `LeaveBalanceRepository.update` is inherited, unmodified, from `BaseRepository` — it performs a
  blind `setattr` write with no non-negative validation (`repositories/base.py:47-55`). The
  non-negative invariant lives entirely in `LeaveBalanceService._validate_non_negative`
  (`services/leave_balance.py:127-133`), a **service-level** check. Any component that writes to
  `LeaveBalance` via `LeaveBalanceRepository` directly, bypassing `LeaveBalanceService`, bypasses
  this invariant entirely — flagged as a concrete risk in §11.

**No repository evidence supports resolving "which `LeaveBalance` row" at the repository layer.**
`period_year` is a plain `Integer` (`models/leave_balance.py:32`) with no derivation rule anywhere
in the codebase connecting it to a `LeaveRequest`'s `start_date`/`end_date` span. This is carried
forward as an unresolved ambiguity (§12), not guessed at here.

---

## 5. Service Boundary

**Question: which component performs the write-composition — reading an approval decision and
writing a balance update — and is this an extension of `ApprovalService`, or something new?**

**`ApprovalService` is the closest and only precedent for "a component that reacts to a
leave-request approval,"** but its precedent is narrower than it first appears, mirroring exactly
the caution `ATTENDANCE_RECONCILIATION_DESIGN.md` §6 applied to the same service for a different
extension:

- **What `ApprovalService` proves, and only this**: (1) an **orchestration category** — a service
  needn't own a single entity (`services/approval.py`, §2) is buildable and testable in this
  codebase; (2) a **dependency-injection pattern** — the `uow_factory`-constructor /
  `get_x_service()`/`Depends()` wiring is the only DI shape this codebase's services use; (3)
  **`UnitOfWork` ownership** — one `uow` per call, opened and closed by the service itself; (4) a
  **repository-coordination style** — multiple repositories can be constructed against one shared
  `uow.session` without incident (already proven by `AttendanceEventService`'s own existence
  checks, and by `ApprovalService`'s per-call choice of repository).
- **What `ApprovalService` does *not* prove**: (a) **multi-aggregate write orchestration** —
  writing to **two** repositories in the same call. Every one of its six public methods
  (`approve_leave_request`, `reject_leave_request`, `approve_overtime_request`,
  `reject_overtime_request`, `approve_timesheet`, `reject_timesheet`) delegates to the private
  `_decide` helper (`services/approval.py:143-179`), which takes a **single**
  `repo: BaseRepository[Any]` parameter and calls `repo.update(...)` exactly once. There is no
  method anywhere in this class, or in any other service in the codebase, that commits writes to
  two different tables in one transaction — the write-side counterpart to the exact gap
  `ATTENDANCE_RECONCILIATION_DESIGN.md` §6 found on the read side: the DI/UnitOfWork shape is
  precedented, the specific multi-repository **write** composition is not. (b) **`LeaveBalance`
  synchronization ownership** — nothing about `ApprovalService`'s existing shape establishes that
  it, specifically, should be the component that performs this synchronization, as opposed to some
  other component built to the same category/pattern/ownership/coordination proven above. (c)
  **Synchronization trigger placement** — nothing about `ApprovalService`'s existing shape
  establishes *where*, mechanically, the trigger for a balance update should sit (inside
  `approve_leave_request` itself, in a separate call made immediately after it, in a listener
  reacting to the status change, or elsewhere). Items (a)–(c) are implementation-PR questions, not
  conclusions this discovery reaches.

**Placements enumerated below for cost analysis only (full analysis with evidence in §8) — this
list is illustrative, not a repository-evidenced narrowing of the design space:**

1. **Extend `ApprovalService.approve_leave_request`** to also construct `LeaveBalanceRepository`
   against the same `uow.session` and update it before `commit()`. This would keep the status
   change and the balance change atomic (both succeed or both roll back, since
   `AbstractUnitOfWork` rolls back the entire session on any unhandled exception,
   `uow/base.py:22-26`) — a real advantage no other placement gets for free. But it would be
   `ApprovalService`'s first two-repository *write*, need a new dependency
   (`HrEmployeeRepository`-style import of `LeaveBalanceRepository`) that has nothing to do with
   the other five methods on the class, and couples an "approval" concept to a "balance" concept
   the class's own docstring never anticipated.
2. **A new dedicated service** (mirroring `ReconciliationService`'s "no owned entity, reads/writes
   via constructed repositories" category, but for **write**-composition instead of read). Would
   keep `ApprovalService` unchanged and scoped to status transitions only, at the cost of
   introducing a second orchestration-service category with, again, no precedent for the specific
   multi-repository **write** behavior it would need to perform, and an unresolved question of how
   it learns an approval happened (§8).
3. **`LeaveBalanceService` gains a method** (e.g. `apply_leave_approval(...)`) that
   `ApprovalService` calls after its own `commit()`. This is the only one of the three that would
   require one service to call **another service** — no precedent for this exists anywhere in the
   codebase (`ApprovalService`'s own docstring states *"it never calls another service"*,
   `services/approval.py:35`) — and it would split the status write and the balance write across
   two separate transactions/commits, reintroducing the atomicity problem Placement 1 avoids. This
   is the one placement current repository evidence provides no support for, specifically because
   it requires modifying `ApprovalService` in a way its own current code declines to do (§8). This
   is a statement about what the current codebase evidences, not a claim that `ApprovalService`
   could never be changed to call another service in some future architectural evolution.

**None of the above is repository evidence selecting a design.** They are enumerated to show what
each would cost, given the four things `ApprovalService` actually proves. Current repository
evidence provides no support for Placement 3 for the reason stated; it does not select between Placement 1, Placement 2, or any
other placement consistent with the boundaries in this section and §4 (§8, §13).

**Must NOT belong in whichever component performs this**, mirroring the boundary every reviewed
service already draws around its neighbors:

- Leave-request lifecycle validation (`pending` → `approved`) — `ApprovalService._decide` already
  owns this exclusively; synchronization only *reacts* to a transition already validated there.
- Accrual, carry-forward, expiration, or period-opening logic for `LeaveBalance` — none of these
  are approval-triggered; they are explicitly listed as separate future concerns
  (`services/leave_balance.py:22-25`) this discovery does not fold in.
- Payroll pay-rate computation — same boundary every reviewed document already draws around
  Payroll as a distinct, unbuilt future consumer.

---

## 6. API Boundary

**Recommendation, evidence-supported: no new route is required for the core synchronization
behavior itself.** The trigger is an existing action — `POST /hr/leave-requests/{id}/approve`
(`api/leave_requests.py:151-166`) — not a new resource lifecycle. Reading the resulting balance is
already served by the existing `LeaveBalance` CRUD surface (`api/leave_balances.py`, `GET
/hr/leave-balances`, `GET /hr/leave-balances/{id}`, `GET /hr/leave-balances/paginated`). This
mirrors `ATTENDANCE_RECONCILIATION_DESIGN.md`'s own reasoning in the opposite direction: that
document proposed a **new** `GET`-only route because reconciliation has no existing resource
surface; here, `LeaveBalance` already has a complete CRUD surface, so nothing new needs to be
exposed to *read* the result.

**What is genuinely open, not resolved here:**

- **Response shape of the existing `approve` endpoint.** It currently returns only
  `LeaveRequestResponse` (`api/leave_requests.py:151`, `schemas/leave_request.py`). Whether the
  caller also needs the updated `LeaveBalance` in the same response (to avoid a second round-trip),
  or should fetch it separately via the existing `leave-balances` routes, is not decidable from the
  repository — no other endpoint in this codebase returns a composite response spanning two
  entities, so there is no precedent to extend either way.
- **Error surface.** If synchronization fails after the `LeaveRequest` status write is prepared
  (e.g. no matching `LeaveBalance` row for the employee/period, §12), does `POST .../approve`
  return a 4xx/5xx and roll back the whole approval, or does the status change succeed
  independently of balance synchronization? No existing endpoint in this codebase has a
  multi-outcome failure mode to copy from — `ApprovalService`'s only current failure mode is
  `InvalidApprovalStateError` → `409` (`api/leave_requests.py:157-158`), which has nothing to do
  with a *second* entity's state.

---

## 7. Infrastructure Analysis

**UnitOfWork / transactionality.** `SQLAlchemyUnitOfWork` (`uow/sqlalchemy.py`) already supports
constructing multiple repositories against one shared `AsyncSession` within a single `uow` block —
proven safe by `AttendanceEventService` (two repositories, one write) and `ReconciliationService`
(four repositories, zero writes). No infrastructure component needs to change to support a two-write
transaction; the capability already exists at the `UnitOfWork` layer. What is missing is a service
that *uses* it this way (§5).

**Concurrency control is absent, infrastructure-wide, and directly relevant here.**
`VersionMixin.version` (`db/mixins.py:39-40`) exists on `LeaveBalance` (and every entity) but
`BaseRepository.update()` never reads or increments it (§2) — there is no optimistic-concurrency
check anywhere in this codebase. A read-modify-write on `LeaveBalance.used_days`/`remaining_days`
(read the current value, add the newly-approved request's day count, write it back) is exactly the
shape of operation optimistic concurrency exists to protect, and this codebase has no working
version of that protection to reuse. This is a repository-wide infrastructure gap, not something
introduced by this discovery, but Leave Balance Synchronization is the first proposed write path
where a lost update (two concurrent approvals for the same employee/period) would silently produce
an incorrect `used_days` value — a business-meaningful bug, not just a stale read.

**Audit logging is infrastructure that exists but is not wired to any HR/Time-Management entity.**
`AuditEntityType` (`core/audit.py:4-13`) currently lists only `ORGANIZATION`, `PROJECT`, `EMPLOYEE`,
`ASSIGNMENT`, `TASK`, `USER`, `ROLE` — no HR or Time-Management entity (`LeaveRequest`,
`LeaveBalance`, `Timesheet`, `OvertimeRequest`, `Holiday`, `Shift`, `AttendanceEvent`) is a member.
`AuditLog`/`AuditLogService` (`services/audit_log.py`) is real, working infrastructure, confirmed
unused by any HR module by every prior discovery (`LEAVE_DESIGN.md` §5: *"exists as infrastructure,
unused by any business module"*) and reconfirmed here. A balance mutation is a stronger candidate
for audit logging than most CRUD writes already in this codebase (it changes a financially-relevant
running total, not a simple field edit), but wiring it in would be the first HR-domain use of
`AuditLog` — evidence supports that the infrastructure exists and is reusable, not that this PR
should be the one to adopt it (§12).

**Event/notification infrastructure exists and is unused by any HR service.** `EventPublisher`
(`events/base.py`) and `NotificationProvider` (`notifications/base.py`) are both real,
working abstractions with in-memory implementations (`events/memory_publisher.py`,
`notifications/memory_provider.py`), consumed today only by `services/event.py`/
`services/notification.py` themselves (generic CRUD-style services over `Event`/`Notification`
records) — grep-confirmed (§2) that no HR service publishes an event or sends a notification
anywhere. An event-driven synchronization design (`ApprovalService` publishes an event; a listener
updates `LeaveBalance`) is mechanically possible against this infrastructure but has **no consumer
precedent** — nothing in this codebase currently subscribes to or acts on a published event. This
is evaluated as Option D in §8 and not recommended, precisely because the "listener" half of that
pattern does not exist anywhere yet.

**Test infrastructure.** Every one of the 34 existing modules has a uniform three-file test set:
`test_<module>_repository.py`, `test_<module>_service.py`, `test_<module>s_api.py` (or `_api.py`
for orchestration services — `test_approval_service.py`, `test_reconciliation_service.py` +
`test_reconciliation_api.py`), confirmed by directory listing of `services/api/tests/`. Whatever
component is chosen would be expected to follow this same three-tier convention — noted for
implementation-readiness (§14), not exercised in this discovery (no tests are being written here).

---

## 8. Candidate Architectures

### Option A — Extend `ApprovalService.approve_leave_request`

**Supporting evidence**: keeps the status write and the balance write in one `uow`/one `commit()`
— genuinely atomic, using infrastructure that already supports it (§7). `ApprovalService` already
imports and constructs repositories beyond the one it primarily operates on in spirit (every CRUD
service does existence checks against a second repository); extending it to write a second
repository, only for this one method, is the smallest change that achieves atomicity.

**Contradicting evidence**: no method on `ApprovalService` currently writes to more than one
repository (§5) — this would be a first, not an extension of an established pattern.
`reject_leave_request`, `approve_overtime_request`, `reject_overtime_request`,
`approve_timesheet`, `reject_timesheet` would gain no analogous behavior (`OvertimeRequest` and
`Timesheet` have no balance concept to synchronize against), so the class would contain five
single-repository-write methods and one two-repository-write method — an asymmetry the current
class has none of.

**Advantages**: atomic by construction; smallest number of new moving parts; no new DI wiring.

**Disadvantages**: couples an approval-transition concern to a balance-accounting concern inside
one method; the non-negative invariant currently enforced only in `LeaveBalanceService` (§4) would
need to be re-implemented or duplicated inside `ApprovalService`, since bypassing
`LeaveBalanceService` bypasses that check entirely.

### Option B — Extend `LeaveBalanceService` with a method `ApprovalService` calls

**Supporting evidence**: keeps `LeaveBalanceService`'s existing non-negative validation
(`services/leave_balance.py:127-133`) in the one place it already lives, reused rather than
duplicated.

**Contradicting evidence**: requires `ApprovalService` to call another service, which no service in
this codebase does — `ApprovalService`'s own docstring states the opposite explicitly
(`services/approval.py:35`, quoted §5). It also means two separate `uow`/`commit()` boundaries (one
inside `ApprovalService._decide`, one inside `LeaveBalanceService`'s new method) unless the two
services are made to share a `uow`, which would require restructuring both services' constructors —
a larger change than either service's current shape supports without modification.

**Advantages**: reuses existing validation without duplicating it; keeps `LeaveBalance`'s
invariants inside `LeaveBalanceService`, matching this codebase's general pattern of a service
owning its own entity's invariants.

**Disadvantages**: no precedent for cross-service calls; non-atomic across the two writes unless a
shared-`uow` refactor (out of scope for this discovery) is also done; failure partway through would
leave `LeaveRequest.status = approved` with no corresponding balance change and no rollback.

### Option C — A new dedicated orchestration service (mirroring `ReconciliationService`'s category, but for writes)

**Supporting evidence**: keeps both `ApprovalService` and `LeaveBalanceService` unchanged and
narrowly scoped, matching this codebase's general preference (seen in every prior discovery) for
new capabilities to get their own component rather than accreting onto an existing one.
`ReconciliationService` is direct, working precedent that a **new**, no-owned-entity,
`uow_factory`-shaped service is buildable and testable in this codebase for a composition problem
that doesn't fit any existing service.

**Contradicting evidence**: `ReconciliationService`'s precedent is for **read**-composition,
explicitly never writing (`ATTENDANCE_RECONCILIATION_DESIGN.md` §8, reconfirmed by direct code
read, §2 above). A write-composition service is a **different, still-unprecedented** capability —
this option would be the first service in the codebase whose entire purpose is writing to two
repositories in one call, triggered by a state change (`LeaveRequest.status → approved`) that
another service, not this one, is responsible for detecting. Unless this new service also
*performs* the approval itself (which would duplicate `ApprovalService`'s `_decide` logic — a
different problem, not resolved by this discovery either), it needs to be invoked *from*
`ApprovalService`, which reintroduces Option B's cross-service-call problem, or subsume
`ApprovalService`'s leave-approval method entirely, which would fragment approval logic across two
services for the one entity (`LeaveRequest`) that has both a status transition and a balance
consequence.

**Advantages**: cleanest separation of concerns on paper; follows the "give it its own component"
instinct every prior discovery has favored.

**Disadvantages**: the *invocation* problem (how does this new service learn an approval happened,
atomically, without either duplicating `ApprovalService`'s transition logic or introducing a
cross-service call) is not solved by giving the write-composition its own class — it is the same
problem Options A and B already face, just relocated.

### Option D — A new `LeaveTransaction`/ledger aggregate

**Supporting evidence**: none found. No `ledger`, `transaction`, or `entry`-shaped table or model
exists anywhere in the codebase to extend. `LeaveBalance`'s own docstring (`models/leave_balance.py:
14-17`) explicitly describes itself as *"persistence-shaped, not calculation/ledger shaped"* —
i.e., the existing schema was deliberately built to **not** need this.

**Contradicting evidence**: introducing a ledger aggregate now, for a single consumer (leave
approval), with no second concrete use case to validate the shape against, repeats the exact
premature-generalization risk `TIMESHEET_DESIGN.md` §7 and `APPROVAL_WORKFLOW_DESIGN.md` §3 both
already declined to take for structurally similar composition problems.

**Advantages**: would solve §12's "which `LeaveRequest`(s) contributed to `used_days`" traceability
gap directly, and would make reversal (§10, §11) mechanical (delete/reverse the ledger entry)
rather than requiring an inverse recomputation.

**Disadvantages**: the largest schema change of any option; runs counter to the existing model's
stated design intent; not justified by current evidence, which shows exactly one consumer (leave approval),
not the "second concrete use case" bar this codebase's own discovery methodology has consistently
required before generalizing (§13).

### Option E — Compute `LeaveBalance.used_days`/`remaining_days` on read, store nothing

**Supporting evidence**: mirrors `ATTENDANCE_RECONCILIATION_DESIGN.md`'s "compute, never store"
resolution for a structurally similar problem (derived value from other aggregates' data).

**Contradicting evidence**: `LeaveBalance.allocated_days`/`used_days`/`remaining_days` are already
persisted, non-nullable, directly-writable columns (`models/leave_balance.py:33-37`) with a full
CRUD surface (`LeaveBalanceService.create`/`.update`, `api/leave_balances.py`) that lets a caller
set `used_days` directly, independent of any `LeaveRequest`. Treating them as read-time-computed
would require either removing that CRUD surface (a breaking change to an already-shipped module,
outside this discovery's evidence-gathering mandate) or maintaining two inconsistent sources of
truth (a stored value a client can overwrite, and a computed value nothing currently reads) —
neither is a clean adoption of the Reconciliation pattern, unlike Reconciliation itself, which had
no persisted columns to reconcile against.

**Advantages**: sidesteps the concurrency/race risk in §7/§11 entirely, since nothing would be
read-modify-written.

**Disadvantages**: runs counter to the already-shipped, already-CRUD-exposed schema shape; not a
same-cost adoption of the Reconciliation precedent the way it might first appear.

**Verdict.** No option is fully evidence-compelled, and evidence does not narrow the field to any
specific remaining option. What follows distinguishes "not evidenced by the current architecture"
from "architecturally impossible" throughout — repository evidence can establish only the former.

**Option B is not supported by current repository evidence**, specifically because it would require
`ApprovalService` to call another service, and `ApprovalService`'s own docstring states explicitly
that it never does. This shows the current codebase provides no basis for modifying `ApprovalService`
this particular way — it does not show that a component calling another service is impossible in
this codebase generally, or that a future architectural evolution could never adopt this shape; no
service happening to call another service today is an absence of precedent, not a prohibition.
**Option D is not supported by current repository evidence**: `LeaveBalance`'s own docstring commits
to a non-ledger, persistence-only shape, and this codebase's discoveries have consistently declined
to generalize into a new aggregate on the strength of one consumer — this is a statement about what
today's evidence justifies building, not a claim that a ledger aggregate could never become the
right shape once a second concrete use case exists. **Option E is not supported by current
repository evidence**: `LeaveBalance`'s columns are already persisted and directly writable through
a shipped CRUD surface, so a compute-on-read model is inconsistent with what exists today — this
does not establish that the schema could never be revisited.

**What the above does not do is select "Option A and Option C" as the remaining field.** Those two
are the placements this discovery happened to enumerate for illustration, evaluated only to show
what each would cost (§ above) and, for Option B, to show specifically why the current code gives no
support for modifying `ApprovalService` that way. Repository evidence does not establish that the
eventual component must be shaped like Option A, like Option C, or like any other specific
placement — only that current evidence gives no support for placing it in a repository (§4), for
modifying `ApprovalService` to call another service (the specific way Option B was evaluated), for a
persisted ledger absent a second concrete use case (Option D), or for discarding `LeaveBalance`'s
existing persisted-column CRUD surface (Option E). Anything consistent with those boundaries —
including but not limited to Option A or Option C — is neither confirmed nor evidenced against here.
**Selecting or designing the concrete component is an implementation-PR decision** (§13), not a
conclusion this discovery reaches.

---

## 9. Migration Considerations

**No migration is strictly required to make *some* form of synchronization possible.** The
`leave_balances` table (migration `6a370704cee5`) already has all three columns
(`allocated_days`, `used_days`, `remaining_days`) needed to record a deduction, and
`BaseRepository.update()` can write to any of them today. A minimal Option A/C implementation could
ship with zero schema changes.

**What a migration would plausibly need to add, contingent on business-rule decisions this
document does not make (§12):**

- **A unique constraint on `(employee_id, period_year)`.** Confirmed absent by direct read of the
  migration (`6a370704cee5:26-49`) — only non-unique indexes exist on `employee_id` and
  `period_year` separately (`ix_leave_balances_employee_id`, `ix_leave_balances_period_year`).
  Without it, multiple `LeaveBalance` rows can exist for the same employee and year today, and
  nothing prevents it. If synchronization needs to select "the" balance row for an employee/year
  deterministically, this ambiguity (§12) must be resolved — either by adding the constraint (a
  real migration, contingent on confirming no existing data already violates it) or by defining a
  selection rule that tolerates multiple rows (e.g. "most recently created").
- **A traceability link between `LeaveBalance` and the `LeaveRequest`(s) that contributed to
  `used_days`.** No FK exists in either direction today. Needed only if Option D (§8, not
  recommended) or a lighter-weight audit trail is adopted; not needed for a simple
  overwrite-style deduction under Options A/B/C.
- **`leave_type` on `LeaveRequest`.** Does not exist today (confirmed absent from
  `models/leave_request.py`, consistent with `LEAVE_DESIGN.md` §12.2's own unresolved item). If
  different leave types draw from different balances (e.g. annual vs. sick), `LeaveBalance` would
  need a `leave_type` column to match against — currently `LeaveBalance` has no such column either
  (`models/leave_balance.py:32-37`), so both sides of this question are unresolved together, not
  independently.

**Alembic chain**: current head is `f4a1c9e6b2d7` (`add_approval_fields_to_leave_requests_
overtime_requests_and_timesheets`), unchanged since PR-047; PR-048 added no migration
(`ReconciliationService` is read-only). Any migration this PR's implementation eventually needs
would chain off `f4a1c9e6b2d7`.

---

## 10. Future Compatibility

- **Payroll**: the clearest anticipated consumer, named as a future dependency by both
  `LEAVE_DESIGN.md` §10 and `TIMESHEET_DESIGN.md` §1/§13.12, neither of which found any existing
  `Payroll`/`PayPeriod` model. A synchronized, trustworthy `LeaveBalance.remaining_days` is a more
  useful input to a future Payroll module than the current always-stale value — this is the primary
  business justification for this PR existing at all, though it is a product/architecture judgment,
  not something derivable purely from repository evidence.
- **Timesheet**: `TIMESHEET_DESIGN.md` §4 already anticipated `LeaveBalance` as optional read
  context ("remaining leave balance context... if surfaced at all") for a future
  `TimesheetService` capability — unaffected structurally by this discovery, since Timesheet would
  only ever *read* `LeaveBalance`, never write it.
- **Attendance Reconciliation**: `ATTENDANCE_RECONCILIATION_DESIGN.md` §4 already confirmed
  `LeaveBalance` is **not** a reconciliation input (entitlement bookkeeping, not a fact about a
  specific date) — this discovery does not change that boundary; `ReconciliationService` needs no
  changes regardless of how Leave Balance Synchronization is ultimately implemented.
- **Reversal / offboarding**: no cancel, revoke, or un-approve endpoint exists anywhere in the
  codebase today (confirmed absent from `api/leave_requests.py` and `services/approval.py` by full
  read) — the only way to remove an approved `LeaveRequest` today is `DELETE
  /hr/leave-requests/{id}`, which performs a **hard delete**
  (`BaseRepository.delete()`, `repositories/base.py:57-64`). If synchronization is built, a
  hard-deleted, previously-approved `LeaveRequest` would leave a `LeaveBalance` deduction with no
  trace of what caused it and no automatic reversal — the same "hard delete leaves no explanatory
  trace" risk `ATTENDANCE_RECONCILIATION_DESIGN.md` §11 already flagged for a different aggregate,
  recurring here for a stronger reason (a financially-meaningful balance, not just a reconciliation
  read).

---

## 11. Risks

Identified, not solved:

- **Multi-repository write composition is unprecedented**, the write-side counterpart to the
  central risk `ATTENDANCE_RECONCILIATION_DESIGN.md` §11 flagged for reads: no service in this
  codebase currently commits changes to two tables from one triggering action, so whichever
  component performs this is new, unreviewed-in-practice territory (§5, §8).
- **No optimistic concurrency control exists to protect a read-modify-write on `used_days`/
  `remaining_days`.** `VersionMixin.version` exists on `LeaveBalance` but is never checked or
  incremented by `BaseRepository.update()` (§7). Two concurrent approvals against the same
  employee/period could silently produce a lost update.
- **The non-negative invariant is enforced only in `LeaveBalanceService`, not in the repository or
  the database.** Any implementation that writes to `LeaveBalance` via `LeaveBalanceRepository`
  directly (Options A/C, §8) bypasses `_validate_non_negative`
  (`services/leave_balance.py:127-133`) unless it re-implements the same check itself — there is no
  CHECK constraint or repository-level guard to fall back on (confirmed by direct read of
  `models/leave_balance.py` and `repositories/leave_balance.py`).
- **No unique constraint on `(employee_id, period_year)`** (§9) means "the" `LeaveBalance` row for
  a given approval is not a well-defined concept today if more than one row exists for the same
  employee/year.
- **Overlapping approved `LeaveRequest`s are not prevented at write time.** `LEAVE_DESIGN.md`
  §12.8 already flagged this, unresolved; it is directly load-bearing here, since two overlapping
  approved requests would each trigger a deduction, and nothing determines whether double-deduction
  for the overlapping days is correct or a bug.
- **Cross-year-spanning requests have no defined `period_year` mapping.** A `LeaveRequest` with
  `start_date` in one calendar year and `end_date` in the next (`models/leave_request.py:44-45`
  places no constraint preventing this) has no rule determining which `LeaveBalance.period_year`
  row(s) it should deduct from, or how the days split.
- **No reversal path.** Hard-delete of an approved, already-synchronized `LeaveRequest` leaves a
  stale deduction with no trace (§10). No cancel/un-approve endpoint exists to reverse a deduction
  in the ordinary course of business either.
- **Half-day / partial-day leave is unresolved**, inherited from `LEAVE_DESIGN.md` §12.12
  (day-count semantics: calendar days vs. working days, and whether half-days are representable at
  all) — directly determines the number synchronization would even compute.
- **No roadmap grounding.** "Leave Balance," "deduction," and "synchronization" do not appear in
  `docs/product/06_PRODUCT_ROADMAP.md` at all — the same gap every Time Management discovery since
  `LEAVE_DESIGN.md` has already flagged, continuing here.

---

## 12. Architectural Ambiguities

Per instructions, listed, not guessed at:

1. **Concrete component.** What component performs synchronization, and where the trigger for it
   is placed. Repository evidence establishes only where this must **not** live — not a repository
   (§4), not a modification requiring `ApprovalService` to call another service (§5, §8) — and does
   not narrow the remaining space to any specific placement, named or unnamed (§8, §13).
2. **Target `LeaveBalance` row selection.** With no unique `(employee_id, period_year)` constraint
   (§9, §11), how is "the" balance row for a given approval determined if zero, one, or multiple
   rows exist for that employee/year?
3. **Cross-year-spanning requests.** How a `LeaveRequest` whose `start_date`/`end_date` cross a
   calendar-year boundary maps to `period_year`, or splits across two `LeaveBalance` rows.
4. **Day-count semantics.** Calendar days vs. working days, and whether/how half-days are
   represented — inherited unresolved from `LEAVE_DESIGN.md` §12.12, directly load-bearing here.
5. **Leave type / multiple balance types.** Whether different `leave_type`s (not yet modeled on
   either `LeaveRequest` or `LeaveBalance`, §9) draw from different balances, and what that means
   for row selection (#2) if introduced.
6. **Reversal semantics.** What happens to a `LeaveBalance` deduction when the originating
   `LeaveRequest` is later hard-deleted (the only removal path that exists today, §10) — is this
   accepted as a known limitation, or does it block shipping synchronization until a reversal or
   soft-delete-aware path exists?
7. **Overlap handling.** Whether two overlapping approved `LeaveRequest`s for the same employee
   should each deduct independently (possible double-counting) — inherited unresolved from
   `LEAVE_DESIGN.md` §12.8.
8. **Failure semantics at the API boundary.** If the balance write fails after the approval write
   is prepared, does the whole `POST .../approve` call fail (§6), and if so, with what status code
   and message — no precedent exists for a two-entity failure mode on this endpoint today.
9. **Response shape.** Whether `POST .../approve` should return the updated `LeaveBalance`
   alongside the `LeaveRequest`, or leave balance-reading to the existing separate endpoints (§6).
10. **Concurrency control.** Whether this PR should be the one to introduce a working version of
    `VersionMixin`-based optimistic locking (§7, §11) given it is the first write path where a lost
    update has direct business consequences, or whether that is deferred as a known, accepted risk.
11. **Audit logging.** Whether this is the PR that extends `AuditEntityType` to cover HR/Time
    Management entities for the first time (§7), given a balance mutation is a stronger audit
    candidate than most existing CRUD writes, or whether that remains deferred alongside every
    other HR module's same gap.
12. **Product intent.** No product document names "leave balance deduction," "synchronization," or
    equivalent — confirmed absent from `docs/product/06_PRODUCT_ROADMAP.md` by direct grep. Whether
    this capability is actually wanted, versus `LeaveBalance` remaining a manually-managed HR record
    indefinitely, is a product decision this discovery cannot make.

---

## 13. Recommendation

**Repository evidence supports treating Leave Balance Synchronization as the best-evidenced next
discovery topic** (§1) and **establishes the architectural constraints current evidence supports**.
Each item below is a statement about what today's repository evidence justifies, not a claim that
the excluded shape is architecturally impossible or could never be adopted by a future evolution of
this codebase — repository evidence can show only that the current architecture provides no support
for a given shape, not that no shape of that kind could ever work:

- Current repository evidence provides no support for synchronization living in either
  repository — `BaseRepository`'s single-model contract has no exception anywhere in this codebase
  (§4).
- Current repository evidence provides no support for implementing this by having
  `LeaveBalanceService` gain a method that `ApprovalService` calls — `ApprovalService`'s own
  docstring states it never calls another service, and no service in this codebase does today (§5,
  §8, Option B/Placement 3).
- Current repository evidence provides no support for a new persisted ledger aggregate absent a
  second concrete use case — `LeaveBalance`'s own docstring commits to a non-ledger,
  persistence-only shape, and this codebase's discoveries have consistently declined to generalize
  on one consumer alone (§8, Option D).
- Current repository evidence provides no support for discarding `LeaveBalance`'s existing
  persisted, directly-writable `allocated_days`/`used_days`/`remaining_days` columns in favor of a
  compute-on-read model — those columns already have a shipped CRUD surface a client can write to
  independently (§8, Option E).
- Whatever component is built should use the `uow_factory` / `Depends()` DI shape and the
  one-`uow`-per-call `UnitOfWork` ownership pattern every service in this codebase already uses —
  not because this discovery selects a component, but because no other DI or transaction-management
  pattern exists anywhere in the codebase to build against (§2, §7).

**Repository evidence is insufficient to determine the concrete orchestration component.**
`ApprovalService` proves an orchestration category, a DI pattern, `UnitOfWork` ownership, and a
repository-coordination style are all buildable in this codebase (§5) — it does not prove that
`ApprovalService` itself should own this synchronization, that a new dedicated service should, or
where the trigger for the write should sit. This discovery does not recommend extending
`ApprovalService`, does not recommend a new dedicated service (under any name), and does not
recommend any other concrete component. **Choosing the orchestration component is an
implementation-PR decision**, to be made with the benefit of the boundaries above, not a conclusion
repository evidence allows this discovery to reach.

**Nor does repository evidence resolve the business rules in §12** — row selection, cross-year
spanning, day-count semantics, overlap handling, and reversal are not decidable from the code as it
stands, several of them inherited, still open, from discovery documents as far back as
`LEAVE_DESIGN.md` (PR-040). These are not implementation-time judgment calls the way the component
choice is; they determine what the computation produces, not just which component produces it, and
cannot be deferred to "whoever implements this" the way the component choice can.

---

## 14. Implementation Readiness

**Not ready — and, as with PR-048's discovery, readiness here spans two distinct kinds of open
item that should not be blurred.**

**Settled by this discovery (repository evidence, not open to guessing — each item is a statement of
what current evidence supports or fails to support, not a claim of architectural impossibility):**
- Current repository evidence provides no support for synchronization living in either repository
  (§4).
- Current repository evidence provides no support for a cross-service call from `ApprovalService`
  to `LeaveBalanceService` (§5, §8 Option B).
- Current repository evidence provides no support for a new ledger aggregate without a second
  concrete use case to justify one (§8 Option D).
- Current repository evidence provides no support for a pure compute-on-read model, given
  `LeaveBalance`'s existing persisted-column shape (§8 Option E).
- Whatever component is chosen must write to `LeaveBalanceRepository` within the same `uow` as the
  `LeaveRequest` status write, to get atomicity from infrastructure that already supports it (§7,
  §8).

**Not settled — an implementation-PR architectural decision, informed by §5/§8 but not made
here:**
1. **The concrete orchestration component, and where its trigger is placed (§12.1).** Repository
   evidence establishes the constraints listed above; it does not establish which component
   satisfies them. This document does not recommend extending `ApprovalService`, does not
   recommend a new dedicated service, and does not recommend any other named component — that
   choice belongs to the implementation PR (§13).

**Not settled — business-rule decisions, requiring product/architecture input neither this
discovery nor the implementation PR can supply from the repository alone:**
2. Target `LeaveBalance` row selection given no unique constraint (§12.2).
3. Cross-year-spanning request handling (§12.3).
4. Day-count semantics — calendar vs. working days, half-days (§12.4), inherited from
   `LEAVE_DESIGN.md` §12.12 and still unresolved three PRs later.
5. Leave type / multiple balance types (§12.5).
6. Reversal semantics on hard-delete of an already-synchronized request (§12.6).
7. Overlap handling for concurrently-approved overlapping requests (§12.7), inherited from
   `LEAVE_DESIGN.md` §12.8.
8. API failure semantics if the balance write fails (§12.8).
9. Response shape — whether `approve` returns the updated balance (§12.9).
10. Whether to introduce real optimistic-concurrency enforcement now, given this is the first write
    path where a lost update has direct business consequences (§12.10).
11. Whether to extend `AuditEntityType` to HR/Time Management entities now, given a balance
    mutation is a stronger audit candidate than most existing writes (§12.11).
12. Confirmation of product intent, given no roadmap document names this capability (§12.12).

**Stopping here per instructions.** No aggregate has been implemented, no migration has been
written, no service or repository method has been added, no code has been changed. Awaiting
direction on the items above — particularly the business-rule ambiguities (§12.2–§12.7), without
which no implementation can begin regardless of how the placement decision (§12.1) is ultimately
made — before proceeding.

---

# PR-049 (Implementation) — Step 1: Architecture Decision

Status: **Architecture decision only. No code, no migrations, no tests. Awaiting review.**

This section resolves §12.1/§14's "concrete orchestration component" open item left by the
discovery above. It is an **implementation decision, made under the architectural constraints the
discovery established** — it does not revise or re-litigate the discovery, and does not reopen any
of §8's already-settled exclusions (Options B, D, E). It also does not resolve any business-rule
ambiguity (§12.2–§12.12); those remain open regardless of this decision.

## A. Chosen implementation

**Extend `ApprovalService.approve_leave_request`** (`services/approval.py`) to perform the
`LeaveBalance` write inside the same `uow`/transaction as the `LeaveRequest` status write, rather
than introducing a new service.

Concretely: the shared `_decide` helper (`services/approval.py:143-179`) currently calls
`uow.commit()` internally on every invocation. `_decide` gains a `commit: bool = True` keyword
parameter. `approve_leave_request` (`services/approval.py:59-71`) is the only one of the six public
methods whose call site changes: it calls `_decide(..., commit=False)`, then — still inside the
same `uow` block, before that block exits — constructs `LeaveBalanceRepository(uow.session)`,
performs the balance write, and calls `uow.commit()` once, after both writes are staged. The other
five call sites (`reject_leave_request`, `approve_overtime_request`, `reject_overtime_request`,
`approve_timesheet`, `reject_timesheet`) are unchanged and keep `_decide`'s default `commit=True`.

- **Ownership**: `ApprovalService`. No new class.
- **Transaction model**: one `SQLAlchemyUnitOfWork`, one `uow.session`, one `commit()` — the status
  write and the balance write succeed or roll back together, using `AbstractUnitOfWork`'s existing
  rollback-on-exit contract (`uow/base.py:22-26`).
- **Trigger location**: inline in `approve_leave_request`, immediately after the status transition
  is staged and before commit — not a listener, not a post-commit hook, not a call from the API
  layer.
- **Dependency direction**: `ApprovalService` gains a direct construction dependency on
  `LeaveBalanceRepository`, the same way it already depends on `LeaveRequestRepository`,
  `OvertimeRequestRepository`, and `TimesheetRepository`. `LeaveBalanceService` gains no new
  dependency and is untouched.
- **Repository usage**: `LeaveBalanceRepository` is constructed against `uow.session`, mirroring
  how every existing service constructs a second repository for an existence check
  (`AttendanceEventService`'s `HrEmployeeRepository`/`ShiftRepository`) or how
  `ReconciliationService` constructs four. The difference — and the precedent this introduces — is
  that this repository is **written to**, not just read (§C).
- **Service interactions**: none. `ApprovalService` calls no other service. `LeaveBalanceService`'s
  own CRUD surface is unaffected; a client can still create/update/delete `LeaveBalance` rows
  directly through it exactly as today.
- **DI**: no change to `api/leave_requests.py`'s wiring — `ApprovalServiceDep` is unchanged, and no
  new `Depends()` is introduced anywhere.

## B. Alternatives considered

1. **A new dedicated `uow_factory`-owning service** (mirroring `ReconciliationService`'s category),
   invoked by `ApprovalService`. Rejected: invoking it would require `ApprovalService` to call
   another service — the specific shape discovery §5/§8 already found no repository support for.
   The only way around that would be for the new service to accept an externally-supplied
   `uow`/session instead of opening its own via `uow_factory` — every service in this codebase,
   without exception, opens its own `uow` per public call; none accept a caller-supplied session.
   That would be a second new precedent stacked on top of the one this decision already introduces
   (§C), for no offsetting benefit over Alternative A.
2. **A new dedicated service invoked from the API route, not from `ApprovalService`** — e.g.
   `api/leave_requests.py`'s `approve_leave_request` route calls both `ApprovalServiceDep` and a new
   `LeaveBalanceSyncServiceDep` in sequence. This avoids the "service calls another service"
   question (the caller would be the route, not a service) and needs no session-sharing precedent.
   Rejected because it forfeits atomicity: two independent `uow`/commits mean a failure in the
   second call leaves `LeaveRequest.status = approved` already committed with no corresponding
   balance change and nothing to roll it back — precisely the "failure semantics at the API
   boundary" risk the discovery left open at §12.8, and this alternative resolves it by accepting
   the inconsistent-state outcome rather than avoiding it. It would also be this codebase's first
   route to invoke two services, a separate new precedent from the one Alternative A/the chosen
   option introduces.
3. **`LeaveBalanceService` gains a method `ApprovalService` calls.** Already found unsupported by
   current repository evidence in the discovery (§8 Option B) on the basis of `ApprovalService`'s
   own "never calls another service" docstring. Not re-evaluated here beyond restating that
   conclusion, per instructions not to reopen resolved discovery debates.
4. **A new persisted ledger aggregate, or a compute-on-read model.** Already found unsupported by
   current repository evidence in the discovery (§8 Options D and E respectively). Not
   re-evaluated here.

## C. Reasons

**Atomicity is the deciding factor, and it is available today only to options that share one
`uow`.** The discovery established this as the one concrete infrastructure advantage available
without inventing anything new (§7/§8 of the discovery: `AbstractUnitOfWork` already rolls back an
entire session on any unhandled exception). Alternative 2 forfeits this outright. Alternative 1 can
only obtain it by giving a new service a second, unprecedented constructor shape (session-accepting
rather than `uow_factory`-owning). Extending `ApprovalService` obtains it directly from the
UnitOfWork contract every service already relies on, with no new DI shape anywhere.

**This choice introduces exactly one new precedent, not several.** Extending `ApprovalService`
means one service method now writes to two different tables in a single transaction — the
discovery already flagged this as this codebase's first multi-repository *write*, unavoidable under
any option that keeps the two writes atomic (§7/§11/§13 of the discovery). Alternative 1 would
introduce that same precedent *and* a session-accepting service constructor. Alternative 2 avoids
the multi-repository-write precedent but introduces a different one (first two-service API route)
and gives up atomicity entirely. Of the three, extending `ApprovalService` introduces the fewest new
architectural shapes for the one outcome (atomic dual-write) the discovery identified as achievable
without invention.

**The specific mechanism minimizes disruption to `_decide`.** Adding a `commit: bool = True`
parameter, defaulted to preserve every other call site's current behavior unchanged, is the smallest
change consistent with keeping `_decide` shared across all six approve/reject methods — it avoids
duplicating `_decide`'s pending-check/update/refresh/expunge logic inside `approve_leave_request`
just to defer the commit.

**Explicitly, per instructions: this decision introduces the repository's first service method that
writes to more than one repository/table within a single transaction.** No service in this codebase
currently does this — not `ApprovalService` today, not any CRUD service, not `ReconciliationService`
(which only reads across repositories). This is **an implementation decision made under the
architectural constraints the discovery established, not a conclusion repository evidence
compels.** The discovery (§13) found that current repository evidence rules out three of the five
originally-evaluated shapes and does not select among what remains; this decision selects one of
what remains, on the implementation-level grounds in this section — not because repository evidence
pointed here.

## D. File impact

### Guaranteed

Required regardless of how the still-open business-rule ambiguities (discovery §12.2–§12.12) are
eventually settled — these files exist because of the architecture decision made in this section,
not because of any business-rule decision:

- `services/approval.py` — `_decide` gains `commit: bool = True`; `approve_leave_request`
  constructs `LeaveBalanceRepository(uow.session)`, calls `_decide(..., commit=False)`, and defers
  `uow.commit()` until after the balance write is staged.
- `repositories/leave_balance.py` — a narrow, same-table method to locate `LeaveBalance` row(s) for
  a given `(employee_id, period_year)`; `get_by_employee` alone does not scope by year
  (`repositories/leave_balance.py:27-30`, confirmed in discovery §4).

### Possible

Will plausibly exist, but shape and content are blocked on business-rule decisions this document
does not make:

- `services/approval.py` — the actual day-count/deduction computation inside
  `approve_leave_request`, blocked on discovery §12.4 (day-count semantics) and §12.2 (row
  selection).
- `alembic/versions/` — a new migration adding a unique `(employee_id, period_year)` constraint,
  contingent on how §12.2 is resolved; not needed if row-selection is resolved a different way.
- `schemas/leave_request.py` / `api/leave_requests.py` — only if §12.9 (whether `approve` should
  return the updated balance) resolves toward a composite response; no change otherwise.
- `tests/test_approval_service.py`, `tests/test_leave_requests_api.py` — three-tier coverage of the
  new behavior, following this codebase's existing test convention (discovery §7); concrete cases
  blocked on the same business rules as the code above.

### Blocked by unresolved business rules

Not files this architecture decision can schedule, because the discovery left the underlying rule
open — listed so it is not mistaken for something this section resolves:

- Day-count computation itself (§12.4).
- Row-selection logic when zero or multiple `LeaveBalance` rows exist for an employee/year (§12.2).
- Cross-year-spanning request handling (§12.3).
- Reversal on hard-delete of an already-synchronized request (§12.6) — no reversal code is planned;
  a cancel/un-approve endpoint does not exist today and is not introduced by this decision.
- Optimistic-concurrency enforcement (§12.10) and `AuditEntityType` extension (§12.11) — both
  remain open product/architecture questions this decision does not resolve or preclude.

**Stopping here per instructions.** No production code, migrations, models, repositories, services,
APIs, or tests have been written. This section records the implementation-shape decision only.
Awaiting review before any file listed above is actually touched.

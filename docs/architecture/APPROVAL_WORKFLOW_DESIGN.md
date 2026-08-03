# PR-046 — Approval Workflow Foundation Discovery

Status: **Discovery only. No code, no migrations. Awaiting approval.**

---

## 1. Executive Summary

**Recommendation: there is no single "Approval aggregate" to build yet.** The evidence
converges on a narrower conclusion than the PR title implies: four independent entities —
`LeaveRequest`, `OvertimeRequest`, `Timesheet`, and (implicitly) `AttendanceEvent` corrections —
each already carry their own `status: String(50)` column, defaulted to `"pending"`, and each
one's own docstring/service class-doc states, verbatim or near-verbatim, *"approval workflow is
a future PR's concern, not this one's."* **This is that future PR.** Three of those four
docstrings even cite this document's future existence indirectly by the pattern they establish.

The central finding is that **"Approval" is not one thing in this codebase yet — it is three
unresolved questions wearing one name**:

1. **Where does approval *state* live?** (embedded status column — already answered, three times
   over, by precedent) — see §3, §4.
2. **Where does approval *history/decision metadata* live?** (who decided, when, why) — **no
   entity anywhere models this**, and the one candidate infrastructure piece that could
   (`AuditLog`) is unused by any business module today — see §4, §5.
3. **Where does approval *authorization* (who is allowed to decide) live?** — `RequireRole`
   exists but is used by exactly one endpoint (`RequireAdmin` in `api/roles.py`); no HR/Time
   Management endpoint is role-gated; there is no `Permission` model, only coarse role-name
   checks — see §6, §9, §10.

None of these three questions can be answered by inventing a new shared aggregate in isolation.
§3 explains why a shared `Approval` entity, a workflow engine, and a generalized state machine
are each rejected as the *data* shape. **But rejecting those three structural alternatives does
not, by itself, decide which component executes an approval decision.** An earlier draft of this
discovery recommended extending each request-shaped entity's existing service
(`LeaveRequestService`, `OvertimeRequestService`, `TimesheetService`) with `approve()`/`reject()`
methods. **That recommendation is withdrawn.** Approval introduces four concerns — authorization,
state-transition validation, audit recording, and optional event/notification dispatch — that do
not exist inside any service reviewed today, and nothing in the repository proves the existing
CRUD services are the correct place to acquire them. §10 (Service Orchestration Analysis)
evaluates the placement options directly against the evidence and finds this to be an open
architectural ambiguity, not a decided question.

The second-most load-bearing finding, inherited unchanged from all five prior discovery
documents and re-confirmed independently here: **the `User` ↔ `HrEmployee` gap still exists.**
No foreign key anywhere links the authenticated `User` (`models/user.py`) to an `HrEmployee`
row. This is more load-bearing for Approval than for any prior module, because approval
inherently requires answering "which `HrEmployee` (e.g. a manager) does this authenticated
`User` correspond to?" — and the codebase provides no way to answer that today (§7).

"Approval Workflow" itself does not appear in `docs/product/06_PRODUCT_ROADMAP.md`, continuing
the pattern already flagged for Leave, Holiday, and Timesheet before it (§2, §14).

---

## 2. Evidence Reviewed

**Time Management aggregates** (`services/api/src/eop_api/models/`): `AttendanceEvent`
(`attendance_event.py`, `core/attendance.py`), `LeaveRequest` (`leave_request.py`), `Holiday`
(`holiday.py`), `OvertimeRequest` (`overtime_request.py`), `LeaveBalance` (`leave_balance.py`),
`Timesheet` (`timesheet.py`) — models, repositories, services, and API routers for all six.

**HR**: `HrEmployee` (`hr_employee.py`), `Shift` (`shift.py`), `EmploymentType`
(`employment_type.py`), `EmploymentStatus` (`employment_status.py`), `JobGrade` (`job_grade.py`).

**Foundation**: `Base`/`BaseEntity` (`db/base.py`), mixins (`db/mixins.py`:
`UUIDMixin`/`TimestampMixin`/`AuditMixin`/`SoftDeleteMixin`/`VersionMixin`), `BaseRepository`
(`repositories/base.py`), `AbstractUnitOfWork`/`SQLAlchemyUnitOfWork` (`uow/base.py`,
`uow/sqlalchemy.py`), `FilterParams`/`SearchParams` (`schemas/search.py`), `Page`/`PaginationParams`
(`schemas/pagination.py`).

**Also directly re-verified in this discovery** (beyond what prior docs reviewed): `User`
(`models/user.py`), `Role`/`user_roles` (`models/role.py`, `models/user_role.py`),
`RoleService` (`services/role.py`), `RequireRole`/`CurrentUser`
(`dependencies/rbac.py`, `dependencies/auth.py`) — confirmed via grep that `RequireRole` is
invoked exactly once in the whole codebase (`api/roles.py:25`, `RequireAdmin`), and no
`Permission` model exists anywhere (`find -iname "*permission*"` returned nothing). `AuditLog`
(`models/audit_log.py`, `services/audit_log.py`, `core/audit.py`) — confirmed it is
infrastructure-only: `AuditLogService.record()`'s own docstring states *"Nothing in this PR calls
it yet"*, and `AuditEntityType`/`AuditAction` (the closed vocabularies it depends on) list only
`ORGANIZATION`/`PROJECT`/`EMPLOYEE`/`ASSIGNMENT`/`TASK`/`USER`/`ROLE` — no Time Management entity
is a member. `events/`, `notifications/`, `jobs/` packages (`events/base.py`,
`notifications/base.py`, `jobs/base.py`, plus their `services/event.py`/`service/notification.py`/
`services/job.py` wrappers) — confirmed via grep these are called nowhere outside their own
service modules; no business module publishes an event, sends a notification, or enqueues a job
today.

**All 24 Alembic migrations** (`alembic/versions/*.py`), in order, confirmed current head is
`0bf3c4001ca5_create_timesheets_table`. Confirmed the incremental-FK pattern (`shift_id` added to
`hr_employees` in `e7a8ed87ea45` after `Shift` landed in `c4a9d3e17f56`; `job_grade_id`/
`employment_type_id`/`employment_status_id` added the same way) and that every request-shaped
entity (`leave_requests`, `overtime_requests`, `timesheets`) landed as a standalone table with one
FK into `hr_employees`, never retroactively modifying an earlier migration.

**Previous discovery documents**: `ATTENDANCE_DESIGN.md` (PR-039), `LEAVE_DESIGN.md` (PR-040),
`HOLIDAY_CALENDAR_DESIGN.md` (PR-041), `TIMESHEET_DESIGN.md` (PR-045). No
`OVERTIME_REQUEST_DESIGN.md` or `TIME_MANAGEMENT_DOMAIN.md` exist in the repository or in
`git log --all -- docs/architecture/` — `TIMESHEET_DESIGN.md` §2 already documented this same gap
for `OvertimeRequest`/`LeaveBalance`; it is reconfirmed here rather than re-derived.

**Also reviewed**: `docs/product/06_PRODUCT_ROADMAP.md` (full file) — "Approval" appears in no
phase and not in the MVP. `docs/adr/` is empty (no architecture decision records exist to check
against). `services/api/tests/` file listing — confirmed the three-tier test pattern
(`test_<entity>_repository.py` / `test_<entity>_service.py` / `test_<entity>s_api.py`) holds for
every entity including `LeaveRequest`/`OvertimeRequest`/`Timesheet`/`AuditLog`/`EventPublisher`/
`NotificationProvider`/`JobProvider` — confirming these infrastructure pieces are tested in
isolation but not exercised by any business-entity test.

**Direct source reads** (full file, not excerpted) of every model, repository, service, and one
representative API router for `LeaveRequest`, `OvertimeRequest`, and `Timesheet` — confirmed all
three are structurally identical (see §3) down to shared docstring language.

---

## 3. Aggregate Analysis

**Question: should Approval be one shared `Approval` aggregate, embedded inside each aggregate,
aggregate-specific approval entities, a workflow engine, or something else?**

| Candidate | Verdict |
|---|---|
| One shared `Approval` aggregate (generic, referenced by any approvable entity) | Rejected |
| A workflow engine / generalized finite-state-machine abstraction | Rejected |
| Aggregate-specific approval entities (e.g. `LeaveRequestApproval`, `OvertimeRequestApproval`) | Rejected as a *new entity* — see below |
| Approval **data** (status, and any future decision metadata) embedded in each existing aggregate as columns, not a shared table | **Recommended — data shape only, see note below** |

**Scope note**: this section answers where approval *data* lives structurally (a schema
question). It does **not** answer which component *writes* that data — i.e., which service or
orchestrating component performs an approve/reject decision. An earlier draft of this document
conflated the two and concluded the latter as well; that conclusion has been withdrawn and is now
analyzed on its own, with evidence for and against each option, in **§10 (Service Orchestration
Analysis)**.

**Why not one shared `Approval` aggregate.** A shared aggregate presupposes a stable, generic
shape for "a thing that can be approved" — polymorphic association (an `approvable_type` +
`approvable_id` pair, or separate nullable FKs to each of `LeaveRequest`/`OvertimeRequest`/
`Timesheet`). **No polymorphic-association pattern exists anywhere in this codebase.** Every FK
reviewed, across all six migrations that reference `hr_employees.id`, is a concrete,
single-target foreign key — there is no precedent for a generic "references one of several
tables" column, and inventing one now would be the first instance of a pattern this codebase has
never needed. This mirrors the exact reasoning `LEAVE_DESIGN.md` §2 used to reject a
balance/ledger aggregate before an entitlement concept existed, and `TIMESHEET_DESIGN.md` §7 used
to decline a cross-aggregate query abstraction on the strength of one consumer: **do not build
shared/generic infrastructure before multiple concrete, confirmed consumers force its shape.**
Here there are three plausible consumers (`LeaveRequest`, `OvertimeRequest`, `Timesheet`), but
they already have a working, precedented shape of their own (a `status` column) that a shared
aggregate would have to either duplicate or replace — see next point.

**Why not a workflow engine / generic FSM.** No state-transition abstraction, finite-state-machine
library, or transition-table concept exists anywhere in the codebase (§8 confirms this
exhaustively). Every lifecycle-bearing entity reviewed — `Project.status`, `Task.status`, and
now `LeaveRequest.status`/`OvertimeRequest.status`/`Timesheet.status` — uses a **plain `String`
column with a default and zero transition validation**, by explicit design: each of the three
Time Management models' own docstrings states *"Storage only -- no transition validation."*
Building a workflow engine now would not extend this pattern, it would replace it — a strictly
larger and more speculative undertaking than the evidence justifies, especially since the actual
transition rules (who may approve, what states are valid, whether transitions are sequential)
are **still completely unconfirmed** — see §10, §14.

**Why not new aggregate-specific approval entities either** (e.g. a separate
`LeaveRequestApproval` row per decision). This would be the correct shape *if* approval decisions
needed a multi-row history (see §4's "aggregate-specific approval entities" analysis for
ownership) — but as a description of where approval *lives structurally*, it is a heavier
solution than the evidence currently supports. The codebase's own `status` column already
answers "what is the current approval state" for all three candidates; a separate entity would
only be justified by a *history* requirement (§4), not by the state itself.

**Recommendation, restated concretely — data shape only**: whatever decision metadata §4
confirms as required should live as columns (or a per-entity history table, §4) directly on
`LeaveRequest`, `OvertimeRequest`, and `Timesheet` — not a new shared aggregate, not a
polymorphic table, not an engine. This is additive to three existing entities, consistent with
this codebase's demonstrated preference (every prior discovery: extend by FK or by column, in a
later migration, never retrofit or merge existing tables). **This recommendation is
deliberately silent on which component writes those columns** (an existing per-entity service, a
new orchestrating service, or something else) — that question is analyzed in §10, not decided
here.

---

## 4. Ownership Analysis

**Question: who owns approval status, approval history, approver identity, approval timestamp,
and rejection reason?**

| Concern | Current owner | Recommendation |
|---|---|---|
| **Approval status** | Already owned by each entity: `LeaveRequest.status`, `OvertimeRequest.status`, `Timesheet.status` — all `String(50)`, all default `"pending"` | **No change of owner.** Each entity keeps its own `status`; this is the one piece of "approval" that already has a confirmed, working, three-times-repeated home |
| **Approval history** (a log of every decision made, not just the current one) | **Nowhere.** No entity in the codebase records more than the current `status` value; `AuditLog` exists but is unused by any business module (§2) | **Ambiguous — not decidable from the codebase.** See below |
| **Approver identity** | **Nowhere as a business-meaningful field.** `AuditMixin.updated_by` records who last wrote the row, but is explicitly documented (every prior discovery, `LEAVE_DESIGN.md` §3, `TIMESHEET_DESIGN.md` §4) as "the acting `User`, not necessarily the `HrEmployee`" — a generic audit column, not an approval-specific one | Would belong on whichever entity owns the *decision act*, once §6's `User`↔`HrEmployee` gap is resolved — see §14 |
| **Approval timestamp** | **Nowhere as a business-meaningful field.** `updated_at` (via `TimestampMixin`) changes on *any* write, not specifically on a decision | Same as approver identity — downstream of §7, and of whether a decision needs its own timestamp distinct from generic `updated_at` |
| **Rejection reason** | **Nowhere.** `LeaveRequest.reason`/`OvertimeRequest.reason` are the *requester's* free-text justification for asking, not a *decision-maker's* justification for rejecting — conflating the two would overload one column with two authors' text | Would be a new field, if approver-authored rejection reasons are confirmed as required — not proposed here as certain, see §14 |

**Should these belong to `LeaveRequest`/`OvertimeRequest`/`Timesheet`, another aggregate, or
nowhere yet?**

- **Status**: belongs to each entity itself. Settled by existing precedent (three times over),
  not an open question.
- **History, approver identity, timestamp, rejection reason**: **this discovery cannot determine
  a single correct owner from the codebase, and explicitly declines to guess.** Two
  evidence-consistent placements exist, and neither is confirmed:
  1. **Additional columns directly on each entity** (`approved_by`, `approved_at`,
     `rejection_reason`) — the simpler option, consistent with how every other business-meaningful
     fact in this codebase lives as a column on the entity it describes (mirrors `AuditMixin`'s own
     shape, just business-named instead of generic). This captures only the *most recent* decision,
     not a history of overturned/re-decided ones.
  2. **A per-entity decision log, analogous to `AuditLog` but entity-specific** (e.g. a
     `LeaveRequestDecision` row per approve/reject action) — captures full history (a request
     rejected, then resubmitted and approved, keeps both decisions), but this would be the first
     "history table" pattern in the codebase for anything other than the generic, currently-unused
     `AuditLog`. Whether to extend `AuditLog` itself (adding Time Management entity types to
     `AuditEntityType`, §2) or build entity-specific decision tables is a **second, nested
     ambiguity** under this one — see §14.

**No existing entity is a plausible owner other than the three named ones.** `LeaveBalance` was
evaluated and rejected: it holds computed totals (`allocated_days`/`used_days`/`remaining_days`),
not decisions, and its own docstring explicitly defers "synchronization with `LeaveRequest`" as a
future concern — it is a consumer of an approved `LeaveRequest`, not a place to store the approval
itself. `Holiday` and `AttendanceEvent` have no request/decision shape at all (`Holiday` has no
`status` column by design, `HOLIDAY_CALENDAR_DESIGN.md` §5; `AttendanceEvent` is a raw fact, not an
ask).

---

## 5. Workflow Analysis

**Question: does the codebase contain any precedent for state transitions, a workflow engine, a
finite-state machine, an audit trail, an approval chain, or role-based approval?**

Answered exhaustively, one at a time, per the instructions to state explicitly if none exists:

- **State transitions**: **none exist.** Every `status` column reviewed (`Project.status`,
  `Task.status`, `LeaveRequest.status`, `OvertimeRequest.status`, `Timesheet.status`) is a plain
  `String` with a default value and no transition logic anywhere in its service. No service method
  branches on a status's *current* value before changing it to a new one.
- **Workflow engine**: **does not exist.** No package, class, or dependency implementing a
  workflow/orchestration engine was found anywhere in `services/api/src/eop_api` or its
  dependencies.
- **Finite-state machine**: **does not exist.** No transition-table, state-graph, or FSM library
  usage found.
- **Audit trail**: **exists as infrastructure, unused by any business module.** `AuditLog`
  (`models/audit_log.py`) is a real, working, append-only entity — "The repository/service layer
  never updates or deletes rows here" — with a `record()` entry point on `AuditLogService` built
  exactly for this purpose. But its own docstring states plainly: *"Nothing in this PR calls it
  yet -- it is infrastructure for later adoption."* Confirmed via grep: no `LeaveRequestService`/
  `OvertimeRequestService`/`TimesheetService`/`AttendanceEventService` call it. This is the single
  closest existing precedent to "approval history," and it is currently dormant.
- **Approval chain** (multi-step/multi-level approval): **does not exist**, and there is no
  data shape anywhere (self-referential FK, ordered sequence, hierarchy table) that resembles one.
  The closest structural analogy in the codebase is `HrEmployee.manager_id` (a self-referential
  FK) — but it models *current org-chart position*, not a decision sequence, and
  `HrEmployeeService` explicitly does no cycle detection or hierarchy validation beyond rejecting
  direct self-management. It is not a workflow precedent, only the nearest hierarchical shape.
- **Role-based approval**: **does not exist.** `RequireRole` (`dependencies/rbac.py`) is real,
  working code — but it is invoked in exactly one place in the entire codebase:
  `RequireAdmin = Annotated[CurrentUser, Depends(RequireRole("admin"))]` in `api/roles.py:25`,
  used to gate role-management endpoints themselves. No HR, Attendance, Leave, Overtime, or
  Timesheet endpoint uses it. There is also no `Permission` model — authorization here is a single
  coarse role-name string check, not a granular permission system.

**Conclusion: if none exist, explicitly state that.** None of state transitions, a workflow
engine, a finite-state machine, an active audit trail, an approval chain, or role-based approval
exist anywhere in this codebase today. The one piece of adjacent infrastructure (`AuditLog`) is
present but dormant, and the one piece of adjacent authorization infrastructure (`RequireRole`) is
present but exercised by a single, unrelated endpoint. **Approval Workflow, if built, would be the
first business feature in this codebase to use either.**

---

## 6. User Identity Analysis

**Question: does the codebase provide any reliable way to map `User` → `HrEmployee`?**

**No.** Directly re-verified in this discovery (not merely inherited from prior docs): `User`
(`models/user.py`) has exactly four business columns (`email`, `password_hash`, `full_name`,
`is_active`) plus a many-to-many `roles` relationship through `user_roles`. **No foreign key,
nullable or otherwise, references `hr_employees.id`.** A grep across every model file for any
`HrEmployee`-referencing FK on `User` confirms zero results. `HrEmployee` itself has no
`user_id`/`account_id` column either — the relationship is absent in both directions.

**Architectural implications, specific to Approval** (this is the single most consequential
open gap for this PR, more so than for any prior discovery):

- **"Who is the approver?" cannot be resolved from an authenticated request alone.** If a manager
  logs in (as a `User`) to approve a direct report's `LeaveRequest`, the system has no way to
  determine which `HrEmployee` row that `User` corresponds to — and therefore no way to check
  "is this `User` actually this employee's manager" (`HrEmployee.manager_id`) before allowing the
  decision. Every request-shaped entity's own approver-identity field (§4) is downstream of this
  gap, not just loosely related to it.
- **`RequireRole`/`RequireAdmin` cannot substitute for this.** Role-gating answers "does this
  `User` hold the `admin` (or a future `manager`/`approver`) role" — a flat, global permission —
  not "is this `User` *this specific employee's* approver." Org-chart-scoped authorization
  (manager-of-requester) and role-based authorization (holds an `approver` role) are two different
  mechanisms, and the codebase currently has infrastructure for neither wired to Time Management,
  and no `User`↔`HrEmployee` bridge to make the org-chart version possible even if built.
  `TIMESHEET_DESIGN.md` §8 already noted `RequireRole` "exists but is used by no
  HR/Attendance/Leave/Overtime endpoint" — Approval is the first feature for which this absence is
  a hard blocker rather than a background observation.
- **`AuditMixin.created_by`/`updated_by` cannot substitute either.** These are `User.id` values
  (whoever authenticated the write), not `HrEmployee.id` values. Using them as "the approver" would
  conflate the acting `User` identity with the business-meaningful `HrEmployee` identity the
  approval decision is actually about — the same conflation every prior discovery flagged as
  unresolved, now directly blocking a concrete feature rather than a hypothetical one.

**This gap must be resolved (i.e., some `User`↔`HrEmployee` linkage must exist) before
role-scoped or manager-scoped approval authorization can be implemented at all.** It does not
block the narrower "any authenticated user can call the approve endpoint" version of Approval
(§9, §10), but that narrower version provides no real authorization boundary — see §13.

---

## 7. API Boundary

**Question: should approval be a CRUD update, action endpoints, an event, a command, or something
else?**

| Candidate | Verdict | Evidence |
|---|---|---|
| Generic `PUT` with a `status` field | Rejected as the sole mechanism | This is exactly what all three entities already support today (`PUT /hr/leave-requests/{id}`, etc., accepting `LeaveRequestUpdate.status`) — and it is exactly the mechanism `LEAVE_DESIGN.md` §12.10 and `TIMESHEET_DESIGN.md` §9 both explicitly left unresolved rather than endorsed, precisely because it lets a client set *any* string into `status` with no validation, no side effects (approver/timestamp not recorded), and no distinction between "editing my request" and "deciding someone else's request" |
| Dedicated action endpoints (`POST /hr/leave-requests/{id}/approve`, `/reject`) | **Recommended** | No endpoint of this shape exists yet anywhere in the codebase — this would be a new pattern, not a copy of an existing one — but it is the only option that lets §4's approver/timestamp/reason fields be populated deterministically by the server (from `CurrentUser`/request body) rather than trusted from arbitrary client-supplied `PUT` payload, and the only option that can be independently authorized (§6) separately from the generic edit path |
| Domain event (publish `LeaveRequestApproved`, consumers react) | Not recommended as the *primary* mechanism, but plausible as a *side effect* | `EventPublisher`/`EventService` exist and are generic enough to support this, but are called by zero business modules today (§2, §5) — using events as the sole approval mechanism would be inventing the first real consumer of dormant infrastructure for the most speculative part of this design. More defensible: whichever component §10 confirms as the decision-orchestrator *could* publish an event after committing, for future consumers (Notifications, §12) to react to — but this is additive, not a replacement for a real endpoint, and not required for this PR |
| Command (an explicit `ApproveLeaveRequestCommand` object, command-bus dispatch) | Rejected | No command-bus, command-dispatch, or CQRS-style command object exists anywhere in the codebase. Every write path reviewed is a direct service method call from an API route. Introducing a command abstraction now would be new infrastructure with no precedent and no second confirmed need — the same class of premature-generalization this codebase's own prior discoveries have repeatedly declined (`TIMESHEET_DESIGN.md` §7) |

**Recommendation, concretely**: `POST /hr/leave-requests/{id}/approve`, `POST
/hr/leave-requests/{id}/reject` (and the equivalent pair for `OvertimeRequest`, `Timesheet`),
each taking `CurrentUser` (for whatever approver-identity resolution §6 eventually allows) and,
for reject, a request body carrying the rejection reason (§4). This is additive — the existing
`PUT`/`GET`/`POST`/`DELETE` routes are unaffected — following the exact `APIRouter` /
`CurrentUser` / service-injected-via-`Depends` shape every reviewed router already uses. **Which
concrete component the route's `Depends`-injected service resolves to** — an existing per-entity
service extended with `approve`/`reject` methods, a new dedicated orchestration service, or
something else — is not decided by this API-shape recommendation; it is analyzed separately in
§10 and left as an open ambiguity there.

**Explicitly not proposed**: any endpoint shape presupposing §4's or §6's unresolved questions —
e.g. `GET /hr/leave-requests/{id}/history` (presupposes the history-ownership ambiguity),
anything role-gated (presupposes §6's `User`↔`HrEmployee` resolution), or a generic
`/hr/approvals` collection endpoint (presupposes the shared-aggregate model already rejected in
§3).

---

## 8. Repository Boundary

**Question: should repositories own approval logic? If not, why?**

**No.** This is not a new conclusion specific to Approval — it is the direct, unbroken
continuation of the repository contract every single repository in this codebase already
observes. `BaseRepository`'s own docstring (`repositories/base.py:14-19`) states it provides
"typed CRUD access" and "never commits: callers own the transaction boundary." Every concrete
repository reviewed (`LeaveRequestRepository`, `OvertimeRequestRepository`,
`TimesheetRepository`, and by extension every other repository in the codebase) does exactly two
things beyond inherited CRUD: declares `SEARCHABLE_FIELDS`/`FILTERABLE_FIELDS`, and overrides
`paginate()` purely to supply those as defaults. **None branches on business state, raises a
business exception, or enforces an invariant** — every one of those responsibilities is drawn, by
uniform precedent, at the service layer instead (§9). *Which* service is a separate question,
analyzed in §10 — it does not change this conclusion about repositories either way.

Approval decision logic — validating that a transition is allowed, resolving who is permitted to
decide, populating approver/timestamp fields — is exactly the class of "business-rule branching"
every prior discovery (`ATTENDANCE_DESIGN.md` §7, `LEAVE_DESIGN.md` §8, `HOLIDAY_CALENDAR_DESIGN.md`
§4, `TIMESHEET_DESIGN.md` §6) has already, independently, kept out of the repository layer. There
is no reason evidenced anywhere in this codebase for Approval to be the exception. A repository
method like `LeaveRequestRepository.approve(...)` would be the first repository method in the
codebase to do more than persist-and-return — it would violate the single, consistent contract
every other repository upholds.

**What repositories should gain, mechanically**: nothing beyond what a plain field update already
requires. If approver/timestamp/reason become confirmed columns (§4), the existing
`BaseRepository.update()` (arbitrary `**values` passed through to `setattr`) already supports
writing them — no new repository capability is needed, only new columns.

---

## 9. Service Boundary

**Question: where do approval rules belong? Does Approval become the first true domain service?**

**Settled by uniform precedent, independent of which specific component ends up implementing
it**: approval business-rule validation belongs at the *service* layer, not the repository layer
(§8) and not the API layer. Every service reviewed (`LeaveRequestService`,
`OvertimeRequestService`, `TimesheetService`, and by extension every other service in the
codebase) owns its own transaction boundary via `uow_factory` and performs its own
existence/structural validation (`EmployeeNotFoundError`, `InvalidLeaveDateRangeError`, etc.)
rather than delegating either to the repository or the API route. Whatever component ends up
owning approval decisions should own its own transaction boundary and raise typed, local
exceptions the same way — that much is settled and does not depend on the answer to the question
below.

**Not settled, and a prior conclusion of this document is withdrawn here**: *which* specific
service or component performs the decision. An earlier draft recommended extending each of
`LeaveRequestService`/`OvertimeRequestService`/`TimesheetService` directly with `approve()`/
`reject()` methods, reasoning that since a shared `Approval` aggregate had already been rejected
(§3), the existing per-entity services were the only place left. **That reasoning does not hold
up on its own**: rejecting a shared *aggregate* is a data-shape conclusion (§3); it says nothing
about where *decision-making behavior* — authorization, state-transition validation, audit
recording, and optional event/notification dispatch — should be orchestrated. None of those four
concerns exists inside any service reviewed today (§5), and the repository provides no example of
a service acquiring all four at once. **This question is analyzed directly, with evidence for and
against each placement, in §10 (Service Orchestration Analysis) — it is not resolved here.**

**Is Approval the first true domain service?** In one specific sense, **yes**, regardless of how
§10 resolves — this would be the first service-layer logic in the codebase that:
- Validates a **state transition** (e.g. only `pending → approved`/`pending → rejected` is legal),
  something no reviewed service does today (every current `status` write is unconditional, per
  §5).
- Potentially requires **authorization beyond authentication** (§6) — every reviewed service today
  trusts `CurrentUser` only as "a valid, logged-in identity," never as "an identity with a specific
  relationship to the data being changed."
- Potentially **coordinates with dormant infrastructure** (`AuditLog` for history, `EventPublisher`
  for notifying consumers) that no service today actually calls (§5, §12).

Whether this added depth is acquired by three existing service classes or by a new one is exactly
what §10 evaluates.

**Must NOT belong in whichever component §10 settles on** (this boundary holds regardless of the
orchestration-placement outcome, since it mirrors every prior discovery's own "must not"
boundary, not a boundary specific to one placement option):
- Payroll computation triggered by an approval (e.g. auto-generating a payroll entry on
  `Timesheet` approval) — a downstream consumer's concern, per `TIMESHEET_DESIGN.md` §11.
- Notification dispatch on decision — plausible future addition (§12) via the existing
  `NotificationService`, but not required to implement the decision itself, and not proposed as
  certain here.
- Attendance/Leave/Overtime reconciliation triggered by approval — same reconciliation boundary
  every prior document already drew (read-time join, not a write-time side effect).
- Any generalized "can this role approve this entity type" rule engine — presupposes the
  role-based-approval infrastructure explicitly confirmed absent in §5.

---

## 10. Service Orchestration Analysis

**Question: where should approval behavior — authorization, state-transition validation, audit
recording, and optional event/notification dispatch — actually be orchestrated: by extending the
existing aggregate services, by a dedicated Approval domain service, by another orchestration
component, or is this left unresolved?**

This question is deliberately analyzed separately from §3 (Aggregate Analysis) and §9 (Service
Boundary), because neither settles it. §3 establishes that there is no shared `Approval` table.
§9 establishes that whatever performs the decision belongs at the service layer, not the
repository or API layer. **Neither establishes *which* service.** An earlier draft of this
document treated "no shared aggregate" as sufficient grounds to default to the three existing
per-entity services; that inference is withdrawn (§1, §3, §9) because it skips over four concerns
— authorization, state-transition validation, audit, and optional event/notification dispatch —
that have no precedent inside *any* service reviewed, existing or otherwise.

### Option A: Extend each existing aggregate service (`LeaveRequestService`, `OvertimeRequestService`, `TimesheetService`)

**Supporting evidence:**
- Every one of the three services already owns its own transaction boundary (`uow_factory`) and
  already performs its own business-rule validation (existence checks, date/time-range checks) —
  structurally, an `approve()`/`reject()` method would slot into the same class shape (§9).
- Path of least structural change: no new class, no new dependency-injection wiring, no new
  test-tier pattern to invent — `test_leave_request_service.py`/`test_overtime_request_service.py`/
  `test_timesheet_service.py` already exist for all three.
- Consistent with this codebase's general preference for additive, in-place extension over new
  abstractions (every prior discovery: extend by column/FK in a later migration, not a new table,
  unless a second concrete need forces it).

**Missing evidence:**
- **No service reviewed in this codebase currently performs authorization beyond
  authentication.** Every service trusts whatever `CurrentUser` the API layer already validated;
  none checks a relationship between the acting user and the entity being modified, and none
  consults a role or permission (§5, §6). Extending `LeaveRequestService.approve()` to do so would
  be a *new kind* of responsibility for that class, not a mechanical continuation of what it
  already does.
- **No service reviewed validates a state transition.** `LeaveRequestService.update()` today
  accepts any `status` string unconditionally (§5, §12). An `approve()`/`reject()` method that
  *does* validate transitions would coexist, in the same class, with an `update()` method that
  does not — the repository offers no example of one service class enforcing a rule on one method
  while leaving a structurally similar sibling method unconstrained.
- **No service reviewed calls `AuditLogService`, `EventPublisher`, or `NotificationService`.** If
  any of these become part of "approval" (§4, §11), `LeaveRequestService` would be the first
  service in the codebase to depend on a *second* service (beyond a same-layer repository) from
  within its own methods — a materially different dependency shape than anything currently in
  `services/leave_request.py`, `services/overtime_request.py`, or `services/timesheet.py`.

**Trade-offs:** Cheapest to build, but concentrates four new categories of responsibility
(authorization, transition validation, audit, event/notification orchestration) into three
classes whose entire existing design center is "validate structural invariants and persist" — a
narrower job than the one this option would give them. Absent a shared helper, three separate
classes would each independently reimplement the same authorization/audit logic — and introducing
that shared helper reopens the "shared component" question this option was meant to avoid.

### Option B: A dedicated `ApprovalService` (or similarly named orchestration service)

**Supporting evidence:**
- Centralizes the four new concerns in one place, avoiding the duplication risk flagged in
  Option A.
- The codebase already has precedent for a service that exists to coordinate cross-cutting
  infrastructure rather than own a single entity's CRUD: `AuditLogService` is exactly this shape
  (owns no "primary" business entity of its own beyond the log; exists to be called *by* other
  modules, per its own docstring), and `EventService`/`NotificationService`/`JobService` are the
  same shape (thin orchestration wrappers around a provider abstraction, called by other code, per
  §2/§5).

**Missing evidence:**
- **No precedent exists for a service that reaches into *another* entity's own service or
  repository to mutate that entity's state.** `AuditLogService`/`EventService`/
  `NotificationService` are called *by* other modules; none of them reaches into `LeaveRequest`/
  `OvertimeRequest`/`Timesheet` and changes a `status` column. An `ApprovalService` that did so
  would be the first service in the codebase whose job is to orchestrate *another* entity's
  lifecycle rather than its own — a new category of component, not an instance of an existing one.
- **No precedent resolves which underlying repository/table such a service would write to.** This
  is the write-side counterpart of the exact problem `TIMESHEET_DESIGN.md` §7 identified for
  cross-aggregate *reads* — every repository reviewed is scoped to exactly one model, and nothing
  in the codebase shows a service composing writes across multiple entities' repositories.
  `TIMESHEET_DESIGN.md` §7 left its read-side version of this question explicitly unresolved
  rather than inventing a shared abstraction on one consumer's evidence; the same caution applies
  here, arguably more strongly, since an incorrect write is higher-stakes than an incorrect read.
- **Nothing in the codebase confirms whether `ApprovalService` would use
  `LeaveRequestRepository`/`OvertimeRequestRepository`/`TimesheetRepository` directly (bypassing
  each entity's own service and its existing validation) or would call into
  `LeaveRequestService`/`OvertimeRequestService`/`TimesheetService` as an external client would**
  (an inversion of the codebase's usual "a service owns its own repository" shape, since
  `ApprovalService` would then be a caller of three services it does not own). Both are
  plausible; neither is evidenced.

**Trade-offs:** Better separation of the four new concerns, and arguably the closest fit to the
"second confirmed consumer" standard this codebase's own discovery methodology has applied before
generalizing (§3 cites `TIMESHEET_DESIGN.md` §7's version of this standard) — here there would be
three consumers (`LeaveRequest`, `OvertimeRequest`, `Timesheet`) from the outset, a stronger case
than Timesheet's own single-consumer read-side question. But it remains a new category of
component with no direct precedent for its core behavior (mutating another entity's row from
outside that entity's own service), and it reopens exactly the repository-access question
`TIMESHEET_DESIGN.md` left unresolved rather than closing it.

### Option C: Another orchestration component (e.g. a policy object, a command/decision handler distinct from both "service" and "repository")

**Supporting evidence:** None found. No component of this shape — a policy object, a command
handler, a decision-table evaluator, an authorization layer beyond `RequireRole` — exists anywhere
in `services/api/src/eop_api`. `RequireRole` (`dependencies/rbac.py`) is the closest adjacent
concept, but it is a FastAPI dependency that gates *route access* before a service method is
called; it does not participate in what a service does once invoked, and is not evidence for a
new in-service-layer orchestration component.

**Missing evidence:** Everything. There is no precedent to evaluate for or against a shape that
has never appeared in this codebase. Proposing a concrete version of it now would mean inventing
architectural vocabulary this discovery has no repository evidence to justify.

**Trade-offs:** Cannot be assessed without inventing structure first. Not recommended to pursue
further without a product/architecture decision made outside this discovery.

### Option D: Leave the decision unresolved for this PR

**Supporting evidence:** The evidence genuinely is insufficient to choose between Option A and
Option B: Option A has real structural fit but asks three existing classes to acquire four
responsibilities they have never had; Option B has a partial precedent (`AuditLogService`'s
shape) but no precedent for the specific cross-entity write-orchestration behavior it would need;
Option C has no precedent at all.

**Missing evidence:** Not applicable — this option's premise is precisely that the evidence to
choose between A and B does not yet exist.

**Trade-offs:** Delays implementation until either (a) a product decision fixes the authorization
model (§6, §13 — which materially affects whether Option A's "just add a method" framing is even
adequate), or (b) a second concrete need for cross-entity write orchestration appears elsewhere in
the codebase, giving Option B the "second consumer" evidence `TIMESHEET_DESIGN.md` §7 and this
document's own §3 both treat as the bar for justifying a new shared component.

**Conclusion: this is an open architectural ambiguity, not a resolved design.** The evidence rules
out Option C (no precedent anywhere, would require inventing structure from nothing). It does
**not** clearly favor Option A over Option B, or vice versa: Option A is cheaper and structurally
closer to what already exists; Option B better separates the four new concerns and has a partial
(not full) precedent in `AuditLogService`'s shape. **This document does not pick between them.**
This is carried forward into §14 (Ambiguities) and §15 (Implementation Readiness) as the central
unresolved question of this discovery, superseding the recommendation this document previously
made and has now withdrawn.

---

## 11. Migration Considerations

**No migration is proposed by this discovery** (constraints of this PR). The following is
**likely future schema evolution**, not implementation:

- **Additive columns on `leave_requests`, `overtime_requests`, `timesheets`** (contingent on §4
  resolving in favor of "columns on the entity," not a separate history table): plausibly
  `approved_by` (UUID, nullable, FK candidate — to `users.id` or `hr_employees.id`, itself
  contingent on §6), `approved_at` (timestamptz, nullable), `rejection_reason` (String, nullable).
  Following the exact incremental-migration precedent already used three times
  (`shift_id`/`job_grade_id`/`employment_type_id`/`employment_status_id` each added to
  `hr_employees` in a *separate*, later migration after the referenced table existed) — these
  would each be a standalone `op.add_column` migration per table, chained off the current head
  (`0bf3c4001ca5`), not a retroactive edit to the three tables' original `create_table` migrations.
- **Alternatively, a new decision-history table per entity** (contingent on §4 resolving in favor
  of history over columns): e.g. `leave_request_decisions` (`id`, `leave_request_id` FK, `decided_by`,
  `decided_at`, `decision` (approved/rejected), `reason`) — mirroring `AuditLog`'s own shape
  (append-only, no update/delete) but scoped per entity rather than generic. This would be a
  **new table per approvable entity**, following the "standalone table, FK-only" migration
  philosophy every prior discovery has used, not a modification of the existing three tables at
  all (beyond, possibly, still needing the `status` column update itself).
- **Or, extending `AuditLog` itself**: adding `LEAVE_REQUEST`/`OVERTIME_REQUEST`/`TIMESHEET` members
  to `AuditEntityType` (`core/audit.py`) and `APPROVE`/`REJECT` to `AuditAction` — the smallest
  possible schema footprint (no new table, no new columns beyond `status` transitions themselves),
  but only captures a generic `details: JSONB` blob per decision, not strongly-typed
  approver/timestamp/reason columns queryable without JSON parsing.
- **No FK from any new approval structure to a generic "approvable" concept.** Consistent with §3:
  whichever of the above is chosen, it attaches to one specific table (`leave_requests` /
  `overtime_requests` / `timesheets`), never a polymorphic reference.
- **`User`↔`HrEmployee` linkage** (§6): if resolved by adding a column, the most consistent
  placement per existing precedent would be a nullable `user_id` FK added to `hr_employees` (or a
  nullable `hr_employee_id` FK added to `users`) in its own standalone migration — but *which*
  direction, and even *whether* this is Approval's problem to solve versus a prerequisite HR/Auth
  module change, is itself unresolved (§14) and explicitly not decided here.

**Which of the three schema shapes above is correct cannot be determined from the codebase.**
This is a central migration-level ambiguity, carried into §14/§15 alongside the separate,
equally-unresolved question of who orchestrates the write (§10).

---

## 12. Future Compatibility

- **Payroll**: would read `status = APPROVED` `Timesheet`/`LeaveRequest`/`OvertimeRequest` rows
  to compute pay — exactly the consumption pattern every prior discovery already anticipated
  (`ATTENDANCE_DESIGN.md` §9, `LEAVE_DESIGN.md` §10, `TIMESHEET_DESIGN.md` §11). Approval doesn't
  change this: Payroll still reads the `status` column, whichever of §11's schema shapes is chosen
  for history/approver metadata doesn't block this read.
- **Timesheet**: already the most cross-cutting existing consumer (`TIMESHEET_DESIGN.md` §7);
  once Timesheet itself gains approval (this PR's own scope), its own downstream consumers
  (Payroll, Analytics) gain a genuine "approved" signal to filter on, where today they would only
  have an unvalidated `status` string.
- **Attendance reconciliation**: unaffected structurally — the reconciliation boundary (a read-time
  join on `employee_id` + date range, no FK) already established by every prior discovery is
  untouched by adding approval columns/history to the *other* side of that join.
- **Notifications**: the clearest new opportunity. `NotificationProvider`/`NotificationService`
  already exist, fully built, currently unused (§2, §5) — an approval decision (`approve`/`reject`)
  is exactly the kind of discrete business event a "notify the requester" feature would key off of.
  This is additive and optional, not required for this PR, but is the most natural first real
  consumer of that dormant infrastructure.
- **Audit**: the second-clearest new opportunity, for the same reason — `AuditLog`/
  `AuditLogService` are built and unused (§2, §5). Whether Approval's own history requirement (§4)
  is satisfied *by* extending `AuditLog`, or needs its own separate mechanism, is the open
  question in §11 — but either way, Approval is the first plausible real consumer for this
  dormant piece of infrastructure too.
- **Reporting**: would aggregate approval rates/turnaround time across employees/departments —
  reachable via the same `HrEmployee` relationship graph (`department_id`/`location_id`/`team_id`)
  every prior discovery has already established as sufficient for this purpose, provided
  approver/timestamp metadata (§4) actually gets recorded somewhere queryable.

---

## 13. Risks

Identified, not solved:

- **Building a role-gated `/approve` endpoint with no way to scope "approver of what."** Even if
  `RequireRole`/a new `approver` role is wired up, without resolving §6 (`User`↔`HrEmployee`), the
  best available authorization is "any `User` holding the `approver` role can approve *any*
  employee's request" — a flat, unscoped permission, not "this employee's manager can approve
  this employee's request." Shipping the narrower, unscoped version first is a real option, but is
  a materially weaker authorization boundary than "approval" implies in ordinary usage, and should
  be a conscious tradeoff, not an accidental one.
- **`status`'s current "no transition validation" design directly conflicts with Approval's basic
  premise.** Every one of the three services today allows `status` to be set to any string via
  `PUT`. Adding dedicated `approve`/`reject` actions without *also* closing off (or at least
  ignoring) the existing generic `PUT ".../status"` path means two competing ways to change
  approval state exist simultaneously — one validated, one not. Whether the generic `PUT` should
  stop accepting `status` changes once dedicated actions exist is unresolved (§14).
- **History vs. columns-only is unresolved and has real data-loss implications.** If
  approver/timestamp/reason are added as plain columns (§11's first option), a
  rejected-then-resubmitted-then-approved cycle overwrites the rejection's record entirely —
  there would be no way to answer "was this ever rejected before being approved?" Whether that
  matters is a product question this discovery cannot answer.
- **`AuditLog` reuse is tempting but underspecified.** Extending `AuditEntityType`/`AuditAction`
  (§11's third option) is the lowest-footprint schema change, but `details: JSONB` is untyped —
  querying "show me all rejections with reason X" would require JSON-path queries rather than a
  plain indexed column, a real cost if approval history is queried often.
- **Every systemic gap already flagged in prior discoveries compounds here.** Soft-delete columns
  present but unhonored by `BaseRepository.delete()`; `VersionMixin.version` present but never
  checked for optimistic-concurrency — both are especially relevant to Approval, where two
  concurrent decisions on the same request (an approve and a reject racing) would not be detected
  today, silently letting the second write win.
- **No roadmap grounding.** "Approval"/"Approval Workflow" appears nowhere in
  `docs/product/06_PRODUCT_ROADMAP.md` — the fourth consecutive Time Management concept (after
  Leave, Holiday, Timesheet) with no documented product intent to validate against.

---

## 14. Ambiguities

Per instructions, these are listed, not guessed at. Implementation should not proceed until they
are resolved:

1. **History vs. columns-only for approver identity/timestamp/reason (§4, §11).** Is only the
   *current* decision needed (plain columns on each entity), or is a full decision history
   required (a new per-entity table, or an extension of the existing but dormant `AuditLog`)? No
   precedent in the codebase favors one over the other — this determines the migration shape
   (§11) and constrains, but does not by itself resolve, the service-orchestration question in
   §10.
2. **`User` ↔ `HrEmployee` linkage (§6).** Confirmed absent in both directions. Must this be
   resolved before Approval ships (blocking manager-scoped or self-service authorization), or can
   a first version ship with only flat role-based gating (any `User` with an `approver` role may
   decide anything)? Not decidable from the codebase; this is a product/security decision, not an
   architectural one this discovery can make.
3. **Authorization model: role-based, org-chart-based (manager-of-requester), or both?**
   `RequireRole` exists but is coarse (single role-name string, no `Permission` model, §6). Whether
   "approver" should be a new role name, a relationship to the requester's `HrEmployee.manager_id`,
   or some combination is unconfirmed — no precedent for either shape exists in the codebase today.
4. **Valid `status` values and whether transitions are sequence-enforced.** `LEAVE_DESIGN.md`
   §12.3 and `TIMESHEET_DESIGN.md` §13.2 already left this open for their own entities; it is now
   the direct subject of this PR rather than a deferred concern, and still has no answer. Is
   `pending → approved` / `pending → rejected` the complete transition set, or are there
   intermediate states (e.g. `submitted`, `in_review`) or terminal-state re-transitions (e.g.
   `rejected → pending` on resubmission, or `approved → cancelled`)?
5. **Should the existing generic `PUT .../{id}` endpoints continue to accept arbitrary `status`
   writes once dedicated `approve`/`reject` actions exist (§7, §13)?** Leaving both open creates
   two competing, inconsistently-validated paths to the same field. No precedent in the codebase
   (no entity has ever gained a second, more-restrictive write path after already having a fully
   open one) to resolve this either way.
6. **Is a single approval decision sufficient, or is multi-level/chained approval required** (e.g.
   manager approval, then HR approval)? Confirmed no approval-chain precedent exists anywhere
   (§5). If required, this changes both §3's data-shape recommendation (a chain plausibly needs
   its own ordered-row shape, not a single embedded status/columns) and §10's orchestration
   analysis (a chain plausibly needs a dedicated coordinating component regardless of which option
   is chosen there).
7. **Does `AttendanceEvent` correction/approval belong in this PR's scope at all?**
   `ATTENDANCE_DESIGN.md` §11.4 flagged correction-approval as an unresolved future concern for
   Attendance specifically, but `AttendanceEvent` has no `status` column today (only `event_type`/
   `source`) — extending it to be "approvable" would be a larger structural change (adding a
   lifecycle field to an entity explicitly designed as an append-mostly event stream) than adding
   decision actions to the three entities that already have `status`. Whether Attendance is in
   scope for this PR or a later one is not resolved here.
8. **Should approval publish a domain event (§7, §12) as part of this PR, or is that strictly a
   later, optional addition?** `EventPublisher` exists and is unused; using it here would be the
   first real adoption of dormant infrastructure, which is a bigger step than the minimum needed
   to satisfy "approval exists."
9. **Retention/concurrency**: same systemic gaps every prior discovery flagged (soft-delete
   unhonored, `version` unchecked, §13) — whether Approval should be the PR that finally addresses
   optimistic-concurrency checking (given two racing decisions is a real, approval-specific risk,
   unlike for most other entities) is unresolved.
10. **Product intent.** "Approval"/"Approval Workflow" is named nowhere in
    `docs/product/06_PRODUCT_ROADMAP.md`. Is this confirmed, prioritized scope, or exploratory work
    ahead of product scoping — the same question already raised, unresolved, for Leave, Holiday,
    and Timesheet before it?
11. **Service-orchestration placement (§10).** Should approval behavior be added to the three
    existing per-entity services (Option A), centralized in a new dedicated orchestration service
    (Option B), placed in some other, not-yet-precedented component (Option C, ruled out), or is
    this genuinely undecidable from the repository as it stands today (Option D)? **This is the
    central unresolved architectural question in this discovery**, superseding what an earlier
    draft of this document treated as a settled recommendation. Resolving it requires either a
    product/architecture decision on the authorization model (#2, #3 above) or a second concrete
    need for cross-entity write orchestration elsewhere in the codebase — neither of which this
    discovery can manufacture from the evidence available.

---

## 15. Implementation Readiness

**Not ready — and the primary blocker is not which service owns approval.** An earlier draft of
this document framed the central blocker as "which existing service should get `approve()`/
`reject()` methods." **That framing is withdrawn.** Choosing a service is not the hard part; the
hard part, unsupported by any precedent in this repository, is this:

> The codebase has no precedent for domain behavior that simultaneously coordinates
> authorization, state transition, audit, and optional event publishing.

This is categorically different from the CRUD service behavior every existing service in this
codebase already performs. `LeaveRequestService`, `OvertimeRequestService`, and
`TimesheetService` each: own a transaction boundary, validate that a referenced `HrEmployee`
exists, validate one structural invariant (`end_date >= start_date` / `end_time > start_time`),
and expunge-on-return. That is the entire responsibility surface of every service reviewed in
this codebase (§2, §9). Approval asks for four responsibilities with **zero combined precedent**:
deciding *who* may act (authorization, §6 — no service checks anything beyond "is this `User`
authenticated"), validating *that a transition is legal* (§5 — no service validates `status`
transitions at all today), *recording that a decision happened* in a way that outlives the
current row (§4 — the only candidate, `AuditLog`, is real but dormant), and *optionally notifying
other systems* (§11 — `EventPublisher`/`NotificationService` are real but dormant). No service in
this codebase does even two of these four today, let alone all four together. Whether that
combined behavior belongs inside the three existing entity services, inside a new dedicated
service, or somewhere else is exactly the question §10 evaluates and explicitly declines to
resolve, for lack of evidence either way.

Unlike `HOLIDAY_CALENDAR_DESIGN.md` (which found zero precedent to build on) or
`TIMESHEET_DESIGN.md` (which found a single narrow architectural blocker), this discovery finds
**abundant precedent for the state itself** (three identical `status` columns, three identical
service docstrings pointing at this exact future PR) but **zero precedent for the behavior that
turns a status column into an actual approval workflow**. The gap is not "there is nothing to
extend" (Holiday's problem) or "the read path is architecturally unclear" (Timesheet's problem)
— it is **"the codebase has no example, anywhere, of a domain operation that owns authorization,
state-transition validation, audit, and optional event/notification dispatch at once, so there is
no shape to extend and no second-consumer evidence to generalize from."**

Concrete decisions required before implementation can begin:

1. **Service-orchestration placement (§10, §14.11)** — the central blocker. Whether authorization,
   state-transition validation, audit recording, and optional event/notification dispatch are
   added to the three existing per-entity services, centralized in a new dedicated service, or
   placed elsewhere must be decided before `LeaveRequestService`/`OvertimeRequestService`/
   `TimesheetService` (or any new class) can be designed at all — every other decision below is
   downstream of, or entangled with, this one.
2. **History vs. columns-only (§14.1)** — determines the migration shape and, jointly with #1,
   the shape of whatever method signature ends up recording a decision.
3. **`User` ↔ `HrEmployee` linkage and authorization model (§14.2, §14.3)** — determines whether
   the first version of Approval has any real authorization boundary beyond "any authenticated
   user," which is a product/security decision this discovery cannot make on its own, and which
   directly shapes what Option A vs. Option B in §10 would even need to implement.
4. **`status` value set and transition rules (§14.4)** — determines what `approve`/`reject` (and
   possibly other actions) actually validate.
5. **Whether the generic `PUT` status-write path is closed off once actions exist (§14.5)** —
   determines whether this PR also touches the three existing `PUT` endpoints, not just adds new
   ones.
6. **Single-decision vs. multi-level approval (§14.6)** — determines whether §3's "columns on the
   existing entity" data-shape recommendation holds, and whether §10's orchestration options need
   revisiting in favor of a shape that coordinates an ordered chain rather than a single decision.
7. **Whether `AttendanceEvent` is in scope (§14.7)** — determines whether this PR's surface is
   three entities or four, and whether a fourth entity needs a new `status` column it doesn't have
   today.
8. **Confirmation that no roadmap/product decision supersedes this discovery (§14.10)**, given
   "Approval Workflow" appears nowhere in `docs/product/06_PRODUCT_ROADMAP.md` — the fourth
   consecutive Time Management concept with this gap.

**Stopping here per instructions.** No aggregate has been implemented, no migration has been
written, no code has been changed. Awaiting direction on the ambiguities above — particularly
§10/§14.11 (service-orchestration placement, the central open question) and §14.2/§14.3 (the
`User`↔`HrEmployee` gap and authorization model, which constrains what any orchestration option
in §10 would actually need to do) — before proceeding.

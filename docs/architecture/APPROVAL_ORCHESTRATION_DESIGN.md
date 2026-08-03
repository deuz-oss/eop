# PR-047 — Approval Workflow Orchestration (Discovery)

Status: **Discovery only. No code, no migrations. Awaiting review.**

---

## 1. Executive Summary

PR-046 built the Approval *foundation* — `approved_by`/`approved_at`/`rejection_reason` columns
on `leave_requests`, `overtime_requests`, `timesheets`, and three symmetric pairs of
`POST .../approve` / `POST .../reject` endpoints that currently do nothing but return `501`. It
deliberately left one question open: **which component executes the approve/reject decision?**
`docs/architecture/APPROVAL_WORKFLOW_DESIGN.md` §10 analyzed this question in detail and
explicitly declined to answer it, concluding the evidence did not favor Option A (extend the
three existing per-entity services) over Option B (a dedicated `ApprovalService`) or vice versa.

This document re-verifies that evidence independently (§2) and finds the codebase **unchanged**
in every respect relevant to that question — no service has gained an `approve`/`reject` method,
no cross-service call pattern has appeared anywhere, `AuditLog`/`EventPublisher`/
`NotificationProvider` remain uncalled by any business module. Re-deriving the same analysis from
scratch does not change PR-046's conclusion, and this document reaches the same one:
**the repository does not contain enough evidence to choose between Option A (extend the existing
per-entity services) and Option B (a dedicated `ApprovalService`).** A prior draft of this document
attempted to break that tie by weighting the fact that three symmetric consumers
(`LeaveRequest`, `OvertimeRequest`, `Timesheet`) exist simultaneously. **That reasoning is
withdrawn.** The number of future or current consumers a hypothetical component would serve is not
evidence of what the repository's existing code does — it is a claim about anticipated reuse, and
this discovery is scoped to what the codebase already contains, not to what would be convenient to
build. Withdrawing it removes the only asymmetry this document had found between Option A and
Option B; with it gone, the two options are exactly as evenly unsupported as PR-046 already found
them to be.

**One factual observation survives, correctly scoped as description rather than as grounds for a
recommendation**: every existing cross-aggregate access in this codebase — five instances, across
four services — reaches into another entity through its **Repository**, never its **Service**
(`HrEmployeeRepository` from `LeaveRequestService`/`OvertimeRequestService`/`TimesheetService`/
`LeaveBalanceService`; `ShiftRepository` from `AttendanceEventService`). No service anywhere
instantiates or calls another service. This is repository evidence about an existing pattern, and
is reported as such in §4. It says nothing about whether Option A or Option B is correct — it only
describes what a cross-aggregate *repository* reach looks like in this codebase today, should one
ever be built, under either option or neither.

**No architectural recommendation is made.** §5 restates Option A and Option B's evidence without
the withdrawn reuse argument; neither is favored. §14 states this explicitly rather than picking
one.

**Four prerequisite ambiguities remain fully open regardless of which orchestration option is
eventually chosen**, and are not resolved by this document: history-vs-columns for decision
metadata, the `User`↔`HrEmployee` identity gap, the authorization model (role-based vs.
org-chart-based), and the valid `status` transition set. These are restated in §12–§14, unchanged
from PR-046, because no evidence bearing on them has appeared since.

---

## 2. Evidence Reviewed

**Independently re-read in full for this document** (not merely cited from PR-046):

- **Infrastructure**: `uow/base.py`, `uow/sqlalchemy.py`, `repositories/base.py`,
  `services/audit_log.py`, `core/audit.py`, `events/base.py`, `events/memory_publisher.py`,
  `services/event.py`, `notifications/base.py`, `notifications/memory_provider.py`,
  `services/notification.py`, `db/mixins.py`, `db/base.py`, `models/audit_log.py`.
- **Aggregate services (all six named in scope), full file**: `services/leave_request.py`,
  `services/overtime_request.py`, `services/timesheet.py`, `services/attendance_event.py`,
  `services/holiday.py`, `services/leave_balance.py`. Confirmed `LeaveRequestService`,
  `OvertimeRequestService`, `TimesheetService` are structurally identical down to shared docstring
  language; `HolidayService`/`LeaveBalanceService` follow the same shape without a `status` column
  (Holiday) or without approval columns at all (LeaveBalance, `AttendanceEventService`).
- **Aggregate models**: `models/leave_request.py`, `models/overtime_request.py`,
  `models/timesheet.py`, `models/attendance_event.py`, `models/holiday.py`,
  `models/leave_balance.py`, `models/hr_employee.py`, `models/user.py`, `models/role.py`.
- **API routers**: `api/leave_requests.py`, `api/overtime_requests.py`, `api/timesheets.py` (full
  files) — confirmed all three carry an identical pair of `approve`/`reject` stub routes, each
  returning `501` with an identical docstring pointing at the (now superseded)
  `APPROVAL_WORKFLOW_DESIGN.md` §10.
- **Auth/authz/DI**: `dependencies/auth.py`, `dependencies/rbac.py`, `core/request_context.py`,
  `core/security.py`, `db/dependencies.py`, `api/roles.py`, `services/role.py`, `main.py`.
- **Migration**: `alembic/versions/20260803_1900-f4a1c9e6b2d7_add_approval_fields_to_leave_requests_.py`
  — confirmed it adds identical `approved_by`/`approved_at`/`rejection_reason` columns plus one
  `RESTRICT` FK to `users.id` to all three tables in one migration (the one departure from the
  "one column per migration" precedent PR-046 §11 anticipated — see §12).
- **Prior discovery documents, full files**: `APPROVAL_WORKFLOW_DESIGN.md` (PR-046),
  `TIMESHEET_DESIGN.md` (PR-045, §7 in particular — the cross-aggregate query-orchestration
  ambiguity, structurally the read-side twin of this document's write-side question).
  `ATTENDANCE_DESIGN.md`, `LEAVE_DESIGN.md`, `HOLIDAY_CALENDAR_DESIGN.md` were not re-read in full;
  their relevant conclusions are already fully synthesized into `APPROVAL_WORKFLOW_DESIGN.md` §2,
  and no evidence suggests re-deriving them independently would change anything below.
  `TIME_MANAGEMENT_DOMAIN.md` and `OVERTIME_REQUEST_DESIGN.md` do not exist in the repository —
  confirmed by `Glob` (no match) — matching `APPROVAL_WORKFLOW_DESIGN.md` §2's prior confirmation.
- **Fresh greps run for this document** (not inherited claims): `RequireRole|RequireAdmin` across
  `src/eop_api` — five matches, all in `api/roles.py` or its own definition; no HR/Time-Management
  route is role-gated. `*permission*` filename search — zero results. Service-to-service call
  search (`grep "def approve\|def reject\|\.approve(\|\.reject("` across all of `src/eop_api`) —
  zero hits outside the three API stub routers; no service implements either method anywhere.
  Test suite (`tests/`) grepped for `approve|reject` — only the three `*_api.py`/`*_service.py`/
  `*_repository.py` files for the three approval-bearing entities matched, and none contains a
  test exercising an `approve`/`reject` method (confirmed by absence of any such test failing —
  no such method exists to test).

---

## 3. Existing Service Architecture

**Every service reviewed — all six in scope, and by extension every other service in the
codebase — is a CRUD/application service, not a domain service in the DDD sense, and none
orchestrates.** Concretely, each of `LeaveRequestService`, `OvertimeRequestService`,
`TimesheetService`, `AttendanceEventService`, `HolidayService`, `LeaveBalanceService`:

- Owns its own transaction boundary via a `uow_factory: Callable[[], SQLAlchemyUnitOfWork]`
  constructor parameter, defaulting to `SQLAlchemyUnitOfWork`.
- Performs exactly `create`/`get`/`list`/`list_paginated`/`update`/`delete`, plus at most one
  narrow, bounded pre-condition check per method (an FK-existence check against exactly one other
  repository, or a structural invariant like `end_date >= start_date`).
- Raises small, local, typed exceptions (`EmployeeNotFoundError`, `InvalidLeaveDateRangeError`,
  etc.) rather than delegating validation to the repository or the API layer.
- Expunges returned entities from the UoW session before it closes (rollback-on-exit semantics),
  and refreshes before expunging on `update` (documented `MissingGreenlet`/`onupdate` rationale,
  identical wording in every service).
- **Never** calls another service. **Never** calls `AuditLogService`, `EventService`, or
  `NotificationService`. **Never** performs authorization beyond what the API-layer `CurrentUser`
  dependency already enforces (i.e., "is this a valid authenticated token," never "does this user
  have a business relationship to this row").

This is uniform across all six aggregates named in scope. `RoleService` (reviewed as a seventh,
representative "coordinating" service — it manages a many-to-many `User`↔`Role` relationship) is
the same shape: owns its own UoW, reaches into `UserRepository` for an existence check exactly the
way the six named services reach into `HrEmployeeRepository`, and never calls another service.

**Conclusion**: services in this codebase are uniformly **CRUD/application services with one
narrow cross-entity existence check**, not domain services encoding business rules beyond
structural validation, and not orchestration services coordinating multiple side effects
(audit, events, notifications, authorization). No service in the codebase today is any of those
three heavier things. Approval — whichever component ends up owning it — would be the first.

---

## 4. Cross-Aggregate Analysis

**Question: does any service today coordinate multiple repositories, audit, notification, event
publishing, or authorization?**

**Repositories — yes, narrowly, five times, in one consistent shape:**

| Service | Reaches into | Purpose |
|---|---|---|
| `LeaveRequestService` | `HrEmployeeRepository` | existence check on `employee_id` |
| `OvertimeRequestService` | `HrEmployeeRepository` | existence check on `employee_id` |
| `TimesheetService` | `HrEmployeeRepository` | existence check on `employee_id` |
| `LeaveBalanceService` | `HrEmployeeRepository` | existence check on `employee_id` |
| `AttendanceEventService` | `HrEmployeeRepository`, `ShiftRepository` | existence checks on `employee_id`, `shift_id` |

Every instance is: (a) a **repository**, never a service; (b) a **boolean existence check**
(`.exists(id)`), never a read of business data or a write; (c) within the same UoW-scoped
transaction as the primary entity's own write. **No service reads business *data* from a second
repository and combines it with its own** (this is exactly the gap `TIMESHEET_DESIGN.md` §7
identified on the read side — period-total computation across five aggregates — and left
unresolved). **No service writes to a second repository at all.** Approval, under either Option A
or Option B, would be the first write to cross this boundary.

**Audit, notification, event publishing, authorization — no, confirmed by direct search:**

- `AuditLogService.record()` — zero callers outside its own module and its own test file. Its own
  docstring: *"Nothing in this PR calls it yet — it is infrastructure for later adoption."*
  `AuditEntityType` (`core/audit.py`) enumerates seven members (`ORGANIZATION`, `PROJECT`,
  `EMPLOYEE`, `ASSIGNMENT`, `TASK`, `USER`, `ROLE`) — **no Time Management entity is a member**,
  and `AuditAction` enumerates only `CREATE`/`UPDATE`/`DELETE` — **no `APPROVE`/`REJECT` action
  exists**. Both enums carry a "will grow" docstring (`AuditAction`: *"add more as future modules
  need them"*), which is evidence the extension is anticipated, not evidence it has happened.
- `EventService.publish()`/`EventPublisher.publish()` — zero callers outside their own modules and
  tests. `InMemoryEventPublisher` has no subscriber mechanism of any kind; publishing today has
  exactly one observable effect (the event is appended to an in-process list), regardless of
  caller.
- `NotificationService.send()`/`NotificationProvider.send()` — same: zero callers, `dataclass`
  request shape exists (`NotificationRequest(recipient, subject, body)`), no transport behind it.
- **Authorization**: `RequireRole` (`dependencies/rbac.py`) exists and is exercised exactly once
  in the entire codebase — `RequireAdmin = Annotated[CurrentUser, Depends(RequireRole("admin"))]`
  in `api/roles.py`, gating role-management endpoints themselves. No HR, Attendance, Leave,
  Overtime, or Timesheet endpoint is role-gated. `main.py:86-88` carries a `TODO` explicitly
  deferring role-gating for Locations "once the platform defines administrative roles for master
  data" — direct evidence that role-gating beyond `RequireAdmin` is a known, not-yet-executed
  intention, not an oversight specific to Approval.

**Explicit statement per instructions**: **no service today coordinates multiple repositories in
a write, audit, notification, event publishing, or authorization beyond authentication.** The one
existing cross-aggregate coordination pattern (repository-level existence checks) is narrower than
any of Approval's four new concerns (§8 of `APPROVAL_WORKFLOW_DESIGN.md`) individually, let alone
combined.

---

## 5. Candidate Architectures

**Neither option below has repository precedent for the core behavior Approval needs.** Option A
would be the first service in this codebase to acquire authorization, state-transition validation,
and (potentially) a dependency on a second service, none of which any existing service does.
Option B would be the first component of any kind in this codebase to reach into another entity's
storage to mutate it, which no `AuditLogService`/`EventService`/`NotificationService`-shaped
component (the closest analog) does today. **The repository does not contain an orchestration
service, a domain service, cross-aggregate write orchestration, or any service-to-service
coordination anywhere.** Both options are evaluated below on that shared footing; neither is
favored by what follows.

### Option A — Approval remains inside each aggregate service

**Supporting evidence**: Every aggregate service already owns a `uow_factory`-scoped transaction
and its own typed exceptions — structurally, `async def approve(self, id, approver_id) -> Entity`
slots into the same class shape as `create`/`update`. Zero new dependency-injection wiring: routers
already resolve `LeaveRequestServiceDep`/etc. Zero new test-tier pattern: `test_leave_request_
service.py` et al. already exist. Matches this codebase's general preference for additive,
in-place extension (every prior aggregate discovery: add a column or FK in a later migration,
not a new component, absent a second forcing need). **This is evidence about how Option A would
fit mechanically if built — it is not evidence that this codebase has ever built the kind of
behavior (authorization, transition validation) Option A would be asked to hold.**

**Contradicting evidence**: No service reviewed performs authorization beyond authentication (§3,
§4) — an `approve()` method would be the first. No service reviewed validates a *state transition*
(current services accept any structural input unconditionally; `LeaveRequestService.update()`
today writes any `status` string with zero transition logic) — `approve()`/`reject()` enforcing
`pending → approved`/`pending → rejected` would coexist, in the same class, with an `update()`
method enforcing nothing on the same column. No service reviewed calls a second service — if audit
or notification dispatch become part of approval, the owning service would be the first in the
codebase with a same-class dependency on another service, a materially different shape than its
current single-repository dependency.

**Advantages**: cheapest to build; no new class; reuses existing DI and test scaffolding;
authorization/audit/event logic, if added, lives next to the data it concerns.

**Disadvantages**: three near-identical implementations of the same authorization/transition/audit
logic (or a shared helper that reopens the "shared component" question this option exists to
avoid); concentrates four unprecedented responsibilities into three classes whose entire design
center today is "validate structural invariants and persist."

### Option B — Dedicated `ApprovalService` orchestrates existing aggregate services

**Supporting evidence**: Centralizes the four new concerns once instead of three times. Partial
precedent for the *shape* of a cross-cutting, non-owning service: `AuditLogService`/`EventService`/
`NotificationService` are each a thin service with no "primary" entity of its own, that exists to
be called *by* other code (per their own docstrings). **This is the only repository-grounded
supporting evidence for Option B.** That `LeaveRequest`, `OvertimeRequest`, and `Timesheet` would
all be consumers of such a service is a fact about anticipated future reuse, not a fact about
code that exists today, and is **not treated as supporting evidence here** — a prior draft of this
document did so and that reasoning has been withdrawn (§1). The repository's own prior
discoveries (`LEAVE_DESIGN.md` §2, `TIMESHEET_DESIGN.md` §7) applied an "evidence of current
duplication, not anticipated reuse" standard before generalizing; anticipated reuse for a
component that does not yet exist does not meet that standard.

**Contradicting evidence**: No precedent exists anywhere for a service that reaches into another
entity's *storage* to mutate it — `AuditLogService`/`EventService`/`NotificationService` are called
by other modules but never call back into `LeaveRequest`/`OvertimeRequest`/`Timesheet`'s own
storage. §4's evidence narrows, but does not eliminate, this gap: the established "reach into
another entity's Repository for a bounded purpose" pattern (five instances) shows *how* such a
reach would look if built (direct `Repository` access, not `Service` access — no service anywhere
calls another service, so `ApprovalService` calling `LeaveRequestService` would itself be
unprecedented in a different way), but no existing instance of that pattern *writes* through the
reached-into repository — every one of the five is `.exists(id)`, read-only. A write of this shape
remains new territory even under the best-fitting precedent available, and this codebase has no
example anywhere of a service whose job is to orchestrate another entity's lifecycle rather than
its own.

**Advantages**: would centralize a single implementation of authorization/transition-validation/
audit/event logic instead of three, *if built*. This is a structural property of the option, not
evidence the repository favors building it — see §1's withdrawal of the reuse argument.

**Disadvantages**: new component category with no full precedent for its central behavior
(mutating another entity's row from outside that entity's own service); the repository-vs-service
access question is narrowed by §4 (direct `Repository` access is the only evidenced shape) but not
the deeper question of whether such a component should exist at all, which has no precedent either
way.

### Option C — Application service above aggregate services

**Supporting evidence**: none. No component of this shape — a use-case/application-service layer
sitting generically above per-entity services, distinct from both a "service" and a "repository" —
exists anywhere in `services/api/src/eop_api`. Every service reviewed talks directly to its own
repository (and, narrowly, to one other repository); none is itself called by another service, and
nothing in the codebase resembles a use-case orchestration layer, a CQRS handler, or an
application/domain-service split. This is a structurally broader claim than Option B (which posits
one new *entity-scoped* orchestrator) — Option C posits a new *architectural layer*, for which
there is categorically zero evidence in this repository, in either direction.

**Contradicting evidence**: not applicable — there is nothing to contradict; the absence is total.

**Advantages**: cannot be assessed without inventing structure first.

**Disadvantages**: would introduce an entirely new layer with no repository precedent to anchor
its shape, its lifecycle, or its relationship to the DI system already in place
(`db/dependencies.py`, per-router `get_*_service()` factories). Rejected on the same
"do not invent architectural vocabulary the codebase gives no evidence for" ground
`APPROVAL_WORKFLOW_DESIGN.md` §10 already used to reject its own Option C (a policy/command
object) — this document's Option C is a different shape but fails on identical grounds: zero
precedent, nothing to evaluate against.

### Option D — Another architecture justified by repository evidence

No fourth shape is justified by evidence beyond what Options A–C already cover. The one
evidence-grounded refinement this document contributes is not a fourth top-level option but a
**constraint on Option B**, established in §4: if Option B is chosen, `ApprovalService` should
reach `LeaveRequestRepository`/`OvertimeRequestRepository`/`TimesheetRepository` directly, not
their Services — matching the codebase's only established cross-aggregate access pattern rather
than inventing a service-to-service call with no precedent anywhere.

**Verdict**: Option C is eliminated — zero evidence in either direction, would require inventing
an unprecedented layer. **Between Option A and Option B, repository evidence does not favor
either one, and this document does not recommend one over the other.** Option A has structural
fit (it slots into an existing class shape) but no precedent for the behaviors it would need to
acquire (authorization, transition validation, a same-class dependency on a second service).
Option B has a partial precedent for its *shape* (`AuditLogService`'s "thin, called-by-others"
pattern) but no precedent at all for its *central behavior* (mutating another entity's row from
outside that entity's own service). Neither gap is smaller than the other in a way the repository
itself settles. This document explicitly does not pick between them — see §14.

---

## 6. Event Analysis

**Question: should Approval become the first production consumer of `EventPublisher`?**

**Repository evidence is insufficient to require this, and insufficient to rule it out —
marked unresolved on the merits, with the reasoning made explicit rather than left silent.**
`EventPublisher`/`InMemoryEventPublisher` are generic and already support the shape an
`ApprovalDecided`-style event would need (`publish(name=..., payload=...)`). But:

- **No consumer of any kind exists anywhere in the codebase.** `InMemoryEventPublisher` has no
  subscriber mechanism — publishing an event today changes nothing observable except appending to
  an in-process list nothing reads. Approval publishing an event would not, by itself, cause any
  other behavior to occur; the value would be entirely speculative until a consumer exists.
- **No service in the codebase performs any action after `uow.commit()`** other than
  `refresh`/`expunge`-then-return. A post-commit `EventService.publish()` call would be new
  *control-flow* territory (a side effect after the transaction boundary closes), not just a new
  *caller* of existing infrastructure.
- Nothing in the repository indicates a broker-backed publisher is planned, scheduled, or even
  named as a target (no config, no dependency, no `TODO` referencing one).

**Conclusion**: technically capable, not evidenced as required. If a centralizing component
(Option B) is what ultimately commits a decision, publishing an event afterward would be a
low-cost, structurally clean addition (the interface already exists and fits) — but the same is
true if Option A is chosen instead, since `EventService` is equally reachable from any service.
This document does not recommend event publishing as part of a first implementation either way,
because no consumer would react to it and no precedent exists for a service acting after its own
commit. Left as an explicit future option, not a requirement, and not a factor in §5's
orchestration-placement question.

---

## 7. Notification Analysis

**Question: do notifications belong in Approval?**

**Not as part of the decision logic itself — no repository evidence supports notifications
gating, blocking, or being required for an approve/reject transition to succeed.** Whether they
belong as an *optional post-commit side effect* is the same unresolved question as §6, for the
same reason (no service acts after its own commit today) plus one additional piece of concrete,
positive evidence: `HrEmployee.email: Mapped[str]` is a real, populated column, so
`NotificationRequest(recipient=hr_employee.email, ...)` is structurally reachable without new
schema — a decision-recipient exists in the data model today, unlike, e.g., a phone/SMS channel.

**Not speculating beyond that**: whether the *product* wants a requester notified on decision is
not a question this discovery can answer from code — `docs/product/06_PRODUCT_ROADMAP.md` does
not mention Approval or notifications on decision anywhere (confirmed in
`APPROVAL_WORKFLOW_DESIGN.md` §2, unchanged). **Marked unresolved**: notifications are structurally
easy to bolt on once an orchestrating component exists and commits a decision, but nothing in the
repository confirms they are in scope for a first implementation.

---

## 8. Audit Analysis

**Question: should Approval own audit creation?**

**Partially resolvable from evidence; partially not.**

**Resolvable**: `AuditLog`/`AuditLogService`/`AuditEntityType`/`AuditAction` are explicitly
designed for incremental growth — `AuditAction`'s own docstring: *"Only actions currently required
by callers are listed here; add more as future modules need them."* Extending `AuditEntityType`
with `LEAVE_REQUEST`/`OVERTIME_REQUEST`/`TIMESHEET` and `AuditAction` with `APPROVE`/`REJECT` is a
small, additive, precedented change to a closed vocabulary explicitly built to be extended — this
is a mechanically low-risk step regardless of which orchestration option is chosen, and regardless
of whether it turns out to be the *primary* record of a decision or a secondary one.

**Not resolvable**: whether `AuditLog.details` (an untyped `JSONB` blob) is an adequate primary
record of "who decided, when, why" for querying purposes, or whether a dedicated per-entity
decision table is needed instead, is exactly `APPROVAL_WORKFLOW_DESIGN.md` §4/§11's still-open
"history vs. columns" ambiguity. No evidence has appeared since PR-046 to resolve it — no query
pattern, no reporting requirement, no roadmap entry specifies how approval history would be read
back. **Marked unresolved, unchanged from PR-046.**

**Conclusion**: Approval should be *capable* of writing to `AuditLog` (the vocabulary extension is
cheap and evidence-supported), but this document does not conclude `AuditLog` should be the *sole*
or *primary* store of decision metadata — that remains an open product/architecture question.

---

## 9. User Identity

**Question: how should approver identity flow through the system? What are the gaps?**

Re-verified directly, not merely cited:

- **Authentication → `CurrentUser` works correctly and is not a gap.** `dependencies/auth.py`
  resolves a bearer token to a `User` row via `AuthService`, binds `user.id` into
  `core/request_context.py`'s `ContextVar`-based request-scoped identity, and exposes it as
  `CurrentUser` for every router to depend on. This part of the identity chain is solid,
  end-to-end, and already used by all three approval-bearing routers' stub endpoints.
- **Gap 1 — no `User`↔`HrEmployee` link in either direction.** `User` (`models/user.py`) has
  exactly `email`, `password_hash`, `full_name`, `is_active`, plus a `roles` many-to-many. No FK to
  `hr_employees`. `HrEmployee` (`models/hr_employee.py`) has FKs to `Organization`, `Department`,
  `Position`, `Team`, `Location`, `JobGrade`, `EmploymentType`, `EmploymentStatus`, `Shift`, and a
  self-referential `manager_id` — **no `user_id` column.** Confirmed by direct file read of both
  models; the relationship is absent in both directions, exactly as `APPROVAL_WORKFLOW_DESIGN.md`
  §6 found. This blocks answering "which `HrEmployee` is this authenticated `User`" — and by
  extension, "is this `User` this specific employee's manager" — from the data model as it stands.
- **Gap 2 — `RequireRole` is real but functionally unused for this domain.** Confirmed by fresh
  grep: exactly one invocation site (`RequireAdmin` in `api/roles.py`), gating role-management
  endpoints only. No `approver`, `manager`, or similar role concept exists. Using `RequireRole` for
  Approval today would mean a single flat, global permission ("holds `approver`"), not "is this
  user *this employee's* approver" — the org-chart-scoped version is blocked by Gap 1 regardless.
- **Gap 3 — no `Permission` model.** Confirmed by filename search (`*permission*` → zero results).
  Authorization in this codebase is coarse role-name string matching only; there is no finer-grained
  mechanism to fall back on.
- **Gap 4 — `AuditMixin.created_by`/`updated_by` cannot substitute for approver identity.** These
  are `User.id` values (whoever authenticated the write) on every `BaseEntity`, populated
  generically, not specifically on a decision. Using them as "the approver" would conflate the
  acting `User` with the business-meaningful `HrEmployee` the decision concerns — the same
  conflation flagged, unresolved, in every prior discovery.

**Conclusion, unchanged from PR-046**: the authenticated-identity chain (`CurrentUser`) is solid
and requires no new infrastructure to consume in an `approve`/`reject` handler. What is missing is
entirely on the *authorization* side — resolving "which `HrEmployee` does this `User` correspond
to" is a prerequisite for any authorization model stronger than "any authenticated user may decide
any request," and nothing in the repository indicates this is scheduled to be resolved by a
specific upcoming change.

---

## 10. API Boundary

**Question: do `POST .../approve` and `POST .../reject` remain the correct public contract?**

**Yes — re-affirmed, not merely inherited.** These are not proposed; they already exist, in code,
symmetrically, on all three entities (`api/leave_requests.py:140-165`,
`api/overtime_requests.py:142-167`, `api/timesheets.py`, each verified directly), each currently
returning `501` with a docstring reserving the shape pending this exact orchestration decision.
Nothing found in this discovery contradicts `APPROVAL_WORKFLOW_DESIGN.md` §7's original reasoning
for this shape over the alternatives it considered and rejected (generic `PUT .../status` — allows
arbitrary client-supplied status with no server-controlled approver/timestamp; a domain-event-only
mechanism — no consumer exists to react, and nothing else in the codebase treats an event as the
primary write path; a command-bus object — no command-dispatch abstraction exists anywhere).

**Still open, unchanged from PR-046 §14.5**: whether the existing generic `PUT
/hr/leave-requests/{id}` (etc.) should continue accepting arbitrary `status` writes once the
dedicated `approve`/`reject` actions are wired up. Today it does (`LeaveRequestUpdate.status` is a
plain, unconstrained `str | None` field, confirmed in `schemas/leave_request.py`), meaning two
competing write paths to the same column would coexist once `approve`/`reject` are implemented —
one validated, one not. **No evidence resolves this**; it is a design decision for the
implementation PR, not something this discovery can settle from current code, since no precedent
exists anywhere in the codebase for an entity gaining a second, more-restrictive write path after
already shipping a fully open one.

**Conclusion**: the API contract (`POST .../approve`, `POST .../reject`) is correct and does not
need to change. The orchestration question (§5) is about what these routes call, not their shape.

---

## 11. Future Compatibility

- **Payroll**: reads `status = approved` rows on `LeaveRequest`/`OvertimeRequest`/`Timesheet` to
  compute pay. Unaffected by which orchestration option is chosen — Payroll consumes the `status`
  column's final value, not the mechanism that set it. Whichever of §8's audit shapes is chosen
  does not block this read either.
- **Attendance Reconciliation**: the reconciliation boundary already established by every prior
  discovery (a read-time join on `employee_id` + date range, no FK) is untouched by adding
  orchestration on the *other* side of that join. Not affected by this document's recommendation.
- **Analytics**: would aggregate approval turnaround/rates, reachable via the existing
  `HrEmployee` relationship graph (`department_id`/`team_id`/`location_id`), *provided*
  approver/timestamp metadata is actually recorded somewhere queryable — directly downstream of
  §8's still-open history-vs-columns ambiguity, not of the orchestration-placement question.
- **Notifications**: the clearest new opportunity for dormant infrastructure (§7), additive and
  optional, not blocking any orchestration option.
- **Workflow expansion / multi-level approval**: **no precedent exists anywhere in the codebase**
  for an approval chain, an ordered decision sequence, or any hierarchy-aware transition logic.
  `HrEmployee.manager_id` is the nearest structural analog (a self-referential FK) but models
  current org position, not a decision sequence, and `HrEmployeeService` does no cycle detection
  beyond rejecting direct self-management. How well Option A vs. Option B would accommodate a
  future multi-level chain is not evaluated here — that would again be reasoning from anticipated
  future reuse rather than from what the repository contains today, the same reasoning §1 withdrew
  for the orchestration-placement question itself. Nothing in
  `docs/product/06_PRODUCT_ROADMAP.md` names multi-level approval as planned.

---

## 12. Risks

- **Both options carry an unprecedented-behavior risk, not just one.** Choosing Option B commits
  to a write pattern with no precedent anywhere (a service mutating another entity's row via that
  entity's own repository). Choosing Option A commits three existing, narrowly-scoped CRUD
  services to acquire authorization and transition-validation responsibilities they have never had,
  with no precedent for how that coexists with those same services' still-unvalidated `update()`
  method on the same column. Neither risk is smaller than the other by repository evidence alone
  (§5); resolving this is an architecture decision for the implementation PR, not something this
  discovery can settle.
- **Neither option resolves authorization.** Whichever component is chosen, it inherits the full
  §9 gap (`User`↔`HrEmployee`) unresolved — shipping either option today means shipping "any
  authenticated user may approve any request," a materially weaker boundary than "approval"
  ordinarily implies, unless that gap is closed first or a flat role-based gate is consciously
  accepted as an interim state.
- **The dual-write-path risk (§10) is unaffected by the orchestration decision.** Whether Option A
  or B is chosen, the existing unrestricted `PUT .../{id}` `status` field remains a second,
  unvalidated way to reach the same column unless separately closed off.
- **Concurrency**: `VersionMixin.version` exists on every `BaseEntity` but is never checked
  (`BaseRepository.update()` does plain `setattr` + flush, no optimistic-concurrency guard). Two
  concurrent decisions on the same request (an approve and a reject racing) would not be detected
  today under either orchestration option — this is a pre-existing, codebase-wide gap, not
  specific to the option chosen here, but especially consequential for Approval.
- **Migration precedent partially broken already**: PR-046's migration added identical columns to
  all three tables in a single migration file, rather than three separate ones — a minor departure
  from the strict "one migration per table" precedent `APPROVAL_WORKFLOW_DESIGN.md` §11
  anticipated. Not a functional risk, but future migrations for this feature should not assume the
  "always separate" precedent is absolute.

---

## 13. Ambiguities

Unresolved by this document, listed rather than guessed at — implementation should not proceed
until these are addressed, regardless of which orchestration option (§5) is selected:

1. **History vs. columns-only** for approver identity/timestamp/reason (§8). No precedent favors
   either shape; determines both the migration design and whether `AuditLog` extension (§8) is
   sufficient on its own.
2. **`User`↔`HrEmployee` linkage** (§9). Confirmed absent in both directions. Blocks any
   authorization model stronger than flat role-gating or "any authenticated user."
3. **Authorization model**: role-based, org-chart-based (manager-of-requester), or both (§9). No
   precedent for either shape exists in the codebase.
4. **Valid `status` transition set**: is `pending → approved`/`pending → rejected` complete, or are
   there intermediate/terminal-reentry states (`submitted`, `rejected → pending` on resubmission)?
   No service anywhere validates a transition today (§3), so there is no precedent to extend.
5. **Whether the generic `PUT .../{id}` status write path is closed off** once dedicated actions
   exist (§10). No precedent for an entity gaining a more-restrictive second write path after
   shipping an open one.
6. **Single-decision vs. multi-level approval** (§11). No chain precedent exists anywhere. If
   required, revisits both the data shape (§8) and the orchestration-placement question (§5); this
   document does not assume a chain is required, and does not treat it as evidence favoring either
   option.
7. **Whether `AttendanceEvent` correction/approval is in this feature's scope.** `AttendanceEvent`
   has no `status` column today (only `event_type`/`source`); adding one would be a larger
   structural change than extending the three entities that already have `status`. Not resolved
   here, matching `APPROVAL_WORKFLOW_DESIGN.md` §14.7's identical open item.
8. **Product intent.** "Approval"/"Approval Workflow" is named nowhere in
   `docs/product/06_PRODUCT_ROADMAP.md`, continuing the same gap flagged for every prior Time
   Management discovery.

---

## 14. Recommendation

**Orchestration placement (§5): no architectural recommendation is made.** Repository evidence is
currently insufficient to distinguish between Option A (extend the existing per-entity services)
and Option B (a dedicated `ApprovalService`). Option A has structural fit but no precedent for the
authorization/transition-validation behavior it would need to acquire; Option B has a partial
precedent for its shape but no precedent anywhere for its central behavior (a service mutating
another entity's row from outside that entity's own service). Neither gap is resolved by anything
in this repository, and — per §1 — the number of aggregates that would eventually consume either
option is not treated as evidence for choosing between them. **This discovery intentionally
leaves the orchestration decision unresolved.** Making that decision is an architecture choice for
the implementation PR, informed by product requirements (particularly the authorization model,
Ambiguity 3) this discovery has no access to — not a conclusion this document can reach from code
alone.

What this document does conclude, independent of the orchestration-placement question:

1. **API contract**: unchanged. `POST .../approve`, `POST .../reject` on all three entities are
   already correctly shaped and already exist as reserved routes (§10). This holds under either
   Option A or Option B — the API shape does not depend on which component the routes call.
2. **`AuditLog`**: extending `AuditEntityType`/`AuditAction` with the Time Management entities and
   `APPROVE`/`REJECT` is low-cost and evidence-supported, explicitly anticipated by the enums'
   own docstrings (§8), regardless of which orchestration option is chosen. Whether this satisfies
   the full history requirement is separately unresolved (Ambiguity 1).
3. **`EventPublisher`/`NotificationProvider`**: not recommended as part of a first
   implementation, under either orchestration option. Both are structurally reachable as optional
   post-commit side effects, but no consumer exists for events, and no product requirement
   confirms notifications are in scope (§6, §7).
4. **Everything in §13 must be resolved by a product/architecture decision outside this document
   before implementation begins**, in addition to the orchestration-placement decision itself.

---

## 15. Implementation Readiness

**Not ready.** This document directly answers five sub-questions PR-046 raised without fully
resolving (events, notifications, audit, user identity, API contract), and re-confirms, rather than
breaks, PR-046's central finding: **the orchestration-placement question (§5, Ambiguity 11 in
PR-046's own numbering) remains unresolved, because the repository does not contain precedent for
either candidate.** This is a deliberate outcome of this discovery, not a gap in it — see §14.

**Repository evidence and architectural decision are two different things, and should not be
blurred.** What the repository evidence in this document establishes: no service today performs
authorization beyond authentication, validates a state transition, or calls another service (§3,
§4); the only existing cross-aggregate access pattern is a read-only repository-level existence
check (§4); no component of any kind mutates another entity's storage from outside that entity's
own service (§5). What it does **not** establish: which of Option A or Option B should be built.
That is an architecture decision, to be made in the implementation PR — informed by, but not
determined by, the evidence gathered here — because the repository, as it stands, supports neither
option over the other. **Whichever architecture is selected, it will be the first orchestration
precedent of its kind in this repository**, and should be recognized and reviewed as such, not
framed as a mechanical continuation of an existing pattern.

**Concrete decisions required before implementation can begin**, in dependency order:

1. **Choose between Option A and Option B (§5, §14)** — this is an architecture decision the
   implementation PR must make; this discovery does not make it and repository evidence does not
   compel one answer.
2. Resolve the `User`↔`HrEmployee` linkage and authorization model (§9, §13.2–3) — determines
   whether the first shipped version has any real authorization boundary, and materially affects
   what either orchestration option would need to implement.
3. Resolve history-vs-columns for decision metadata (§8, §13.1) — determines the migration shape.
4. Confirm the valid `status` transition set (§13.4) and whether the generic `PUT` status path is
   closed off once actions exist (§13.5).
5. Confirm single-decision vs. multi-level approval is out of scope for a first version (§13.6).
6. Confirm `AttendanceEvent` is out of scope for a first version (§13.7).
7. Confirm no roadmap/product decision supersedes this discovery (§13.8).

**Stopping here per instructions.** No aggregate has been implemented, no migration has been
written, no code has been changed.

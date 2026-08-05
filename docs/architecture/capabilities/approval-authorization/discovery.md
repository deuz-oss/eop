# Approval Authorization — Discovery

**Status:** Complete

**Capability:** Approval Authorization

**Owner:** EOP Architecture Governance

---

# Purpose

This document records repository evidence for the Approval Authorization capability.

Discovery exists to understand the current repository state.

It does not define architecture.

Architecture decisions are documented separately.

---

# Discovery Scope

The following areas were inspected:

- Approval entry points (services, endpoints, repositories)
- `ApprovalService`
- Approval API endpoints (`leave_requests`, `overtime_requests`, `timesheets`)
- Existing approval rules
- `HrEmployee.manager_id`
- Approval actors
- Authorization Foundation (PR-052 / ADR-007)
- Approval-related exceptions
- Prior approval discovery/design documents (`APPROVAL_WORKFLOW_DESIGN.md`, `APPROVAL_ORCHESTRATION_DESIGN.md`)
- ADR-003, ADR-004, ADR-005, ADR-006, ADR-007
- `ARCHITECTURE_STATUS.md`, `CAPABILITY_CATALOG.md`
- Test suite (`test_approval_service.py`, `test_authorization_*.py`)

---

# 1. Repository Summary

Repository discovery confirms:

`ApprovalService` (`services/api/src/eop_api/services/approval.py`) exists and orchestrates `approve`/`reject` transitions for `LeaveRequest`, `OvertimeRequest`, and `Timesheet`.

Six API endpoints exist (`.../approve`, `.../reject` on all three entities) and are wired to `ApprovalService`.

Authorization Foundation (`AuthorizationService`, `AuthorizationEvaluator`, `AuthorizationDecision`, `AuthorizationRequest`) exists in the repository (ADR-007) but is not imported, referenced, or called anywhere in the approval code path.

Identity Context Foundation (`EmployeeContext`, `RequestContext`, `EmployeeContextResolver`) exists but is not used by any approval endpoint or by `ApprovalService`.

`ApprovalService` and every approval endpoint perform authentication only, via `CurrentUser`. No ownership check, role check, or manager-relationship check exists in the approval code path.

`ARCHITECTURE_STATUS.md` records "Approval Authorization" as not yet started (all lifecycle columns `⬜`) and lists it as the first "Next Planned Capability."

`CAPABILITY_CATALOG.md` records Leave/Timesheet/Overtime/Reconciliation as "Complete (authorization pending)" and "Approval Authorization" as "Planned" under the Authorization Roadmap.

ADR-003 ("Approval as Workflow Capability," accepted 2026-08-04) states explicitly, under "Current Limitation": *"Approval authorization belum diimplementasikan"* ("Approval authorization has not been implemented"), and names the current state as "Authentication only."

---

# 2. Repository Evidence

## 2.1 Approval Entry Points

Every approval entry point in the repository is one of the six endpoints below, each delegating to `ApprovalService`:

| Endpoint | File | Service method |
|---|---|---|
| `POST /hr/leave-requests/{id}/approve` | `api/leave_requests.py:148-162` | `ApprovalService.approve_leave_request` |
| `POST /hr/leave-requests/{id}/reject` | `api/leave_requests.py:165-182` | `ApprovalService.reject_leave_request` |
| `POST /hr/overtime-requests/{id}/approve` | `api/overtime_requests.py:150-166` | `ApprovalService.approve_overtime_request` |
| `POST /hr/overtime-requests/{id}/reject` | `api/overtime_requests.py:169-186` | `ApprovalService.reject_overtime_request` |
| `POST /hr/timesheets/{id}/approve` | `api/timesheets.py:150-162` | `ApprovalService.approve_timesheet` |
| `POST /hr/timesheets/{id}/reject` | `api/timesheets.py:165-178` | `ApprovalService.reject_timesheet` |

No other approval entry point exists in the repository. `LeaveRequestService`, `OvertimeRequestService`, and `TimesheetService` (their own `create`/`get`/`list`/`update`/`delete` methods) contain no `approve`/`reject` method — all six routers import `ApprovalService` from `eop_api.services.approval` for this behavior (`api/leave_requests.py:17`, `api/overtime_requests.py:17`, `api/timesheets.py:18`).

Each endpoint also injects `ApprovalServiceDep` via a router-local `get_approval_service()` factory (e.g. `api/leave_requests.py:34-38`), repeated identically in all three router files.

## 2.2 `ApprovalService`

Full file: `services/api/src/eop_api/services/approval.py`.

Responsibilities (per its own docstring, `approval.py:28-63`):

- Orchestrates `approve`/`reject` decisions for `LeaveRequest`, `OvertimeRequest`, `Timesheet`.
- Reaches directly into `LeaveRequestRepository`/`OvertimeRequestRepository`/`TimesheetRepository` (`approval.py:11-13`), bypassing `LeaveRequestService`/`OvertimeRequestService`/`TimesheetService`.
- Owns its own `SQLAlchemyUnitOfWork` via a `uow_factory` constructor parameter (`approval.py:65-68`), the same shape as every other service in the codebase.
- Enforces exactly one business rule: a `pending → approved`/`pending → rejected` transition is legal; any other current status raises `InvalidApprovalStateError` (`approval.py:214-217`).
- Six public methods (`approve_leave_request`, `reject_leave_request`, `approve_overtime_request`, `reject_overtime_request`, `approve_timesheet`, `reject_timesheet`), each following the same two-step `_apply_decision` (stage, never commits) / `_complete_decision` (commit, refresh, expunge) pattern (`approval.py:190-236`).

Dependencies: `LeaveRequestRepository`, `OvertimeRequestRepository`, `TimesheetRepository`, `BaseRepository`, `SQLAlchemyUnitOfWork`. No dependency on `AuthorizationService`, `AuthorizationEvaluator`, `EmployeeContext`, `RequestContext`, `RoleService`, or `HrEmployeeRepository`.

State transitions: `pending → approved` and `pending → rejected` only (`ApprovalStatus`, `approval.py:17-21`). Any other current status raises `InvalidApprovalStateError` (`approval.py:24-25`).

**Authorization**: the class docstring states explicitly: *"Authorization beyond authentication ... [is] explicitly out of scope for this service"* (`approval.py:44-46`). Every public method accepts `approver_id: uuid.UUID` as a plain parameter and writes it unconditionally to `approved_by` (`approval.py:219-225`) — no repository evidence shows this id being checked against a role, a `HrEmployee` relationship, or an `AuthorizationDecision` anywhere in this file.

## 2.3 Approval Endpoints

All six endpoints (`api/leave_requests.py:148-182`, `api/overtime_requests.py:150-186`, `api/timesheets.py:150-178`) share an identical shape:

- **`CurrentUser` usage**: each endpoint depends on `CurrentUser` (authentication dependency, `dependencies/auth.py:47`) and passes `current_user.id` directly to `ApprovalService` as `approver_id` (e.g. `api/leave_requests.py:155`). `CurrentUser` is not used for any authorization check inside the endpoint body.
- **Service invocation**: each endpoint calls the corresponding `ApprovalService` method inside a `try`/`except` block.
- **Exception handling**: each endpoint catches only `InvalidApprovalStateError` and maps it to `409 Conflict` (e.g. `api/leave_requests.py:156-157`); a `None` return from the service (entity not found) is mapped to `404 Not Found` (e.g. `api/leave_requests.py:158-161`).
- **Authorization behavior**: no endpoint contains a role check (`RequireRole`), an ownership check, or a call into `AuthorizationService`. No endpoint can currently return `403 Forbidden`.

Reject endpoints additionally accept a request body (`LeaveRequestRejectRequest`/`OvertimeRequestRejectRequest`/`TimesheetRejectRequest`) carrying a `reason: str`, passed through to `ApprovalService` unchanged.

## 2.4 Existing Approval Rules

The only approval rule found in the repository is state validation:

- A `pending → approved` or `pending → rejected` transition is legal; any other current `status` value raises `InvalidApprovalStateError` (`approval.py:214-217`).

No repository evidence was found for:

- **Approver assignment** — no field, table, or lookup designates who is permitted to decide a given `LeaveRequest`/`OvertimeRequest`/`Timesheet`.
- **Ownership validation** — no code compares the acting `CurrentUser`/`approver_id` to the requester's `employee_id`, or to any relationship of the requester.
- **Manager relationship** — `HrEmployee.manager_id` is never read by `ApprovalService`, by any approval endpoint, or by any approval test (see §2.5).

`LeaveRequest.status`/`OvertimeRequest.status`/`Timesheet.status` are plain `String(50)` columns with no `CHECK` constraint (`models/leave_request.py:48`, `models/overtime_request.py:50`, `models/timesheet.py:51`) — the only enforcement of the `pending`-origin rule is in `ApprovalService`, not the database.

The existing generic `PUT /hr/leave-requests/{id}` (and equivalents) endpoints still accept an unconstrained `status` field via `LeaveRequestUpdate`/`OvertimeRequestUpdate`/`TimesheetUpdate` (`api/leave_requests.py:112-134` et al.), independent of and unvalidated by `ApprovalService`'s transition rule.

## 2.5 Manager Hierarchy

`HrEmployee.manager_id` (`models/hr_employee.py:76-78`) is a nullable, self-referential foreign key (`ON DELETE RESTRICT`), with a `manager` relationship (`models/hr_employee.py:105`) and an index (`models/hr_employee.py:44`).

Its only current usage, found in `services/api/src/eop_api/services/hr_employee.py`:

- Existence check: if `manager_id` is set, the referenced `HrEmployee` must exist, else `ManagerNotFoundError` (`hr_employee.py:175-177`, `hr_employee.py:302-304`).
- Self-manager rejection: an `HrEmployee` cannot reference itself as `manager_id`, else `SelfManagerError` (`hr_employee.py:300-301`).

No repository evidence shows `manager_id` read, joined, or otherwise consulted by `ApprovalService`, any approval endpoint, `AuthorizationEvaluator`, `AuthorizationService`, or any approval test. Its own model docstring confirms: *"only a direct self-manager is rejected ... no recursive validation or cycle detection across the tree"* (`models/hr_employee.py:31-32`).

## 2.6 Approval Actors

Repository evidence supports exactly one actor role in the current approval code path:

- **Any authenticated `User`** — `CurrentUser` (`dependencies/auth.py:47`) is the only identity checked before an approve/reject call succeeds. Its `id` is written to `approved_by` unconditionally.

Two other entities appear in the surrounding data model but are not enforced as approval actors by any code:

- **Requester** — the `HrEmployee` referenced by `LeaveRequest.employee_id`/`OvertimeRequest.employee_id`/`Timesheet.employee_id`. No code compares this to the acting user.
- **Administrator** — `RequireRole("admin")` (aliased as `RequireAdmin`, `api/roles.py:25`) exists, but repository-wide grep confirms it is used only by `api/roles.py` (role-management endpoints); no approval endpoint depends on it.

No repository evidence was found for a distinct "manager" or "approver" role, permission, or claim.

## 2.7 Existing Exceptions

| Exception | Defined | Thrown | HTTP mapping |
|---|---|---|---|
| `InvalidApprovalStateError` | `approval.py:24-25` | `ApprovalService._apply_decision` when current status is not `pending` (`approval.py:214-217`) | `409 Conflict`, all three routers (`api/leave_requests.py:156-157`, `api/overtime_requests.py:160-161`, `api/timesheets.py:158-159`) |
| Entity not found (`None` return, no dedicated exception type) | — | `ApprovalService._apply_decision` returns `None` if `repo.get(entity_id)` is `None` (`approval.py:210-212`) | `404 Not Found`, all three routers |

No `Forbidden`/`Unauthorized`/`AuthorizationError`-style exception exists anywhere in the approval code path — consistent with the absence of any authorization check to raise one. `main.py` registers three global handlers (`http_exception_handler`, `validation_exception_handler`, `unhandled_exception_handler`, `main.py:78-80`); none is approval-specific.

## 2.8 Authorization Foundation Components (ADR-007)

All five files exist under `services/api/src/eop_api/services/`:

- `authorization.py` — `AuthorizationService.authorize(request: AuthorizationRequest) -> AuthorizationDecision`, delegates to an `AuthorizationEvaluator` (`authorization.py:6-20`).
- `authorization_evaluator.py` — `AuthorizationEvaluator.evaluate()` unconditionally returns `AuthorizationDecision(allowed=True)` (`authorization_evaluator.py:17-18`); its own docstring states no permission/ownership/role model exists yet.
- `authorization_decision.py` — `AuthorizationDecision` is an immutable `@dataclass(frozen=True)` with `allowed: bool` and `reason: str | None` (`authorization_decision.py:4-14`).
- `authorization_request.py` — `AuthorizationRequest` wraps a `RequestContext` only; no `Subject`/`Action`/`Resource`/ownership/role field exists (`authorization_request.py:6-20`).
- `employee_context.py` — `EmployeeContext` (`user`, `employee`), `RequestContext` (`user`, `employee_context`), `EmployeeContextResolver.resolve(user) -> EmployeeContext` (`employee_context.py:29-84`).

Consumers: repository-wide grep for `CurrentEmployeeContext|CurrentRequestContext|EmployeeContextResolver|AuthorizationService|AuthorizationEvaluator|AuthorizationRequest|AuthorizationDecision` returns matches only inside the five files above, `dependencies/employee_context.py`, and their own unit test files (`test_authorization_decision.py`, `test_authorization_evaluator.py`, `test_authorization_request.py`, `test_authorization_service.py`). No API router, no `ApprovalService`, and no other business service imports any of them.

`dependencies/employee_context.py` (`CurrentEmployeeContext`, `CurrentRequestContext`) is explicitly documented as *"Not wired into any router: this capability adds no endpoint behavior"* (`dependencies/employee_context.py:13`), and `AuthorizationService`'s own docstring states *"Not wired into any router or business service: this capability adds no endpoint behavior"* (`authorization.py:12-13`).

---

# 3. Current Approval Architecture

Execution flow for every approve/reject call, as implemented today:

```
Client
  │
  ▼
API Router (leave_requests.py / overtime_requests.py / timesheets.py)
  │  CurrentUser  (authentication only — dependencies/auth.py)
  ▼
ApprovalService (services/approval.py)
  │  _apply_decision: fetch, validate pending→approved/rejected, stage update
  │  _complete_decision: commit, refresh, expunge
  ▼
LeaveRequestRepository / OvertimeRequestRepository / TimesheetRepository
  │
  ▼
Database (leave_requests / overtime_requests / timesheets)
```

`ApprovalService` is a standalone orchestration service per ADR-003 ("Approval as Workflow Capability"), used by Leave, Overtime, and Timesheet, positioned outside those three domains' own per-entity services.

Per ADR-003's own "Target Architecture" section, the intended flow is `Business Request → Workflow Engine → Decision → Domain Update`; the "Current Limitation" section of the same ADR states this exists today only as `Authentication`, with `Authorization` and `Workflow Policy` marked as future.

---

# 4. Authorization Surface

Repository-wide occurrence check for each named mechanism:

| Mechanism | Where used | Where not used |
|---|---|---|
| `CurrentUser` | Every approval endpoint (`api/leave_requests.py:59,77,89,102,117,139,152,170`; equivalents in `overtime_requests.py`, `timesheets.py`); every other authenticated endpoint in the repository | Not used inside `ApprovalService` itself (the API layer resolves it and passes `current_user.id` as a plain UUID parameter) |
| `RequireRole` / `RequireAdmin` | `api/roles.py:25` only (role-management endpoints: create/update/delete role, assign/remove role) | Not used by any approval endpoint, any Leave/Overtime/Timesheet endpoint, or `ApprovalService` |
| `AuthorizationService` | `services/authorization.py` (definition), `test_authorization_service.py` | Not used by any API router, `ApprovalService`, or any other business service |
| `AuthorizationEvaluator` | `services/authorization.py`, `services/authorization_evaluator.py` (definition), `test_authorization_evaluator.py` | Not used outside Authorization Foundation's own files/tests |
| `AuthorizationRequest` | `services/authorization.py`, `services/authorization_request.py` (definition), `test_authorization_request.py` | Not constructed anywhere in the approval code path |
| `AuthorizationDecision` | `services/authorization.py`, `services/authorization_evaluator.py`, `services/authorization_decision.py` (definition), `test_authorization_decision.py`, `test_authorization_service.py`, `test_authorization_evaluator.py` | Never returned to, or consumed by, any endpoint or business service |
| `EmployeeContext` | `services/employee_context.py` (definition), `dependencies/employee_context.py`, `services/authorization_request.py` (type reference via `RequestContext`) | Not resolved on, or consumed by, any approval endpoint |
| `RequestContext` | Same as `EmployeeContext` | Same as `EmployeeContext` |

`test_approval_service.py` (34 tests) exercises `ApprovalService` directly with an arbitrary `approver_id: uuid.UUID` fixture (`test_approval_service.py:158-168`) that is a bare `User` row with no `HrEmployee`/role/manager relationship — no test in this file asserts any authorization outcome (allow or deny).

---

# 5. Dependency Analysis

```
API Layer
  (leave_requests.py, overtime_requests.py, timesheets.py)
        │
        │ CurrentUser (authentication only)
        ▼
ApprovalService
        │
        ▼
LeaveRequestRepository / OvertimeRequestRepository / TimesheetRepository
        │
        ▼
Database
```

Authorization Foundation, shown for completeness, with its actual (disconnected) position:

```
Authentication (dependencies/auth.py)
        │
        ▼
Identity Context (services/employee_context.py, dependencies/employee_context.py)
        │
        ▼
Authorization Foundation (services/authorization*.py)
        │
        ✕  ← no repository evidence of an edge from here into ApprovalService or any approval endpoint
        ▼
ApprovalService
```

Both Identity Context and Authorization Foundation are present in the repository and structurally capable of preceding `ApprovalService` in the request path (per ADR-006/ADR-007's documented target architecture), but no import, call, or dependency-injection wiring connects them to `ApprovalService` or to `api/leave_requests.py`/`api/overtime_requests.py`/`api/timesheets.py` today.

`CAPABILITY_CATALOG.md` records the same dependency direction declaratively: `Authorization Foundation → Business Capabilities`, with "Approval Authorization" listed as `Planned` under "Authorization Roadmap" and Leave/Timesheet/Overtime/Reconciliation listed as `Complete (authorization pending)`.

---

# 6. Architectural Gaps

Gaps identified between the current implementation and the Authorization Foundation capability (ADR-007), stated as repository evidence, not as recommendations:

- `ApprovalService` accepts `approver_id: uuid.UUID` directly from `CurrentUser.id` and writes it to `approved_by` without constructing an `AuthorizationRequest` or invoking `AuthorizationService`/`AuthorizationEvaluator` (`approval.py:70-188`).
- No approval endpoint depends on `CurrentEmployeeContext` or `CurrentRequestContext`; all six depend on `CurrentUser` only.
- `AuthorizationEvaluator`'s only existing implementation unconditionally allows every request (`authorization_evaluator.py:17-18`) — even if wired into the approval path today, it carries no rule capable of constraining an approval decision.
- No repository evidence connects `HrEmployee.manager_id` to any approval, authorization, or ownership check — its only consumers are existence and self-reference validation in `HrEmployeeService` (§2.5).
- No repository evidence of an `OwnershipResolver` or `RoleResolver` implementation; ADR-007 defines both as abstractions with "concrete ownership implementations belong to business capabilities" and states integration is "intentionally deferred."
- `RequireRole` is not invoked by any approval endpoint; `ApprovalService` and all six approval endpoints do not distinguish "any authenticated user" from any narrower actor.
- The generic `PUT /hr/leave-requests/{id}` (and equivalents) endpoints continue to accept an unconstrained `status` field (§2.4), independent of and unvalidated by whatever authorization model may eventually gate `.../approve`/`.../reject`.
- ADR-003 itself records this as a known, named limitation ("Approval authorization belum diimplementasikan") rather than an unnoticed omission.

---

# 7. Open Questions

Repository evidence does not answer the following:

- Which actor(s) are intended as valid approvers — role holder, manager-of-requester (via `HrEmployee.manager_id`), administrator, or some combination? ADR-003's "Future" section names "Authorization" and "Workflow Policy" without specifying a model; no ADR defines one.
- At which point in the execution flow authorization should be evaluated for approval specifically — API layer, `ApprovalService`, or elsewhere — given ADR-007 states Authorization Foundation "is not wired into any router or business service" and defers all integration.
- Whether `approved_by` (currently a `User.id`, `models/leave_request.py:51-53` et al.) is intended to remain a `User` reference or become an `HrEmployee` reference once/if authorization is added, given ADR-004 leaves `hr_employees.user_id` cardinality ("UNRESOLVED") unsettled — resolving `CurrentUser` to a single `HrEmployee` for approval-actor purposes inherits that same unresolved cardinality (`EmployeeContextResolver`, `employee_context.py:56-84`, already raises `MultipleEmployeeContextError` for this reason).
- Whether the existing generic `PUT .../{id}` `status` write path is intended to remain open once/if `.../approve`/`.../reject` gain authorization enforcement (§2.4) — no repository evidence resolves this either way; it was already flagged, unresolved, in `APPROVAL_WORKFLOW_DESIGN.md` §14.5 and `APPROVAL_ORCHESTRATION_DESIGN.md` §13.5.
- Whether `OwnershipResolver`/`RoleResolver` (named as abstractions in ADR-007 but not present as concrete files in this repository) are expected to be introduced as part of Approval Authorization or a separate capability.

---

# 8. Recommended Next Step

```
Architecture Decision
```

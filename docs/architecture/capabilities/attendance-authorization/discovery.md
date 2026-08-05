# Attendance Authorization — Discovery

**Status:** Complete

**Capability:** Attendance Authorization

**Owner:** EOP Architecture Governance

---

# Purpose

This document records repository evidence for the Attendance Authorization capability.

Discovery exists to understand the current repository state.

It does not define architecture.

It does not choose a policy model.

Architecture decisions and policy discovery are documented separately, per `AI_DISCOVERY_GUIDE.md`.

---

# Discovery Scope

The following areas were inspected (full file reads unless noted):

- Attendance entry points: `models/attendance_event.py`, `core/attendance.py`, `schemas/attendance_event.py`, `repositories/attendance_event.py`, `services/attendance_event.py`, `api/attendance_events.py`
- Attendance Reconciliation (downstream consumer of `AttendanceEvent`): `services/reconciliation.py`, `api/reconciliation.py`, `schemas/reconciliation.py`
- Identity Context Foundation: `services/employee_context.py`, `dependencies/employee_context.py`
- Authorization Foundation (ADR-007): `services/authorization.py`, `services/authorization_evaluator.py`, `services/authorization_request.py`, `services/authorization_decision.py`
- Approval Authorization (ADR-008, merged): `services/approval.py`, `services/approval_authorization.py`
- Leave Authorization (merged, no governing ADR/capability doc found — see Findings): `services/leave_request.py`, `services/leave_authorization.py`, `api/leave_requests.py`
- `HrEmployee` model (`models/hr_employee.py`) — `manager_id`, `shift_id`, `user_id`
- `main.py` router registration
- Governance documents: `MASTER_ARCHITECTURE_ROADMAP.md`, `MASTER_ARCHITECTURE_BLUEPRINT.md`, `ARCHITECTURE_STATUS.md`, `CAPABILITY_CATALOG.md`, `TECHNICAL_DEBT_REGISTER.md`
- `ADR-007-authorization-foundation.md`, `ADR-008-Approval Authorization Policy Model`
- `docs/architecture/ATTENDANCE_DESIGN.md` (PR-039, discovery), `docs/architecture/ATTENDANCE_RECONCILIATION_DESIGN.md` (PR-048, discovery + implementation decision)
- Prior capability discovery precedent: `docs/architecture/capabilities/approval-authorization/discovery.md`, `docs/architecture/capabilities/identity-authorization/decision.md`
- Test suite: `test_attendance_events_api.py`, `test_attendance_event_repository.py`, `test_attendance_event_service.py`, `test_reconciliation_service.py`, `test_reconciliation_api.py`, `test_leave_authorization_evaluator.py`
- `git log` for `docs/architecture/00-governance`, `docs/architecture/10-reference`, `docs/architecture/capabilities`

---

# 1. Repository Summary

Repository discovery confirms:

`AttendanceEventService` (`services/attendance_event.py`) and its six-route CRUD API (`api/attendance_events.py`, prefix `/hr/attendance-events`) exist and are fully implemented, tested, and wired into `main.py`. Every route depends on `CurrentUser` only (authentication). No route depends on `CurrentEmployeeContext` or `CurrentRequestContext`. No authorization check, ownership check, role check, or manager-relationship check exists anywhere in the Attendance code path.

`ReconciliationService` (`services/reconciliation.py`) and its single `GET /hr/reconciliation` endpoint (`api/reconciliation.py`) also exist, are implemented and tested, and read `AttendanceEvent` (via `AttendanceEventRepository.exists_between`) as one of four inputs to compute a per-employee-day attendance result. This endpoint also depends on `CurrentUser` only, and accepts an arbitrary `employee_id` query parameter with no scoping to the caller's own identity — any authenticated user can request any employee's reconciliation result.

Authorization Foundation (`AuthorizationService`, `AuthorizationEvaluator`, `AuthorizationDecision`, `AuthorizationRequest`, ADR-007) exists in the repository and is consumed by two other capabilities (Approval Authorization, ADR-008; Leave Authorization, no governing ADR found — see §7) but is not imported, referenced, or called anywhere in `services/attendance_event.py`, `api/attendance_events.py`, `services/reconciliation.py`, or `api/reconciliation.py`.

Identity Context Foundation (`EmployeeContext`, `RequestContext`, `EmployeeContextResolver`, `CurrentEmployeeContext`, `CurrentRequestContext`) exists and is consumed by Leave Authorization and Approval Authorization, but is not used by any Attendance or Reconciliation endpoint or service.

`MASTER_ARCHITECTURE_ROADMAP.md` lists "Attendance Authorization" as `Planned`, positioned after "Leave Authorization" (also listed `Planned`) in both the "Remaining Capability Authorizations" table and the "Dependency Roadmap" diagram (`Authentication → Identity Context → Authorization Foundation → Approval Authorization → Leave Authorization → Attendance Authorization → Payroll Authorization → Enterprise Authorization`).

`ARCHITECTURE_STATUS.md` and `CAPABILITY_CATALOG.md` (both dated 2026-08-05) record only "Approval Authorization" as `Implemented` under authorization capabilities; neither document lists "Leave Authorization" at all, despite `LeaveAuthorizationEvaluator`, `LeaveRequestService._authorize`, `LeaveAuthorizationDeniedError`, and `test_leave_authorization_evaluator.py` all existing in the repository and `git log` showing it merged (`0a9b669 feat(auth): implement leave authorization capability`, merge commit `bdb475e`, PR #56) — after `ARCHITECTURE_STATUS.md`'s and `CAPABILITY_CATALOG.md`'s last-updated date. See §7 for detail.

---

# 2. Repository Evidence

## 2.1 Attendance Entry Points

Every Attendance entry point in the repository is one of the six endpoints below, all in `api/attendance_events.py`, prefix `/hr/attendance-events`, each delegating to `AttendanceEventService`:

| Endpoint | File | Service method |
|---|---|---|
| `POST /hr/attendance-events` | `api/attendance_events.py:58-72` | `AttendanceEventService.create` |
| `GET /hr/attendance-events` | `api/attendance_events.py:75-80` | `AttendanceEventService.list` |
| `GET /hr/attendance-events/paginated` | `api/attendance_events.py:83-97` | `AttendanceEventService.list_paginated` |
| `GET /hr/attendance-events/{event_id}` | `api/attendance_events.py:100-109` | `AttendanceEventService.get` |
| `PUT /hr/attendance-events/{event_id}` | `api/attendance_events.py:112-133` | `AttendanceEventService.update` |
| `DELETE /hr/attendance-events/{event_id}` | `api/attendance_events.py:136-144` | `AttendanceEventService.delete` |

No other Attendance entry point exists. Each endpoint injects `AttendanceEventServiceDep` via a router-local `get_attendance_event_service()` factory (`api/attendance_events.py:26-32`), the same shape used by every other CRUD router reviewed (Leave Requests, Approval).

A seventh, related entry point exists outside this router: `GET /hr/reconciliation` (`api/reconciliation.py:21-33`), which reads `AttendanceEvent` data (via `ReconciliationService`) but is not part of `AttendanceEventService`'s CRUD surface — see §2.5.

## 2.2 `AttendanceEventService`

Full file: `services/attendance_event.py`.

Responsibilities (per its own docstring, `attendance_event.py:22-43`):

- CRUD for `AttendanceEvent` — "a single clock transaction... not an employee-day or summary shaped" record.
- Validates only the existence of `employee_id` (via `HrEmployeeRepository`) and `shift_id` (via `ShiftRepository`) on `create`/`update` (`attendance_event.py:54-58`, `105-111`).
- Its own docstring states explicitly: *"Sequencing (e.g. rejecting a clock-out before a clock-in), duplicate-event detection, and shift-matching are explicitly out of scope for this module and belong to future business-workflow PRs."*

Constructor signature: `__init__(self, uow_factory: Callable[[], SQLAlchemyUnitOfWork] = SQLAlchemyUnitOfWork)` (`attendance_event.py:45-48`) — identical shape to every other CRUD service, and to `LeaveRequestService`/`ApprovalService` before authorization was added to them.

**No method on `AttendanceEventService` accepts a `RequestContext`, `EmployeeContext`, or any authorization-related parameter.** `create`, `get`, `list`, `list_paginated`, `update`, and `delete` (`attendance_event.py:50-127`) take only the same parameters as the CRUD data (`AttendanceEventCreate`/`AttendanceEventUpdate`/`uuid.UUID`/pagination-search-filter objects). This is a structural difference from `LeaveRequestService` (§2.8), whose six methods after Leave Authorization was added all take an additional `request_context: RequestContext` parameter (`leave_request.py:78-206`).

No `_authorize` method, or any equivalently named private method, exists on `AttendanceEventService`.

`list` (`attendance_event.py:73-78`) and `list_paginated` (`attendance_event.py:80-92`) return **all** `AttendanceEvent` rows in the system (or all matching the caller-supplied `filters`, including an arbitrary `employee_id` filter, `api/attendance_events.py:36-52`) — there is no in-memory or repository-level scoping to the caller's own `employee_id`, unlike `LeaveRequestService.list`/`list_paginated`, which force-scope to `request_context.employee_context.employee.id` (`leave_request.py:111-125`, `127-154`).

## 2.3 Attendance API Endpoints

All six endpoints (`api/attendance_events.py:58-144`) share an identical shape:

- **`CurrentUser` usage**: each endpoint depends on `CurrentUser` (`dependencies/auth.py:47`, authentication only) as an unused positional parameter (`_: CurrentUser`, e.g. `attendance_events.py:60`). `CurrentUser` is never read inside any endpoint body.
- **No `CurrentEmployeeContext` or `CurrentRequestContext` dependency** appears anywhere in `api/attendance_events.py` — confirmed by full-file read and by repository-wide grep (only `Leave Requests`/`api/leave_requests.py:6` and `Approval`/`approve`/`reject` routes import `CurrentRequestContext`, per §2.8).
- **Exception handling**: each endpoint catches only `EmployeeNotFoundError`/`ShiftNotFoundError` (mapped to `404`), or a `None` return (mapped to `404`) — no endpoint contains a `403 Forbidden` branch, because no exception type exists in `services/attendance_event.py` that would represent a denied authorization decision (§2.9).
- **No role check**: no endpoint depends on `RequireRole`/`RequireAdmin`.

`AttendanceEventCreate` (`schemas/attendance_event.py:9-15`) accepts `employee_id: uuid.UUID` as a caller-supplied field with no default and no server-side derivation from the caller's own identity — any authenticated user can create an `AttendanceEvent` for any `employee_id` that exists, and `AttendanceEventUpdate` (`schemas/attendance_event.py:18-24`) permits changing `employee_id` on an existing event the same way.

## 2.4 `AttendanceEvent` Domain Boundaries

`AttendanceEvent` (`models/attendance_event.py:19-61`) is explicitly documented as event-shaped, not employee-day/summary-shaped (model docstring, `attendance_event.py:20-35`): *"Employee-day rollups, timesheets, overtime, and payroll are all future projections built on top of this stream — out of scope here."*

Fields: `employee_id` (FK → `hr_employees.id`, `ON DELETE RESTRICT`), `shift_id` (FK → `shifts.id`, `ON DELETE RESTRICT`), `event_type` (`EventType`: `CLOCK_IN`/`CLOCK_OUT`/`BREAK_IN`/`BREAK_OUT`, `core/attendance.py:4-10`), `event_time` (`DateTime(timezone=True)`), `source` (`EventSource`: `SYSTEM`/`MANUAL`/`IMPORT`, `core/attendance.py:13-18`), `remarks` (nullable `String(2000)`).

`AttendanceEvent.shift_id` is independent of `HrEmployee.shift_id` (`models/hr_employee.py:88-90`) — both are separate, non-null FKs to `shifts.id`, and `AttendanceEventService.create`/`update` only validate that the supplied `shift_id` **exists** (`ShiftRepository(...).exists(...)`, `attendance_event.py:57-58`, `109-111`); no code path compares an event's `shift_id` to the referenced `HrEmployee.shift_id` for equality or relevance.

`ATTENDANCE_DESIGN.md` (PR-039, the original Attendance discovery) §11 flagged, as ambiguity #2, that no FK linked the authenticated `User` to `HrEmployee`, blocking any self-service resolution of "who is clocking in." This has since been resolved at the platform level by Identity Context (ADR-006, `hr_employees.user_id`, `EmployeeContextResolver`) — but `AttendanceEventService`/`api/attendance_events.py` do not consume that resolution (§2.2, §2.3); the capability-level gap remains open even though the platform-level blocker it depended on has closed.

## 2.5 `ReconciliationService` (Downstream Consumer)

Full file: `services/reconciliation.py`. Implemented (not a stub) per `ATTENDANCE_RECONCILIATION_DESIGN.md`'s "Chosen implementation" section (naming decision only; composition logic built afterward — confirmed by direct read of the current file, which contains a working `reconcile` method, not a shell).

`ReconciliationService.reconcile(employee_id: uuid.UUID, target_date: date)` (`reconciliation.py:68-100`) reads four repositories against one shared `uow.session` — `HrEmployeeRepository` (existence only), `HolidayRepository`, `LeaveRequestRepository`, `AttendanceEventRepository` — and returns one of `"holiday"`/`"leave"`/`"present"`/`"absent"`, evaluated in that precedence order. It never calls `uow.commit()` (read-only, per its own docstring, `reconciliation.py:36`).

`GET /hr/reconciliation` (`api/reconciliation.py:21-33`) depends on `CurrentUser` only (`_: CurrentUser`, `api/reconciliation.py:24`) and takes `employee_id: uuid.UUID` as a caller-supplied query parameter (`api/reconciliation.py:25`) with no comparison to the caller's own resolved identity. No `CurrentEmployeeContext`/`CurrentRequestContext` dependency exists in `api/reconciliation.py`.

This is the only other place in the repository, besides `AttendanceEventService` itself, that reads `AttendanceEvent` data (via `AttendanceEventRepository.exists_between`, `reconciliation.py:90-92`) to produce a result exposed through an API.

## 2.6 Identity Context Integration

Repository-wide grep for `CurrentEmployeeContext|CurrentRequestContext|EmployeeContextResolver` confirms these symbols are imported by exactly: `dependencies/employee_context.py` (definition), `api/leave_requests.py`, `services/leave_request.py`, `services/approval.py`, and their own test files. **Zero occurrences** in any Attendance or Reconciliation file (`models/attendance_event.py`, `core/attendance.py`, `schemas/attendance_event.py`, `repositories/attendance_event.py`, `services/attendance_event.py`, `api/attendance_events.py`, `services/reconciliation.py`, `api/reconciliation.py`).

## 2.7 Authorization Foundation Components (ADR-007)

All four files exist under `services/`: `authorization.py` (`AuthorizationService.authorize`), `authorization_evaluator.py` (`AuthorizationEvaluator.evaluate` — base class, unconditionally returns `AuthorizationDecision(allowed=True)`, `authorization_evaluator.py:17-18`, its own docstring states it is the "foundation-phase," "replaceable extension point"), `authorization_request.py` (`AuthorizationRequest`, wraps `RequestContext` + optional `resource: Any | None`), `authorization_decision.py` (`AuthorizationDecision`, frozen dataclass, `allowed: bool`, `reason: str | None`).

Consumers, confirmed by repository-wide grep: `ApprovalAuthorizationEvaluator` (`services/approval_authorization.py`, subclasses `AuthorizationEvaluator`, ADR-008) and `LeaveAuthorizationEvaluator` (`services/leave_authorization.py`, subclasses `AuthorizationEvaluator`). **No `AttendanceAuthorizationEvaluator` or equivalently named class exists anywhere in the repository.**

## 2.8 Approval Authorization and Leave Authorization (Merged Precedent)

Both are fully merged and wired into their respective API routes as of the current branch's base (`git log`: `0a9b669` Leave Authorization, `4c029b8` Approval Authorization). Reviewed in full as the two existing, working examples of a capability integrating Authorization Foundation:

**Approval Authorization** (`services/approval.py`, `services/approval_authorization.py`, governed by ADR-008): `ApprovalService._authorize` (`approval.py:209-232`) resolves the target entity's `employee_id` to its `HrEmployee.manager_id`, constructs an `ApprovalAuthorizationEvaluator(requester.manager_id)`, wraps `RequestContext` (no `resource`) in an `AuthorizationRequest`, and calls `AuthorizationService(evaluator).authorize(...)`. A denied decision raises `ApprovalAuthorizationDeniedError`, caught by the API layer and mapped to `403 Forbidden` (`api/leave_requests.py:177-178` and equivalents). Formal rule, per `ApprovalAuthorizationEvaluator`'s own docstring (`approval_authorization.py:9-21`): `request.employee.manager_id == approver.employee.id`.

**Leave Authorization** (`services/leave_authorization.py`, `services/leave_request.py`): `LeaveRequestService._authorize` (`leave_request.py:207-222`) wraps `RequestContext` **and** `resource` (the `LeaveRequestCreate` payload or loaded `LeaveRequest`) in an `AuthorizationRequest`, and calls `AuthorizationService(LeaveAuthorizationEvaluator()).authorize(...)`. A denied decision raises `LeaveAuthorizationDeniedError`, mapped to `403 Forbidden` (`api/leave_requests.py:74-75` and equivalents). Formal rule, per `LeaveAuthorizationEvaluator`'s own docstring (`leave_authorization.py:6-15`): `resource.employee_id == context.employee_context.employee.id`.

Both integrations share a common shape not present anywhere in the Attendance code path: (a) every mutating/reading method takes `request_context: RequestContext`, sourced from `CurrentRequestContext` at the API layer; (b) a private `_authorize` method on the owning service delegates to `AuthorizationService`/a capability-specific `AuthorizationEvaluator` subclass, never comparing fields itself; (c) a dedicated `*AuthorizationDeniedError` exception type is raised on denial and mapped to `403 Forbidden` at the API layer; (d) the evaluator subclass performs no repository access of its own (`ApprovalAuthorizationEvaluator` accepts an already-resolved `manager_id`; `LeaveAuthorizationEvaluator` accepts an already-resolved `resource`).

**Both patterns are structurally different from each other**: Approval Authorization's evaluator is constructed per-call with data the *service* resolved via a repository lookup (`manager_id`); Leave Authorization's evaluator is stateless and receives all data through `AuthorizationRequest.resource`. Repository evidence shows two distinct, already-precedented integration shapes, not one uniform template.

## 2.9 Existing Exceptions

| Exception | Defined | Thrown | HTTP mapping |
|---|---|---|---|
| `EmployeeNotFoundError` | `services/attendance_event.py:14-15` | `AttendanceEventService.create`/`update` when `HrEmployeeRepository.exists()` is `False` | `404 Not Found` (`api/attendance_events.py:64-67`, `121-124`) |
| `ShiftNotFoundError` | `services/attendance_event.py:18-19` | `AttendanceEventService.create`/`update` when `ShiftRepository.exists()` is `False` | `404 Not Found` (`api/attendance_events.py:68-71`, `125-128`) |
| Entity not found (`None` return) | — | `get`/`update`/`delete` when `repo.get(...)` is `None` | `404 Not Found` (`api/attendance_events.py:105-108`, `129-132`, `141-144`) |

No `Forbidden`/`Unauthorized`/`*AuthorizationDeniedError`-style exception exists anywhere in `services/attendance_event.py` or `services/reconciliation.py` — consistent with the absence of any authorization check to raise one. No Attendance or Reconciliation endpoint can currently return `403 Forbidden`.

## 2.10 Manager Hierarchy and Ownership Data Available

`HrEmployee.manager_id` (`hr_employee.py:76-78`, nullable, self-referential FK, `ON DELETE RESTRICT`) and `HrEmployee.user_id` (`hr_employee.py:91-93`, nullable FK → `users.id`, `ON DELETE SET NULL`) both exist and are already consumed by other capabilities (`manager_id` by `ApprovalAuthorizationEvaluator` via `ApprovalService._authorize`; `user_id` by `EmployeeContextResolver.resolve`, `employee_context.py:72-84`). Neither is read anywhere in `services/attendance_event.py`, `api/attendance_events.py`, `services/reconciliation.py`, or `api/reconciliation.py`.

`AttendanceEvent.employee_id` (the record's subject) is directly comparable to `EmployeeContext.employee.id` (the resolved caller's own `HrEmployee.id`) using the same pattern `LeaveAuthorizationEvaluator` already uses for `LeaveRequest.employee_id` (§2.8) — this is a structural observation about available data, not a policy recommendation.

## 2.11 Tests

`test_attendance_events_api.py`, `test_attendance_event_repository.py`, `test_attendance_event_service.py`, `test_reconciliation_service.py`, `test_reconciliation_api.py` — repository-wide grep for `Authoriz|CurrentUser|RequestContext|Forbidden` inside the Attendance/Reconciliation test files returns matches only for `CurrentUser`-unrelated fixture setup (`_create_user`, plain authentication token helper for `TestClient`). None of the five files import `RequestContext`, `EmployeeContext`, `AuthorizationService`, or any `*AuthorizationDeniedError`/`*AuthorizationEvaluator` symbol. `AttendanceEventService(...)` and `ReconciliationService(...)` are constructed and called in tests with no `request_context` argument anywhere — consistent with §2.2's finding that no such parameter exists on either service's public methods.

`test_leave_authorization_evaluator.py` exists as a dedicated unit-test file for `LeaveAuthorizationEvaluator`, confirming the Leave Authorization pattern (§2.8) has its own isolated test coverage, structurally distinct from the CRUD-only Attendance test files.

---

# 3. Current Attendance Architecture

Execution flow for every Attendance CRUD call, as implemented today:

```
Client
  │
  ▼
API Router (api/attendance_events.py)
  │  CurrentUser  (authentication only — dependencies/auth.py)
  ▼
AttendanceEventService (services/attendance_event.py)
  │  create/update: HrEmployeeRepository.exists(), ShiftRepository.exists()
  │  no authorization check
  ▼
AttendanceEventRepository
  │
  ▼
Database (attendance_events)
```

Execution flow for the one downstream consumer that reads `AttendanceEvent`:

```
Client
  │
  ▼
API Router (api/reconciliation.py)
  │  CurrentUser  (authentication only)
  │  employee_id  (caller-supplied query param, unscoped)
  ▼
ReconciliationService (services/reconciliation.py)
  │  reads HrEmployeeRepository, HolidayRepository,
  │  LeaveRequestRepository, AttendanceEventRepository
  │  no authorization check
  ▼
Database (attendance_events, holidays, leave_requests, hr_employees)
```

Both Identity Context and Authorization Foundation are present in the repository and structurally capable of preceding either flow above (per ADR-006/ADR-007's documented target architecture, and per their proven integration into Leave Authorization/Approval Authorization, §2.8), but no import, call, or dependency-injection wiring connects them to `AttendanceEventService`, `api/attendance_events.py`, `ReconciliationService`, or `api/reconciliation.py` today.

---

# 4. Authorization Surface

Repository-wide occurrence check for each named mechanism, scoped to the Attendance and Reconciliation code paths:

| Mechanism | Used by Attendance/Reconciliation? | Used elsewhere |
|---|---|---|
| `CurrentUser` | Yes — every one of the 7 endpoints (6 Attendance + 1 Reconciliation) | Every authenticated endpoint in the repository |
| `CurrentEmployeeContext` / `CurrentRequestContext` | **No** | `api/leave_requests.py` (all 8 routes), `services/leave_request.py`, `services/approval.py` |
| `RequireRole` / `RequireAdmin` | No | `api/roles.py` only |
| `AuthorizationService` | **No** | `services/approval.py`, `services/leave_request.py` |
| `AuthorizationEvaluator` (or a subclass) | **No** | `ApprovalAuthorizationEvaluator`, `LeaveAuthorizationEvaluator` |
| `AuthorizationRequest` | **No** | `services/approval.py`, `services/leave_request.py` |
| `AuthorizationDecision` | **No** | Same as `AuthorizationRequest`, plus Authorization Foundation's own files |
| `*AuthorizationDeniedError` (403-mapped) | **No** | `ApprovalAuthorizationDeniedError`, `LeaveAuthorizationDeniedError` |
| `HrEmployee.manager_id` read | No | `ApprovalService._authorize` (`approval.py:225-226`) |
| `HrEmployee.user_id` read | No (indirectly available via `EmployeeContext` if wired) | `EmployeeContextResolver.resolve` |

---

# 5. Dependency Analysis

```
API Layer
  (api/attendance_events.py, api/reconciliation.py)
        │
        │ CurrentUser (authentication only)
        ▼
AttendanceEventService / ReconciliationService
        │
        ▼
AttendanceEventRepository / HolidayRepository / LeaveRequestRepository / HrEmployeeRepository
        │
        ▼
Database
```

Authorization Foundation and Identity Context, shown for completeness, with their actual (disconnected) position relative to Attendance:

```
Authentication (dependencies/auth.py)
        │
        ▼
Identity Context (services/employee_context.py, dependencies/employee_context.py)
        │
        ▼
Authorization Foundation (services/authorization*.py)
        │
        ✕  ← no repository evidence of an edge from here into AttendanceEventService,
        │      api/attendance_events.py, ReconciliationService, or api/reconciliation.py
        ▼
AttendanceEventService / ReconciliationService
```

`CAPABILITY_CATALOG.md`'s own dependency graph (`Authentication → Identity Context → Authorization Foundation → Approval Authorization → Approval Workflow → Business Capabilities`) and `MASTER_ARCHITECTURE_ROADMAP.md`'s "Dependency Roadmap" (`... → Approval Authorization → Leave Authorization → Attendance Authorization → Payroll Authorization → ...`) both record the same declarative dependency direction — Attendance Authorization is positioned downstream of Leave Authorization in the documented roadmap sequence.

`ReconciliationService` is an existing, in-repository consumer of `AttendanceEvent` (§2.5) not named in either governance document's capability list or dependency graph — neither `CAPABILITY_CATALOG.md` nor `MASTER_ARCHITECTURE_ROADMAP.md` mentions "Reconciliation" or "Attendance Reconciliation" as a capability, despite `services/reconciliation.py`, `api/reconciliation.py`, and their tests existing and being wired into `main.py`.

---

# 6. Findings

Findings are stated as repository evidence, not as recommendations.

- `AttendanceEventService` and all six of its API endpoints perform no authorization check beyond authentication (`CurrentUser`) — confirmed by full-file read of `services/attendance_event.py` and `api/attendance_events.py` (§2.2, §2.3).
- `ReconciliationService` and its one API endpoint perform no authorization check beyond authentication, and accept a caller-supplied, unscoped `employee_id` (§2.5) — this endpoint reads `AttendanceEvent` data the same way the Attendance CRUD endpoints do, but is not part of `AttendanceEventService`'s own router or test suite.
- Neither `AttendanceEventService`'s nor `ReconciliationService`'s public methods accept a `RequestContext` or `EmployeeContext` parameter — a structural difference from `LeaveRequestService` and `ApprovalService`, both of which take `request_context: RequestContext` on every relevant method after their own authorization capabilities were added (§2.2, §2.8).
- No `AttendanceAuthorizationEvaluator` (or equivalently named class) exists anywhere in the repository (§2.7).
- No `*AuthorizationDeniedError`-style exception, and no `403 Forbidden` branch, exists in `services/attendance_event.py`, `api/attendance_events.py`, `services/reconciliation.py`, or `api/reconciliation.py` (§2.9).
- `AttendanceEvent.employee_id` is caller-suppliable on `create` with no server-side derivation from the caller's own resolved identity, and mutable via `update` (§2.3).
- `HrEmployee.manager_id` and `HrEmployee.user_id` both exist and are already consumed by other authorization-integrated capabilities, but are not read anywhere in the Attendance or Reconciliation code path (§2.10).
- Two distinct, already-implemented authorization integration patterns exist in the repository (Approval Authorization's service-resolved-data-into-evaluator shape; Leave Authorization's `AuthorizationRequest.resource`-carrying shape) — repository evidence does not show these converging on one uniform template (§2.8).
- `AttendanceEvent.shift_id` and `HrEmployee.shift_id` are two independent, uncompared foreign keys to `shifts.id` (§2.4).

---

# 7. Governance Documentation State

Repository evidence shows a discrepancy between merged code and governance documents, stated here per the Evidence Rule and the Escalation Rule ("repository contradicts documentation"):

- `git log` confirms Leave Authorization is merged (`0a9b669 feat(auth): implement leave authorization capability`, `bdb475e` merge commit, PR #56) and its code is present and tested (`services/leave_authorization.py`, `LeaveRequestService._authorize`, `LeaveAuthorizationDeniedError`, `test_leave_authorization_evaluator.py`).
- `LeaveAuthorizationEvaluator`'s own docstring (`leave_authorization.py:9`) and `LeaveAuthorizationDeniedError`'s own docstring (`leave_request.py:28`) both cite `docs/architecture/capabilities/leave-authorization/decision.md` as the governing document for the "Owner Only" policy. **No such path exists in the repository** — confirmed by `find`/`Glob` returning no match for any `leave-authorization` directory or file anywhere under `docs/`.
- No discovery, policy-discovery, decision, or implementation-plan document exists anywhere in the repository for "Leave Authorization" as a named capability — confirmed by repository-wide search.
- `ARCHITECTURE_STATUS.md` (Last Updated: 2026-08-05) lists only "Approval Authorization" as `Implemented` under authorization capabilities and does not mention "Leave Authorization" in its Capability Status Summary or Authorization Adoption Status tables.
- `CAPABILITY_CATALOG.md` (Last Updated: 2026-08-05) lists only "Identity Context," "Authorization Foundation," "Approval Authorization," "Approval Workflow," and "HR Master Data" as `Implemented`; "Leave Authorization" does not appear anywhere in the document, including its Capability Overview table and Capability Maturity table.
- `MASTER_ARCHITECTURE_ROADMAP.md` (Last Updated: 2026-08-05) lists "Leave Authorization" as `Planned` in both its "Remaining Capability Authorizations" table (Phase 5) and its "Capability Roadmap" summary table.
- `TECHNICAL_DEBT_REGISTER.md` (Last Updated: 2026-08-05) TD-005 ("Authorization Foundation Consumer Coverage") states *"Implemented consumer: Approval Authorization"* and lists "Future capabilities still require... discovery... before authorization integration" — not reflecting Leave Authorization as an already-implemented second consumer.
- `ARCHITECTURE_STATUS.md`'s own stated governance rule: *"All implemented architecture capabilities must have: ADR, discovery evidence, capability decision, implementation plan, validation result."* No such document set exists in the repository for Leave Authorization, per the search above.

This finding is reported per the Escalation Rule and is not resolved here. It is directly relevant to this discovery because "Attendance Authorization" is positioned immediately after "Leave Authorization" in the roadmap's stated capability sequence (§5), and the nature/completeness of Leave Authorization's own governance trail is unclear from the documents that are supposed to record it.

---

# 8. Open Questions

Repository evidence does not answer the following:

- Whether the governance-document gap identified in §7 (Leave Authorization merged without a discoverable ADR, discovery, decision, or implementation-plan document) reflects documents that exist outside this repository, documents not yet written, or a process deviation — the repository alone cannot distinguish these.
- Whether `ReconciliationService`/`GET /hr/reconciliation` (§2.5) is considered in scope for "Attendance Authorization" as named in the roadmap, given it is not listed as its own capability in `CAPABILITY_CATALOG.md` or `MASTER_ARCHITECTURE_ROADMAP.md`, yet reads the same `AttendanceEvent` data and has the same absence of authorization.
- Whether `AttendanceEvent.employee_id` (§2.3) is intended to remain caller-suppliable on `create`/`update` once authorization is added, or whether that is itself part of what an authorization policy would need to constrain.
- Whether `AttendanceEvent.source` (`SYSTEM`/`MANUAL`/`IMPORT`, `core/attendance.py:13-18`) has any bearing on who is permitted to act on a given event — no code path currently branches on `source` for any purpose, authorization or otherwise.
- Whether the two structurally different authorization-integration shapes already in the repository (Approval Authorization's manager-resolution-in-service shape; Leave Authorization's resource-carrying shape, §2.8) are both considered valid precedent for a third capability, or whether one is preferred — repository evidence shows both exist and both work, but does not indicate a preference.

---

# 9. Architectural Ambiguities

Listed per `AI_DISCOVERY_GUIDE.md`; not resolved here.

- The relationship, if any, between "Attendance Authorization" (named in the roadmap) and `ReconciliationService`/`GET /hr/reconciliation` (an existing, unnamed-in-governance-docs consumer of the same `AttendanceEvent` data) is not established by repository evidence.
- `AttendanceEvent.shift_id` and `HrEmployee.shift_id` are independent, uncompared fields (§2.4); whether any future authorization or business rule is expected to relate them is not decidable from the repository.
- The completeness and location of Leave Authorization's own governance trail (§7) is unresolved and directly precedes Attendance Authorization in the roadmap's stated sequence.
- `AttendanceEvent.employee_id`'s caller-suppliable, unscoped nature on `create`/`update` (§2.3) is a fact about the current schema and service, not an interpretation of what should change.

---

# 10. Recommended Next Step

```
Policy Discovery
```

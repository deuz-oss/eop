# Attendance Authorization — Implementation Plan

**Capability:** Attendance Authorization

**Status:** Approved — Ready for Implementation

**Version:** 1

**Depends On**

- ADR-006 — Employee Context Resolution
- ADR-007 — Authorization Foundation
- Attendance Authorization Discovery
- Attendance Authorization Policy Discovery
- Attendance Authorization Decision

---

# 1. Summary

This plan implements Owner Only authorization for `AttendanceEvent.create`/`get`/`update`/`delete`, and caller-scoping for `list`/`list_paginated`, per the approved Capability Decision. It reuses the Authorization Foundation and the `AuthorizationRequest.resource` extension point exactly as Leave Authorization already does, adding one new evaluator and wiring it through the existing `AttendanceEventService`/`api/attendance_events.py` shape. No new architectural concept, no new ADR, and no schema/migration change are required.

Scope is strictly limited to `AttendanceEventService` and the Attendance Event API. `ReconciliationService`, Approval, Payroll, Reporting, Enterprise Authorization, RBAC, and any permission model are explicitly excluded, per the Capability Decision's boundary ruling (§1 of `decision.md`) and this plan's own Out of Scope section (§9).

This document is a plan only. No production code, no test code, and no ADR are created by it.

---

# 2. Scope

Implement authorization only for:

- `AttendanceEventService` (`services/api/src/eop_api/services/attendance_event.py`)
- Attendance Event API (`services/api/src/eop_api/api/attendance_events.py`)

## Out of Scope (restated from the Decision, binding on implementation)

Do not include:

- `ReconciliationService` / `GET /hr/reconciliation`
- Approval (`ApprovalService`, `ApprovalAuthorizationEvaluator`, ADR-008)
- Payroll
- Reporting
- Enterprise Authorization
- RBAC
- Permission Model
- Manager access
- Role checks
- Hybrid policy
- `source`-based authorization (`EventSource.SYSTEM`/`MANUAL`/`IMPORT` do not affect the rule)

---

# 3. Architecture

Reuse the existing Authorization Foundation exactly — no new abstraction, no modification to `AuthorizationService`, `AuthorizationEvaluator`, or `AuthorizationDecision`.

```
API
  ↓
AttendanceEventService
  ↓
AuthorizationService
  ↓
AttendanceAuthorizationEvaluator
  ↓
Repository
```

Rules:

- No layer skipping. The API never calls `AuthorizationService`/`AttendanceAuthorizationEvaluator` directly; it calls `AttendanceEventService` only.
- Repository remains persistence-only. `AttendanceEventRepository` gains no authorization awareness and is not called by `AttendanceAuthorizationEvaluator`.
- `AttendanceAuthorizationEvaluator` must never access repositories, the database session, or any `uow`. It receives `resource` already resolved by `AttendanceEventService`.

This is structurally identical to Leave Authorization's integration (`LeaveRequestService` → `AuthorizationService` → `LeaveAuthorizationEvaluator`), substituting the resource type and rule only.

---

# 4. Authorization Policy

Selected policy (per `decision.md` §4):

```
Owner Only
```

Rule:

```
AttendanceEvent.employee_id
==
RequestContext.employee_context.employee.id
```

No other authorization predicate shall be introduced.

---

# 5. Authorization Flow

```
CurrentUser

↓

CurrentEmployeeContext

↓

CurrentRequestContext

↓

AuthorizationRequest (context, resource)

↓

AuthorizationService

↓

AttendanceAuthorizationEvaluator

↓

AuthorizationDecision

↓

AttendanceEventService
```

The Service resolves the `AttendanceEvent` resource:

- `create` — resource is the `AttendanceEventCreate` payload (not yet persisted); `employee_id` is read directly from the submitted payload.
- `get`/`update`/`delete` — resource is the already-loaded `AttendanceEvent` row, fetched before authorization is evaluated.

The Service constructs:

```python
AuthorizationRequest(
    context=request_context,
    resource=resource,
)
```

The Service invokes:

```python
AuthorizationService(
    AttendanceAuthorizationEvaluator()
).authorize(authorization_request)
```

The evaluator performs only policy evaluation — it reads `request.resource.employee_id` and `request.context.employee_context.employee.id`, and returns `AuthorizationDecision`. It performs no persistence, no repository call, and no workflow.

A denied decision raises `AttendanceAuthorizationDeniedError`, thrown only by `AttendanceEventService`, never by `AttendanceAuthorizationEvaluator` or `AuthorizationService` themselves — mirroring `LeaveAuthorizationDeniedError`'s existing contract exactly.

## Method-Level Sequencing

| Method | Order |
|---|---|
| `create` | 1. `HrEmployeeRepository.exists(employee_id)` → `EmployeeNotFoundError` if missing. 2. `ShiftRepository.exists(shift_id)` → `ShiftNotFoundError` if missing. 3. `_authorize(data, request_context)` → `AttendanceAuthorizationDeniedError` if denied. 4. Create. |
| `get` | 1. `repo.get(event_id)` → return `None` if missing. 2. `_authorize(event, request_context)` → `AttendanceAuthorizationDeniedError` if denied. |
| `update` | 1. `repo.get(event_id)` → return `None` if missing. 2. `_authorize(event, request_context)` against the **currently-loaded** event → `AttendanceAuthorizationDeniedError` if denied. 3. `HrEmployeeRepository.exists`/`ShiftRepository.exists` if `employee_id`/`shift_id` are being changed. 4. Update. |
| `delete` | 1. `repo.get(event_id)` → return `None`/`False` if missing (via existing `repo.delete` contract). 2. `_authorize(event, request_context)` → `AttendanceAuthorizationDeniedError` if denied. 3. Delete. |
| `list` | No per-item authorization. Fetch all via `repo.list()`, filter in-memory to `event.employee_id == request_context.employee_context.employee.id`, mirroring `LeaveRequestService.list` exactly (`AttendanceEventRepository`, like `LeaveRequestRepository`, has no filter parameter on its inherited `BaseRepository.list()`). |
| `list_paginated` | No per-item authorization. Force `employee_id` into `FilterParams`, overriding any caller-supplied value, then delegate to `AttendanceEventRepository.paginate` — `employee_id` is already a `FILTERABLE_FIELD` on this repository, so no repository change is required. Mirrors `LeaveRequestService.list_paginated` exactly. |

Existence-check-before-authorization ordering on `create`/`update` matches the codebase's existing convention (`LeaveRequestService.create`/`update` check entity existence before invoking `_authorize`) and is preserved rather than reordered, to avoid introducing a new sequencing convention outside this plan's scope.

---

# 6. Operations

Protected (per-request authorization):

- `create`
- `get`
- `update`
- `delete`

Collection endpoints (scoped, not per-item authorized):

- `list`
- `list_paginated`

must return only the authenticated employee's own `AttendanceEvent` records (§5, method-level sequencing).

---

# 7. `AttendanceAuthorizationEvaluator`

## Responsibilities

Owns:

- Owner Only policy evaluation for `AttendanceEvent`

Consumes:

- `AuthorizationRequest` (`context`, `resource`)

Produces:

- `AuthorizationDecision`

Must remain:

- deterministic
- stateless
- side-effect free

Must not:

- access repositories
- execute workflow
- perform persistence
- translate HTTP
- mutate domain objects
- infer business policy beyond Owner Only

## Shape (planned, not implemented)

Subclasses `AuthorizationEvaluator`, matching `LeaveAuthorizationEvaluator`'s exact structure:

- `evaluate(request: AuthorizationRequest) -> AuthorizationDecision`
- Reads `request.resource` and `request.context.employee_context.employee.id`.
- `resource is None`, or `resource.employee_id != current_employee_id`, → `AuthorizationDecision(allowed=False, reason=...)`.
- `resource.employee_id == current_employee_id` → `AuthorizationDecision(allowed=True)`.

No constructor arguments, matching `LeaveAuthorizationEvaluator` (unlike `ApprovalAuthorizationEvaluator`, which takes a pre-resolved `manager_id` — not applicable here, since Owner Only needs no data beyond what `AuthorizationRequest` already carries).

---

# 8. `AuthorizationService`

No change. Continues to coordinate evaluator invocation only; must not evaluate Owner Only itself, execute workflow, access repositories, or introduce Attendance-specific policy.

---

# 9. `AttendanceEventService`

`AttendanceEventService` remains the workflow/CRUD orchestrator. Before any protected operation:

1. Resolve the resource (§5).
2. Build `AuthorizationRequest`.
3. Invoke `AuthorizationService(AttendanceAuthorizationEvaluator())`.
4. Receive `AuthorizationDecision`.
5. Raise `AttendanceAuthorizationDeniedError` when denied.
6. Continue the existing CRUD logic when allowed.

`AttendanceEventService` must never evaluate the Owner Only rule directly — all comparison logic stays inside `AttendanceAuthorizationEvaluator`, delegated to via a private `_authorize` method, mirroring `LeaveRequestService._authorize` exactly.

Every public method (`create`, `get`, `list`, `list_paginated`, `update`, `delete`) gains a required `request_context: RequestContext` parameter. This is a breaking signature change to an internal service class with no other production caller besides `api/attendance_events.py` (confirmed by discovery — no other file imports `AttendanceEventService`), so no compatibility shim is introduced.

---

# 10. Exception

Create:

```python
class AttendanceAuthorizationDeniedError(Exception):
    """Raised when the Attendance Authorization Policy (Owner Only) denies
    a create/get/update/delete call."""
```

Thrown only when:

```
AuthorizationDecision.allowed == False
```

No other component may throw this exception.

---

# 11. API Changes

`api/attendance_events.py`:

- Replace `_: CurrentUser` with `request_context: CurrentRequestContext` on every route (`create`, `get`, `list`, `list_paginated`, `update`, `delete`) — `list`/`list_paginated` need `request_context` too, to pass through to the now-scoping service methods (§5, §6), even though they raise no `403`.
- Map `AttendanceAuthorizationDeniedError` → `HTTP 403 Forbidden` on `create`, `get`, `update`, `delete` — the same four operations that call `_authorize` (§5). `list`/`list_paginated` do not need this mapping, since they never raise it.
- Existing `EmployeeNotFoundError`/`ShiftNotFoundError` → `404`, and `None`/`False` return → `404`, mappings are unchanged.

Do not change approval endpoints. `AttendanceEvent` has no approve/reject surface (no `status` field, confirmed by discovery) — this note is carried forward from the instructions for completeness; there is no approval endpoint in `api/attendance_events.py` to leave unchanged or otherwise.

API remains responsible only for: authentication, request-context resolution, validation, HTTP translation. API must not contain authorization logic.

---

# 12. Dependencies

Reuse existing platform components. No new platform abstraction shall be introduced.

- `CurrentUser`
- `CurrentEmployeeContext`
- `CurrentRequestContext`
- `EmployeeContext`
- `RequestContext`
- `AuthorizationRequest` (including the existing `resource` field — already introduced by Leave Authorization; not modified again by this plan)
- `AuthorizationService`
- `AuthorizationDecision`

---

# 13. Files To Create

- `services/api/src/eop_api/services/attendance_authorization.py` — `AttendanceAuthorizationEvaluator` (§7).

---

# 14. Files To Modify

- `services/api/src/eop_api/services/attendance_event.py` — add `request_context: RequestContext` parameter to all six public methods; add private `_authorize` method; add `AttendanceAuthorizationDeniedError`; scope `list`/`list_paginated` to the caller's own `employee_id` (§5, §9, §10).
- `services/api/src/eop_api/api/attendance_events.py` — switch routes from `CurrentUser` to `CurrentRequestContext`; add `403` exception mapping (§11).
- `services/api/tests/test_attendance_event_service.py` — required, not optional: every existing test constructs `AttendanceEventService` calls without a `request_context` argument (confirmed by discovery); adding a required parameter to six public methods breaks every existing call site, so this file must be updated as part of the same change, not as a follow-up. New coverage per §15.
- `services/api/tests/test_attendance_events_api.py` — required, not optional, for the same reason: every existing request goes through `CurrentUser`-authenticated routes with no `EmployeeContext`/`HrEmployee` fixture; switching to `CurrentRequestContext` requires each test's fixture to provision a linked `HrEmployee` (`user_id`), the same fixture shape `test_leave_requests_api.py` already established. New coverage per §15.

No repository, model, schema, or migration file is created or modified. `AttendanceEventRepository`'s `FILTERABLE_FIELDS` already includes `employee_id` (confirmed by discovery) — no repository change is needed to support `list_paginated` scoping (§5).

This document does not modify any of the files above. It records what a later implementation phase must change.

---

# 15. Tests (planned coverage)

## Unit Tests — `AttendanceAuthorizationEvaluator`

New file: `test_attendance_authorization_evaluator.py`, in-memory, no database, mirroring `test_leave_authorization_evaluator.py`'s exact structure:

- owner → allow
- non-owner → deny
- missing `resource` → deny, not raise

## Service Tests — `AttendanceEventService` (DB-backed)

Additions to `test_attendance_event_service.py`, mirroring `test_leave_request_service.py`'s fixture shape (real `HrEmployee`/`User` rows, `request_context` built per test):

- create: owner allowed / non-owner forbidden
- get: owner allowed / non-owner forbidden
- update: owner allowed / non-owner forbidden
- delete: owner allowed / non-owner forbidden
- list: returns only the caller's own records
- list_paginated: returns only the caller's own records, including when a different `employee_id` is supplied in `filters`
- existing non-authorization behavior (missing employee, missing shift, not-found handling) continues to pass unchanged, with `request_context` added to each call site

## API Tests — `api/attendance_events.py` (DB-backed)

Additions to `test_attendance_events_api.py`, mirroring `test_leave_requests_api.py`'s pattern:

- `403` on create/get/update/delete for non-owner
- ownership scoping on list/list_paginated
- existing authentication-required and not-found tests continue to pass unchanged

Coverage required, restated from the instructions:

- owner allowed
- non-owner forbidden
- list scoped
- paginated list scoped
- HTTP 403 mapping

Existing behavior unrelated to authorization must remain unchanged — no test asserting current CRUD/validation behavior (missing employee, missing shift, date/field validation, not-found handling) should have its assertions altered, only its call sites updated to supply `request_context`.

---

# 16. Validation Plan

Execute, once implementation is complete:

```
ruff check .

mypy src

pytest
```

Regression scope: attendance events, authorization foundation, employee context. `ApprovalService`/approval endpoints and `ReconciliationService` are explicitly out of scope for this change (§2) and are not expected to be affected — a passing full test suite run should confirm this rather than assume it.

---

# 17. Success Criteria

Implementation is complete when:

- only the owning employee can create/get/update/delete their own `AttendanceEvent`
- non-owners receive `AuthorizationDecision(allowed=False)`, surfaced as `AttendanceAuthorizationDeniedError` → `403 Forbidden`
- `list`/`list_paginated` return only the caller's own records regardless of any caller-supplied `employee_id` filter
- `AttendanceEventService` contains no Owner Only comparison logic outside `_authorize`'s delegation
- `AttendanceAuthorizationEvaluator` performs no repository access
- Authorization Foundation's evaluation mechanism is unchanged
- `ReconciliationService`, Approval endpoints, and all other out-of-scope items (§2) are unmodified
- repository layer unchanged; no migration introduced
- architectural layering (API → Service → Evaluator/Foundation → Repository) preserved

---

# 18. Risks Carried Into Implementation

Restated from `decision.md` § Unresolved Risks — implementation must not attempt to independently resolve these; doing so would be a policy decision beyond Owner Only as approved, requiring its own future capability decision:

1. **`update`'s authorization check runs against the pre-update resource, not the submitted payload.** An owner can submit `AttendanceEventUpdate.employee_id` reassigning their own event to a different employee; `_authorize` (evaluated on the currently-loaded, owned event) will pass, and nothing separately re-checks the new `employee_id` value being written. This mirrors `LeaveRequestService.update`'s identical, pre-existing pattern. Implementation must reproduce this behavior, not silently fix it — closing it is a distinct policy question (e.g., "can an owner transfer their own record to another employee?") outside this plan's scope.
2. **No supported path for `SYSTEM`/`IMPORT`-sourced writes by a non-owner actor.** By design (§9 of `decision.md`), `source` does not affect authorization. Implementation must not add a `source`-based exemption.
3. **`ReconciliationService` remains unauthorized.** Out of scope (§2). Implementation must not extend `AttendanceAuthorizationEvaluator`, `AttendanceAuthorizationDeniedError`, or `CurrentRequestContext` into `services/reconciliation.py` or `api/reconciliation.py`.
4. **`EmployeeContext` resolution failure (TD-001) is inherited unchanged.** A caller with no or multiple linked `HrEmployee` rows will receive `HTTP 500` on any Attendance Authorization-gated route, via the same unresolved gap already present for Approval Authorization and Leave Authorization. Implementation must not add a capability-specific fix for this — resolution is centrally tracked in `TECHNICAL_DEBT_REGISTER.md` TD-001.
5. **Breaking signature change.** Adding a required `request_context` parameter to all six `AttendanceEventService` methods requires every existing call site (all in `api/attendance_events.py` and the two test files, §14) to be updated in the same change — there is no backward-compatible, additive way to introduce this parameter given the Decision's constraint that authorization apply to every listed operation.

---

# Architecture Contract

The following documents collectively define the implementation contract:

- ADR-006
- ADR-007
- Attendance Authorization Discovery
- Attendance Authorization Policy Discovery
- Attendance Authorization Decision

Implementation shall conform to these documents.

If repository evidence contradicts any approved architectural document: implementation must stop immediately. Implementation must not reinterpret Owner Only, the capability boundary (§2), or the `source` decision (§9 of `decision.md`). Architecture Governance is required before implementation may continue.

No architectural decision may be made during implementation.

---

# Escalation Matrix

Implementation must stop immediately under the following conditions.

## Business Policy Ambiguity

Examples: the Owner Only rule cannot be evaluated for a given call site; a resource shape other than `AttendanceEventCreate`/`AttendanceEvent` is encountered.

Action: Stop. Escalate to Architecture Governance.

## Repository Contradiction

Examples: `AttendanceEventRepository` behavior contradicts this plan; `AttendanceEvent.employee_id` is found to be nullable or otherwise not directly comparable to `EmployeeContext.employee.id`.

Action: Stop. Escalate.

## Missing Capability

Examples: implementation requires manager access, role checks, a permission model, or a `source`-aware actor concept to proceed.

Action: Stop. Do not expand capability scope. These are explicitly out of scope (§2, §9).

## Architecture Conflict

Examples: implementation requires changes to ADR-006, ADR-007, or this plan itself.

Action: Stop immediately. Architecture must be revised before implementation resumes.

---

# Architecture Review Checklist

Before merge, verify:

- [ ] Authorization Foundation unchanged
- [ ] `AttendanceEventService` remains CRUD-orchestration-only outside `_authorize`'s delegation
- [ ] `AttendanceAuthorizationEvaluator` owns Owner Only evaluation, no repository access
- [ ] `AuthorizationService` orchestrates evaluation only
- [ ] API performs HTTP translation only
- [ ] Repository contains no authorization logic
- [ ] `list`/`list_paginated` scoped correctly, including when a caller-supplied `employee_id` filter is present
- [ ] No manager access introduced
- [ ] No role-based access introduced
- [ ] No `source`-based authorization introduced
- [ ] `ReconciliationService` unmodified
- [ ] Approval endpoints unmodified
- [ ] Layering preserved
- [ ] No database schema changes
- [ ] All five risks in §18 reproduced/documented, not silently resolved

---

# References

- ADR-006
- ADR-007
- Attendance Authorization Discovery
- Attendance Authorization Policy Discovery
- Attendance Authorization Decision
- Leave Authorization Implementation Plan (structural precedent)
- MASTER_ARCHITECTURE_BLUEPRINT.md

# Leave Authorization — Discovery

**Status:** Complete

**Capability:** Leave Authorization

**Owner:** EOP Architecture Governance

---

# Purpose

This document records repository evidence for the Leave Authorization capability.

Discovery exists to understand the current repository state.

It does not define architecture.

**Synchronization note:** Leave Authorization was implemented and merged (`0a9b669 feat(auth): implement leave authorization capability`, PR #56) before this discovery record was written. This document reconstructs the discovery findings from repository evidence — the pre-implementation state (via `git show`/`git log` on the parent commit), the implementation itself, and the surrounding capability set — for governance-trail synchronization, per `ARCHITECTURE_STATUS.md`'s requirement that every implemented capability have discovery evidence on record.

---

# Discovery Scope

The following areas were inspected:

- `LeaveRequest` current state before authorization (via `git show 0a9b669` diff and the immediately preceding commit)
- `services/leave_request.py`, `api/leave_requests.py` (post-implementation)
- Existing Approval Authorization separation: `services/approval.py`, `services/approval_authorization.py` (ADR-008)
- Authorization Foundation integration point: `services/authorization.py`, `services/authorization_evaluator.py`, `services/authorization_request.py`, `services/authorization_decision.py` (ADR-007)
- Identity Context: `services/employee_context.py`, `dependencies/employee_context.py` (ADR-006)
- `ADR-007-authorization-foundation.md`, `ADR-008-Approval Authorization Policy Model`
- `docs/architecture/capabilities/approval-authorization/` (prior capability precedent)
- Test suite: `test_leave_request_service.py`, `test_leave_requests_api.py`, `test_leave_authorization_evaluator.py`, `test_authorization_request.py`

---

# 1. Repository Summary

Prior to commit `0a9b669`, `LeaveRequestService` (`services/leave_request.py`) was CRUD-only: its `create`/`get`/`list`/`list_paginated`/`update`/`delete` methods took no `RequestContext` parameter, validated only `employee_id` existence and `start_date <= end_date`, and every `api/leave_requests.py` route depended on `CurrentUser` only (authentication) — structurally identical to the current `AttendanceEventService`/`api/attendance_events.py` shape (confirmed by direct comparison; see the Attendance Authorization discovery for the still-current version of this same shape).

At the same commit, Approval Authorization (ADR-008, PR-053) was already merged and provided a first, working example of a capability integrating Authorization Foundation (ADR-007) for a different resource — `LeaveRequest.approve`/`.reject`, orchestrated by the separate `ApprovalService`, not by `LeaveRequestService`.

Commit `0a9b669` added Leave Authorization by: creating `services/leave_authorization.py` (`LeaveAuthorizationEvaluator`); adding a `request_context: RequestContext` parameter and a private `_authorize` method to every `LeaveRequestService` method; adding `LeaveAuthorizationDeniedError`; switching `api/leave_requests.py`'s CRUD routes from `CurrentUser` to `CurrentRequestContext`; and extending `AuthorizationRequest` (`services/authorization_request.py`) with a new `resource: Any | None = None` field. This last change touches Authorization Foundation itself — see §4.

---

# 2. Repository Evidence

## 2.1 `LeaveRequest` State Before Authorization

Confirmed via `git show 0a9b669 --stat`: the pre-authorization `services/leave_request.py` and `api/leave_requests.py` had no authorization-related code. `LeaveRequestService`'s constructor (`uow_factory`-only) and CRUD method shapes were unchanged by the commit — only new parameters, a new private method, and new imports were added; no method was removed or restructured.

`test_leave_request_service.py` and `test_leave_requests_api.py` both grew substantially in the same commit (108 and 42 lines changed respectively in the two source files, versus 247 and 330 lines changed in their corresponding test files) — the bulk of the change is test coverage for the new authorization behavior, not the behavior itself.

## 2.2 Existing Approval Authorization Separation

`ApprovalService` (`services/approval.py`) and `LeaveRequestService` (`services/leave_request.py`) remain two separate services after this commit: `ApprovalService` continues to own `approve`/`reject` transitions for `LeaveRequest`/`OvertimeRequest`/`Timesheet` (ADR-008, Manager Approval policy), while `LeaveRequestService` owns `create`/`get`/`list`/`list_paginated`/`update`/`delete` (now gated by Leave Authorization, Owner Only policy). No method moved between the two services. `LeaveRequestService` does not import `ApprovalService`, `ApprovalAuthorizationEvaluator`, or any Approval-specific symbol, and vice versa — the two authorization policies (Owner Only vs. Manager Approval) apply to disjoint sets of operations on the same `LeaveRequest` row.

## 2.3 Authorization Foundation Integration Point

`LeaveRequestService._authorize` (`leave_request.py:207-222`) constructs `AuthorizationRequest(context=request_context, resource=resource)` and calls `AuthorizationService(LeaveAuthorizationEvaluator()).authorize(...)`, raising `LeaveAuthorizationDeniedError` on denial. This is the same `AuthorizationService`/`AuthorizationRequest`/`AuthorizationDecision` triad Approval Authorization already uses (§2.2) — no new orchestration mechanism was introduced.

`resource` is populated differently per call site: the `LeaveRequestCreate` payload on `create` (not yet a persisted `LeaveRequest`), or the already-loaded `LeaveRequest` row on `get`/`update`/`delete` (`leave_request.py:78-206`). `LeaveAuthorizationEvaluator.evaluate` (`leave_authorization.py:17-24`) reads `request.resource.employee_id` — meaning the same evaluator method executes against two different Python types depending on which method called it, unified only by both exposing an `employee_id` attribute.

## 2.4 Authorization Foundation Modification

Commit `0a9b669` modified `services/authorization_request.py`, a Foundation-owned file (ADR-007), adding `resource: Any | None = None` to `AuthorizationRequest` (confirmed via `git show 0a9b669 -- services/api/src/eop_api/services/authorization_request.py`). The field's own docstring states it is "the extension point anticipated by the original design" and defaults to `None` so "every existing caller (e.g. Approval Authorization, ADR-008) is unaffected" — Approval Authorization's own call site (`services/approval.py:227`, `AuthorizationRequest(context=request_context)`) was not changed by this commit and continues to omit `resource`.

This is evidence that Leave Authorization's implementation was not fully confined to new files — it made one additive, backward-compatible change to an existing Authorization Foundation file. `resource` is typed `Any | None`, carrying no shape constraint at the Foundation level (§4, Architectural Ambiguities).

## 2.5 Authorization Gaps at the Time of Discovery

Before this commit, the same gaps documented in `docs/architecture/capabilities/approval-authorization/discovery.md` for Approval applied identically to `LeaveRequestService`'s own CRUD surface: authentication-only protection, no ownership check, `employee_id` freely settable on create/update, and no `403 Forbidden` path anywhere in `api/leave_requests.py`'s non-approval routes.

---

# 3. Current Architecture

```
Client
  │
  ▼
API Router (api/leave_requests.py — create/get/list/update/delete routes)
  │  CurrentRequestContext (CurrentUser + EmployeeContext, resolved)
  ▼
LeaveRequestService (services/leave_request.py)
  │  _authorize: AuthorizationRequest(context, resource) → AuthorizationService
  │              → LeaveAuthorizationEvaluator → AuthorizationDecision
  │  deny → LeaveAuthorizationDeniedError → 403 Forbidden
  ▼
LeaveRequestRepository
  │
  ▼
Database (leave_requests)
```

`approve`/`reject` routes on the same `LeaveRequest` resource continue to run through the separate `ApprovalService` flow (Manager Approval, ADR-008), unchanged by this commit — see `docs/architecture/capabilities/approval-authorization/discovery.md` §3 for that flow.

---

# 4. Open Questions

Repository evidence does not answer the following:

- Whether extending `AuthorizationRequest` with `resource: Any | None` (§2.4) required its own architecture decision, or whether ADR-007's "remains replaceable" / "future capability can add such fields" language was treated as sufficient prior authorization for this change.
- Whether `resource`'s untyped (`Any | None`) shape is intended to remain untyped as more capabilities adopt the resource-carrying pattern, or whether a narrower type is expected once a second consumer of `resource` exists.

---

# 5. Recommended Next Step

```
Policy Discovery
```

(Reconstructed for governance-trail synchronization — see `leave-authorization/policy-discovery.md`.)

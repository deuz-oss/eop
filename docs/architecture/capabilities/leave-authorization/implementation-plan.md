# Leave Authorization — Implementation Plan

**Capability:** Leave Authorization

**Status:** Completed (retroactively documented)

**Version:** 1

**Depends On**

- ADR-006 — Employee Context Resolution
- ADR-007 — Authorization Foundation
- ADR-008 — Approval Authorization Policy Model (structural precedent)
- Leave Authorization Discovery
- Leave Authorization Policy Discovery
- Leave Authorization Decision

**Synchronization note:** This plan records an implementation that is already complete and merged (`0a9b669 feat(auth): implement leave authorization capability`, PR #56). It is written retroactively, from the actual diff (`git show 0a9b669 --stat`), for governance-trail synchronization — not as a forward-looking plan.

---

# Objective

Implement Leave Authorization (Owner Only) using the existing Authorization Foundation, gating `LeaveRequestService`'s CRUD surface, consistent with the Capability Decision.

---

# Scope (as implemented)

- `LeaveAuthorizationEvaluator`
- `LeaveAuthorizationDeniedError`
- `LeaveRequestService` authorization integration (`_authorize`, `request_context` parameter on every public method)
- `AuthorizationRequest.resource` extension field (Authorization Foundation, additive)
- API integration: `api/leave_requests.py` CRUD routes switched from `CurrentUser` to `CurrentRequestContext`, `403 Forbidden` mapping for `LeaveAuthorizationDeniedError`
- Unit tests, service tests, API tests

---

# Out of Scope (confirmed not implemented)

- manager access
- role-based access
- hybrid authorization
- delegated access
- workflow assignment
- permission model
- RBAC redesign
- Authorization Foundation evaluation-mechanism redesign
- Employee Context redesign
- `ApprovalService`/Approval Authorization changes
- repository redesign
- database schema changes

Confirmed by `git show 0a9b669 --stat`: no model, repository, or migration file appears in the commit's file list.

---

# Business Rule

Leave Authorization Policy is defined by the Capability Decision (`leave-authorization/decision.md`).

```
LeaveRequest.employee_id (via AuthorizationRequest.resource)
==
RequestContext.employee_context.employee.id
```

No additional authorization predicate was introduced.

---

# Authorization Flow (as implemented)

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

LeaveAuthorizationEvaluator

↓

AuthorizationDecision

↓

LeaveRequestService
```

Every `create`/`get`/`update`/`delete` call passes through `LeaveRequestService._authorize` before proceeding. `list`/`list_paginated` are scoped to the caller's own `employee_id` instead (per the Decision — no per-item resource to evaluate a decision against for a collection read).

---

# Files Created

- `services/api/src/eop_api/services/leave_authorization.py` — `LeaveAuthorizationEvaluator`, subclassing `AuthorizationEvaluator`, evaluating `resource.employee_id == context.employee_context.employee.id`.
- `services/api/tests/test_leave_authorization_evaluator.py` — unit tests, in-memory (no database), mirroring `test_approval_authorization_evaluator.py`'s structure: owner allowed, non-owner denied, missing `resource` denied.

---

# Files Modified

- `services/api/src/eop_api/services/leave_request.py` — added `request_context: RequestContext` parameter to `create`/`get`/`list`/`list_paginated`/`update`/`delete`; added private `_authorize` method; added `LeaveAuthorizationDeniedError`; scoped `list`/`list_paginated` to the caller's own `employee_id`.
- `services/api/src/eop_api/api/leave_requests.py` — switched CRUD routes' dependency from `CurrentUser` to `CurrentRequestContext`; added `LeaveAuthorizationDeniedError` → `403 Forbidden` exception mapping on `create`/`get`/`update`/`delete`.
- `services/api/src/eop_api/services/authorization_request.py` — added `resource: Any | None = None` field to `AuthorizationRequest` (Authorization Foundation extension point; additive, default-`None`, does not change `AuthorizationService.authorize`'s signature or behavior for existing callers such as Approval Authorization).

## Related Tests Modified

- `services/api/tests/test_leave_request_service.py` — extended with authorization-scoped fixtures (`_request_context(employee_id)`, DB-backed via real `HrEmployee` rows) and denial-path tests (`test_create_denied_for_non_owner`, `test_get_denied_for_non_owner`, `test_update_denied_for_non_owner`, `test_delete_denied_for_non_owner`, `test_list_returns_only_owned`, `test_list_paginated_returns_only_owned`).
- `services/api/tests/test_leave_requests_api.py` — extended with API-level forbidden-path tests (`test_create_leave_request_forbidden_for_non_owner`, `test_get_leave_request_forbidden`, `test_update_leave_request_forbidden`, `test_delete_leave_request_forbidden`, each asserting `response.status_code == 403`) and ownership-scoping tests (`test_list_leave_requests_returns_only_owned`, `test_list_leave_requests_paginated_returns_only_owned`).
- `services/api/tests/test_authorization_request.py` — extended with coverage for the new `resource` field (default `None`, explicit value).

---

# Dependencies

Reused existing platform components — no new platform abstraction was introduced beyond the additive `resource` field (§ Files Modified):

- `CurrentUser`
- `CurrentEmployeeContext`
- `CurrentRequestContext`
- `EmployeeContext`
- `AuthorizationRequest`
- `AuthorizationService`
- `AuthorizationDecision`

---

# Testing Strategy (as implemented)

## Unit Tests

`LeaveAuthorizationEvaluator` (`test_leave_authorization_evaluator.py`, in-memory, no database):

- owner → allow (`test_owner_is_allowed`)
- non-owner → deny (`test_non_owner_is_denied`)
- missing `resource` → deny, not raise (`test_missing_resource_is_denied`)

`AuthorizationRequest` (`test_authorization_request.py`): `resource` field default and explicit-value coverage.

## Service Tests (DB-backed)

`LeaveRequestService` (`test_leave_request_service.py`, real migration-managed tables, truncated per test):

- create/get/update/delete denied for non-owner
- list/list_paginated scoped to owner only
- pre-existing CRUD behavior (missing employee, invalid date range) unaffected

## API Tests (DB-backed)

`api/leave_requests.py` routes (`test_leave_requests_api.py`, `TestClient` against the real app):

- 403 on create/get/update/delete for non-owner
- ownership scoping on list/list_paginated
- authentication-required checks unchanged
- approve/reject routes (Approval Authorization, ADR-008) unaffected by this commit

---

# Validation

Execute:

```
ruff check .

mypy src

pytest
```

Regression scope: leave requests, authorization foundation, employee context, approval (unaffected-by-change confirmation).

---

# Success Criteria (met, per repository evidence)

- Only the owning employee can create/get/update/delete their own `LeaveRequest`.
- Non-owners receive `AuthorizationDecision(allowed=False)`, surfaced as `LeaveAuthorizationDeniedError` → `403 Forbidden`.
- `LeaveRequestService` contains no Owner Only comparison logic outside `_authorize`'s delegation.
- Authorization Foundation's evaluation mechanism is unchanged; only the additive `resource` field was introduced, confirmed non-breaking for Approval Authorization's existing call site.
- Repository layer unchanged; no migration in the commit.
- Architectural layering (API → Service → Evaluator/Foundation → Repository) preserved.

---

# Architecture Contract

The following documents collectively define the implementation contract:

- ADR-006
- ADR-007
- ADR-008
- Leave Authorization Discovery
- Leave Authorization Policy Discovery
- Leave Authorization Decision

Since this plan is retroactive, no escalation occurred during implementation per repository evidence — no contradiction between the merged code and ADR-006/ADR-007 was found during this synchronization review, with the one noted exception of the additive `AuthorizationRequest.resource` field (§ Files Modified), which repository evidence shows was anticipated by ADR-007's own "remains replaceable" / extension-point language rather than contradicting it.

---

# Architecture Review Checklist

- [x] Authorization Foundation's evaluation mechanism unchanged (only an additive field was introduced)
- [x] `LeaveRequestService` remains CRUD-orchestration-only outside `_authorize`'s delegation
- [x] `LeaveAuthorizationEvaluator` owns Owner Only evaluation
- [x] `AuthorizationService` orchestrates evaluation only
- [x] API performs HTTP translation only (`403` mapping)
- [x] Repository contains no authorization logic
- [x] No manager access introduced
- [x] No role-based access introduced
- [x] No delegated access introduced
- [x] Layering preserved
- [x] No database schema changes
- [ ] Formal Architecture Review sign-off recorded prior to merge — **not found in repository**; see `leave-authorization/architecture-review.md` for this synchronization's own review record

---

# References

- ADR-006
- ADR-007
- ADR-008
- Leave Authorization Discovery
- Leave Authorization Policy Discovery
- Leave Authorization Decision
- MASTER_ARCHITECTURE_BLUEPRINT.md

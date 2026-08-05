# Leave Authorization — Capability Decision

**Capability:** Leave Authorization

**Status:** Approved

**Version:** 1

**Owner:** Architecture

**Synchronization note:** Reconstructed from repository evidence for governance-trail synchronization — implementation already merged (`0a9b669`, PR #56) when this document was written.

---

# Purpose

This capability defines the Leave Authorization Policy governing `LeaveRequest.create`/`get`/`list`/`list_paginated`/`update`/`delete`.

It selects the business policy that consumes the Authorization Foundation introduced by ADR-007, for the `LeaveRequest` CRUD surface — distinct from Approval Authorization (ADR-008), which governs `approve`/`reject` on the same resource.

This decision intentionally defines **business policy** only.

It does **not** modify:

- Authorization Foundation's evaluation mechanism
- Authentication
- Identity Context
- Employee Context
- Approval Authorization (ADR-008)

---

# Background

The platform, at the time of implementation, already provided:

- Authentication
- Identity Context
- Employee Context
- Authorization Foundation
- Approval Authorization (ADR-008, Manager Approval, scoped to `approve`/`reject` only)

Repository Discovery established:

- `LeaveRequestService`'s CRUD methods required authentication only.
- No ownership, role, or manager check gated `create`/`get`/`list`/`update`/`delete`.
- `LeaveRequest.employee_id` was caller-suppliable with no scoping to the caller's own identity.

Policy Discovery evaluated the following candidate policies:

- Owner Only
- Manager Access
- Role Based
- Hybrid

Repository evidence showed that **Owner Only** was the only policy with full (not partial) repository support, requiring no new data model or role vocabulary.

---

# Decision

The platform adopts **Owner Only** as the Leave Authorization Policy.

Access to a given `LeaveRequest`'s `create`/`get`/`update`/`delete` operations is granted only to the employee who owns it. `list`/`list_paginated` are scoped to the caller's own `employee_id` rather than authorized per-item, since there is no single resource to evaluate a decision against for a collection read.

No other authorization rule participates in Leave Authorization.

---

# Authorization Rule

Access is granted only when the following condition is true:

```
LeaveRequest.employee_id
==
RequestContext.employee_context.employee.id
```

For `create`, `resource` is the `LeaveRequestCreate` payload (not yet persisted) — the same field, `employee_id`, is evaluated against the caller's resolved identity before the row is written.

No additional authorization predicate shall be evaluated.

---

# Architecture

```
CurrentUser
        │
        ▼
EmployeeContext
        │
        ▼
RequestContext
        │
        ▼
AuthorizationRequest (context, resource)
        │
        ▼
AuthorizationService
        │
        ▼
LeaveAuthorizationEvaluator
        │
        ▼
Owner Only Policy
        │
        ▼
AuthorizationDecision
        │
        ▼
LeaveRequestService
```

---

# Architecture Constraints

- **Service owns authorization orchestration.** `LeaveRequestService._authorize` is the sole caller of `AuthorizationService`/`LeaveAuthorizationEvaluator`; `LeaveRequestService`'s public methods never compare `employee_id` themselves.
- **Evaluator owns policy evaluation.** `LeaveAuthorizationEvaluator.evaluate` is the sole location where the Owner Only rule is expressed.
- **Evaluator must not access repository.** `LeaveAuthorizationEvaluator` receives `resource` already resolved by `LeaveRequestService` (via `AuthorizationRequest.resource`) and performs no persistence or repository call of its own.
- **Authorization Foundation remains policy agnostic.** `AuthorizationService`/`AuthorizationEvaluator`/`AuthorizationDecision` carry no Owner Only-specific logic. The one Foundation-level change this capability required — adding `resource: Any | None = None` to `AuthorizationRequest` (`services/authorization_request.py`) — is an opaque, additive extension point (default `None`, does not alter `AuthorizationService.authorize`'s signature or behavior for existing callers) and does not embed Leave-specific policy into the Foundation. See `leave-authorization/discovery.md` §2.4 for the underlying evidence.

---

# Responsibilities

## Authorization Foundation

Owns:

- `AuthorizationRequest` (including the `resource` extension point)
- `AuthorizationDecision`
- `AuthorizationEvaluator`
- `AuthorizationService`

Does **not** own:

- Owner Only policy
- any other capability's policy

## `LeaveAuthorizationEvaluator`

Owns:

- Owner Only policy evaluation

Consumes:

- `AuthorizationRequest` (`context`, `resource`)

Produces:

- `AuthorizationDecision`

Must remain:

- deterministic
- stateless
- policy-focused

Must not:

- execute workflow
- access HTTP
- perform persistence
- perform repository orchestration

## `LeaveRequestService`

Owns:

- `LeaveRequest` CRUD orchestration
- authorization invocation via `_authorize`
- repository coordination

Consumes:

- `AuthorizationDecision`

Must never:

- evaluate authorization itself
- infer manager hierarchy
- contain Owner Only comparison logic outside `_authorize`'s delegation

## API

Owns:

- authentication (`CurrentUser`)
- request-context resolution (`CurrentRequestContext`)
- HTTP mapping (`LeaveAuthorizationDeniedError` → `403 Forbidden`)

Must never:

- evaluate authorization
- determine ownership

---

# Repository Evidence

Repository already contained, before this capability's implementation:

- `LeaveRequest.employee_id`
- `EmployeeContext`
- `RequestContext`
- Authorization Foundation
- `LeaveRequestService`

No new business relationship was required. No database redesign was required.

---

# Explicit Constraints

Implementation shall:

- evaluate only `resource.employee_id == context.employee_context.employee.id`
- consume `EmployeeContext`/`RequestContext`
- produce `AuthorizationDecision`
- integrate through `AuthorizationService`
- preserve existing layering

Implementation shall not:

- introduce manager-based access
- introduce role-based access
- introduce delegated access
- redesign `LeaveRequestService`'s CRUD behavior beyond authorization
- embed Owner Only policy logic in Authorization Foundation

---

# Explicit Exclusions

The following are explicitly outside the scope of this policy:

- manager access to a subordinate's `LeaveRequest`
- HR administrator override
- role-based access
- delegated access
- workflow assignment
- hybrid authorization

---

# Deferred Capabilities

Future capabilities may extend Leave Authorization with:

- manager access
- role-based access
- hybrid authorization
- delegated access

Such capabilities extend this policy. They do not replace the Authorization Foundation.

---

# Alternatives Considered

## Manager Access

Rejected for this initial policy. Repository evidence distinguishes "manager may approve" (ADR-008) from "manager may edit/view" — no repository evidence supports collapsing the two.

## Role Based

Rejected for this initial policy. Repository contains RBAC infrastructure but no leave-specific or HR-specific role vocabulary.

## Hybrid

Rejected for this initial policy. Depends on Manager Access and/or Role Based, both individually unresolved.

---

# Consequences

Leave Authorization now has an explicit business policy, distinct from and non-overlapping with Approval Authorization.

Authorization Foundation gained one opaque, additive extension point (`AuthorizationRequest.resource`) but remains policy-agnostic.

`LeaveRequestService` remains the sole owner of `LeaveRequest` CRUD orchestration; authorization logic is fully delegated.

---

# Risks

Current policy supports only the owning employee. Any assisted/proxy/administrative leave-request workflow will require a future capability extension.

`AuthorizationRequest.resource` is typed `Any | None` — the Foundation carries no shape guarantee for it; each Evaluator that reads it is individually responsible for handling an unexpected or missing shape (`LeaveAuthorizationEvaluator` already handles `resource is None`, per its own implementation).

---

# Success Criteria

The capability is considered successful when:

- only the owning employee can create/get/update/delete their own `LeaveRequest`
- non-owners are denied with `403 Forbidden`
- Authorization Foundation's evaluation mechanism remains unchanged (only the additive `resource` field was introduced)
- `LeaveRequestService` contains no Owner Only comparison logic outside `_authorize`'s delegation
- layering remains preserved
- no database schema changes were required

---

# References

- ADR-006 — Employee Context Resolution
- ADR-007 — Authorization Foundation
- ADR-008 — Approval Authorization Policy Model (structural precedent, distinct policy)
- Leave Authorization Discovery
- Leave Authorization Policy Discovery
- MASTER_ARCHITECTURE_BLUEPRINT.md

# Attendance Authorization — Capability Decision

**Capability:** Attendance Authorization

**Status:** Approved

**Version:** 1

**Owner:** Architecture

---

# Purpose

This capability defines the Attendance Authorization Policy governing `AttendanceEvent` create/get/update/delete.

It selects the business policy that consumes the Authorization Foundation introduced by ADR-007, building on the two existing capability-level precedents already in the repository: Approval Authorization (ADR-008, Manager Approval) and Leave Authorization (Owner Only).

This decision intentionally defines **business policy and capability boundary** only.

It does **not** modify:

- Authorization Foundation's evaluation mechanism
- Authentication
- Identity Context
- Approval Authorization
- Leave Authorization

It does not implement code.

---

# Background

Discovery and Policy Discovery are both complete and approved (`attendance-authorization/discovery.md`, `attendance-authorization/policy-discovery.md`). Repository evidence established:

- `AttendanceEventService`/`api/attendance_events.py` perform authentication only; no authorization exists.
- `ReconciliationService`/`GET /hr/reconciliation` reads the same `AttendanceEvent` data (among three other repositories) with an unscoped `employee_id` parameter and the same authentication-only protection, but is not itself an `AttendanceEvent` CRUD surface and is not recorded as its own capability anywhere in `CAPABILITY_CATALOG.md` or `MASTER_ARCHITECTURE_ROADMAP.md`.
- `AttendanceEvent.employee_id` is directly comparable to `EmployeeContext.employee.id`, the same shape Leave Authorization already uses for `LeaveRequest.employee_id`.
- Policy Discovery scored Owner Only "High" repository support (both operands already implemented) against "Partial" for Manager Access and Role Based, and "Very Low" for Hybrid, which depends on both.

---

# 1. Capability Boundary

**Attendance Authorization, as decided here, covers `AttendanceEvent` create/get/update/delete only — `AttendanceEventService` and `api/attendance_events.py`.**

**`ReconciliationService`/`GET /hr/reconciliation` is explicitly out of scope for this decision.** Reasons, per repository evidence:

- Reconciliation's own protected resource is not an `AttendanceEvent` — it is a computed result over four repositories (`HrEmployeeRepository`, `HolidayRepository`, `LeaveRequestRepository`, `AttendanceEventRepository`), keyed by a caller-supplied `(employee_id, date)` pair rather than by a persisted entity with its own `employee_id` column. Applying the Owner Only rule verbatim would require redefining what "the resource" means for a query parameter rather than a row — a decision this capability's evidence does not resolve.
- Reconciliation is not listed as its own capability in `CAPABILITY_CATALOG.md` or `MASTER_ARCHITECTURE_ROADMAP.md` (confirmed absent by discovery). Deciding its authorization here would extend this capability's scope to a resource neither governance document currently recognizes.
- `ATTENDANCE_RECONCILIATION_DESIGN.md`'s own "Future Compatibility" section names Timesheet, Payroll, and Analytics/Dashboards as future consumers of Reconciliation's output that would aggregate results *across* employees — a cross-employee access pattern in evident tension with an owner-scoped rule, and one this decision has no evidence to resolve either way.

Reconciliation's authorization is deferred to a future capability decision. Until then, it remains authentication-only, unchanged by this decision (§ Unresolved Risks).

---

# 2. Protected Resource

The protected resource is `AttendanceEvent`, identified by its `employee_id` field.

Two shapes are evaluated, matching Leave Authorization's precedent for the equivalent `LeaveRequest`/`LeaveRequestCreate` distinction:

- **`create`**: the resource is the `AttendanceEventCreate` payload (not yet persisted) — `employee_id` is read directly from the submitted payload.
- **`get`/`update`/`delete`**: the resource is the already-loaded `AttendanceEvent` row.

`shift_id`, `event_type`, `event_time`, `source`, and `remarks` carry no authorization meaning under this decision — only `employee_id` participates in the rule (§5 addresses `source` specifically).

---

# 3. Operations Requiring Authorization

`create`, `get`, `update`, `delete` — each authorized individually against the resource shape defined in §2, before the operation proceeds.

`list`/`list_paginated` are **not** authorized per-item. Following Leave Authorization's identical precedent (there is no single resource to evaluate a decision against for a collection read), both are instead **scoped to the caller's own `employee_id`** at the repository-filter level — overriding any caller-supplied `employee_id` filter, the same way `LeaveRequestService.list_paginated` already overrides a caller-supplied `employee_id` filter today. This is a behavior change from the current, unauthorized state, where `list`/`list_paginated` return all `AttendanceEvent` rows (or all matching an arbitrary caller-supplied filter) system-wide.

---

# 4. Selected Policy

**Selected:**

Owner Only

**Rejected:**

- Manager Access
- Role Based

**Deferred:**

Hybrid

## Authorization Rule

```
AttendanceEvent.employee_id (via AuthorizationRequest.resource)
==
RequestContext.employee_context.employee.id
```

Access to a given `AttendanceEvent`'s `create`/`get`/`update`/`delete` operations is granted only to the employee who owns it (§2, §3).

No other authorization rule participates in Attendance Authorization.

## Rationale

Owner Only is the only evaluated policy with full (not partial) repository support: both operands (`AttendanceEvent.employee_id`, `EmployeeContext.employee.id`) are already implemented, tested platform data, requiring no new data model, no new role vocabulary, and no new architectural concept — `LeaveAuthorizationEvaluator` already proves the identical rule shape, including the `AuthorizationRequest.resource` extension point this policy reuses unchanged.

**Manager Access** is rejected for this decision. `HrEmployee.manager_id`'s only existing authorization use (Approval Authorization, ADR-008) is scoped to a one-actor approval relationship on a different resource type; no repository evidence extends it to a two-actor (owner OR manager) CRUD/visibility rule, and no evaluator in the repository expresses that shape. `TD-003` additionally constrains any such rule to a direct-manager-only relationship.

**Role Based** is rejected for this decision. No `ATTENDANCE_ADMIN`/`HR_ADMIN`-equivalent role exists anywhere in the repository, and `TD-004` requires architecture approval — a future ADR — before introducing new role/permission vocabulary. Adopting Role Based now would require exactly the new architectural concept this decision is instructed to avoid absent a specific requirement for one.

**Hybrid** is deferred, not rejected outright — it depends on Manager Access and/or Role Based, and inherits both of their currently-unresolved gaps plus an unprecedented composite-evaluator shape (§ Policy Discovery, Policy D). It remains the most plausible future extension if a manager-visibility or import-actor need is later confirmed by product/architecture decision (§5, § Unresolved Risks).

This decision does not require a new architectural concept beyond what ADR-007 and Leave Authorization already introduced (the `AuthorizationRequest.resource` extension point, already present in the repository). **No new ADR is created.**

---

# 5. `AttendanceEvent.source` and Authorization Behavior

Repository evidence (`core/attendance.py`) defines three `EventSource` values, not two: `SYSTEM`, `MANUAL`, `IMPORT`. This decision addresses all three, since limiting the analysis to the two named in the request instructions would omit repository evidence the Evidence Rule requires considering.

**Decision: `source` does not change authorization behavior.** The Owner Only rule (§4) applies uniformly to every `AttendanceEvent` create/get/update/delete request regardless of its `event_type`/`source` value.

## Rationale

No repository evidence ties any `EventSource` value to an actor-identity concept distinct from the authenticated `User`/`EmployeeContext` already resolved by every request. In particular:

- The repository has no service-account, integration-identity, or non-human-caller concept anywhere — `CurrentUser` always resolves to a `User` row, and `EmployeeContext` always resolves to exactly one `HrEmployee`. There is no existing mechanism by which a `SYSTEM`- or `IMPORT`-sourced request could be authenticated as anything other than a specific human user.
- Introducing a `source`-based exemption (e.g., "`IMPORT` bypasses Owner Only") without such a mechanism would mean inventing an unevidenced actor concept — exactly what ADR-008's own governing principle for this platform prohibits ("implementation must never invent policy... if no approved policy exists, implementation must stop").

## Consequence

A `MANUAL`-sourced event, created by the employee it describes through their own authenticated session, is the only capture path Owner Only supports cleanly today. `SYSTEM` (e.g., a biometric device or integration) and `IMPORT` (e.g., an HR bulk-load) sourced writes, if they are ever performed by an actor other than the employee the event describes, are **denied** under this policy unless that actor's own request is separately, legitimately made under the target employee's own identity (not established as possible anywhere in the repository) — or unless a future capability introduces the missing actor concept. This is recorded as an explicit, accepted limitation, not an oversight (§ Unresolved Risks).

---

# 6. Architecture Constraints Preserved

## API

Owns:

- authentication (`CurrentUser`)
- request-context resolution (`CurrentRequestContext`)
- HTTP mapping (`AttendanceAuthorizationDeniedError` → `403 Forbidden`)

Must never:

- evaluate authorization
- determine ownership

Transport only, per the constraint given.

## `AttendanceEventService`

Owns:

- `AttendanceEvent` CRUD orchestration
- authorization invocation via a private `_authorize` method
- repository coordination
- `list`/`list_paginated` employee-scoping (§3)

Must never:

- evaluate authorization itself (i.e., no `employee_id` comparison outside `_authorize`'s delegation)
- infer manager hierarchy or role membership

Orchestrates authorization, per the constraint given — mirrors `LeaveRequestService._authorize` exactly.

## `AttendanceAuthorizationEvaluator` (name reserved by this decision; not yet created — no code is implemented)

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

- access repositories
- execute workflow
- perform persistence
- perform repository orchestration

Owns policy evaluation with no repository access, per the two constraints given — mirrors `LeaveAuthorizationEvaluator` exactly.

## Authorization Foundation

Owns:

- `AuthorizationRequest` (including the existing `resource` extension point)
- `AuthorizationDecision`
- `AuthorizationEvaluator`
- `AuthorizationService`

Does **not** own:

- Owner Only policy
- any other capability's policy

No change to Authorization Foundation is required by this decision — `resource` already exists (introduced by Leave Authorization). Remains policy-agnostic, per the constraint given.

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
AttendanceAuthorizationEvaluator
        │
        ▼
Owner Only Policy
        │
        ▼
AuthorizationDecision
        │
        ▼
AttendanceEventService
```

---

# Repository Evidence

Repository already contains, unmodified by this decision:

- `AttendanceEvent.employee_id`
- `EmployeeContext`
- `RequestContext`
- Authorization Foundation, including `AuthorizationRequest.resource`
- `AttendanceEventService`

No new business relationship is required. No database redesign is required.

---

# Explicit Constraints

Implementation (when planned and executed in a later phase) shall:

- evaluate only `resource.employee_id == context.employee_context.employee.id`
- consume `EmployeeContext`/`RequestContext`
- produce `AuthorizationDecision`
- integrate through `AuthorizationService`
- scope `list`/`list_paginated` to the caller's own `employee_id`
- preserve existing layering

Implementation shall not:

- introduce manager-based access
- introduce role-based access
- introduce a `source`-based authorization exemption
- introduce delegated access
- redesign `AttendanceEventService`'s CRUD behavior beyond authorization
- embed Owner Only policy logic in Authorization Foundation
- extend authorization to `ReconciliationService` under this decision

---

# Explicit Exclusions

The following are explicitly outside the scope of this policy:

- `ReconciliationService`/`GET /hr/reconciliation` (§1)
- manager access to a subordinate's `AttendanceEvent`
- HR administrator override
- role-based access
- `source`-conditioned authorization behavior
- delegated access
- workflow assignment
- hybrid authorization

---

# Deferred Capabilities

Future capabilities may extend Attendance Authorization with:

- Reconciliation authorization (requires its own capability decision — resource shape differs from `AttendanceEvent`, §1)
- manager access (requires resolving the two-actor evaluator shape gap and `TD-003`'s hierarchy limitation)
- role-based or hybrid access (requires a future ADR introducing role/permission vocabulary, per `TD-004`)
- a `source`-aware or integration-actor authorization model, if `SYSTEM`/`IMPORT`-sourced writes by non-owner actors are confirmed as a real requirement

Such capabilities extend this policy. They do not replace the Authorization Foundation.

---

# Alternatives Considered

## Manager Access

Rejected. See §4 Rationale.

## Role Based

Rejected. See §4 Rationale.

## Hybrid

Deferred, not rejected. See §4 Rationale.

## Extending scope to `ReconciliationService` in this same decision

Rejected. See §1 — Reconciliation's resource shape and cross-employee future-consumer profile are not resolved by Owner Only's evidence, and neither governance document currently recognizes it as its own capability.

---

# Consequences

Attendance Authorization now has an explicit business policy, structurally identical in shape to Leave Authorization and non-overlapping with it (different resource, no approval/workflow concept on `AttendanceEvent`).

`list`/`list_paginated` behavior changes from returning all records to returning only the caller's own — a behavior change from today's unauthorized state, decided explicitly in §3.

`SYSTEM`/`IMPORT`-sourced writes by a non-owner actor are not supported under this policy (§5) — an accepted, explicit limitation, not an oversight.

`ReconciliationService` remains authorization-free until a separate capability decision addresses it (§1).

Authorization Foundation remains unchanged; no new ADR is created.

---

# Unresolved Risks

- **`update` authorization is evaluated against the pre-update resource, not the submitted payload.** Following `LeaveRequestService.update`'s identical existing pattern, `_authorize` runs against the already-loaded `AttendanceEvent` before new values are applied. An owner could therefore submit an `AttendanceEventUpdate.employee_id` reassigning their own event to a different employee — the authorization check (evaluated on the pre-update resource, which they own) would pass, but nothing re-checks the new `employee_id` value being written. This is not a new gap introduced by this decision; it is inherited, unaddressed, from Leave Authorization's own implementation of the same pattern, and is recorded here rather than silently carried forward.
- **`SYSTEM`/`IMPORT`-sourced writes by a non-owner actor have no supported path** (§5). If this is later confirmed as a real business requirement, it requires a new actor-identity concept this repository does not currently have, and a future capability decision.
- **`ReconciliationService` remains unauthorized** (§1). Any consumer relying on Reconciliation output being access-controlled the same way `AttendanceEvent` CRUD now is would be mistaken until a separate decision is made.
- **`EmployeeContext` resolution failure (TD-001)** is inherited unchanged: `EmployeeContextNotFoundError`/`MultipleEmployeeContextError` have no dedicated HTTP mapping, so a caller with no or multiple linked `HrEmployee` rows would receive `HTTP 500` rather than a meaningful error on any Attendance Authorization-gated route, exactly as already recorded for Approval Authorization and Leave Authorization.

---

# References

- ADR-006 — Employee Context Resolution
- ADR-007 — Authorization Foundation
- ADR-008 — Approval Authorization Policy Model (structural precedent, distinct policy)
- Attendance Authorization Discovery
- Attendance Authorization Policy Discovery
- Leave Authorization Decision (structural precedent)
- TECHNICAL_DEBT_REGISTER.md — TD-001, TD-003, TD-004
- MASTER_ARCHITECTURE_BLUEPRINT.md

# Leave Authorization — Policy Discovery

**Capability:** Leave Authorization

**Status:** Discovery

**Synchronization note:** Reconstructed from repository evidence for governance-trail synchronization — Leave Authorization was already implemented and merged (`0a9b669`, PR #56) when this document was written. Evaluated policies and evidence below reflect the platform state at that commit.

---

# Purpose

This document evaluates candidate Leave Authorization policies using repository evidence.

It does not define architecture.

It does not choose implementation ahead of the evidence presented.

Its purpose is to determine which policy models were technically feasible within the platform state at the time Leave Authorization was implemented, and to record why the implemented policy (Owner Only) was the one repository evidence supported.

---

# Background

Repository state at commit `0a9b669`'s parent:

- Authentication exists.
- Identity Context exists (ADR-006).
- Authorization Foundation exists (ADR-007).
- Approval Authorization exists (ADR-008, Manager Approval policy, scoped to `approve`/`reject` only).
- `LeaveRequestService` CRUD (`create`/`get`/`list`/`list_paginated`/`update`/`delete`) has no authorization beyond authentication.

The remaining architectural question, scoped to `LeaveRequestService`'s own CRUD surface (distinct from the already-authorized `approve`/`reject` surface):

> Who is allowed to create, view, update, or delete a given `LeaveRequest`?

---

# Candidate Policy Models

---

# Policy A — Owner Only

## Description

Only the employee who owns a `LeaveRequest` (`LeaveRequest.employee_id`) may create, view, update, or delete it.

Conceptually:

```
resource.employee_id == context.employee_context.employee.id
```

## Repository Evidence

`LeaveRequest.employee_id` (FK → `hr_employees.id`) already exists and is directly comparable to `EmployeeContext.employee.id`, resolved by the already-implemented `EmployeeContextResolver` (ADR-006). No new field, table, or relationship is required.

## Repository Support

**High.** Every piece of data the rule needs — `LeaveRequest.employee_id`, `RequestContext.employee_context.employee.id` — already exists and is already resolved by an implemented, tested platform capability (Identity Context).

## Advantages

- No new data model.
- No dependency on `HrEmployee.manager_id` or any hierarchy concept.
- Symmetric with the resource's own identity — a `LeaveRequest` is naturally "about" the employee it belongs to.
- Consistent with `LeaveRequestService.list`/`list_paginated`'s pre-existing intent to scope results to the caller (see `leave_request.py` docstrings).

## Disadvantages

- Does not allow a manager, HR administrator, or delegate to act on an employee's behalf.
- Provides no path for HR staff to create a `LeaveRequest` on behalf of another employee.

## Missing Repository Support

None for the rule itself. Missing only if broader access (manager/admin) is later required.

## Future Compatibility

Good — a narrower starting policy that a future capability can broaden (Manager Access, Role Based, Hybrid) without breaking existing Owner Only behavior, provided any broadening is additive (an `OR` over Owner Only, not a replacement of it).

---

# Policy B — Manager Access

## Description

A `LeaveRequest`'s owner, or the owner's direct manager, may act on it.

## Repository Evidence

`HrEmployee.manager_id` exists and is already consumed by Approval Authorization (`ApprovalAuthorizationEvaluator`, ADR-008) for the *separate* `approve`/`reject` surface. No repository evidence shows `manager_id` used for CRUD access to a subordinate's `LeaveRequest` (as opposed to an approval decision on it).

## Repository Support

**Partial.** The relationship exists and is already read by `ApprovalService._authorize`, but applying it to CRUD access (rather than approval) is a distinct authorization question ADR-008 does not answer — ADR-008 is scoped explicitly to "who is allowed to approve a request," not "who is allowed to create/view/edit a request."

## Advantages

Would let a manager view or correct a subordinate's leave request without going through the owner.

## Disadvantages

Conflates two different actions (CRUD access vs. approval decision) under one relationship; risks a manager editing a request they have not yet been asked to approve, or editing it after approving it.

## Missing Repository Support

No repository evidence distinguishes "manager may approve" from "manager may edit" — `ApprovalAuthorizationEvaluator`'s own rule (`request.employee.manager_id == approver.employee.id`) is scoped by ADR-008 to approval only.

## Future Compatibility

Good, if introduced as an explicit extension rather than inferred from the existing Approval Authorization relationship.

---

# Policy C — Role Based

## Description

Access determined by RBAC (e.g., an `HR_ADMIN` role bypassing ownership).

## Repository Evidence

`Role`, `UserRole`, `RequireRole` exist. Current usage is `admin` only (`RequireAdmin`, `api/roles.py`). No `HR_ADMIN`, `LEAVE_ADMIN`, or equivalent role is defined anywhere in the repository.

## Repository Support

**Partial.** RBAC infrastructure exists; no leave-specific role vocabulary exists.

## Advantages

Centralized, auditable, consistent with any future admin-override requirement.

## Disadvantages

Requires introducing new role vocabulary — a role-naming decision this discovery does not make.

## Missing Repository Support

- Leave-specific or HR-specific role definitions.
- Any existing consumer of `RequireRole` scoped to `LeaveRequest`.

## Future Compatibility

Excellent — RBAC infrastructure is already reusable platform-wide.

---

# Policy D — Hybrid

## Description

Combination of Owner Only with Manager Access and/or Role Based (e.g., owner OR manager OR `HR_ADMIN`).

## Repository Evidence

Depends on Policy B and/or Policy C, both only partially supported (see above). No repository evidence combines them today.

## Repository Support

**Very Low**, inherited from its dependent policies.

## Advantages

Most flexible; matches how Approval Authorization's own documentation (ADR-008) frames future policy evolution as additive.

## Disadvantages

Highest complexity; requires resolving Policy B's and/or Policy C's own open gaps first.

## Missing Repository Support

Everything Policy B and Policy C are individually missing.

## Future Compatibility

Excellent, once its dependent policies are individually resolved.

---

# Comparison Matrix

| Policy       | Repository Support | Complexity | Extensibility | Current Recommendation |
| ------------ | ------------------- | ---------- | -------------- | ----------------------- |
| Owner Only   | High                | Low        | Good           | Candidate               |
| Manager Access | Partial            | Medium     | Good           | Future                  |
| Role Based   | Partial             | Medium     | Excellent      | Future                  |
| Hybrid       | Very Low            | Very High  | Excellent      | Future                  |

---

# Architecture Constraints

**ADR-007** — Authorization Foundation remains policy-agnostic; policy is defined at capability level.

**ADR-008** — Precedent, not a constraint on this capability: establishes that approval eligibility (a different question) is a separate, architecture-owned policy decision, and that implementation must not infer policy that has not been approved.

No ADR governs Leave Authorization's own CRUD-access policy directly; this discovery treats ADR-007's "capability level" delegation as the applicable authority, consistent with how Approval Authorization's own policy (ADR-008) was scoped as a capability-level decision built on the same Foundation.

---

# Decision

**Selected:**

Owner Only

**Rejected:**

- Manager Access
- Role Based

**Deferred:**

Hybrid

---

# Rationale

Owner Only is the only evaluated policy with full (not partial) repository support at the time of implementation: both operands of its rule (`LeaveRequest.employee_id`, `EmployeeContext.employee.id`) were already implemented, tested platform data, requiring no new model, no new role vocabulary, and no reinterpretation of `HrEmployee.manager_id` beyond its already-approved use in Approval Authorization (ADR-008).

Manager Access and Role Based are each rejected for this initial policy — not as permanently unsuitable, but because each requires resolving a gap (respectively: an undefined CRUD-vs-approval distinction for `manager_id`; an undefined role vocabulary) that repository evidence at the time did not close. Hybrid is deferred because it depends on the same two unresolved policies.

---

# Risks

## Owner Only

No path exists for a manager or HR administrator to act on an employee's behalf. Organizations requiring assisted/proxy leave requests will require a future capability extension.

## Manager Access (deferred)

Risks conflating approval authority with CRUD authority if introduced by reusing `manager_id` without an explicit new rule.

## Role Based (deferred)

Requires a role-vocabulary decision this document does not make.

## Hybrid (deferred)

Combines the risks of its dependent policies.

---

# Open Questions

- Whether HR administrators are ever expected to create/edit `LeaveRequest` rows on behalf of an employee, and if so, whether that is Policy C (Role Based) or a distinct exception to Owner Only.
- Whether Manager Access, if introduced later, should reuse `HrEmployee.manager_id` the same way Approval Authorization does, or be evaluated as a structurally distinct rule.

---

# Recommendation

The next artifact is the Capability Decision, recording Owner Only as the selected policy with its formal rule and constraints — see `leave-authorization/decision.md`.

---

# References

- ADR-006 — Employee Context Resolution
- ADR-007 — Authorization Foundation
- ADR-008 — Approval Authorization Policy Model
- Leave Authorization Discovery
- Approval Authorization Policy Discovery (structural precedent)
- MASTER_ARCHITECTURE_BLUEPRINT.md

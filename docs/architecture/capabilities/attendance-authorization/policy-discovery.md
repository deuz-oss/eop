# Attendance Authorization — Policy Discovery

**Capability:** Attendance Authorization

**Status:** Discovery

**Owner:** EOP Architecture Governance

---

# Purpose

This document evaluates candidate Attendance Authorization policies using repository evidence collected in `attendance-authorization/discovery.md` (Discovery phase, approved).

It does not define architecture.

It does not select a policy.

Its purpose is to compare the four candidate policy models named for evaluation — Owner Only, Manager Access, Role Based, Hybrid — on repository evidence, advantages, disadvantages, architectural impact, and dependency impact, so a subsequent Capability Decision can select among them.

---

# Background

Repository state, per the approved Discovery:

- `AttendanceEventService` (`services/attendance_event.py`) and all six of its API endpoints (`api/attendance_events.py`) perform authentication only — no authorization check exists.
- `ReconciliationService`/`GET /hr/reconciliation` reads the same `AttendanceEvent` data with an unscoped, caller-suppliable `employee_id` and the same authentication-only protection.
- `AttendanceEvent.employee_id` (FK → `hr_employees.id`) exists and is directly comparable to `EmployeeContext.employee.id`.
- `HrEmployee.manager_id` exists and is already consumed by Approval Authorization (ADR-008) for a structurally different purpose — approval eligibility on `LeaveRequest`/`OvertimeRequest`/`Timesheet`, not attendance CRUD.
- `AttendanceEvent.source` (`EventType`/`EventSource`, `core/attendance.py`) distinguishes `SYSTEM`/`MANUAL`/`IMPORT` capture — no code branches on this value for any purpose today, authorization included, but the enum itself is repository evidence that not every `AttendanceEvent` is necessarily written by the employee it belongs to.
- Two authorization-integration shapes already exist and work in the repository: Approval Authorization's service-resolves-then-injects-into-evaluator shape (`ApprovalService._authorize`, ADR-008), and Leave Authorization's resource-carrying-`AuthorizationRequest` shape (`LeaveRequestService._authorize`, Owner Only). Neither is a role/RBAC-based shape.
- `Role`, `UserRole`, `RequireRole`/`RequireAdmin` exist (`api/roles.py`), used only for `admin`-gated role-management endpoints. No `ATTENDANCE_ADMIN`, `HR_ADMIN`, or equivalent role is defined anywhere.
- `AttendanceEvent` carries no `status`/workflow field (unlike `LeaveRequest`/`OvertimeRequest`/`Timesheet`) — there is no approval concept on attendance records themselves, only a raw event stream.
- `TD-003` (Employee Manager Hierarchy Limitation) records that `HrEmployee.manager_id` supports only a direct-manager lookup — no chain traversal, no escalation path.
- `TD-004` (Permission and Policy Model Not Implemented) records that introducing role/permission vocabulary requires architecture approval before implementation.

The remaining architectural question, scoped to `AttendanceEventService`'s CRUD surface (and, per discovery §2.5/§8, an open question of whether it extends to `ReconciliationService`):

> Who is allowed to create, view, update, or delete a given `AttendanceEvent`?

---

# Candidate Policy Models

---

# Policy A — Owner Only

## Description

Only the employee the `AttendanceEvent` belongs to (`AttendanceEvent.employee_id`) may create, view, update, or delete it.

```
resource.employee_id == context.employee_context.employee.id
```

## Repository Evidence

`AttendanceEvent.employee_id` already exists and is directly comparable to `EmployeeContext.employee.id`, resolved by the already-implemented `EmployeeContextResolver` (ADR-006). `LeaveAuthorizationEvaluator` (`services/leave_authorization.py`) already implements exactly this rule shape for a structurally similar resource (`LeaveRequest.employee_id`), including the `resource`-carrying `AuthorizationRequest` extension point (`AuthorizationRequest.resource: Any | None`) needed to compare a not-yet-persisted `AttendanceEventCreate` payload the same way `LeaveRequestCreate` is compared today.

Counter-evidence: `AttendanceEvent.source` (`SYSTEM`/`MANUAL`/`IMPORT`) is repository evidence that not every event is necessarily authored by the employee it describes — no code currently exempts `SYSTEM`/`IMPORT`-sourced writes from an owner check, and no code currently performs one either, so this tension is latent in the schema rather than resolved by any existing behavior.

## Advantages

- Identical implementation shape to Leave Authorization — one evaluator subclass, a `request_context` parameter added to `AttendanceEventService`'s six methods, `CurrentRequestContext` wired into `api/attendance_events.py`, one `*AuthorizationDeniedError` mapped to `403`. No new data model, no new role vocabulary.
- Both operands of the rule are already implemented, tested platform data (same basis Leave Authorization's own policy-discovery cited as the reason Owner Only had "High" repository support there).

## Disadvantages

- Does not accommodate `SYSTEM`- or `IMPORT`-sourced writes performed by an actor other than the employee (a device integration, a bulk-import operator) — the enum values these sources represent already exist in the schema, so a strict Owner Only rule would deny a class of write the data model itself anticipates, unless such writes are made to always impersonate the target employee's own identity (a fact not established anywhere in the repository).
- No path for a manager or HR administrator to view or correct a subordinate's attendance record.
- Extending this rule to `ReconciliationService`/`GET /hr/reconciliation` (discovery §2.5, §8) would change that endpoint's current behavior, which accepts an arbitrary `employee_id` with no ownership check today.

## Architectural Impact

Requires adding `request_context: RequestContext` to every `AttendanceEventService` public method and a private `_authorize` method, mirroring `LeaveRequestService`'s existing shape exactly — a structural change with direct precedent, not a new pattern. Leaves open (not resolved by this policy alone) whether `ReconciliationService` is in scope for the same rule, since it reads the same underlying data through a different service.

## Dependency Impact

Depends only on Identity Context (`EmployeeContext`) and Authorization Foundation. No new dependency on `HrEmployee.manager_id` or on `Role`/`UserRole`. Matches Leave Authorization's dependency footprint exactly.

---

# Policy B — Manager Access

## Description

The `AttendanceEvent`'s owner, or the owner's direct manager, may act on or view it.

## Repository Evidence

`HrEmployee.manager_id` exists and is already read by `ApprovalAuthorizationEvaluator`/`ApprovalService._authorize` (ADR-008) — but exclusively for approval eligibility on a different resource type, not for attendance CRUD or visibility. No repository evidence uses `manager_id` for viewing or editing a subordinate's records of any kind. Leave Authorization's own Policy Discovery evaluated and rejected an equivalent candidate for `LeaveRequest` CRUD on this same basis (conflating an approval relationship with a CRUD-access relationship) — `AttendanceEvent` has no approval/workflow concept at all (no `status` field), so there is even less existing precedent tying `manager_id` to it than there was for `LeaveRequest`.

## Advantages

Would give a manager visibility into, or correction rights over, a subordinate's attendance record — a plausible operational need given `ATTENDANCE_RECONCILIATION_DESIGN.md`'s own identification of Timesheet/Payroll/Analytics as future consumers that aggregate attendance data across employees, contexts that typically involve manager or HR oversight.

## Disadvantages

- `manager_id`'s only existing authorization use (Approval Authorization) is explicitly scoped by its own decision document to "no recursive traversal, no hierarchy inference, no organizational lookup" for a one-actor, one-relationship rule (manager approves subordinate's request) — reusing it for a two-actor CRUD rule (owner OR manager, each with potentially different permitted operations) is a different shape neither existing document nor evaluator expresses.
- No repository evidence resolves whether "manager access" would mean read-only visibility, full CRUD parity with the owner, or something narrower (e.g., view only, no delete) — a distinction that matters more for a raw, append-mostly event stream than it did for a whole-record workflow entity like `LeaveRequest`.
- `TD-003` records the underlying relationship itself as limited: direct manager only, no chain, no escalation.

## Architectural Impact

Would require `AttendanceEventService` (or its evaluator) to resolve the target event's owning `HrEmployee.manager_id`, mirroring `ApprovalService._authorize`'s existing shape (`services/approval.py:209-232`) — a second, already-proven integration pattern, distinct from Leave Authorization's resource-carrying shape. Neither existing evaluator (`ApprovalAuthorizationEvaluator`, `LeaveAuthorizationEvaluator`) evaluates an OR across two possible actors; both evaluate exactly one relationship. A Manager Access evaluator would be the first in the repository to do so.

## Dependency Impact

Adds a dependency on `HrEmployee.manager_id`, and on an `HrEmployeeRepository` lookup from within the authorization path (mirroring `ApprovalService._authorize`'s existing repository call) — a heavier dependency footprint than Owner Only. Inherits `TD-003`'s direct-manager-only limitation as a constraint on what this policy can express.

---

# Policy C — Role Based

## Description

Access determined by RBAC role membership (e.g., an `ATTENDANCE_ADMIN` or `HR_ADMIN` role), independent of `employee_id` or `manager_id` comparison.

## Repository Evidence

`Role`, `UserRole`, `RequireRole`/`RequireAdmin` (`api/roles.py`) exist. Current usage is `admin`-gated role-management endpoints only — confirmed by discovery as the sole consumer. No attendance- or HR-scoped role is defined anywhere. Leave Authorization's own Policy Discovery reached an identical conclusion (Policy C there) for the same reason and was rejected on the same missing-vocabulary gap; no role-vocabulary work has occurred since.

`AttendanceEvent.source == IMPORT` is evidence, specific to Attendance and not present on `LeaveRequest`, that plausibly correlates with an administrative actor (a bulk-import operation is more likely performed by staff than by the employee it describes) — but no repository evidence links `EventSource` to any role check; this is an unimplemented correlation, not a confirmed rule.

## Advantages

- Reuses existing `RequireRole`/`RequireAdmin` infrastructure directly — no new authorization mechanism.
- Naturally fits `SYSTEM`/`IMPORT`-sourced writes (§ evidence above) without requiring those writes to impersonate an employee's own identity, unlike Owner Only.
- Centralized and auditable.

## Disadvantages

- Requires introducing new role vocabulary — a decision this document does not make, and one `TD-004` explicitly requires architecture approval for before implementation ("Do not introduce permission concepts without architecture approval").
- Does not, by itself, cover the "employee views/edits their own attendance" case — combining it with ownership would be Hybrid, not Role Based alone; granting the new role to every authenticated user would be equivalent to no authorization.

## Architectural Impact

`RequireRole` and `AuthorizationService`/`AuthorizationEvaluator` are two structurally separate mechanisms today — discovery confirms `RequireRole` is used only by `api/roles.py`, never in the same code path as `AuthorizationService`. A pure Role Based policy would be the first capability to gate business-entity CRUD via `RequireRole` rather than via Authorization Foundation, departing from both existing precedents (Approval Authorization, Leave Authorization), neither of which uses `RequireRole`.

## Dependency Impact

Depends on `Role`/`UserRole`/`RequireRole` rather than on Identity Context/`EmployeeContext` — a different dependency chain than Owner Only, and one not currently used by any Authorization-Foundation-integrated capability, per repository evidence.

---

# Policy D — Hybrid

## Description

A combination of the above — for example, Owner Only OR Manager Access OR Role Based, so an employee, their manager, and an administrative/import actor can each act on an `AttendanceEvent` under different conditions.

## Repository Evidence

Depends entirely on Policy B and/or Policy C, both only partially supported (§ above). No repository evidence combines any two of these mechanisms today: `ApprovalAuthorizationEvaluator` and `LeaveAuthorizationEvaluator` each evaluate exactly one relationship; no evaluator in the repository evaluates a disjunction across multiple conditions.

## Advantages

Most flexible; would accommodate all three actor types the Attendance data model plausibly implies (employee self-service via `MANUAL` source, manager/HR correction, automated/bulk writes via `SYSTEM`/`IMPORT`). Leave Authorization's own Policy Discovery flagged Hybrid as the natural eventual extension path for the same underlying reason (multiple partially-supported policies, none individually sufficient).

## Disadvantages

- Highest complexity; inherits every open gap of Manager Access (no existing evaluator shape for a two-actor OR) and Role Based (undefined role vocabulary) simultaneously.
- No repository evidence resolves precedence if more than one condition could apply to the same request (e.g., an admin who is also the record's manager) — the same class of unresolved precedence question `ATTENDANCE_RECONCILIATION_DESIGN.md` §12.2 already flags, unresolved, for a different Attendance-adjacent computation.

## Architectural Impact

Would require either a new composite evaluator (an OR-combinator over Owner-Only-shaped, Manager-Access-shaped, and Role-Based-shaped sub-checks) or a single evaluator encoding all conditions directly — neither shape exists as precedent anywhere in the repository. `AuthorizationEvaluator`'s existing subclasses (`ApprovalAuthorizationEvaluator`, `LeaveAuthorizationEvaluator`) are each framed as one deterministic predicate, not a composed set.

## Dependency Impact

Union of Owner Only's, Manager Access's, and Role Based's dependencies simultaneously: Identity Context, Authorization Foundation, `HrEmployee.manager_id` (and its `TD-003` limitation), and `Role`/`UserRole`/`RequireRole` (and its `TD-004` vocabulary gap). The broadest dependency footprint of the four candidates.

---

# Comparison Matrix

| Policy | Repository Support | Complexity | Extensibility | New Dependencies |
|---|---|---|---|---|
| Owner Only | High — both operands already implemented | Low | Moderate (owner-only ceiling) | None beyond Identity Context |
| Manager Access | Partial — relationship exists, not for this purpose | Medium | Moderate | `HrEmployee.manager_id` + repository lookup |
| Role Based | Partial — RBAC infra exists, vocabulary does not | Medium | Good | `Role`/`UserRole`/`RequireRole` |
| Hybrid | Very Low — combines two partially-supported policies | Very High | Best | All of the above |

---

# Architecture Constraints

**ADR-007** — Authorization Foundation remains policy-agnostic; policy is defined at capability level. All four candidates are compatible with this constraint at the evaluation-mechanism level; none requires modifying `AuthorizationService`/`AuthorizationEvaluator`'s own contract (Owner Only and Manager Access both fit the existing `AuthorizationRequest`/`AuthorizationDecision` shape; Role Based would sit outside it, per § Policy C Architectural Impact).

**TD-003** — Employee Manager Hierarchy Limitation constrains Manager Access and Hybrid to a direct-manager-only relationship; neither can express chain traversal or escalation without a separate future capability.

**TD-004** — Permission and Policy Model Not Implemented requires architecture approval before introducing role/permission vocabulary; this constrains Role Based and Hybrid specifically, not Owner Only or Manager Access.

No ADR specific to Attendance Authorization exists, and none is created by this document, per instruction. As with Leave Authorization, ADR-007's capability-level delegation is the applicable authority for whichever policy a future Capability Decision selects.

---

# Open Questions

Carried forward from Discovery, still unresolved by this comparison:

- Whether `ReconciliationService`/`GET /hr/reconciliation` is in scope for whichever policy is eventually selected, given it reads the same `AttendanceEvent` data through a separate service with its own, currently unscoped `employee_id` parameter.
- Whether `AttendanceEvent.source` is intended to have any bearing on authorization (relevant to Owner Only's disadvantage and Role Based's/Hybrid's advantage) — no repository evidence currently ties `source` to any actor-identity rule.
- Whether "manager access," if selected, means read visibility, full CRUD parity, or a narrower subset — not decidable from the repository.
- Whether a Role Based or Hybrid policy's required role vocabulary is expected to be Attendance-specific (`ATTENDANCE_ADMIN`) or shared platform-wide (`HR_ADMIN`) — no repository evidence indicates either.

---

# Recommendation

Repository discovery and policy comparison are complete. No policy is selected by this document.

The next artifact is the Capability Decision, which must select exactly one policy (or an explicitly scoped combination) with its formal rule and constraints.

```
Capability Decision
```

---

# References

- Attendance Authorization Discovery
- Leave Authorization Policy Discovery (structural precedent)
- Approval Authorization Policy Discovery (structural precedent)
- ADR-006 — Employee Context Resolution
- ADR-007 — Authorization Foundation
- ADR-008 — Approval Authorization Policy Model
- TECHNICAL_DEBT_REGISTER.md — TD-003, TD-004
- MASTER_ARCHITECTURE_BLUEPRINT.md

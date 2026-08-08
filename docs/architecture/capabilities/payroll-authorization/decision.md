# Payroll Authorization — Capability Decision

**Capability:** Payroll Authorization

**Status:** Superseded by Addendum (Version 2) — Policy Resolved. §1–§8 below are retained unmodified as the historical record of why this capability was deferred at authorship time; they are no longer the operative decision. See the Addendum immediately below.

**Version:** 2 (Addendum) — Version 1's deferral is superseded, not deleted

**Owner:** Architecture

---

# Addendum (Version 2) — Prerequisite Satisfied, Policy Resolved

Version 1 of this document (§1–§8 below, unmodified) deferred Payroll Authorization because "no Payroll resource exists" and named, in its own §5, exactly what would need to exist before a policy could be selected: a persisted Payroll aggregate, a Service able to resolve a concrete `AuthorizationRequest.resource`, and a prior "Payroll" (non-authorization) Capability Decision.

**That prerequisite is now satisfied, by work this document did not need to re-derive:**

- `docs/architecture/capabilities/payroll/decision.md` (Approved) is the prior Payroll Capability Decision §5 called for. It decided `PayrollRun` and `Payslip` as persisted aggregates.
- Payroll Iteration 1 (merged, `5d4378d`/PR #58) implemented both, plus `Compensation` (`compensation/decision.md`, also Approved): `models/payroll_run.py`, `models/payslip.py`, `models/compensation.py`, each with a dedicated `*Service`/`*Repository`/router, confirmed present in the repository at authorship of this addendum.
- Each owning Service (`PayrollRunService`, `PayslipService`, `CompensationService`) is capable of resolving a concrete resource for `AuthorizationRequest.resource`, the same role `AttendanceEventService`/`LeaveRequestService`/`ApprovalService` already play for their own resources (original §1.2–§1.3).

§2's original holding — "Payroll Authorization is not currently a valid capability to decide a policy for" — is superseded for exactly this reason: the evidentiary gap it was based on no longer exists. §3's rationale, §4's rejected alternatives, and §7's risks remain valid *as a record of that period* and are not rewritten.

## Policy Decision

Resolved directly against repository evidence gathered for this addendum (model shape of `PayrollRun`, `Payslip`, `Compensation`, confirmed by direct inspection), following the same Owner Only precedent as Leave Authorization / Attendance Authorization wherever the resource shape matches, per the original §4's own caution against picking a policy "by analogy" *before* a resource existed — the resource now exists and its actual shape, not an assumption, drives this choice:

| Resource | Policy | Rule | Basis |
|---|---|---|---|
| `Compensation` | **Owner Only** | `resource.employee_id == context.employee_context.employee.id` | `models/compensation.py` carries `employee_id` (`ForeignKey("hr_employees.id")`), structurally identical to `LeaveRequest`/`AttendanceEvent`. |
| `Payslip` | **Owner Only** | `resource.employee_id == context.employee_context.employee.id` | `models/payslip.py` carries `employee_id`, same shape. |
| `PayrollRun` | **Role Based** | `RequireRole("admin")`, enforced via the existing `dependencies/rbac.py` mechanism at the router boundary — not an `AuthorizationEvaluator`/`AuthorizationRequest.resource` comparison | `models/payroll_run.py` carries no `employee_id` or any employee-equivalent field (confirmed, `payroll/decision.md` §6: "deliberately not employee-scoped"). Owner Only and Manager Access both require a resource field to compare against; none exists. No HR/Payroll-specific role exists in the repository (`roles` table is free-form with no seed data; the only established role/dependency precedent anywhere is the generic `"admin"` string, used solely by `RequireAdmin` in `api/roles.py` to gate role management itself). Reusing `"admin"` was chosen over introducing a new `"payroll_admin"` role to avoid adding role-provisioning scope to this PR; this is recorded as a known limitation (§ Known Limitations, `implementation-plan` equivalent), not a re-litigation — a narrower role is a legitimate future refinement, not a blocker. |

This resolves §5's original prerequisite and closes the deferral. No other capability's decision is reopened by this addendum.

## Known Limitations Carried Forward

- **`PayrollRun`'s policy uses the generic `admin` role**, not a Payroll-specific one. Anyone holding `admin` (a broader grant than "HR/Payroll staff" in any real deployment) gets `PayrollRun` access. Introducing a scoped `payroll_admin` role is a valid future refinement, deliberately out of scope here per the business decision recorded above.
- **Internal, non-HTTP consumption of `Compensation`/`Payslip` is not authorization-gated.** `PayrollCalculationService` (`services/payroll_calculation.py`) reads `CompensationService.get_by_employee` and writes via `PayslipService.create` on behalf of an arbitrary employee, as the system-driven payroll computation step — not a `context`-carrying user request. Both methods accept an optional `request_context` that, when omitted, preserves this trusted-internal-caller behavior unchanged; when supplied (every API-router call site), Owner Only is enforced. This mirrors the repository's existing treatment of `ApprovalService`/`ReconciliationService` as internal domain orchestration outside per-request authorization scope, and avoids modifying `PayrollCalculationService` (out of scope for this PR).
- **`Payslip.create`/`Compensation.create` being Owner Only** means, taken literally, only an employee could create their own compensation/payslip via the API — a self-service framing that does not match how these records are actually populated in practice (HR sets `Compensation`; `PayrollCalculationService` computes `Payslip`). This mirrors the Leave/Attendance precedent exactly, as directed, and is recorded here rather than silently deviated from. Refining `create`'s policy (e.g., a separate HR-write / employee-read split) is a future iteration, not decided here.

---

# Version 1 (Historical Record — Superseded, Not Deleted)

The following sections (§1–§8, including their own internal numbering) are the original Version 1 decision text, unmodified. They document why Payroll Authorization was correctly deferred at the time they were written. They are retained for governance history and are no longer the operative decision — see the Addendum above.

---

# Purpose

This document records the Capability Decision for Payroll Authorization, per the governance sequence already established by `CAPABILITY_CATALOG.md` (Discovery → Policy Discovery → Capability Decision → Implementation Plan → Implementation → Architecture Review).

It answers exactly one question, as instructed: **does a Payroll resource exist in the repository, and if not, is Payroll Authorization currently a valid capability to decide a policy for?**

It does not select a policy. It does not implement code. It does not modify any other governance document. It does not invent a `PayrollRun`, `Payslip`, `PayrollPeriod`, `SalaryRecord`, or any other aggregate.

---

# Background

Two discovery documents precede this decision:

- `docs/architecture/capabilities/payroll-authorization/discovery.md` — repository-wide search confirming no Payroll-related model, service, repository, schema, API route, or migration exists anywhere in the repository.
- A second Repository Discovery pass (Payroll Capability, same conversation) confirming five producer capabilities (`HrEmployee`, `AttendanceEvent`/Reconciliation, `LeaveRequest`/`LeaveBalance`, `OvertimeRequest`, `Timesheet`) exist and are implemented, but none carries a monetary field, and no entity anywhere in the repository is named or shaped as a Payroll resource.

Both discoveries independently reach the same finding: **no Payroll resource exists**. This decision evaluates what that finding means for Payroll Authorization specifically, following Approval Authorization (ADR-008), Leave Authorization, and Attendance Authorization as the three existing precedents for how this repository structures a capability-specific authorization decision.

---

# 1. Repository Evidence

## 1.1 No Payroll Resource Exists

Confirmed by both prior discoveries, restated here as the evidentiary basis for this decision:

- Repository-wide filename search for `*payroll*`, `*payslip*`, `*salary*`, `*compensation*` under `services/api/src`, `services/api/tests`, `services/api/alembic` returns zero files.
- Repository-wide content grep for `payroll|payslip|salary|compensation` returns matches only in (a) docstrings of unrelated, already-implemented modules stating payroll is explicitly out of scope for them, (b) "Future Compatibility" sections of other capabilities' design documents, (c) governance/roadmap documents naming a future, `Planned` capability, (d) one product-scope document listing "Payroll Processing" as an HRIS exclusion.
- No model anywhere in `services/api/src/eop_api/models/` defines a Payroll aggregate.
- No monetary field (salary, wage, rate, allowance, deduction, tax, benefit) exists on any model, including `HrEmployee` (`models/hr_employee.py:54-105`) and `JobGrade` (`models/job_grade.py`, fields limited to `code`/`name`/`level`/`description`).
- `main.py`'s 24 registered routers (`main.py:82-112`) include no Payroll router.
- `services/api/alembic/versions/` (26 migrations) contains no payroll-related table or column.
- No test file, of 107 in `services/api/tests`, references Payroll.

## 1.2 What Authorization Foundation Requires to Produce a Meaningful Decision

`AuthorizationRequest.resource` (`services/authorization_request.py:33-34`) is `Any | None = None`, described in its own docstring as carrying "whatever the calling Service has already resolved — e.g. the entity being authorized against." The same docstring states: *"Resolving `resource` remains the Service's responsibility — Authorization Foundation performs no persistence and gains none by carrying it."*

`AuthorizationEvaluator`'s base implementation (`services/authorization_evaluator.py:17-18`) performs no resource inspection and unconditionally returns `AuthorizationDecision(allowed=True)` — it is described as the "foundation-phase" default with "no business rule."

Every one of the three existing capability-specific evaluators requires a real, already-resolved resource to produce a non-trivial decision:

- `ApprovalAuthorizationEvaluator` (`services/approval_authorization.py`) is constructed with a `manager_id` that `ApprovalService._authorize` resolves by loading the target entity's `employee_id` and looking up its `HrEmployee.manager_id` (`services/approval.py:225-226`) — this requires an already-persisted `LeaveRequest`/`OvertimeRequest`/`Timesheet` row.
- `LeaveAuthorizationEvaluator` (`services/leave_authorization.py`) compares `resource.employee_id == context.employee_context.employee.id`, where `resource` is a submitted `LeaveRequestCreate` payload or a loaded `LeaveRequest` row (`services/leave_request.py:207-222`).
- `AttendanceAuthorizationEvaluator` (`services/attendance_authorization.py:17-24`) performs the identical comparison against a submitted `AttendanceEventCreate` payload or a loaded `AttendanceEvent` row (`services/attendance_event.py:196-213`).

In all three cases, the entity compared against `context.employee_context.employee.id` (or resolved to a `manager_id`) is a real, already-implemented model with a persisted or submitted `employee_id` field. No evaluator in the repository evaluates a policy against data that does not already exist as a concrete Service-resolved resource.

## 1.3 No Payroll Service Exists to Resolve a Resource

`AttendanceAuthorizationEvaluator`, `LeaveAuthorizationEvaluator`, and `ApprovalAuthorizationEvaluator` are each invoked by their owning Service's own `_authorize` method (`attendance_event.py:196-213`, `leave_request.py:207-222`, `approval.py:209-232`) — the Service is what resolves the concrete resource before authorization runs. No `PayrollService`, `PayrollRunService`, or equivalent exists anywhere in the repository (§1.1) to perform this resolution. There is no code that could call a `PayrollAuthorizationEvaluator` with a real resource, because there is no Service that owns a Payroll entity to resolve one from.

---

# 2. Decision

**Payroll Authorization is not currently a valid capability to decide a policy for.**

No protected resource exists. No Payroll model, aggregate, schema, or Service exists anywhere in the repository (§1.1). Authorization Foundation's own design principle — that the calling Service resolves a concrete `resource` before an evaluator interprets it (§1.2) — has no Service to perform that role for Payroll (§1.3). There is nothing in the repository for a `PayrollAuthorizationEvaluator` to compare, own, get, update, or delete.

**Selecting a policy (Owner Only, Manager Access, Role Based, Hybrid, or any other) is not possible on repository evidence alone**, because every one of those policies presupposes a resource with at least one field (an `employee_id`, a submitter, an owner) to evaluate against — none exists.

This decision does not reject Payroll Authorization as a future capability. It defers it, pending a prerequisite that has not yet occurred (§5).

---

# 3. Rationale

- Every existing authorization-integrated capability in this repository (Approval, Leave, Attendance) was decided only after its own protected resource — a persisted model with an `employee_id` or equivalent — already existed and was already implemented as CRUD (`attendance-authorization/decision.md` was written after `AttendanceEventService`/`api/attendance_events.py` existed; the same is true of Leave Authorization and Approval Authorization, per the prior discovery's review of both). No precedent exists in this repository for deciding an authorization policy before its resource exists.
- Authorization Foundation is explicitly designed so that Authorization Foundation itself "performs no persistence and gains none by carrying [resource]" (`authorization_request.py:27-28`) — resource resolution is unconditionally the calling Service's job. Writing a policy decision for a resource with no resolving Service would require this decision to invent what that Service and its resource look like, which is expressly excluded by instruction and by the Evidence Rule (`AI_DISCOVERY_GUIDE.md`: "Never assume missing functionality... If evidence cannot be found: Report 'No repository evidence found.' Do not invent implementation.").
- A policy decided against an imagined resource shape (e.g., assuming a `PayrollRun.employee_id` field) would not be evidence-driven — it would be speculation formatted as a decision. The instruction governing this document explicitly prohibits inventing such an aggregate.

---

# 4. Rejected Alternatives

## Selecting Owner Only now, by analogy to Leave/Attendance Authorization

Rejected. Owner Only's rule in both existing precedents is `resource.employee_id == context.employee_context.employee.id` — a comparison against a real field on a real resource. No such field exists on any Payroll entity because no Payroll entity exists. Applying this rule "by analogy" would require guessing that a future Payroll resource will have an `employee_id` field shaped the same way `LeaveRequest`/`AttendanceEvent` do — an assumption about unbuilt architecture, not a reading of existing evidence.

## Selecting Manager Access now, by analogy to Approval Authorization

Rejected for the same reason, compounded: Approval Authorization's evaluator additionally requires resolving the target entity's `employee_id` to an `HrEmployee.manager_id` (`approval.py:225-226`) — two levels of resolution against a resource that does not exist.

## Deciding a provisional or placeholder policy pending Payroll's own build

Rejected. A "provisional" policy would still require a concrete resource shape to attach to `AuthorizationRequest.resource`, and any shape chosen now would be invented, not observed — the same objection as above. A placeholder policy also creates a governance artifact (a "Capability Decision") for a capability that, per §2, is not yet decidable, which misrepresents the document's own status.

## Treating "Payroll Authorization" and "Payroll" as already-decided by the roadmap's mere listing

Rejected. `MASTER_ARCHITECTURE_ROADMAP.md` lists "Payroll Authorization" as `Planned` — a roadmap position, not evidence of an existing resource, model, or Service. A roadmap entry names an intended future capability; it does not substitute for the repository evidence (a real model, a real Service) every other Capability Decision in this repository was written against.

---

# 5. Prerequisite Capabilities

The following must exist as repository evidence — not as a roadmap entry — before a Payroll Authorization Capability Decision can select a policy:

- A Payroll aggregate (whatever shape a future Payroll Capability Decision determines — not specified or invented here) — a persisted model with at least one field identifying whose data it represents.
- A Service that owns that aggregate's CRUD and can resolve a concrete `resource` for `AuthorizationRequest`, the same role `AttendanceEventService`/`LeaveRequestService`/`ApprovalService` already play for their own resources (§1.2, §1.3).
- A prior "Payroll" (non-authorization) Capability Decision establishing what that aggregate is, what it owns, and what it consumes — this document does not make that decision and is not a substitute for it.

Separately, and unresolved by any repository evidence reviewed (governance-inconsistency findings from the prior discovery, not restated in full here): whether "Payroll Authorization" (`MASTER_ARCHITECTURE_ROADMAP.md`), "Payroll Integration" (`CAPABILITY_DEPENDENCY_GRAPH.md`), and "Payroll Processing" (`docs/product/02_PRODUCT_SCOPE.md`) name the same prerequisite capability. This decision does not resolve that ambiguity; it is a precondition to knowing which document governs the prerequisite named above.

---

# 6. Architectural Constraints Preserved

## Authorization Foundation

Owns:

- `AuthorizationRequest`, `AuthorizationDecision`, `AuthorizationEvaluator`, `AuthorizationService`

Does **not** own, and this decision does not ask it to own:

- Any Payroll-specific policy
- Resolution of a Payroll resource

No change to Authorization Foundation is proposed or required by this decision. `resource` already exists as an extension point (introduced by Leave Authorization) and remains available, unused, for a future Payroll Authorization Evaluator once its prerequisite (§5) is satisfied.

## This Decision

Owns:

- The determination that no Payroll resource currently exists and that policy selection is therefore not possible on repository evidence (§2).

Must never:

- Select a policy against an assumed or invented resource shape.
- Create, imply, or reserve the name of a `PayrollAuthorizationEvaluator`, `PayrollRun`, `Payslip`, `PayrollPeriod`, or `SalaryRecord` — unlike `attendance-authorization/decision.md`, which reserved `AttendanceAuthorizationEvaluator`'s name against an *already-existing* `AttendanceEvent` resource, this decision has no existing resource to reserve an evaluator name against, and does not do so.

---

# 7. Remaining Risks

- **Governance-sequence risk.** `MASTER_ARCHITECTURE_ROADMAP.md` sequences "Payroll Authorization" immediately after "Attendance Authorization," which could be read as license to proceed directly to a Payroll Authorization policy decision now that Attendance Authorization is merged. This decision records that the roadmap's sequencing names an authorization capability, not a data capability, and that no data capability exists yet to authorize (§2, §5).
- **Naming-ambiguity risk.** Three governance/product documents use three different terms (§5, restated from the prior discovery) without a stated relationship. Any future work that assumes these are the same capability, without resolving the ambiguity first, risks building against the wrong scope.
- **Analogy risk.** The three existing authorization capabilities (Approval, Leave, Attendance) are close, real precedents for *how* a future Payroll Authorization Capability Decision would be structured once its resource exists. This decision does not use them to *select* a policy now (§4), but a future decision could be tempted to reuse Owner Only or Manager Access by pattern-matching alone rather than by re-evaluating repository evidence for whatever Payroll resource is eventually built — that evidence does not exist today and cannot be pre-judged.
- **No repository evidence resolves whether Payroll's resource, once built, will even have a single `employee_id`-shaped owner field** (the shape every existing Owner Only/Manager Access rule depends on) — e.g., a `PayrollRun` batch resource might be organization-scoped rather than employee-scoped. This decision does not assume either shape.

---

# 8. Recommendation

**Implementation Planning must not begin.** There is no Payroll resource, model, Service, or API for an implementation plan to target, and no policy has been or can currently be selected (§2).

**Governance should stop at this decision until a Payroll capability (the data-owning capability, not its authorization) is discovered and decided.** Per §5, the next repository-evidence-producing step is a Discovery and Capability Decision for **Payroll** itself — what aggregate it owns, what it consumes, what Service resolves it — not for Payroll Authorization. Only once that prerequisite exists as repository evidence (a real model and a real Service, per the pattern every other authorization capability in this repository already followed) does a Payroll Authorization Policy Discovery and Capability Decision become answerable from repository evidence rather than from invention.

This document is the Capability Decision for Payroll Authorization requested. Its decision is deferral, not policy selection (§2). No ADR is created. No implementation plan is created.

---

# References

- `docs/architecture/capabilities/payroll-authorization/discovery.md`
- Payroll Capability Repository Discovery (this conversation, not yet persisted as its own file)
- ADR-007 — Authorization Foundation
- ADR-008 — Approval Authorization Policy Model (structural precedent, distinct capability)
- Attendance Authorization Decision (`docs/architecture/capabilities/attendance-authorization/decision.md`) — structural precedent for how a Capability Decision is written once a resource exists
- `MASTER_ARCHITECTURE_ROADMAP.md`, `CAPABILITY_DEPENDENCY_GRAPH.md`, `docs/product/02_PRODUCT_SCOPE.md` — source of the unresolved naming ambiguity recorded in §5

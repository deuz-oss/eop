# Architecture Status

**Document:** Architecture Status
**Status:** Active
**Owner:** Architecture Governance
**Version:** 1.0
**Last Updated:** 2026-08-05

---

# Purpose

This document provides the current architecture status of the EOP platform.

It describes:

- implemented capabilities
- active architecture direction
- capability maturity
- deferred capabilities
- known limitations

This document is a status overview.

Detailed decisions remain in:

- ADR documents
- Capability Decision documents
- Implementation Plans

---

# Architecture Maturity Overview

Current architecture maturity:

Foundation Established
↓
Authorization Capability Introduced
↓
Capability-Level Authorization Adoption
↓
Future Enterprise Governance Expansion

---

# Current Architecture State

The platform currently follows:

Authentication
↓
Identity Context
↓
Authorization Foundation
↓
Capability Authorization Policy
↓
Business Capability

---

# Capability Status Summary

| Capability | Status | Description |
|---|---|---|
| Identity Context | Implemented | User to employee context resolution |
| Authorization Foundation | Implemented | Generic authorization mechanism |
| Approval Authorization | Implemented | Manager Approval policy |
| Leave Authorization | Implemented | Owner Only policy |
| Payroll Authorization | Implemented | Authorization enforcement on payroll capabilities |
| Effective Dating | Implemented | Column-composition mixin + stateless evaluator for temporal validity |
| Monetary Representation | Implemented | Shared `Money` type for monetary values |
| Compensation | Implemented | Effective-dated employee compensation history |
| Payroll (Run + Calculation) | Implemented | Payroll run lifecycle and base-salary payroll calculation |
| Payslip | Implemented | Structural payslip record (create/get/list) |
| Payroll Calculation (Advanced) | Implemented | Tax/formula engine, overtime, rate resolution |
| Shift Assignment | Closed — Subsumed by Work Schedule | No separate implementation; resolved by `WorkSchedule` |
| Work Schedule | Implemented | Employee-scoped, effective-dated weekly working-day pattern |
| Recruitment | Implemented | `JobRequisition`/`Candidate`/`Application` (lifecycle) + `Interview`/`Offer` (flat records), `RequireRole("admin")` auth |
| Performance | Implemented | `PerformanceReview` minimal flat CRUD record, `RequireRole("admin")` auth |
| Store | Implemented | `Store`/`StoreType` master data (Customer & Store unified), `RequireRole("admin")` auth |
| Visit | Implemented | Field employee store visits, Owner Only auth (`VisitAuthorizationEvaluator`) |
| Permission Model | Deferred | Not introduced |
| Policy Engine | Deferred | Not introduced |
| Delegated Approval | Deferred | Not introduced |
| Organization Hierarchy | Deferred | Not introduced |

---

# Implemented Capabilities

---

# Identity Context

**Status:**

Implemented

**Related:**

- ADR-006

---

## Purpose

Provides consistent employee identity resolution.

Flow:

CurrentUser
↓
HrEmployee
↓
EmployeeContext

---

## Responsibilities

Identity Context owns:

- user-to-employee resolution
- employee context creation
- identity validation

---

## Consumers

Current consumers include:

- authorization flows
- approval workflows

---

## Known Limitation

Resolved. EmployeeContext exceptions now have centralized HTTP mappings
(`EmployeeContextNotFoundError` -> 403, `MultipleEmployeeContextError` -> 409),
implemented in `dependencies/employee_context.py`.

Tracked in:

TECHNICAL_DEBT_REGISTER.md
TD-001

---

# Authorization Foundation

**Status:**

Implemented

**Related:**

- ADR-007
- PR-052

---

## Purpose

Provides generic authorization infrastructure.

Components:

- AuthorizationRequest
- AuthorizationDecision
- AuthorizationEvaluator
- AuthorizationService

---

## Design Principle

Authorization mechanism is separated from authorization policy.

Architecture:

Authorization Foundation

Capability Authorization Policy

---

## Responsibilities

Authorization Foundation owns:

- authorization execution
- decision representation
- evaluator abstraction

---

## Does Not Own

The foundation does not define:

- permissions
- roles
- ownership
- approval rules
- business policies

---

# Approval Authorization

**Status:**

Implemented

**Related:**

- ADR-008
- PR-053
- Approval Authorization Decision
- Approval Authorization Implementation Plan

---

## Purpose

Provides authorization enforcement for approval workflows.

---

## Current Policy

Policy:

Manager Approval

Rule:

request.employee.manager_id
approver.employee.id

---

## Supported Behavior

Allowed:

Direct Manager
↓
Approve / Reject

---

Denied:

Non Manager
↓
Forbidden

---

## Integration Flow

Current implementation:

CurrentRequestContext
↓
AuthorizationRequest
↓
AuthorizationService
↓
ApprovalAuthorizationEvaluator
↓
AuthorizationDecision
↓
ApprovalService

---

## Constraints

The capability does not implement:

- delegated approval
- indirect approval
- recursive hierarchy
- approval roles
- workflow assignment
- permission model

---

# Leave Authorization

**Status:**

Implemented

**Related:**

- Leave Authorization Discovery
- Leave Authorization Policy Discovery
- Leave Authorization Decision
- Leave Authorization Implementation Plan
- Leave Authorization Architecture Review

---

## Purpose

Provides authorization enforcement for `LeaveRequest` create/get/update/delete operations, distinct from Approval Authorization's `approve`/`reject` enforcement on the same resource.

---

## Current Policy

Policy:

Owner Only

Rule:

LeaveRequest.employee_id
==
RequestContext.employee_context.employee.id

---

## Supported Behavior

Allowed:

Owner
↓
Create / Get / Update / Delete

---

Denied:

Non Owner
↓
Forbidden

---

## Integration Flow

Current implementation:

CurrentRequestContext
↓
AuthorizationRequest
↓
AuthorizationService
↓
LeaveAuthorizationEvaluator
↓
AuthorizationDecision
↓
LeaveRequestService

---

## Constraints

The capability does not implement:

- manager access
- role-based access
- hybrid authorization
- delegated access
- workflow assignment
- permission model

---

# Approval Workflow

**Status:**

Implemented

---

## Responsibilities

Approval workflow owns:

- approval state transition
- approval execution
- workflow lifecycle

---

## Authorization Boundary

Approval workflow does not own:

- authorization policy evaluation
- role validation
- ownership validation

Authorization is delegated to:

Authorization Foundation

---

# Business Domain Capabilities

---

# Effective Dating

**Status:**

Implemented

**Related:**

- `docs/architecture/capabilities/effective-dating/decision.md` §12

---

## Purpose

Provides a reusable temporal-validity mechanism for aggregates that must retain historical, effective-dated rows.

Components:

- `EffectiveDatingMixin` (column-composition mixin — `effective_from`/`effective_to`)
- `EffectiveDatingEvaluator` (stateless resolve/is-effective evaluation)

---

## Design Principle

Effective Dating owns the temporal mechanism only. It has no persistence of its own and no business policy — overlap rules, correction semantics, and business meaning belong to the consuming capability.

---

## Consumers

Current:

- Compensation

---

# Monetary Representation

**Status:**

Implemented

**Related:**

- `docs/architecture/capabilities/monetary-representation/implementation-readiness-review.md`
- `docs/architecture/capabilities/monetary-representation/monetary-adoption-policy.md`

---

## Purpose

Provides a shared `Money` type (frozen dataclass, two-decimal half-up normalization) for monetary values, replacing ad hoc float/Decimal handling per capability.

---

## Consumers

Current:

- Compensation
- Payslip

---

# Compensation

**Status:**

Implemented

**Related:**

- `docs/architecture/capabilities/compensation/decision.md` §17–19
- `docs/architecture/capabilities/compensation/final-governance-summary.md` (superseded by §17–19 addendums — retained for governance history only)

---

## Purpose

Represents the monetary terms agreed between employer and employee as an effective-dated history, not a single mutable row.

---

## Responsibilities

Compensation owns:

- employee compensation agreement and business meaning
- effective-dated history (multiple historical rows per employee via Effective Dating)
- overlap policy (mutually exclusive effective periods, hard reject)
- compensating-correction semantics (`corrects_id`, corrected row remains immutable)

Compensation does not own:

- payroll calculation or execution
- payslip generation
- the monetary or temporal mechanism (consumed from Monetary Representation / Effective Dating)

---

## Constraints

The capability does not implement:

- Daily Rate persistence
- Allowance ownership/model
- Payroll's as-of-date resolution (`PayrollRun` date/period semantics remain deferred; Payroll integration with multi-row Compensation is a separate task)

---

# Payroll (Run + Calculation)

**Status:**

Implemented

**Related:**

- `docs/architecture/capabilities/payroll/decision.md`
- `docs/architecture/capabilities/payroll/architecture-review.md`

---

## Purpose

Provides payroll run lifecycle (`PayrollRun`: DRAFT → PROCESSING → COMPLETED) and base-salary payroll calculation (`PayrollCalculationService`).

---

## Constraints

Scoped to the accepted implementation plan only. Does not implement:

- tax/statutory formula calculation
- pay-period cadence beyond what iteration 1–2 requires
- rate sources beyond Compensation's base salary

These remain the separate, still-blocked "Payroll Calculation (Advanced)" capability — see Deferred Architecture below.

---

# Payslip

**Status:**

Implemented

**Related:**

- `docs/architecture/capabilities/payslip/decision.md`
- `docs/architecture/capabilities/payslip/architecture-review.md` ("Approved with Known Risks")

---

## Purpose

Structural payslip record. Scoped to create/get/list only — no update or delete ("CRUD-minus-mutation"), matching the accepted implementation plan.

---

# Authorization Adoption Status

Current adoption:

| Capability | Authorization Status |
|---|---|
| Approval Workflow | Implemented |
| Leave Approval | Implemented |
| Overtime Approval | Implemented |
| Timesheet Approval | Implemented |

---

# Deferred Architecture

The following capabilities are intentionally deferred.

---

# Permission Model

**Status:**

Deferred

---

## Reason

Current authorization model does not require centralized permissions.

---

## Future Requirement

May support:

- permission vocabulary
- permission assignment
- reusable access control

Requires ADR before implementation.

---

# Policy Engine

**Status:**

Deferred

---

## Reason

Current capability-specific evaluators are sufficient.

---

## Future Requirement

May support:

- policy composition
- policy registry
- dynamic evaluation

Requires architecture decision.

---

# Delegated Approval

**Status:**

Deferred

---

## Reason

No business decision exists for:

- delegation rules
- delegation lifetime
- delegation ownership

---

# Organization Hierarchy

**Status:**

Deferred

---

## Current Model

Current employee relationship:

Employee
↓
Direct Manager

---

## Not Supported

- recursive hierarchy
- escalation chain
- organizational graph

---

## Payroll Calculation (Advanced)

**Status:** Implemented

**Related:** `docs/architecture/capabilities/payroll-calculation/decision.md`, `payroll-calculation/iteration-1-implementation-plan.md`

Pay-period cadence, statutory/tax formula (configurable via `PayrollStatutoryParameter`), overtime calculation, and rate resolution, layered onto the base-salary Payroll Calculation above. Attendance/leave deduction (`AttendanceLeaveDeductionCalculator`) is implemented: a day is deductible only when `ReconciliationService` classifies it `absent` and the employee's effective `WorkSchedule` marks that weekday as worked (D5 Option (a), unchanged) — resolves the integration gap this capability previously deferred pending Work Schedule's existence.

---

## Shift Assignment

**Status:** Closed — Subsumed by Work Schedule

**Related:** `docs/architecture/capabilities/shift-assignment/final-governance-summary.md`

No separate implementation exists. Work Schedule's `WorkSchedule` aggregate already is, field for field, the effective-dated employee↔shift relationship this capability investigated; a separate entity would have duplicated it.

---

## Work Schedule

**Status:** Implemented

**Related:** `docs/architecture/capabilities/work-schedule/iteration-1-implementation-plan.md`

Employee-scoped, effective-dated weekly working-day pattern (`WorkSchedule`), referencing `Shift`, with `corrects_id` correction lineage — mirrors Compensation's effective-dating/correction shape.

---

## Recruitment

**Status:** Implemented

**Related:** `docs/architecture/capabilities/recruitment/iteration-1-scope-and-implementation-plan.md`, `iteration-2-business-decision-package.md` (Approved), `authorization-decision.md`

`JobRequisition` (open positions), `Candidate` (people applying, not `HrEmployee`s), `Application` (peer-association linking the two, mirrors `Assignment`). CPO/CTO product decision, superseding Recruitment's prior HRIS exclusion in `docs/product/02_PRODUCT_SCOPE.md`.

`Application` owns the recruitment lifecycle (Iteration 2, Approved): `applied → screening → interviewing → offered → hired`, with `rejected`/`withdrawn` reachable from any non-terminal stage, forward-only, terminal states not reopenable. `JobRequisition` closure never cascades to `Application`.

`Interview`/`Offer` (Iteration 3): minimal, flat CRUD records linked to `Application` by FK, no status/lifecycle of their own, no coupling to `Application`'s transitions, no compensation terms on `Offer`.

Still open, not resolved by any iteration so far: candidate self-service, candidate-to-employee conversion, interview/offer acceptance-or-expiry semantics, organization scoping.

**Authorization:** Role Based (`RequireRole("admin")`), CPO/CTO decision — see `docs/architecture/capabilities/recruitment/authorization-decision.md`. Admin-only for all Recruitment routes (`JobRequisition`/`Candidate`/`Application`/`Interview`/`Offer`); non-admin authenticated users get 403.

---

## Performance

**Status:** Implemented

**Related:** `docs/architecture/capabilities/performance/iteration-1-scope-and-implementation-plan.md`, `iteration-2-business-decision-package.md` (Approved)

`PerformanceReview` (Iteration 1): minimal, flat CRUD record (`employee_id`, `review_period_start`/`review_period_end`, `notes`). No effective dating, no uniqueness constraint — mirrors the `PayrollRun`/`Interview`/`Offer` "CRUD shell first" precedent. CPO/CTO product decision, superseding Performance Review's prior HRIS exclusion in `docs/product/02_PRODUCT_SCOPE.md` (distinct from the already-in-scope §7 "Performance Management" field/sales KPIs, which this capability does not touch).

`PerformanceReview` owns a minimal lifecycle (Iteration 2, Approved, D1 Option B): `draft → finalized`, admin-only transition, forward-only, terminal state not reopenable, no re-finalizing. `status` is never accepted by `PerformanceReviewCreate`/`PerformanceReviewUpdate` — the only way to reach `finalized` is the dedicated `finalize` transition. Finalized reviews reject substantive field changes via ordinary update.

Still open, not resolved by any iteration so far: rating scales, competency frameworks, employee acknowledgement, manager/peer/self-review semantics, approval hierarchy, calibration, goal weighting, review cadence, employee-manager relationships, organization scoping, notifications.

**Authorization:** Role Based (`RequireRole("admin")`), same mechanism as `PayrollRun`/Recruitment. Admin-only for all `PerformanceReview` routes; non-admin authenticated users get 403.

---

## Store

**Status:** Implemented

**Related:** `docs/architecture/capabilities/store/iteration-1-scope-and-implementation-plan.md`

`Store` (Iteration 1): single aggregate fulfilling Roadmap Phase 3's "Customer"/"Store"/"Outlet"/"Modern Trade"/"General Trade"/"Store Classification"/"Geolocation" items — Customer and Store resolved as the same entity, not two, per product evidence (MVP Scope names only "Store"; "Product Boundaries" places account/billing concepts in ERP/CRM, out of scope). Fields: `code`/`name`/`organization_id`/`store_type_id`/`address`/`latitude`/`longitude`/`description`. `StoreType` is a free-form trade-channel lookup mirroring `LocationType`, covering Modern Trade/General Trade/Store Classification collectively. Flat CRUD, no lifecycle.

No relationship to `HrEmployee`, `Location`, or Territory/Region/Area. The Territory/Region/Area vs. Organization Hierarchy (TD-003/Phase 6) naming-collision boundary is explicitly held open, not resolved by this capability.

**Authorization:** Role Based (`RequireRole("admin")`), same mechanism as `PayrollRun`/Recruitment/Performance. Admin-only for all `Store`/`StoreType` routes; non-admin authenticated users get 403.

---

## Visit

**Status:** Implemented

**Related:** `docs/architecture/capabilities/visit/iteration-1-scope-and-implementation-plan.md`

`Visit` (Iteration 1): a field employee's visit to a `Store`, per Roadmap Phase 4 "Field Operations". Fields: `employee_id`, `store_id`, `visited_at`, `notes`. Flat CRUD, no lifecycle/status field.

No Mission reference — resolved from evidence as independent, ad-hoc visits (every product document naming both `Visit` and `Mission` treats them as parallel concepts, never nested; `Mission Planning` groups with `Territory Assignment` in Product Scope §5, a further reason not to couple them). No GPS coordinates, no photo/selfie evidence, no check-in/check-out timestamps — all explicitly deferred, no field added in Iteration 1.

Explicitly distinct from the existing HR `AttendanceEvent`/`ReconciliationService` capability (shift clock-in/out feeding Payroll's attendance deduction) despite the shared word "Attendance" in product scope — neither reused nor modified. Field Execution's own "Attendance" concept (grouped in Product Scope §6 with Check In/Check Out/GPS Validation/Selfie Verification) remains a separate, unscoped future item.

No relationship to `Location`, Territory/Region/Area, or Organization Hierarchy.

**Authorization:** Owner Only, via a dedicated `VisitAuthorizationEvaluator` mirroring `AttendanceAuthorizationEvaluator`'s exact shape — reuse of the established per-capability Owner Only evaluator convention (`resource.employee_id == context.employee_context.employee.id`), not new authorization infrastructure.

---

# Technical Debt Status

Current tracked debt:

| ID | Title | Status |
|---|---|---|
| TD-001 | EmployeeContext HTTP Exception Mapping | Resolved |
| TD-002 | Approval Authorization Concurrency Protection | Open |
| TD-003 | Employee Manager Hierarchy Limitation | Open |
| TD-004 | Permission and Policy Model Not Implemented | Open |
| TD-005 | Authorization Foundation Consumer Coverage | Open |

Reference:

TECHNICAL_DEBT_REGISTER.md

---

# Architecture Governance Status

Governance process:

Discovery
↓
Policy Discovery
↓
Capability Decision
↓
Implementation Plan
↓
Implementation
↓
Architecture Review

---

## Current State

All implemented architecture capabilities must have:

- ADR
- discovery evidence
- capability decision
- implementation plan
- validation result

---

# Current Architecture Risks

## Identity Context Mapping

Resolved (TD-001) — EmployeeContext failures now map to 403/409, not generic errors.

---

## Authorization Expansion

Risk:

Future authorization requirements may require additional abstractions.

Examples:

- permissions
- roles
- policy engine

Resolution requires ADR.

---

## Hierarchy Expansion

Risk:

Future approval escalation requires organizational hierarchy capability.

Current direct manager model is intentionally limited.

---

# Architecture Roadmap Alignment

Current roadmap position:

Phase 1
Foundation
✓ Identity Context
✓ Authorization Foundation
Phase 2
Capability Authorization
✓ Approval Authorization
✓ Leave Authorization
Phase 3
Enterprise Authorization
○ Permission Model
○ Policy Engine
○ Delegated Approval
○ Organization Hierarchy

---

# References

- MASTER_ARCHITECTURE_BLUEPRINT.md
- MASTER_ARCHITECTURE_ROADMAP.md
- ARCHITECTURE_PRINCIPLES.md
- ARCHITECTURE_CHANGELOG.md
- TECHNICAL_DEBT_REGISTER.md
- CLAUDE_IMPLEMENTATION_GUIDE.md
- ADR documents
- Capability Decision documents

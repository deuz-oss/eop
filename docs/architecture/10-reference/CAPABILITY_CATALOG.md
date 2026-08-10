# Capability Catalog

**Document:** Capability Catalog
**Status:** Active
**Owner:** Architecture Governance
**Version:** 1.0
**Last Updated:** 2026-08-05

---

# Purpose

This document provides a catalog of all architectural capabilities within the EOP platform.

A capability represents a cohesive architectural responsibility that may be implemented by one or more modules.

This catalog provides:

- capability ownership
- implementation status
- architectural dependencies
- governing ADRs
- implementation references

Detailed implementation remains in the individual capability documents.

---

# Capability Lifecycle

| Status | Meaning |
|--------|---------|
| Planned | Architecture approved but not implemented |
| In Progress | Currently being implemented |
| Implemented | Fully implemented |
| Deferred | Explicitly postponed |
| Retired | No longer used |

---

# Capability Overview

| Capability | Status | Owner | Primary ADR |
|------------|--------|-------|-------------|
| Identity Context | Implemented | Platform | ADR-006 |
| Authorization Foundation | Implemented | Platform | ADR-007 |
| Approval Authorization | Implemented | Approval | ADR-008 |
| Leave Authorization | Implemented | Leave | ADR-007 |
| Payroll Authorization | Implemented | Payroll | ADR-007 |
| Approval Workflow | Implemented | Approval | ADR-004 |
| HR Master Data | Implemented | HR | ADR-003 |
| Effective Dating | Implemented | Platform | — (capability decision only) |
| Monetary Representation | Implemented | Platform | — (capability decision only) |
| Compensation | Implemented | HR | — (capability decision only) |
| Payroll (Run + Calculation) | Implemented | Payroll | — (capability decision only) |
| Payslip | Implemented | Payroll | — (capability decision only) |
| Payroll Calculation (Advanced) | Implemented | Payroll | — (capability decision only) |
| Shift Assignment | Closed — Subsumed by Work Schedule | HR | — |
| Work Schedule | Implemented | HR | — (capability decision only) |
| Recruitment | Implemented | HR | — (CPO/CTO product decision) |
| Performance | Implemented | HR | — (CPO/CTO product decision) |
| Store | Implemented | Organization Management & Master Data | — (capability decision only) |
| Visit | Implemented | Field Operations | — (capability decision only) |
| Target | Implemented | Performance Management | — (CPO/CTO product decision) |
| Achievement | Implemented | Performance Management | — (CPO/CTO product decision) |
| Dashboard (Performance Management) | Implemented | Performance Management | — (capability decision only) |
| Permission Model | Deferred | Platform | Future ADR |
| Policy Engine | Deferred | Platform | Future ADR |
| Delegated Approval | Deferred | Approval | Future ADR |
| Organization Hierarchy | Deferred | HR | Future ADR |

---

# Identity Context

**Status**

```
Implemented
```

---

## Purpose

Provides deterministic employee identity resolution.

Flow:

```
CurrentUser

↓

HrEmployee

↓

EmployeeContext
```

---

## Responsibilities

- Resolve authenticated user
- Resolve employee
- Build RequestContext
- Provide EmployeeContext

---

## Dependencies

- Authentication

---

## Consumers

- Authorization Foundation
- Approval Authorization

---

## Governing ADR

ADR-006

---

## Implementation

Implemented

---

# Authorization Foundation

**Status**

```
Implemented
```

---

## Purpose

Provides reusable authorization infrastructure.

---

## Responsibilities

Provides:

- AuthorizationRequest
- AuthorizationDecision
- AuthorizationEvaluator
- AuthorizationService

---

## Does NOT Define

- roles
- permissions
- ownership
- approval rules

---

## Dependencies

Identity Context

---

## Consumers

- Approval Authorization

---

## Governing ADR

ADR-007

---

## Implementation

Completed in:

```
PR-052
```

---

# Approval Authorization

**Status**

```
Implemented
```

---

## Purpose

Protect approval workflows using capability-specific authorization policy.

---

## Policy

Current policy:

```
Manager Approval
```

Authorization rule:

```
request.employee.manager_id
==
approver.employee.id
```

Only direct manager approval is supported.

---

## Responsibilities

- Evaluate approval authorization
- Produce AuthorizationDecision
- Deny unauthorized approvals

---

## Architecture

```
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
```

---

## Dependencies

Requires:

- Identity Context
- Authorization Foundation
- Approval Workflow

---

## Consumers

- Leave Approval
- Overtime Approval
- Timesheet Approval

---

## Governing ADR

ADR-008

---

## Implementation

Completed in:

```
PR-053
```

---

## Out of Scope

Not implemented:

- delegated approval
- recursive hierarchy
- approval roles
- workflow assignment
- permission model
- policy engine

---

# Leave Authorization

**Status**

```
Implemented
```

---

## Purpose

Protect `LeaveRequest` create/get/update/delete operations using capability-specific authorization policy, distinct from Approval Authorization's `approve`/`reject` enforcement on the same resource.

---

## Policy

Current policy:

```
Owner Only
```

Authorization rule:

```
LeaveRequest.employee_id
==
RequestContext.employee_context.employee.id
```

Only the owning employee may create, view, update, or delete their own `LeaveRequest`.

---

## Responsibilities

- Evaluate leave authorization
- Produce AuthorizationDecision
- Deny unauthorized access

---

## Architecture

```
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
```

---

## Dependencies

Requires:

- Identity Context
- Authorization Foundation

---

## Consumers

- None (LeaveRequest CRUD lifecycle only)

---

## Governing ADR

ADR-007 (Authorization Foundation dependency; no dedicated Leave Authorization ADR exists)

---

## Implementation

Completed in:

```
PR-056
```

---

## Out of Scope

Not implemented:

- manager access
- role-based access
- hybrid authorization
- delegated access
- permission model
- policy engine

---

# Approval Workflow

**Status**

```
Implemented
```

---

## Purpose

Execute approval business workflows.

---

## Responsibilities

- approve
- reject
- state transition

---

## Delegates

Authorization to:

```
Approval Authorization
```

---

## Governing ADR

ADR-004

---

## Implementation

Implemented

---

# HR Master Data

**Status**

```
Implemented
```

---

## Purpose

Provide reusable HR reference data.

---

## Includes

- Job Grade
- Employment Type
- Employment Status
- Shift
- Holiday

---

## Governing ADR

ADR-003

---

# Effective Dating

**Status**

```
Implemented
```

---

## Purpose

Reusable temporal-validity mechanism: column-composition mixin (`effective_from`/`effective_to`) plus a stateless evaluator. No persistence of its own, no business policy.

---

## Consumers

- Compensation

---

## Governing Decision

`docs/architecture/capabilities/effective-dating/decision.md` §12

---

# Monetary Representation

**Status**

```
Implemented
```

---

## Purpose

Shared `Money` type (frozen dataclass, two-decimal half-up normalization) for monetary values.

---

## Consumers

- Compensation
- Payslip

---

## Governing Decision

`docs/architecture/capabilities/monetary-representation/implementation-readiness-review.md`, `monetary-adoption-policy.md`

---

# Compensation

**Status**

```
Implemented
```

---

## Purpose

Effective-dated employee compensation history: multiple historical rows per employee, overlap rejection, compensating-correction semantics (`corrects_id`).

---

## Dependencies

- Effective Dating
- Monetary Representation
- HrEmployee, JobGrade

---

## Consumers

- Payroll Calculation (base-salary tier)

---

## Governing Decision

`docs/architecture/capabilities/compensation/decision.md` §17–19

---

## Out of Scope

- Daily Rate persistence
- Allowance ownership/model
- Payroll as-of-date resolution

---

# Payroll (Run + Calculation)

**Status**

```
Implemented
```

---

## Purpose

`PayrollRun` lifecycle (DRAFT → PROCESSING → COMPLETED) and base-salary `PayrollCalculationService`.

---

## Dependencies

- Compensation
- Payroll Authorization

---

## Governing Decision

`docs/architecture/capabilities/payroll/decision.md`, `architecture-review.md`

---

## Out of Scope

- tax/statutory formula calculation
- pay-period cadence beyond iteration 1–2
- rate sources beyond Compensation base salary
(tracked separately as Payroll Calculation (Advanced) — Blocked)

---

# Payslip

**Status**

```
Implemented
```

---

## Purpose

Structural payslip record — create/get/list only ("CRUD-minus-mutation").

---

## Dependencies

- Payroll (Run + Calculation)
- Monetary Representation

---

## Governing Decision

`docs/architecture/capabilities/payslip/decision.md`, `architecture-review.md`

---

# Payroll Calculation (Advanced)

**Status**

```
Implemented
```

---

## Purpose

Pay-period cadence, statutory/tax deduction, overtime, attendance/leave deduction, and rate-resolution calculation, layered onto the base Payroll (Run + Calculation) capability. Attendance/leave deduction (`AttendanceLeaveDeductionCalculator`) reads `ReconciliationService`/`WorkScheduleService` read-only — a day is deductible only when classified `absent` and scheduled per the employee's effective `WorkSchedule`.

---

## Governing Decision

`docs/architecture/capabilities/payroll-calculation/decision.md` (business decisions resolved), `payroll-calculation/iteration-1-implementation-plan.md`

---

# Shift Assignment

**Status**

```
Closed — Subsumed by Work Schedule
```

---

## Reason

Work Schedule's `WorkSchedule` aggregate (`employee_id`, `shift_id`, `effective_from`/`effective_to`, `corrects_id`) is, field for field, the effective-dated employee↔shift relationship this capability's own governance investigated. Building a separate `ShiftAssignment` entity would duplicate an already-merged mechanism. No implementation exists under this name; `WorkSchedule.get_by_employee` is the resolution method.

---

## Governing Decision

`docs/architecture/capabilities/shift-assignment/final-governance-summary.md`

---

# Work Schedule

**Status**

```
Implemented
```

---

## Purpose

Employee-scoped, effective-dated weekly working-day pattern plus the `Shift` worked on those days, with `corrects_id` correction lineage.

---

## Governing Decision

`docs/architecture/capabilities/work-schedule/iteration-1-implementation-plan.md` (gaps resolved under CPO/CTO directive, citing Effective Dating/Compensation precedent)

---

# Recruitment

**Status**

```
Implemented
```

---

## Purpose

`JobRequisition` (open positions, master-data-shaped), `Candidate` (people applying, not `HrEmployee`s), `Application` (peer-association linking the two, mirrors `Assignment`, owns the recruitment lifecycle — Iteration 2: `applied → screening → interviewing → offered → hired`, with `rejected`/`withdrawn` reachable from any non-terminal stage, forward-only, no reopening). `Interview`/`Offer` (Iteration 3): minimal, flat CRUD records linked to `Application`, no status/lifecycle of their own, no coupling to `Application`'s transitions. No candidate self-service, no candidate-to-employee conversion, no interview/offer acceptance-or-expiry semantics, no organization scoping — each remains a genuinely open decision, not resolved by any iteration so far.

---

## Authorization

Role Based (`RequireRole("admin")`) — admin-only for all `JobRequisition`/`Candidate`/`Application`/`Interview`/`Offer` routes. Same mechanism and rationale as `PayrollRun` (`payroll-authorization/decision.md` Addendum): none of the five entities carries an `employee_id`-shaped owner field, so Owner Only does not apply, and no new authorization framework was introduced. See `docs/architecture/capabilities/recruitment/authorization-decision.md`.

---

## Governing Decision

CPO/CTO product decision (superseded `docs/product/02_PRODUCT_SCOPE.md`'s prior HRIS exclusion), `docs/architecture/capabilities/recruitment/iteration-1-scope-and-implementation-plan.md`

---

# Performance

**Status**

```
Implemented
```

---

## Purpose

`PerformanceReview`: minimal, flat CRUD record (`employee_id`, `review_period_start`/`review_period_end`, `notes`), no effective dating (discrete historical event, not evolving current state), no uniqueness constraint (multiple reviews per employee permitted). Mirrors the same "CRUD shell first" precedent as `PayrollRun`/`JobRequisition`/`Interview`/`Offer`.

Owns a minimal lifecycle (Iteration 2, Approved, D1 Option B): `draft → finalized`, admin-only, forward-only, `finalized` terminal, no reopening, no re-finalizing. `status` is not accepted by `PerformanceReviewCreate`/`PerformanceReviewUpdate` — only the dedicated `finalize` transition can set it. Finalized reviews reject substantive field changes via ordinary update.

Rating scales, competency frameworks, employee acknowledgement, manager/peer/self-review semantics, approval hierarchy, calibration, goal weighting, review cadence, and notifications remain undecided — none required so far.

---

## Authorization

Role Based (`RequireRole("admin")`) — admin-only for all `PerformanceReview` routes, including `finalize`. Same mechanism and rationale as `PayrollRun`/Recruitment: no new authorization framework introduced.

---

## Governing Decision

CPO/CTO product decision (superseded `docs/product/02_PRODUCT_SCOPE.md`'s prior HRIS exclusion for "Performance Review" — distinct from the already-in-scope §7 "Performance Management" field/sales KPIs), `docs/architecture/capabilities/performance/iteration-1-scope-and-implementation-plan.md`, `iteration-2-business-decision-package.md` (Approved)

---

# Store

**Status**

```
Implemented
```

---

## Purpose

`Store`: single aggregate fulfilling the Roadmap Phase 3 "Customer"/"Store"/"Outlet"/"Modern Trade"/"General Trade"/"Store Classification"/"Geolocation" items — Customer and Store are the same real-world entity in this product's domain language, not two separate aggregates (evidence: `docs/product/02_PRODUCT_SCOPE.md` MVP Scope names only "Store"; "Product Boundaries" places account/billing/pipeline concepts in ERP/CRM, both out of scope). `code`/`name`/`organization_id`/`store_type_id`/`address`/`latitude`/`longitude`/`description`, flat CRUD, no lifecycle. `StoreType` is a free-form trade-channel lookup (mirrors `LocationType` exactly) covering Modern Trade/General Trade/Store Classification collectively — not a fixed enum, since no closed value set is named anywhere in product scope.

No relationship to `HrEmployee`, `Location`, or any Territory/Region/Area concept — that boundary is explicitly held open, not resolved, pending a future Territory-focused discovery (`docs/architecture/capabilities/store/iteration-1-scope-and-implementation-plan.md` §6).

---

## Authorization

Role Based (`RequireRole("admin")`) — admin-only for all `Store`/`StoreType` routes. Same mechanism and rationale as `PayrollRun`/`JobRequisition`/`PerformanceReview`: no natural owner-employee field, no new authorization framework introduced.

---

## Governing Decision

`docs/architecture/capabilities/store/iteration-1-scope-and-implementation-plan.md` (Discovery + Implementation, per Roadmap Phase 3 / Product Scope §4 "Customer & Store")

---

# Visit

**Status**

```
Implemented
```

---

## Purpose

`Visit`: a field employee's visit to a `Store`, per Roadmap Phase 4 "Field Operations". Fields: `employee_id`, `store_id`, `visited_at`, `notes`. Flat CRUD, no lifecycle/status field, no Mission reference (evidence-resolved as independent, ad-hoc visits — every product document naming both treats them as parallel concepts, never nested), no GPS/photo/check-in-out (all explicitly deferred, no field added). Explicitly distinct from `AttendanceEvent` (HR shift clock-in/out feeding Payroll) despite the shared word "Attendance" in product scope — neither reused nor modified.

No relationship to `HrEmployee` beyond the owning FK, no `Location`, no Territory/Region/Area, no Organization Hierarchy.

---

## Authorization

Owner Only — `resource.employee_id == context.employee_context.employee.id`, via a dedicated `VisitAuthorizationEvaluator` mirroring `AttendanceAuthorizationEvaluator`'s exact shape (confirmed reuse of the established per-capability Owner Only evaluator convention, not new authorization infrastructure).

---

## Governing Decision

`docs/architecture/capabilities/visit/iteration-1-scope-and-implementation-plan.md`

---

# Target

**Status**

```
Implemented
```

---

## Purpose

`Target`: an employee-scoped goal for one `Kpi`, for one calendar month — the definition/assignment layer in Roadmap Phase 5's `KPI → Target → Achievement → Dashboard → Reporting` sequence, sitting directly after the already-implemented `Kpi` (definition-only reference data) and before the not-yet-built `Achievement` (future capability, measured/actual value). Fields: `kpi_id`, `employee_id`, `period_year`, `period_month`, `goal_value`. Flat CRUD, no lifecycle.

Ownership scope resolved to Employee by CPO/CTO product decision — Store, Organization, and Territory/Region/Area were evaluated and not required for Iteration 1; `employee_id` is a business-scope assignment field, not an Organization Hierarchy relationship, and introduces no new dependency on the separately-gated Organization Hierarchy capability (TD-003/Phase 6). At most one `Target` per `(employee_id, kpi_id, period_year, period_month)`, enforced at the database level.

This is the Target layer only. No `Achievement` (actual/measured value, achievement percentage, scoring), no `Dashboard`, no `Reporting`, no calculation or formula engine, no team/organization/store/territory-scoped targets, no approval or workflow.

---

## Authorization

Role Based (`RequireRole("admin")`) — a `Target` is assigned to an employee by an administrator, not self-authored by the employee. `employee_id` is Target's business scope, not its authorization boundary — no Owner Only evaluator exists for this entity, a deliberate distinction from `Visit`/`Survey`/`Compensation`. Same mechanism as `Kpi`/`Store`/`PayrollRun`, no new authorization framework introduced.

---

## Governing Decision

`docs/architecture/capabilities/performance/target-iteration-1-scope-and-implementation-plan.md`

---

# Achievement

**Status**

```
Implemented
```

---

## Purpose

`Achievement`: the manually recorded actual value against exactly one `Target` — the actual-value layer in Roadmap Phase 5's `KPI → Target → Achievement → Dashboard → Reporting` sequence, sitting directly after `Target` (employee-scoped monthly goal) and before the not-yet-built `Dashboard`/`Reporting`. Fields: `target_id`, `actual_value`. Flat CRUD, no lifecycle.

`target_id` is the sole relationship (`ON DELETE RESTRICT`) — `employee_id`/`kpi_id`/`period_year`/`period_month` are not duplicated on `Achievement`; they are read through `Achievement.target`. At most one `Achievement` per `Target`, enforced at the database level via a unique `target_id`.

`actual_value` (`Numeric(18, 6)`, mirrors `Target.goal_value`'s precedent exactly) is entered manually by an administrator — no automatic calculation, Visit/Survey aggregation, Attendance/Payroll integration, or KPI formula engine. Computed/derived Achievement is explicitly deferred to a future capability/decision.

---

## Authorization

Role Based (`RequireRole("admin")`) — an `Achievement` is manually recorded by an administrator, mirroring exactly how an administrator manually assigns the `Target` goal. `Target.employee_id` remains business scope only, never an authorization boundary — no `AchievementAuthorizationEvaluator` exists. Same mechanism as `Kpi`/`Target`/`Store`, no new authorization framework introduced.

---

## Governing Decision

`docs/architecture/capabilities/performance/achievement-iteration-1-scope-and-implementation-plan.md`

---

# Dashboard (Performance Management)

**Status**

```
Implemented
```

---

## Purpose

Performance Management Dashboard Iteration 1: a read-only summary of `Kpi`/`Target`/`Achievement` row counts, organization-wide — the counts layer in Roadmap Phase 5's `KPI → Target → Achievement → Dashboard → Reporting` sequence, sitting directly after `Achievement` and before the not-yet-built `Reporting`. Route: `GET /performance/dashboard`. Response: `kpi_count`, `target_count`, `achievement_count`. No repository of its own — reads directly via `KpiRepository`/`TargetRepository`/`AchievementRepository`'s existing `BaseRepository.count()`.

Deliberately distinct from the pre-existing, unrelated `GET /dashboard` endpoint (Phase 1/2 generic `Organization`/`Project`/`Employee`/`Assignment`/`Task` scaffold) — that endpoint is not part of Phase 5 and was not modified by this capability.

No ratios, percentages, or "on track"/"achieved" scoring of any kind — counts only. No Territory/Region/Area or Organization Hierarchy scoping — organization-wide only.

---

## Authorization

`CurrentUser` (any authenticated user) — no `RequireRole("admin")` gate. Mirrors the pre-existing `/dashboard` endpoint's own precedent for aggregate-count endpoints; not a new authorization mechanism.

---

## Governing Decision

`docs/architecture/capabilities/dashboard/iteration-1-scope-and-implementation-plan.md`

---

# Deferred Capabilities

---

# Permission Model

**Status**

```
Deferred
```

---

## Purpose

Introduce reusable permission vocabulary.

---

## Depends On

Authorization Foundation

---

## Reason

Current architecture does not require centralized permissions.

---

# Policy Engine

**Status**

```
Deferred
```

---

## Purpose

Provide reusable policy evaluation.

---

## Depends On

Permission Model

---

## Reason

Current capability-specific evaluators are sufficient.

---

# Delegated Approval

**Status**

```
Deferred
```

---

## Purpose

Support delegated approval authority.

---

## Depends On

Approval Authorization

---

## Reason

Business policy not yet defined.

---

# Organization Hierarchy

**Status**

```
Deferred
```

---

## Purpose

Support hierarchical reporting relationships.

---

## Current State

Only direct manager exists:

```
Employee

↓

Manager
```

---

## Not Supported

- manager chain
- director hierarchy
- escalation path

---

# Capability Dependency Graph

```
Authentication

↓

Identity Context

↓

Authorization Foundation

↓

Approval Authorization

↓

Approval Workflow

↓

Business Capabilities
```

---

# Capability Maturity

| Capability | Discovery | Decision | Implementation | Status |
|------------|-----------|----------|----------------|--------|
| Identity Context | ✓ | ✓ | ✓ | Implemented |
| Authorization Foundation | ✓ | ✓ | ✓ | Implemented |
| Approval Authorization | ✓ | ✓ | ✓ | Implemented |
| Leave Authorization | ✓ | ✓ | ✓ | Implemented |
| Payroll Authorization | ✓ | ✓ | ✓ | Implemented |
| Approval Workflow | ✓ | ✓ | ✓ | Implemented |
| Effective Dating | ✓ | ✓ | ✓ | Implemented |
| Monetary Representation | ✓ | ✓ | ✓ | Implemented |
| Compensation | ✓ | ✓ | ✓ | Implemented |
| Payroll (Run + Calculation) | ✓ | ✓ | ✓ | Implemented |
| Payslip | ✓ | ✓ | ✓ | Implemented |
| Payroll Calculation (Advanced) | ✓ | ✓ | ✓ | Implemented |
| Shift Assignment | ✓ | ✓ | — | Closed — Subsumed by Work Schedule |
| Work Schedule | ✓ | ✓ | ✓ | Implemented |
| Recruitment | ✓ | ✓ | ✓ | Implemented |
| Performance | ✓ | ✓ | ✓ | Implemented |
| Store | ✓ | ✓ | ✓ | Implemented |
| Visit | ✓ | ✓ | ✓ | Implemented |
| Target | ✓ | ✓ | ✓ | Implemented |
| Achievement | ✓ | ✓ | ✓ | Implemented |
| Dashboard (Performance Management) | ✓ | ✓ | ✓ | Implemented |
| Permission Model | ✗ | ✗ | ✗ | Deferred |
| Policy Engine | ✗ | ✗ | ✗ | Deferred |
| Delegated Approval | ✗ | ✗ | ✗ | Deferred |
| Organization Hierarchy | ✗ | ✗ | ✗ | Deferred |

---

# Technical Debt

Known capability limitations are tracked in:

```
TECHNICAL_DEBT_REGISTER.md
```

Current related debt:

- TD-001 EmployeeContext HTTP Exception Mapping
- TD-002 Approval Authorization Concurrency Protection
- TD-003 Employee Manager Hierarchy Limitation
- TD-004 Permission and Policy Model
- TD-005 Authorization Foundation Consumer Coverage

---

# Governance Rules

Every new capability must provide:

1. Discovery
2. Policy Discovery (if applicable)
3. Capability Decision
4. Implementation Plan
5. Architecture Review

Capabilities must not introduce new architecture independently.

Architecture changes require ADR approval.

---

# References

- MASTER_ARCHITECTURE_ROADMAP.md
- ARCHITECTURE_STATUS.md
- ARCHITECTURE_CHANGELOG.md
- ARCHITECTURE_DECISION_INDEX.md
- TECHNICAL_DEBT_REGISTER.md
- ADR-003
- ADR-004
- ADR-006
- ADR-007
- ADR-008

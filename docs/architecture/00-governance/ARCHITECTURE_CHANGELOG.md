# Architecture Changelog

**Document:** Architecture Changelog
**Status:** Active
**Owner:** Architecture Governance
**Version:** 1.0
**Last Updated:** 2026-08-05

---

# Purpose

This document records significant architecture changes introduced into the EOP platform.

Architecture changes include:

- new architectural capabilities
- new ADR decisions
- capability completion
- structural changes
- architectural constraints introduced

This document does not replace ADRs.

For detailed decisions, refer to the related ADR or Capability Decision.

---

# Change History

---

# 2026-08-10 — Reporting Iteration 1 (Achievement-Anchored Operational Report) Completed

**Reference:**

- PR #92
- `docs/architecture/capabilities/performance/reporting-iteration-1-scope-and-implementation-plan.md`

**Capability:**

Reporting (Performance Management)

**Status:**

Implemented

---

## Summary

Brought Roadmap Phase 5's "Reporting" item into implementation — the last item in the `KPI → Target → Achievement → Dashboard → Reporting` sequence: a read-only operational report at `GET /performance/reporting`, one row per existing `Achievement`, resolved through `Target` to `Kpi` and `HrEmployee` (relationship: `Achievement → Target → Kpi + HrEmployee`). `Target` rows with no recorded `Achievement` do not appear. Response includes human-readable KPI (`kpi_code`, `kpi_name`) and employee (`employee_number`, `employee_full_name`) information alongside `period_year`, `period_month`, `goal_value`, `actual_value`. Pagination is mandatory, with no unbounded plain-list endpoint; filterable by `employee_id`, `kpi_id`, `period_year`, `period_month` — the same dimensions `Target`/`Achievement` already expose. `ReportingRepository` is not tied to a single model, mirroring `DashboardRepository`'s established precedent for cross-aggregate, read-only queries. No CSV/PDF/export, no scheduled reports or email delivery, no persisted report definitions/templates/history, no report builder, no calculation/formula engine, no scoring or achievement percentage, no Territory/Region/Area or Organization Hierarchy scoping. Distinct and separate from the Phase 7 "Reporting Platform" (enterprise infrastructure, deferred, its own future ADR gate) — untouched by this capability. Authorization is Role Based (`RequireRole("admin")`, reused unmodified) — this endpoint exposes row-level, per-employee performance data, the same exposure category as `Kpi`/`Target`/`Achievement`'s own list/get endpoints, not Dashboard's aggregate-counts-only `CurrentUser` exposure.

---

# 2026-08-10 — Dashboard Iteration 1 (Performance Management Summary Counts) Completed

**Reference:**

- PR #90
- `docs/architecture/capabilities/dashboard/iteration-1-scope-and-implementation-plan.md`

**Capability:**

Dashboard (Performance Management)

**Status:**

Implemented

---

## Summary

Brought Roadmap Phase 5's "Dashboard" item into implementation as Performance Management Dashboard Iteration 1: a read-only summary of `Kpi`/`Target`/`Achievement` row counts, organization-wide, at `GET /performance/dashboard` (response: `kpi_count`, `target_count`, `achievement_count`). This is the counts layer in the `KPI → Target → Achievement → Dashboard → Reporting` sequence — `Achievement` (already implemented, Iteration 1) is the actual-value layer; `Reporting` remains a future, unimplemented capability, not pre-committed to any schema or behavior by this change. No repository of its own: reads directly via `KpiRepository`/`TargetRepository`/`AchievementRepository`'s existing `BaseRepository.count()`. Deliberately distinct from the pre-existing, unrelated `GET /dashboard` endpoint (Phase 1/2 generic `Organization`/`Project`/`Employee`/`Assignment`/`Task` scaffold) — that endpoint is not part of Phase 5 and was not modified. Scope is organization-wide counts only: no ratios, percentages, or "on track"/"achieved" scoring, and no Territory/Region/Area or Organization Hierarchy scoping. Authorization is `CurrentUser` (any authenticated user), no `RequireRole("admin")` gate — mirroring the pre-existing `/dashboard` endpoint's own precedent for aggregate-count endpoints, not a new authorization mechanism.

---

# 2026-08-10 — Achievement Iteration 1 (Manual Actual Value Against Target) Completed

**Reference:**

- PR #88
- `docs/architecture/capabilities/performance/achievement-iteration-1-scope-and-implementation-plan.md`

**Capability:**

Achievement

**Status:**

Implemented

---

## Summary

Brought Roadmap Phase 5's "Achievement" item into implementation: the manually recorded actual value against exactly one `Target` (`target_id`, `ON DELETE RESTRICT`, unique — at most one `Achievement` per `Target`, enforced at the database level; `actual_value`, `Numeric(18, 6)`, mirroring `Target.goal_value`'s precedent), flat CRUD, no lifecycle. This is the actual-value layer in the `KPI → Target → Achievement → Dashboard → Reporting` sequence — `Target` (already implemented, Iteration 1) is the employee-scoped monthly goal; `Achievement` is the manually entered actual result against it; `Dashboard` and `Reporting` remain future, unimplemented capabilities, not pre-committed to any schema or behavior by this change. No `employee_id`/`kpi_id`/`period_year`/`period_month` on `Achievement` itself — all inherited through `Achievement.target`, avoiding duplication of Target's own identity. CPO/CTO decision resolved Achievement as manual-entry only: no automatic calculation, Visit/Survey aggregation, Attendance/Payroll integration, or KPI formula engine — computed/derived Achievement is explicitly deferred to a future capability/decision. Authorization is Role Based (`RequireRole("admin")`, reused unmodified) — an Achievement is manually recorded by an administrator, mirroring exactly how an administrator manually assigns the Target goal; no new authorization evaluator introduced.

---

# 2026-08-09 — Target Iteration 1 (Employee-Scoped KPI Goal) Completed

**Reference:**

- PR #86
- `docs/architecture/capabilities/performance/target-iteration-1-scope-and-implementation-plan.md`

**Capability:**

Target

**Status:**

Implemented

---

## Summary

Brought Roadmap Phase 5's "Target" item into implementation: an employee-scoped goal for one `Kpi`, for one calendar month (`kpi_id`, `employee_id`, `period_year`, `period_month`, `goal_value`), flat CRUD, no lifecycle. This is the definition/assignment layer in the `KPI → Target → Achievement → Dashboard → Reporting` sequence — `Kpi` (already implemented, Iteration 1) is the indicator definition; `Target` is the employee-scoped monthly goal assignment against it; `Achievement` (the measured/actual value), `Dashboard`, and `Reporting` remain future, unimplemented capabilities, not pre-committed to any schema, ownership, or calculation model by this change. Ownership scope resolved to Employee by CPO/CTO product decision — Store, Organization, and Territory/Region/Area were evaluated and not required for Iteration 1; `employee_id` is a business-scope assignment field, not an Organization Hierarchy relationship, introducing no new dependency on the separately-gated Organization Hierarchy capability (TD-003/Phase 6). At most one `Target` per `(employee_id, kpi_id, period_year, period_month)`, enforced at the database level. Authorization is Role Based (`RequireRole("admin")`, reused unmodified) — a `Target` is assigned by an administrator, not self-authored by the employee, so `employee_id` is business scope only, not an authorization boundary; no Owner Only evaluator was introduced, a deliberate distinction from `Visit`/`Survey`/`Compensation`.

---

# 2026-08-09 — Visit Iteration 1 (Field Employee Store Visits) Completed

**Reference:**

- PR #82
- `docs/architecture/capabilities/visit/iteration-1-scope-and-implementation-plan.md`

**Capability:**

Visit

**Status:**

Implemented

---

## Summary

Brought Roadmap Phase 4's "Visit" item into implementation as a minimal aggregate: `employee_id`, `store_id`, `visited_at`, `notes`, flat CRUD, no lifecycle. Discovery resolved no `Mission` reference is required — every product document naming both `Visit` and `Mission` treats them as parallel, independent concepts, never nested, and `Mission Planning`'s grouping with `Territory Assignment` (Product Scope §5) further argued against coupling them. GPS coordinates, photo/selfie evidence, and check-in/check-out timestamps are all explicitly deferred, with no field added in Iteration 1. Authorization is Owner Only via a new `VisitAuthorizationEvaluator`, mirroring `AttendanceAuthorizationEvaluator`'s exact shape — confirmed by CPO/CTO as reuse of the established per-capability Owner Only evaluator convention, not new authorization infrastructure. Explicitly distinct from the existing HR `AttendanceEvent`/`ReconciliationService` capability despite the shared word "Attendance" in product scope — neither reused nor modified; Field Execution's own "Attendance" concept remains a separate, unscoped future item. No relationship to `Location`, Territory/Region/Area, or Organization Hierarchy.

---

# 2026-08-09 — Store Iteration 1 (Customer & Store) Completed

**Reference:**

- PR #80
- `docs/architecture/capabilities/store/iteration-1-scope-and-implementation-plan.md`

**Capability:**

Store

**Status:**

Implemented

---

## Summary

Brought Roadmap Phase 3's "Customer"/"Store"/"Outlet"/"Modern Trade"/"General Trade"/"Store Classification"/"Geolocation" items into implementation as a single `Store` aggregate — discovery established that Customer and Store are the same real-world entity in this product's domain language, not two separate aggregates (MVP Scope names only "Store"; "Product Boundaries" places account/billing/pipeline concepts in ERP/CRM, both explicitly out of platform scope). `Store` (`code`, `name`, `organization_id`, `store_type_id`, `address`, `latitude`/`longitude`, `description`) + `StoreType` (free-form trade-channel lookup mirroring `LocationType`, covering Modern Trade/General Trade/Store Classification collectively — not a fixed enum). Flat CRUD, no lifecycle. `RequireRole("admin")` reused unmodified, mirrors `PayrollRun`/`JobRequisition`/`PerformanceReview`'s identical rationale (no natural owner-employee field). No relationship to `HrEmployee`, `Location`, or any Territory/Region/Area concept — that boundary against the separately-gated Organization Hierarchy capability (TD-003/Phase 6) is explicitly held open, not resolved, pending a future Territory-focused discovery.

---

# 2026-08-09 — Attendance/Leave Deduction Wired to Work Schedule

**Reference:**

- PR #78

**Capability:**

Payroll Calculation (Advanced)

**Status:**

Implemented

---

## Summary

Resolved the integration gap `AttendanceLeaveDeductionCalculator`'s own docstring had named since Advanced Payroll: the calculator previously always returned `None` because `ReconciliationService`'s `absent` classification had no concept of an employee's scheduled work days. Now, a day is deductible only when both hold: `ReconciliationService.get_range` classifies it `absent`, and the employee's `WorkSchedule` effective on that date (via `WorkScheduleService.get_by_employee`, unmodified) marks the corresponding weekday as worked. `holiday`/`leave` days remain never deductible; an employee with no applicable `WorkSchedule` row is simply not deductible for that day (mirrors `OvertimeCalculator`/`StatutoryTaxCalculator`'s existing "no applicable data → no line item" convention, not a fail-loud error). Implements D5 Option (a) exactly as already accepted — no new business rule. `WorkScheduleService`/`ReconciliationService` remain unmodified and are read-only from Payroll's side; no schema or migration change; no API change.

---

# 2026-08-09 — Performance Iteration 2 (Review Lifecycle) Completed

**Reference:**

- PR #76
- `docs/architecture/capabilities/performance/iteration-2-business-decision-package.md` (Approved)

**Capability:**

Performance

**Status:**

Implemented

---

## Summary

CPO/CTO approved D1 (Option B: admin-only `draft → finalized` lifecycle for `PerformanceReview` — no employee acknowledgement, manager/self/peer review, calibration, approval hierarchy, notifications, or generic workflow engine). Implemented as `PerformanceReviewStatus` (`core/performance.py`, mirrors `ApplicationStatus`'s exact enum/transition-table pattern) and a fixed transition table enforced by a new `PerformanceReviewService.finalize` method, exposed via `POST /hr/performance-reviews/{id}/finalize`, reusing the existing `RequireRole("admin")` authorization unmodified. `PerformanceReviewCreate`/`PerformanceReviewUpdate` do not accept `status` — every new review starts `draft`; the only way to reach `finalized` is `finalize`. `finalized` is terminal: re-finalizing is rejected, not a no-op. Finalized reviews additionally reject substantive field changes (`employee_id`, `review_period_start`/`end`, `notes`) via ordinary `update()`, raising a new `PerformanceReviewFinalizedError` (409). Rating scales, competency frameworks, employee acknowledgement, manager/peer/self-review semantics, and organization scoping remain out of scope and undecided.

---

# 2026-08-09 — Performance Iteration 1 (Performance Review) Completed

**Reference:**

- PR #74

**Capability:**

Performance

**Status:**

Implemented

---

## Summary

Brought Performance Review into product scope, superseding its prior HRIS exclusion in `docs/product/02_PRODUCT_SCOPE.md` using the same CPO/CTO precedent applied to Recruitment (distinct from the already-in-scope §7 "Performance Management" field/sales KPIs — unrelated concepts sharing a word). Added `PerformanceReview`: minimal, flat CRUD record (`employee_id` FK `ON DELETE RESTRICT`, `review_period_start`/`review_period_end`, `notes`), no status/lifecycle, no effective dating, no uniqueness constraint (multiple reviews per employee permitted) — mirrors the `PayrollRun`/`Interview`/`Offer` "CRUD shell first" precedent. Only validation is a basic period sanity check (`review_period_end >= review_period_start`). `RequireRole("admin")` reused unmodified as `RequirePerformanceAdmin`. Rating scales, competency frameworks, review workflow, manager/peer/self-review semantics, approval hierarchy, calibration, goal weighting, review cadence, employee-manager relationships, and organization scoping all remain undecided and out of scope.

---

# 2026-08-09 — Recruitment Iteration 3 (Interview + Offer) Completed

**Reference:**

- PR #72

**Capability:**

Recruitment

**Status:**

Implemented

---

## Summary

Added `Interview` and `Offer`: minimal, flat CRUD records linked to `Application` by FK (`ON DELETE RESTRICT`), no uniqueness constraint (multiple per `Application` permitted). Neither carries a status/lifecycle of its own and neither is coupled to `ApplicationService.transition` in any way — `Application` alone owns the recruitment lifecycle (Iteration 2). `Interview` carries no `type`/`interviewer`/`location` field; `Offer` deliberately carries no compensation/monetary field (never silently derived from Payroll `Compensation`). `RequireRole("admin")` reused unmodified from Recruitment Authorization. Interview/offer lifecycle, acceptance/expiry semantics, and any Application-transition integration remain out of scope and undecided.

---

# 2026-08-09 — Recruitment Iteration 2 (Application Lifecycle) Completed

**Reference:**

- `docs/architecture/capabilities/recruitment/iteration-2-business-decision-package.md` (Approved)

**Capability:**

Recruitment

**Status:**

Implemented

---

## Summary

CPO/CTO approved D1 (Application stage/transition model: Standard Funnel — `applied → screening → interviewing → offered → hired`, `rejected`/`withdrawn` from any non-terminal stage, forward-only, terminal states not reopenable) and D2 (`JobRequisition` closure never cascades to `Application`). Implemented as `ApplicationStatus` (`core/recruitment.py`, mirrors `PayrollRunStatus`'s exact enum/column pattern) and a fixed transition table enforced by a new `ApplicationService.transition` method, exposed via `POST /recruitment/applications/{id}/transition`, reusing the existing `RequireRole("admin")` authorization unmodified. `ApplicationCreate`/`ApplicationUpdate` no longer accept `status` — every new `Application` starts `APPLIED`; all subsequent moves go through `transition` only. No cascading logic was added to `JobRequisitionService`. Interview scheduling, offer management, candidate self-service, candidate-to-employee conversion, and organization scoping remain out of scope and undecided.

---

# 2026-08-09 — Recruitment Authorization Decided

**Reference:**

- `docs/architecture/capabilities/recruitment/authorization-decision.md`

**Capability:**

Recruitment

**Status:**

Implemented

---

## Summary

Closed the gap left by Recruitment Iteration 1 (`CurrentUser`-only access to `JobRequisition`/`Candidate`/`Application`, including `Candidate` PII). CPO/CTO decision: Role Based (`RequireRole("admin")`), reusing `PayrollRun`'s own existing authorization mechanism unmodified — no new evaluator, permission model, policy engine, or role introduced. Recruitment pipeline/stage, hiring workflow, candidate conversion, and other Iteration 2 capabilities remain deferred, unaffected by this decision.

---

# 2026-08-09 — Recruitment (Iteration 1) Completed

**Reference:**

- PR #69
- `docs/architecture/capabilities/recruitment/iteration-1-scope-and-implementation-plan.md`
- `docs/product/02_PRODUCT_SCOPE.md` (Recruitment removed from HRIS exclusion list)

**Capability:**

Recruitment

**Status:**

Implemented

---

## Summary

CPO/CTO product decision brought Recruitment into scope, superseding its prior "Out of Scope — HRIS" listing (the same exclusion list Payroll Processing was in before Payroll was built). No prior governance chain existed; scope and implementation-level decisions were made directly from repository precedent in a single document rather than a full six-phase governance cycle.

Implemented: `JobRequisition` (open positions, mirrors `Shift`'s master-data shape), `Candidate` (people applying, explicitly not `HrEmployee`s), `Application` (peer-association linking the two, mirrors `Assignment`, `RESTRICT` delete rules). `CurrentUser`-only authorization — none of the three entities has a natural employee-owner field.

**Explicitly not decided by this iteration** (structure only): recruitment pipeline/stage semantics, interview scheduling, offer management, candidate self-service, candidate-to-employee conversion, dedicated Recruitment Authorization, organization scoping. Each remains open, requiring a separate CPO/CTO/governance decision before any Iteration 2 work begins.

---

# 2026-08-09 — EmployeeContext HTTP Exception Mapping Resolved

**Reference:**

- PR #67
- TECHNICAL_DEBT_REGISTER.md TD-001

**Capability:**

Identity Context

**Status:**

Resolved

---

## Summary

`EmployeeContextNotFoundError`/`MultipleEmployeeContextError` now map to HTTP 403/409 in `dependencies/employee_context.py`, mirroring `dependencies/auth.py`'s existing DI-layer exception pattern, instead of propagating to the generic handler as unhandled 500s.

---

# 2026-08-09 — Shift Assignment Closed (Subsumed by Work Schedule)

**Reference:**

- PR #66
- `docs/architecture/capabilities/shift-assignment/final-governance-summary.md`

**Capability:**

Shift Assignment

**Status:**

Closed — Subsumed by Work Schedule

---

## Summary

Shift Assignment's governance chain (previously "Additional Governance Required") was reconciled against the newly-merged Work Schedule capability. Work Schedule's `WorkSchedule` aggregate already implements, field for field, the effective-dated employee↔shift relationship Shift Assignment's own governance investigated. No separate `ShiftAssignment` entity was built, to avoid duplicating an already-merged mechanism.

---

# 2026-08-09 — Work Schedule Completed

**Reference:**

- PR #65
- `docs/architecture/capabilities/work-schedule/iteration-1-implementation-plan.md`

**Capability:**

Work Schedule

**Status:**

Implemented

---

## Summary

Work Schedule's 15 blocking unknowns and 6 missing-concepts classifications were resolved under CPO/CTO directive, primarily by reuse of precedent established after the capability's original governance chain was written (Effective Dating, Compensation's `corrects_id` correction lineage, Owner Only authorization). Implemented as an employee-scoped, effective-dated aggregate (`WorkSchedule`: `employee_id`, `shift_id`, seven weekday flags, `effective_from`/`effective_to`, `corrects_id`).

---

# 2026-08-09 — Payroll Calculation (Advanced) Completed

**Reference:**

- `docs/architecture/capabilities/payroll-calculation/decision.md`

**Capability:**

Payroll Calculation (Advanced)

**Status:**

Implemented

---

## Summary

Pay-period cadence, configurable statutory/tax deduction (`PayrollStatutoryParameter`), overtime calculation, and daily/hourly rate resolution implemented, layered onto the base-salary Payroll Calculation capability. Attendance/leave deduction was deliberately scoped out as a no-op pending Work Schedule's existence — see the 2026-08-09 "Attendance/Leave Deduction Wired to Work Schedule" entry below for the completed integration.

---

# 2026-08-05 — Approval Authorization Completed

**Reference:**

- PR-053
- ADR-008
- Approval Authorization Decision
- Approval Authorization Implementation Plan

**Capability:**

Approval Authorization

**Status:**

Implemented

---

## Summary

Approval Authorization capability has been implemented using the existing Authorization Foundation.

The capability introduces authorization enforcement for approval workflows.

The implemented policy is:

Manager Approval

Approval is allowed only when:

request.employee.manager_id
approver.employee.id

Only direct manager approval is supported.

---

## Architecture Impact

Added:

- ApprovalAuthorizationEvaluator
- Approval authorization decision flow
- Authorization denial handling

Integrated:

CurrentRequestContext
↓
AuthorizationService
↓
AuthorizationDecision
↓
ApprovalService

---

## Architectural Constraints Preserved

The implementation does not modify:

- Authorization Foundation
- Identity Context model
- Approval workflow model
- database schema
- repository architecture

---

## Deferred Capabilities

Not introduced:

- delegated approval
- indirect manager approval
- recursive hierarchy traversal
- approval roles
- workflow assignment
- permission model
- policy engine

---

## Related Debt

Introduced awareness of:

- EmployeeContext HTTP exception mapping
- Approval authorization concurrency protection

Tracked in:

TECHNICAL_DEBT_REGISTER.md

---

# 2026-08-03 — Authorization Foundation Completed

**Reference:**

- PR-052
- ADR-007
- Authorization Foundation Decision

**Capability:**

Authorization Foundation

**Status:**

Implemented

---

## Summary

Implemented the platform authorization foundation.

The foundation provides generic authorization primitives without embedding business authorization rules.

Introduced:

- AuthorizationRequest
- AuthorizationDecision
- AuthorizationEvaluator
- AuthorizationService

---

## Design Principle

Authorization Foundation follows:

Generic Authorization Mechanism

Capability Specific Authorization Policy

The foundation does not own:

- permission vocabulary
- business policy
- ownership rules
- role hierarchy

---

## Architecture Impact

Future capabilities may consume Authorization Foundation.

Consumers must define their own:

- discovery
- policy discovery
- capability decision
- implementation plan

---

## Constraints Introduced

Do not introduce:

- global authorization rules
- permission models
- RBAC redesign
- policy engines

without architecture decision.

---

# 2026-08-01 — Architecture Governance Framework Established

**Reference:**

- MASTER_ARCHITECTURE_ROADMAP
- ARCHITECTURE_PRINCIPLES
- CLAUDE_IMPLEMENTATION_GUIDE

**Status:**

Implemented

---

## Summary

Established architecture governance process.

Introduced documentation flow:

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

## Purpose

The governance model separates:

Business decisions

from

Implementation decisions.

---

## Rules Introduced

Architecture decisions must be documented before implementation.

Implementation agents must not:

- infer business rules
- redesign architecture
- resolve ambiguity independently

---

# 2026-07-31 — Authorization Architecture Direction Defined

**Reference:**

- ADR-007

**Capability:**

Authorization

**Status:**

Approved

---

## Summary

Defined the initial authorization architecture direction.

Authorization is implemented as a replaceable foundation.

The foundation separates:

Authorization Mechanism
from
Authorization Policy

---

## Architectural Decision

The platform does not initially introduce:

- permission system
- RBAC redesign
- policy engine

Authorization rules remain capability-owned.

---

# 2026-07-30 — Identity Context Architecture Established

**Reference:**

- ADR-006

**Capability:**

Identity Context

**Status:**

Implemented

---

## Summary

Established employee identity resolution model.

The platform resolves:

CurrentUser
↓
HrEmployee
↓
EmployeeContext

---

## Architectural Impact

Business capabilities may consume EmployeeContext instead of independently resolving employee identity.

---

## Known Limitation

EmployeeContext exception transport mapping remains deferred.

Tracked in:

TECHNICAL_DEBT_REGISTER.md

---

# 2026-07-28 — Approval Workflow Architecture Baseline Established

**Reference:**

- ADR-004
- ADR-005

**Capability:**

Approval Workflow

**Status:**

Established

---

## Summary

Approval workflow architecture established.

ApprovalService remains responsible for:

- state transition
- approval workflow execution

Authorization responsibility remains separate.

---

## Constraint Introduced

Approval workflow must not contain:

- authorization policy
- role evaluation
- ownership rules

Authorization must be introduced through dedicated authorization capability.

---

# Architecture Change Categories

| Category | Description |
|---|---|
| Capability | New platform capability |
| ADR | Architecture decision |
| Governance | Process or documentation change |
| Integration | Existing capability integration |
| Debt | Known limitation |

---

# Current Architecture Evolution

Current direction:

Authentication
↓
Identity Context
↓
Authorization Foundation
↓
Capability Authorization Policies
↓
Business Capabilities

---

# Current Completed Capabilities

| Capability | Status |
|---|---|
| Identity Context | Implemented |
| Authorization Foundation | Implemented |
| Approval Authorization | Implemented |

---

# Current Deferred Capabilities

| Capability | Status |
|---|---|
| Permission Model | Deferred |
| Policy Engine | Deferred |
| Delegated Approval | Deferred |
| Workflow Assignment | Deferred |
| Organization Hierarchy | Deferred |

---

# Governance Rules

All architecture changes must:

1. Have documented motivation.
2. Have clear ownership.
3. Preserve architectural boundaries.
4. Avoid introducing undocumented assumptions.
5. Reference related ADR or Capability Decision.

---

# References

- MASTER_ARCHITECTURE_BLUEPRINT.md
- MASTER_ARCHITECTURE_ROADMAP.md
- ARCHITECTURE_STATUS.md
- ARCHITECTURE_PRINCIPLES.md
- TECHNICAL_DEBT_REGISTER.md
- ADR documents
- Capability Decision documents

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
| Payroll Calculation (Advanced) | Blocked | Tax/formula engine — pending business decisions |
| Shift Assignment | Blocked | Pending business decisions (see capability decision doc) |
| Work Schedule | Blocked | Pending business decisions (see capability decision doc) |
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

EmployeeContext exceptions do not yet have centralized HTTP mappings.

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

# Blocked — Pending Business Decision

The following capabilities have completed architecture governance work but implementation remains genuinely blocked on unresolved business/product decisions (not architecture). No business rules have been invented to unblock them.

---

## Payroll Calculation (Advanced)

**Status:** Blocked

**Related:** `docs/architecture/capabilities/payroll-calculation/decision.md`

Requires business/product decisions this repository does not evidence: pay-period cadence, tax/statutory formula, and execution mechanism (request- vs. event/job-driven). Distinct from the already-implemented base-salary Payroll Calculation above.

---

## Shift Assignment

**Status:** Blocked

**Related:** `docs/architecture/capabilities/shift-assignment/implementation-plan.md` §12

11 of 13 open items are genuine business gaps (effective-dating necessity, dedicated lifecycle, LeaveRequest hour-consumption interaction, naming). The remaining 2 (relationship shape, delete rule) are architecture-only and could be resolved without new business input, but do not by themselves unblock implementation while the business gaps remain open.

---

## Work Schedule

**Status:** Blocked

**Related:** `docs/architecture/capabilities/work-schedule/implementation-plan.md` §12

15 blocking unknowns, predominantly business/repository gaps (recurring-schedule identity, overlap validation, historical lookup) with no corresponding evidence anywhere in the repository.

---

# Technical Debt Status

Current tracked debt:

| ID | Title | Status |
|---|---|---|
| TD-001 | EmployeeContext HTTP Exception Mapping | Open |
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

Risk:

EmployeeContext failures may produce generic HTTP errors.

Owner:

Identity Context.

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

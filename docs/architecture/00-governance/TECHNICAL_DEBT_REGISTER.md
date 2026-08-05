# Technical Debt Register

**Document:** Technical Debt Register
**Status:** Active
**Owner:** Architecture Governance
**Version:** 1.0
**Last Updated:** 2026-08-05

---

# Purpose

This document records known technical debt within the EOP platform architecture.

Technical debt represents:

- known architectural limitations
- accepted trade-offs
- missing capabilities
- deferred improvements

This document exists to provide visibility and governance.

Technical debt:

- does not override ADR decisions
- does not introduce new architecture
- does not authorize implementation shortcuts
- requires architecture review before resolution

---

# Technical Debt Lifecycle

| Status | Meaning |
|---|---|
| Open | Identified and not yet resolved |
| Planned | Resolution approach approved |
| In Progress | Currently being addressed |
| Resolved | Completed |

---

# Severity Definition

| Severity | Meaning |
|---|---|
| Low | Improvement opportunity with limited impact |
| Medium | Affects future capability development or reliability |
| High | Blocks capability implementation or creates significant risk |
| Critical | Requires immediate architectural attention |

---

# Technical Debt Summary

| ID | Title | Capability | Severity | Status |
|---|---|---|---|---|
| TD-001 | EmployeeContext HTTP Exception Mapping | Identity Context | Medium | Open |
| TD-002 | Approval Authorization Concurrency Protection | Approval Authorization | Low | Open |
| TD-003 | Employee Manager Hierarchy Limitation | HR Employee | Medium | Open |
| TD-004 | Permission and Policy Model Not Implemented | Authorization | Medium | Open |
| TD-005 | Authorization Foundation Consumer Coverage | Authorization | Low | Open |

---

# TD-001 — EmployeeContext HTTP Exception Mapping

**Status:** Open
**Severity:** Medium

**Capability:**

Identity Context

**Introduced:**

PR-053 — Approval Authorization

---

## Description

EmployeeContext resolution is now consumed by business capabilities requiring authorization decisions.

The resolution flow:

CurrentUser
↓
EmployeeContext Resolver
↓
HrEmployee
↓
EmployeeContext

requires exactly one valid employee context.

The resolver may raise:

- EmployeeContextNotFoundError
- MultipleEmployeeContextError

when resolution fails.

---

## Current Behavior

These exceptions do not currently have dedicated HTTP mappings.

When exposed through API flows:

CurrentRequestContext

the exception reaches the generic error handler.

Current result:

HTTP 500

---

## Impact

Users may receive an internal server error when:

- authenticated user has no linked employee
- authenticated user has multiple linked employee records

This affects any capability consuming EmployeeContext.

---

## Root Cause

Identity Context currently owns:

- user-to-employee resolution
- context validation

but does not yet define centralized transport exception handling.

---

## Resolution Direction

Create centralized HTTP exception mapping under Identity Context.

Potential mapping:

EmployeeContextNotFoundError
        ↓
HTTP 404 / 403

MultipleEmployeeContextError
        ↓
HTTP 409

Final status mapping requires Identity Context decision.

---

## Constraints

Resolution must not be implemented inside:

- Approval Authorization
- Leave Management
- Overtime Management
- Timesheet Management

---

## Related Documents

- ADR-006 — Employee Context Resolution
- PR-053 — Approval Authorization

---

# TD-002 — Approval Authorization Concurrency Protection

**Status:** Open
**Severity:** Low

**Capability:**

Approval Authorization

---

## Description

Approval Authorization verifies authorization before approval state transition.

Current flow:

Authorization Evaluation
↓
Approval State Transition
↓
Transaction Commit

There is no additional concurrency validation between authorization evaluation and final persistence.

---

## Example Risk

The requester manager relationship changes after authorization evaluation.

Example:

Employee.manager_id
changes
after authorization check
before commit

The approval operation may continue using the previous authorization state.

---

## Current Limitation

This is part of a broader platform concurrency limitation.

Current versioning support exists but is not consistently enforced across all business workflows.

---

## Resolution Direction

Future improvement may introduce:

- optimistic locking enforcement
- approval transition version checks
- transaction consistency validation

Requires broader architecture review.

---

## Constraints

Do not introduce capability-specific concurrency behavior without platform decision.

---

## Related Documents

- ADR-008 — Approval Authorization Policy Model
- Approval Authorization Implementation Plan

---

# TD-003 — Employee Manager Hierarchy Limitation

**Status:** Open
**Severity:** Medium

**Capability:**

HR Employee

---

## Description

Current employee relationship model supports only direct manager reference:

Employee
↓
Manager

through:

HrEmployee.manager_id

---

## Current Supported Behavior

Supported:

- direct manager lookup
- direct manager approval

Not supported:

- manager chain traversal
- organizational hierarchy
- escalation path

---

## Impact

Future capabilities requiring:

- indirect approval
- escalation workflow
- organizational reporting

cannot be implemented without extending the employee hierarchy model.

---

## Resolution Direction

Future architecture decision required for:

- organizational graph model
- hierarchy traversal
- reporting structure

---

## Constraints

Do not introduce:

- recursive manager lookup
- hierarchy assumptions

inside individual capabilities.

---

## Related Documents

- ADR-008 — Approval Authorization Policy Model
- HR Employee Capability

---

# TD-004 — Permission and Policy Model Not Implemented

**Status:** Open
**Severity:** Medium

**Capability:**

Authorization Foundation

---

## Description

Authorization Foundation currently provides:

- AuthorizationRequest
- AuthorizationDecision
- AuthorizationEvaluator
- AuthorizationService

The foundation intentionally does not provide:

- permission model
- policy engine
- RBAC expansion
- centralized policy registry

---

## Current State

Authorization policies are introduced at capability level.

Example:

ApprovalAuthorizationEvaluator

implements:

Manager Approval Policy

---

## Impact

Future capabilities requiring:

- reusable permissions
- complex policy composition
- centralized authorization rules

require additional architecture work.

---

## Resolution Direction

Create future ADR before introducing:

- permission abstraction
- policy engine
- authorization vocabulary
- RBAC redesign

---

## Constraints

Do not introduce permission concepts without architecture approval.

---

## Related Documents

- ADR-007 — Authorization Foundation
- ADR-008 — Approval Authorization Policy Model

---

# TD-005 — Authorization Foundation Consumer Coverage

**Status:** Open
**Severity:** Low

**Capability:**

Authorization Foundation

---

## Description

Authorization Foundation has been implemented as a platform capability.

Current consumers are introduced incrementally through capability-specific decisions.

---

## Current State

Implemented consumers:

- Approval Authorization
- Leave Authorization

Future capabilities still require:

- discovery
- policy analysis
- capability decision
- implementation plan

before authorization integration.

---

## Impact

Some capabilities may continue operating with authentication-only protection until authorization policies are defined.

---

## Resolution Direction

Each capability should follow:

Discovery
↓
Policy Discovery
↓
Capability Decision
↓
Implementation Plan
↓
Implementation

before adding authorization behavior.

---

## Constraints

Do not introduce global authorization behavior without capability approval.

---

## Related Documents

- ADR-007 — Authorization Foundation
- CLAUDE_IMPLEMENTATION_GUIDE.md

---

# Governance Rules

All technical debt entries must:

- have clear ownership
- have evidence
- identify impact
- avoid speculative solutions
- avoid bypassing ADR governance

Resolution requires:

1. Technical assessment
2. Architecture review
3. ADR or Capability Decision update if architecture changes

---

# Review Process

Technical debt should be reviewed during:

- architecture review
- capability planning
- roadmap planning
- periodic architecture health review

---

# References

- MASTER_ARCHITECTURE_ROADMAP.md
- ARCHITECTURE_STATUS.md
- ARCHITECTURE_CHANGELOG.md
- ARCHITECTURE_PRINCIPLES.md
- ARCHITECTURE_DECISION_INDEX.md
- ADR documents
- Capability Decision documents

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
| Approval Workflow | Implemented | Approval | ADR-004 |
| HR Master Data | Implemented | HR | ADR-003 |
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
| Approval Workflow | ✓ | ✓ | ✓ | Implemented |
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

# Master Architecture Roadmap

**Document:** Master Architecture Roadmap
**Status:** Active
**Owner:** Architecture Governance
**Version:** 1.0
**Last Updated:** 2026-08-05

---

# Purpose

This roadmap defines the long-term architectural evolution of the EOP platform.

It answers:

- What architecture already exists?
- What capability comes next?
- Which capabilities are intentionally deferred?
- Which architectural foundations must be completed first?

This document is architectural.

It is **not** a product roadmap or release plan.

---

# Architecture Vision

The EOP platform evolves through successive architectural layers.

```
Foundation

↓

Identity

↓

Authorization

↓

Business Capabilities

↓

Enterprise Platform
```

Each layer depends on the stability of the previous layer.

---

# Current Architecture State

```
Authentication
        │
        ▼
Identity Context
        │
        ▼
Authorization Foundation
        │
        ▼
Capability Authorization
        │
        ▼
Business Capabilities
```

---

# Architecture Phases

---

# Phase 1 — Platform Foundation

## Status

```
Completed
```

---

## Objectives

Establish the common architectural foundation.

---

## Capabilities

| Capability           | Status |
| -------------------- | ------ |
| Layered Architecture | ✅     |
| Repository Pattern   | ✅     |
| Unit of Work         | ✅     |
| SQLAlchemy Models    | ✅     |
| API Structure        | ✅     |
| Validation Pattern   | ✅     |

---

## Related ADR

- ADR-001
- ADR-002

---

# Phase 2 — HR Domain Foundation

## Status

```
Completed
```

---

## Objectives

Build reusable HR master-data capabilities.

---

## Capabilities

| Capability        | Status |
| ----------------- | ------ |
| Job Grade         | ✅     |
| Employment Type   | ✅     |
| Employment Status | ✅     |
| Shift             | ✅     |
| Holiday           | ✅     |

---

## Related ADR

- ADR-003

---

# Phase 3 — Identity Foundation

## Status

```
Completed
```

---

## Objectives

Provide deterministic employee identity resolution.

---

## Capability

```
Identity Context
```

---

## Deliverables

- EmployeeContext
- RequestContext
- CurrentRequestContext

---

## Related ADR

- ADR-006

---

# Phase 4 — Authorization Foundation

## Status

```
Completed
```

---

## Objectives

Provide reusable authorization infrastructure.

---

## Deliverables

- AuthorizationRequest
- AuthorizationDecision
- AuthorizationEvaluator
- AuthorizationService

---

## Consumers

Current:

- Approval Authorization

Future:

- Leave
- Attendance
- Payroll
- Performance
- Recruitment

---

## Related ADR

- ADR-007

---

## Implemented

```
PR-052
```

---

# Phase 5 — Capability Authorization

## Status

```
In Progress
```

---

## Objective

Each business capability defines and owns its authorization policy while consuming the Authorization Foundation.

---

## Completed

| Capability             | Status |
| ---------------------- | ------ |
| Approval Authorization | ✅     |
| Leave Authorization    | ✅     |

---

## Current Policy

```
Manager Approval
```

Rule:

```
request.employee.manager_id
==
approver.employee.id
```

Only direct manager approval is supported.

---

## Related ADR

- ADR-008

---

## Implemented

```
PR-053
```

---

## Leave Authorization Policy

```
Owner Only
```

Rule:

```
LeaveRequest.employee_id
==
RequestContext.employee_context.employee.id
```

Only the owning employee may act on their own LeaveRequest.

---

## Related ADR

- ADR-007 (Authorization Foundation dependency; no dedicated Leave Authorization ADR exists)

---

## Implemented

```
PR-056
```

---

## Remaining Capability Authorizations

| Capability                | Status  |
| ------------------------- | ------- |
| Attendance Authorization  | Planned |
| Payroll Authorization     | Planned |
| Recruitment Authorization | Planned |
| Performance Authorization | Planned |

---

# Phase 6 — Enterprise Authorization

## Status

```
Planned
```

---

## Objective

Extend authorization beyond capability-specific policies.

---

## Planned Capabilities

### Permission Model

Reusable permission vocabulary.

---

### Policy Engine

Reusable policy evaluation.

---

### Delegated Approval

Temporary approval delegation.

---

### Organization Hierarchy

Enterprise reporting structure.

---

### Workflow Assignment

Dynamic approver assignment.

---

## Dependencies

Requires:

- Identity Context
- Authorization Foundation
- Capability Authorization

---

# Phase 7 — Enterprise Platform

## Status

```
Future
```

---

## Potential Capabilities

- Event Bus
- Audit Platform
- Notification Platform
- Scheduling Engine
- Reporting Platform
- Search Platform
- Integration Platform

Future ADRs required.

---

# Capability Roadmap

| Capability               | Status         |
| ------------------------ | -------------- |
| Identity Context         | ✅ Implemented |
| Authorization Foundation | ✅ Implemented |
| Approval Authorization   | ✅ Implemented |
| Leave Authorization      | ✅ Implemented |
| Attendance Authorization | Planned        |
| Payroll Authorization    | Planned        |
| Permission Model         | Deferred       |
| Policy Engine            | Deferred       |
| Delegated Approval       | Deferred       |
| Organization Hierarchy   | Deferred       |

---

# Dependency Roadmap

```
Authentication
        │
        ▼
Identity Context
        │
        ▼
Authorization Foundation
        │
        ▼
Approval Authorization
        │
        ▼
Leave Authorization
        │
        ▼
Attendance Authorization
        │
        ▼
Payroll Authorization
        │
        ▼
Enterprise Authorization
```

---

# Deferred Architecture

The following remain intentionally outside the current roadmap phase.

- Permission Model
- Policy Engine
- Approval Roles
- Delegated Approval
- Recursive Manager Hierarchy
- Workflow Assignment
- Organization Graph

Each requires a dedicated ADR before implementation.

---

# Technical Debt Alignment

Current roadmap blockers and deferred work are tracked in:

```
TECHNICAL_DEBT_REGISTER.md
```

Current tracked debt:

- TD-001 — EmployeeContext HTTP Exception Mapping
- TD-002 — Approval Authorization Concurrency Protection
- TD-003 — Employee Manager Hierarchy Limitation
- TD-004 — Permission and Policy Model
- TD-005 — Authorization Foundation Consumer Coverage

---

# Governance Principles

Architecture evolves according to the following sequence:

```
Discovery

↓

Policy Discovery

↓

ADR (if required)

↓

Capability Decision

↓

Implementation Plan

↓

Implementation

↓

Architecture Review

↓

Merge
```

No implementation may bypass this governance process.

---

# Success Criteria

The architecture roadmap is considered healthy when:

- Platform foundations remain stable.
- Business capabilities consume shared foundations.
- Capability-specific policies remain isolated.
- Architectural decisions are documented before implementation.
- Technical debt is tracked and intentionally managed.

---

# Related Documents

- MASTER_ARCHITECTURE_BLUEPRINT.md
- ARCHITECTURE_STATUS.md
- ARCHITECTURE_CHANGELOG.md
- ARCHITECTURE_DECISION_INDEX.md
- CAPABILITY_CATALOG.md
- TECHNICAL_DEBT_REGISTER.md
- ARCHITECTURE_PRINCIPLES.md
- ADR-001 ~ ADR-008

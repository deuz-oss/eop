# Architecture Decision Index

**Document:** Architecture Decision Index
**Status:** Active
**Owner:** Architecture Governance
**Version:** 1.0
**Last Updated:** 2026-08-05

---

# Purpose

This document provides an index of all Architecture Decision Records (ADR) within the EOP platform.

The purpose of this index is to:

- identify active architecture decisions
- provide decision ownership visibility
- track implementation status
- connect decisions with capabilities

Detailed decisions remain inside individual ADR documents.

---

# ADR Status Definition

| Status | Meaning |
|---|---|
| Proposed | Decision under discussion |
| Accepted | Approved architecture decision |
| Superseded | Replaced by newer decision |
| Deprecated | No longer recommended |

---

# Architecture Decision Summary

| ADR | Title | Status | Capability | Implementation Status |
|---|---|---|---|---|
| ADR-001 | Backend Architecture Structure | Accepted | Platform | Implemented |
| ADR-002 | Database and Persistence Strategy | Accepted | Platform | Implemented |
| ADR-003 | HR Domain Architecture Direction | Accepted | HR | Implemented |
| ADR-004 | Approval Workflow Architecture | Accepted | Approval Workflow | Implemented |
| ADR-005 | Approval Authorization Separation | Accepted | Approval | Implemented |
| ADR-006 | Identity Context Resolution | Accepted | Identity Context | Implemented |
| ADR-007 | Authorization Foundation | Accepted | Authorization | Implemented |
| ADR-008 | Approval Authorization Policy Model | Accepted | Approval Authorization | Implemented |

---

# ADR-001 — Backend Architecture Structure

**Status:**

Accepted

**Capability:**

Platform Architecture

---

## Decision

The backend follows layered architecture:

API
↓
Service
↓
UnitOfWork
↓
Repository
↓
Model

---

## Principles

Responsibilities are separated.

API:

- transport handling
- request validation mapping

Service:

- business logic
- orchestration

Repository:

- persistence only

---

## Implementation

Implemented across existing backend modules.

---

## Related

- ARCHITECTURE_PRINCIPLES.md

---

# ADR-002 — Database and Persistence Strategy

**Status:**

Accepted

**Capability:**

Platform Persistence

---

## Decision

Database access follows repository abstraction.

Persistence concerns remain isolated from business logic.

---

## Principles

Repositories must not contain:

- business validation
- workflow decisions
- authorization rules

---

## Implementation

Implemented through SQLAlchemy models and repositories.

---

# ADR-003 — HR Domain Architecture Direction

**Status:**

Accepted

**Capability:**

HR Platform

---

## Decision

HR capabilities are developed as independent domain capabilities.

Master data and transactional workflows are separated.

---

## Principles

Master data:

- reference information

Transactions:

- business processes

---

## Related Capabilities

- Employee
- Employment Type
- Employment Status
- Job Grade
- Approval workflows

---

# ADR-004 — Approval Workflow Architecture

**Status:**

Accepted

**Capability:**

Approval Workflow

---

## Decision

Approval workflow is responsible for:

- approval lifecycle
- state transitions
- approval execution

---

## Not Responsible For

Approval workflow does not own:

- authorization policy
- permission evaluation
- role decisions

---

## Implementation

ApprovalService implemented as workflow orchestrator.

---

# ADR-005 — Approval Authorization Separation

**Status:**

Accepted

**Capability:**

Approval

---

## Decision

Approval authorization must be separated from approval workflow.

Authorization is a distinct concern.

---

## Principles

ApprovalService:

May:

- request authorization

Must not:

- implement authorization policy

---

## Future Extensions

Possible future models:

- RBAC approval
- resource policy
- workflow assignment

Require separate decisions.

---

# ADR-006 — Identity Context Resolution

**Status:**

Accepted

**Capability:**

Identity Context

---

## Decision

Authenticated identity is resolved into employee context.

Flow:

CurrentUser
↓
HrEmployee
↓
EmployeeContext

---

## Purpose

Provides consistent identity information for business capabilities.

---

## Implementation

Implemented.

---

## Known Limitation

HTTP exception mapping remains deferred.

Tracked:

TECHNICAL_DEBT_REGISTER.md
TD-001

---

# ADR-007 — Authorization Foundation

**Status:**

Accepted

**Capability:**

Authorization

---

## Decision

Introduce generic authorization foundation.

Components:

- AuthorizationRequest
- AuthorizationDecision
- AuthorizationEvaluator
- AuthorizationService

---

## Design Principle

Separate:

Authorization Mechanism
from
Authorization Policy

---

## Does Not Introduce

- permission model
- RBAC redesign
- policy engine
- ownership framework

---

## Implementation

Implemented:

PR-052

---

## Consumers

Current:

Approval Authorization

---

# ADR-008 — Approval Authorization Policy Model

**Status:**

Accepted

**Capability:**

Approval Authorization

---

## Decision

Approval authorization uses:

Manager Approval Policy

---

## Authorization Rule

A user may approve only when:

request.employee.manager_id
approver.employee.id

---

## Scope

Supported:

- direct manager approval
- approve authorization
- reject authorization

---

## Not Supported

The decision does not introduce:

- recursive manager hierarchy
- delegated approval
- workflow assignment
- approval roles
- permission model

---

## Implementation

Implemented:

PR-053

---

## Dependencies

Requires:

- Identity Context
- Authorization Foundation
- Approval Workflow

---

# Decision Dependency Map

ADR-006
Identity Context
    |

    v
ADR-007
Authorization Foundation
    |

    v
ADR-008
Approval Authorization Policy
    |

    v
Approval Capabilities

---

# Capability Decision Relationship

Architecture decisions are consumed by capability decisions.

Flow:

ADR
↓
Capability Decision
↓
Implementation Plan
↓
Implementation

---

# Current Active Architecture Decisions

| Area | Active Decision |
|---|---|
| Backend Structure | ADR-001 |
| Persistence | ADR-002 |
| HR Domain | ADR-003 |
| Approval Workflow | ADR-004 |
| Authorization Separation | ADR-005 |
| Identity Context | ADR-006 |
| Authorization Foundation | ADR-007 |
| Approval Authorization Policy | ADR-008 |

---

# Superseded Decisions

None.

---

# Deprecated Decisions

None.

---

# Future Decision Areas

The following areas require future ADR before implementation:

| Area | Reason |
|---|---|
| Permission Model | Requires authorization vocabulary |
| Policy Engine | Requires policy architecture |
| Delegated Approval | Requires business decision |
| Organization Hierarchy | Requires employee structure decision |
| Workflow Assignment | Requires workflow architecture |

---

# Governance Rules

Architecture decisions:

- must be documented before implementation
- must have clear scope
- must define constraints
- must identify non-goals
- must reference implementation

Implementation must not create new ADR decisions implicitly.

---

# References

- MASTER_ARCHITECTURE_BLUEPRINT.md
- MASTER_ARCHITECTURE_ROADMAP.md
- ARCHITECTURE_STATUS.md
- ARCHITECTURE_CHANGELOG.md
- TECHNICAL_DEBT_REGISTER.md
- ARCHITECTURE_PRINCIPLES.md
- CLAUDE_IMPLEMENTATION_GUIDE.md
- Individual ADR documents

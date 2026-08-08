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
| ADR-009 | Enterprise Authorization Governance Gate | Accepted | Enterprise Authorization | Blocked / Deferred |

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

# ADR-009 — Enterprise Authorization Governance Gate

**Status:**

Accepted

**Decision Type:**

Architecture Governance

**Capability:**

Enterprise Authorization

**Scope:**

Enterprise Authorization — Phase 6

**Predecessor:**

Payroll Authorization

---

## Context

Payroll Authorization has been completed.

The EOP architecture roadmap places Enterprise Authorization after Payroll Authorization in the Dependency Roadmap:

Attendance Authorization → Payroll Authorization → Enterprise Authorization

However, the same roadmap contains conflicting implementation-readiness signals.

**Dependency Roadmap**

The dependency diagram places Enterprise Authorization after Payroll Authorization. This establishes an architectural dependency/order relationship.

**Capability Roadmap / Deferred Architecture**

The Capability Roadmap marks the Enterprise Authorization constituent capabilities as Deferred, including:

- Permission Model
- Policy Engine
- Delegated Approval
- Organization Hierarchy

The Deferred Architecture section further states that these capabilities remain outside the current roadmap phase and require dedicated ADRs before implementation.

**Phase 5 Remaining Capability Authorizations**

The roadmap also still lists:

- Recruitment Authorization — Planned
- Performance Authorization — Planned

Neither has a corresponding protected resource implemented in the repository. Therefore, these Planned entries do not currently provide an actionable implementation target either.

---

## Problem Statement

The Dependency Roadmap does not by itself establish implementation authorization.

At the same time, the roadmap contains other sequencing signals that have not been reconciled.

The repository therefore needs to distinguish:

1. architectural dependency/order;
2. implementation readiness;
3. selection of the next implementation workstream.

These are not equivalent decisions.

---

## Decision

Enterprise Authorization remains DEFERRED and is NOT selected as the next implementation workstream.

The Dependency Roadmap is interpreted as establishing an architectural dependency/order relationship only.

The Capability Roadmap and Deferred Architecture remain the controlling evidence for Enterprise Authorization implementation readiness.

Therefore:

Payroll Authorization being complete does not authorize Enterprise Authorization implementation.

This ADR does not select the next implementation workstream.

---

## Phase 5 Planned Items

This ADR explicitly records the unresolved status of the remaining Phase 5 authorization entries:

- Recruitment Authorization — Planned
- Performance Authorization — Planned

Neither is selected by this ADR.

Repository evidence shows that neither currently has a protected resource required for an actionable authorization capability.

Therefore, these entries remain roadmap items but do not become implementation targets through this ADR.

Determining whether either should become the next actionable workstream is a separate roadmap-sequencing decision.

---

## Relationship to Roadmap Sequencing Decision

Upon acceptance, this ADR supersedes the unresolved Enterprise Authorization interpretation question recorded in:

`docs/architecture/00-governance/ROADMAP_SEQUENCING_DECISION.md`

Specifically, this ADR provides the governance interpretation that was previously left unresolved:

> The Enterprise Authorization dependency pointer does not constitute implementation authorization.

However, this ADR does not supersede the broader sequencing question recorded there. In particular, it does not decide:

- Recruitment Authorization vs. Performance Authorization
- Enterprise Authorization vs. another capability
- Phase 7 Enterprise Platform
- the globally correct "next" implementation workstream

Those questions remain outside the scope of this ADR.

---

## Relationship to Existing Authorization Capabilities

Existing authorization capabilities provide implementation precedent only.

Relevant precedent includes:

- Identity Authorization
- Approval Authorization
- Leave Authorization
- Attendance Authorization
- Payroll Authorization

Their implementation patterns may be referenced by future Enterprise Authorization discovery. They do not automatically establish Enterprise Authorization policy.

---

## Prerequisites

Before Enterprise Authorization implementation can begin, its governance sequence must be completed:

1. Discovery
2. Policy Discovery
3. Dedicated ADR(s), where required
4. Capability Decision
5. Implementation Plan
6. Implementation

No source code, migration, model, API, authorization evaluator, or database change is authorized by this ADR.

---

## Explicitly Out of Scope

This ADR does not decide the design of:

- Permission Model
- Policy Engine
- Delegated Approval
- Organization Hierarchy
- Workflow Assignment
- enterprise roles
- permission storage
- policy representation
- policy evaluation
- delegation rules
- organization hierarchy semantics
- workflow ownership
- migration/schema requirements

No implementation architecture is selected for these items.

---

## Implementation Gate

Enterprise Authorization:

BLOCKED / DEFERRED — not authorized for implementation.

Recruitment Authorization:

NOT SELECTED — remains Planned but currently lacks an actionable protected resource.

Performance Authorization:

NOT SELECTED — remains Planned but currently lacks an actionable protected resource.

Next Workstream:

UNRESOLVED — this ADR deliberately does not choose the next implementation workstream.

---

## Implementation

None — blocked; see Implementation Gate above.

No source code, migration, model, API, authorization evaluator, or database change is authorized by this ADR.

---

## Consequences

Positive:

- Separates dependency ordering from implementation authorization.
- Prevents Enterprise Authorization from being implemented merely because it appears after Payroll Authorization.
- Preserves the roadmap's Deferred Architecture constraint.
- Explicitly records the unresolved Phase 5 Planned entries.
- Prevents this ADR from being mistaken for a complete roadmap-sequencing decision.

Negative:

- Enterprise Authorization remains blocked.
- The repository still requires a separate Architecture Governance decision to determine the next actionable workstream.

These consequences are intentional.

---

## Final Decision

Enterprise Authorization remains DEFERRED.

The roadmap dependency:

Payroll Authorization → Enterprise Authorization

is treated as an architectural dependency/order relationship, not an implementation command.

This ADR resolves the Enterprise Authorization implementation-readiness ambiguity. It does not select the next roadmap workstream.

No implementation may begin under this ADR.

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
| Enterprise Authorization Governance | ADR-009 |

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

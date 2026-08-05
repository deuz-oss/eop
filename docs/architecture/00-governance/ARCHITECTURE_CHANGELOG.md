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

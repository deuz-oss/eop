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

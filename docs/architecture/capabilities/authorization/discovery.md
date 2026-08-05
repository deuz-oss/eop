# Authorization Foundation — Discovery

**Status:** Complete

**Capability:** Authorization Foundation

**Owner:** EOP Architecture Governance

---

# Purpose

This document records repository evidence for the Authorization Foundation capability.

Discovery exists to understand the current repository state.

It does not define architecture.

Architecture decisions are documented separately.

---

# Discovery Scope

The following areas were inspected:

- Authentication
- Identity Context Foundation
- Role Management
- Employee Context
- Request Context
- Approval
- Leave
- Overtime
- Timesheet
- Reconciliation
- HrEmployee
- Manager hierarchy

---

# Repository Summary

Repository discovery confirms:

Authentication is fully implemented.

Identity Context Foundation has been implemented.

EmployeeContext and RequestContext are available.

Role-based enforcement exists only for Role administration.

Business capabilities perform authentication only.

No reusable authorization platform currently exists.

---

# Existing Authorization Surface

## Authentication

Implemented.

CurrentUser authenticates every inspected endpoint.

Authentication is the only platform capability currently consumed by business modules.

---

## Identity Context

Implemented.

Repository provides:

- EmployeeContext
- RequestContext
- EmployeeContextResolver

These components currently have no production consumers.

They are consumed only by their own tests.

---

## Role Enforcement

Repository contains:

- Role
- UserRole
- RequireRole
- RequireAdmin

Repository evidence shows RequireRole is used only by Role administration endpoints.

No business capability consumes RequireRole.

---

## Ownership Validation

Repository evidence shows no ownership validation.

No capability determines whether the authenticated caller owns a requested resource.

---

## Approval Authorization

Repository evidence shows no authorization layer.

ApprovalService performs workflow orchestration only.

Authorization beyond authentication is explicitly outside its responsibility.

---

## Business Capabilities

The following capabilities depend only on CurrentUser:

- Leave
- Overtime
- Timesheet
- Reconciliation

Repository evidence shows no ownership validation.

Repository evidence shows no role validation.

Repository evidence shows no authorization abstraction.

---

## Manager Hierarchy

Repository contains:

```
HrEmployee.manager_id
```

Repository evidence indicates:

- direct reporting relationship exists
- self-manager validation exists

Repository evidence does not show any authorization use of manager_id.

---

# Dependency Analysis

Current dependency flow:

```
Authentication

↓

Identity Context

↓

Business Services
```

Missing capability:

```
Authorization Foundation
```

Target architecture has not yet been implemented.

---

# Findings

Repository currently provides:

✅ Authentication

✅ Identity Context

✅ Role storage

Repository does not provide:

- AuthorizationService
- OwnershipResolver
- AuthorizationDecision
- AuthorizationPolicy
- reusable authorization abstraction

---

# Architectural Ambiguities

Discovery identified the following unresolved topics.

## Authorization Boundary

Repository does not define where authorization should execute.

Possible locations:

- API
- Service
- Dedicated Authorization Component

Architecture decision required.

---

## Ownership Resolution

Repository contains no ownership abstraction.

Architecture decision required.

---

## Policy Evaluation

Repository contains no reusable policy model.

Architecture decision required.

---

## Permission Model

Repository contains no permission abstraction.

Architecture decision required.

---

# Open Questions

Discovery could not determine:

- authorization execution boundary
- ownership model
- policy abstraction
- future permission model
- manager-scoped authorization
- delegated authorization

These require architecture decisions.

---

# Recommended Next Step

Architecture Decision

Repository evidence is sufficient.

Discovery is complete.

Proceed to:

- decision.md
- ADR-007
- implementation-plan.md

# Authorization Foundation — Architecture Decision

**Status:** Approved

**Capability:** Authorization Foundation

**Owner:** EOP Architecture Governance

---

# Purpose

This document records the architectural decisions for the Authorization Foundation capability.

Authorization Foundation introduces a reusable platform capability responsible for evaluating whether an authenticated request may execute a business operation.

Authorization Foundation is a platform capability.

It is not a business capability.

It owns no business workflow.

It owns no transport concerns.

---

# Repository Context

Repository discovery confirms the following:

Authentication is fully implemented.

Identity Context Foundation is fully implemented.

Repository currently provides:

- CurrentUser
- EmployeeContext
- EmployeeContextResolver
- RequestContext

Business capabilities currently consume authentication only.

Repository contains:

- Role
- UserRole
- RequireRole

RequireRole is currently used only for Role administration.

Repository contains no reusable authorization capability.

Repository contains no ownership abstraction.

Repository contains no authorization evaluation layer.

Repository contains no reusable authorization decision model.

---

# Problem Statement

Authentication answers:

> Who is making the request?

Identity Context answers:

> Which employee does this request represent?

Repository currently contains no platform capability capable of answering:

> May this request perform this operation?

Without a reusable authorization capability:

- business services would own authorization
- authorization logic would become duplicated
- ownership validation would become inconsistent
- future authorization models would become difficult to evolve

---

# Decision

EOP adopts Authorization Foundation as an independent platform capability.

Authorization Foundation evaluates authorization.

Business capabilities execute business logic.

Identity Context resolves identity.

Authentication authenticates users.

Each capability owns exactly one responsibility.

---

# Capability Boundary

Authorization Foundation owns:

- authorization orchestration
- authorization evaluation
- authorization decision
- ownership abstraction
- role abstraction

Authorization Foundation does not own:

- authentication
- identity resolution
- workflow
- business validation
- approval
- leave
- overtime
- timesheet
- payroll
- notification
- persistence

---

# Platform Position

Authorization Foundation is positioned between Identity Context and Business Services.

Execution flow becomes:

```
Authentication

↓

Identity Context

↓

Authorization Foundation

↓

Business Service

↓

Repository
```

Business Services must never bypass Authorization Foundation.

Repositories remain persistence-only.

---

# Authorization Service

AuthorizationService becomes the application entry point for authorization.

Responsibilities:

- coordinate authorization
- delegate ownership evaluation
- delegate role evaluation
- delegate authorization evaluation
- return AuthorizationDecision

AuthorizationService owns no business workflow.

AuthorizationService owns no persistence.

AuthorizationService owns no transport behavior.

---

# Authorization Evaluator

Authorization evaluation is performed through a dedicated AuthorizationEvaluator abstraction.

AuthorizationEvaluator determines whether a request is authorized.

AuthorizationEvaluator:

- contains no persistence
- contains no workflow
- contains no transport logic
- contains no repository logic

AuthorizationEvaluator remains replaceable.

---

# Authorization Decision

Authorization Foundation returns AuthorizationDecision.

AuthorizationDecision is an immutable value object.

AuthorizationDecision represents the outcome of authorization evaluation.

AuthorizationDecision is transport-independent.

AuthorizationDecision is not an exception.

Business capabilities determine how denied decisions should be handled.

---

# Ownership Resolution

Ownership resolution becomes a platform abstraction.

Ownership resolution determines whether a request context owns a requested resource.

OwnershipResolver does not understand business workflow.

OwnershipResolver does not mutate repository state.

Business capabilities provide concrete ownership implementations during future integration.

---

# Role Resolution

Role resolution becomes a platform abstraction.

RoleResolver encapsulates role lookup.

Business services must not inspect roles directly.

Existing RequireRole remains available for coarse-grained administrative endpoints.

Business capabilities should consume Authorization Foundation instead.

---

# Request Context

Authorization Foundation consumes RequestContext.

RequestContext remains the canonical execution context.

Authorization Foundation must never bypass RequestContext.

Authorization components must not depend directly on CurrentUser.

---

# Employee Context

Authorization Foundation consumes EmployeeContext.

EmployeeContext remains responsible only for identity resolution.

Authorization Foundation must not extend EmployeeContext with:

- permissions
- authorization state
- workflow state
- business state

Identity Context and Authorization remain separate capabilities.

---

# API Boundary

API endpoints remain transport-only.

API responsibilities remain:

- dependency injection
- request validation
- exception translation

Authorization must not be implemented inside API routes.

---

# Repository Boundary

Repositories remain persistence-only.

Repositories must never contain:

- authorization
- ownership
- permission evaluation
- authorization decisions

---

# Database Boundary

Authorization Foundation introduces no database changes.

Authorization Foundation introduces no migrations.

Authorization Foundation introduces no persistence model.

Future authorization persistence requires a separate architecture decision.

---

# Exception Strategy

Authorization Foundation does not raise transport-specific exceptions.

Authorization Foundation returns AuthorizationDecision.

Business capabilities or API adapters may translate denied decisions into exceptions when appropriate.

Transport concerns remain outside Authorization Foundation.

---

# Dependency Direction

Dependency direction becomes:

```
Authentication

↓

Identity Context

↓

Authorization Foundation

↓

Business Capability
```

Authorization Foundation must never depend on business capabilities.

Business capabilities may depend on Authorization Foundation.

---

# Consumers

Future consumers include:

- Approval
- Leave
- Timesheet
- Overtime
- Reconciliation
- Attendance
- Payroll
- Workflow

Each consumer integrates Authorization Foundation independently.

---

# Out of Scope

Authorization Foundation intentionally excludes:

- Leave authorization rules
- Approval authorization rules
- Timesheet authorization rules
- Overtime authorization rules
- Manager hierarchy
- Organization hierarchy
- Delegated authority
- Permission persistence
- Policy engine
- ABAC
- RBAC redesign
- Workflow authorization

These belong to future capabilities.

---

# Alternatives Considered

## Business-Service Authorization

Rejected.

Reason:

Business services should not own authorization.

---

## API-Level Authorization

Rejected.

Reason:

Authorization belongs to the application layer.

---

## Repository Authorization

Rejected.

Reason:

Repositories remain persistence-only.

---

# Consequences

Positive:

- reusable authorization platform
- single authorization entry point
- clear capability boundaries
- simplified business services
- consistent authorization model

Negative:

- introduces an additional application capability
- future capabilities must integrate Authorization Foundation
- authorization becomes an additional platform dependency

---

# Future Evolution

Future architecture may introduce:

- manager authorization
- delegated authority
- organization-scoped authorization
- policy composition
- permission persistence
- caching
- audit integration

Each extension requires a separate architecture decision.

---

# Related Documents

- ADR-004 — HrEmployee User Identity Link
- ADR-005 — Request Context Architecture
- ADR-006 — Employee Context Resolution Model
- Authorization Foundation Discovery
- Master Architecture Blueprint
- Master Architecture Roadmap

---

# Decision Summary

Authentication authenticates.

Identity resolves.

Authorization evaluates.

Business capabilities execute business logic.

Each platform capability owns one responsibility.

Authorization Foundation becomes the single reusable authorization platform for EOP.

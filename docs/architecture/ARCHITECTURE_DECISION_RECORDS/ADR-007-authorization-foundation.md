# ADR-007 — Authorization Foundation

**Status:** Accepted

**Date:** YYYY-MM-DD

**Owner:** EOP Architecture Governance

**Capability**

```
Authorization Foundation
```

---

# Context

EOP currently provides two foundational platform capabilities.

Authentication establishes the identity of the caller.

Identity Context Foundation deterministically resolves the authenticated user into an EmployeeContext and RequestContext.

Repository discovery confirms the following:

Implemented:

- Authentication
- Identity Context Foundation
- Role storage
- Role membership

Missing:

- Authorization evaluation
- Ownership abstraction
- Authorization decision model
- Reusable authorization platform

Business capabilities currently execute immediately after identity resolution.

No reusable authorization capability exists.

---

# Problem

Authentication answers:

> Who is calling?

Identity Context answers:

> Which employee does this request represent?

The platform currently cannot answer:

> Is this request allowed to perform this operation?

Without a reusable authorization capability:

- authorization becomes duplicated
- business services become responsible for authorization
- ownership rules become inconsistent
- authorization evolves independently across capabilities

This violates capability-oriented architecture.

---

# Decision

EOP introduces Authorization Foundation as a standalone platform capability.

Authorization Foundation becomes responsible for authorization evaluation.

Business capabilities remain responsible for business workflow.

Authentication remains responsible for authentication.

Identity Context remains responsible for identity resolution.

---

# Architecture

Platform execution becomes:

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

Authorization Foundation evaluates requests.

Business Services execute workflows.

Repositories persist data.

---

# Capability Responsibilities

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
- persistence
- business validation
- transport behavior

---

# Platform Independence

Authorization Foundation is transport-independent.

Authorization Foundation has no dependency on:

- HTTP
- FastAPI
- routers
- controllers
- API contracts

Authorization Foundation exists entirely inside the application layer.

---

# Authorization Service

AuthorizationService becomes the platform entry point.

Responsibilities:

- coordinate authorization
- invoke ownership resolution
- invoke role resolution
- invoke authorization evaluation
- return AuthorizationDecision

AuthorizationService performs no workflow.

AuthorizationService performs no persistence.

---

# Authorization Evaluator

AuthorizationEvaluator performs authorization evaluation.

AuthorizationEvaluator:

- evaluates authorization
- contains no persistence
- contains no workflow
- contains no transport logic

AuthorizationEvaluator remains replaceable.

Future authorization models may replace evaluator implementation without affecting consumers.

---

# Authorization Decision

Authorization Foundation returns AuthorizationDecision.

AuthorizationDecision represents authorization outcome.

AuthorizationDecision is immutable.

AuthorizationDecision is transport-independent.

AuthorizationDecision is not an exception.

AuthorizationDecision contains no workflow behavior.

Consumers determine how denied decisions should be handled.

---

# Ownership Resolution

Ownership resolution becomes an application abstraction.

OwnershipResolver determines whether a request owns a resource.

OwnershipResolver remains business-independent.

Concrete ownership implementations belong to business capabilities.

Authorization Foundation owns only the abstraction.

---

# Role Resolution

RoleResolver encapsulates role lookup.

Business services must never inspect role membership directly.

Existing administrative RequireRole remains valid.

Business capabilities should consume Authorization Foundation.

---

# Identity Integration

Authorization Foundation consumes:

```
RequestContext
```

Authorization Foundation consumes:

```
EmployeeContext
```

Authorization Foundation never consumes JWT directly.

Authorization Foundation never consumes CurrentUser directly.

Identity Context remains responsible for identity resolution.

---

# Repository Boundary

Repositories remain persistence-only.

Repositories never perform:

- authorization
- ownership validation
- role validation
- policy evaluation

---

# Database Impact

Authorization Foundation introduces:

- no migration
- no schema changes
- no new persistence model

Future permission persistence requires a separate ADR.

---

# Exception Strategy

Authorization Foundation does not raise transport-specific exceptions.

Authorization Foundation returns AuthorizationDecision.

Consumers decide how denied authorization should be represented.

HTTP exception mapping belongs outside Authorization Foundation.

---

# Dependency Direction

Platform dependency becomes:

```
Authentication

↓

Identity Context

↓

Authorization Foundation

↓

Business Capability
```

Business capabilities depend on Authorization Foundation.

Authorization Foundation never depends on business capabilities.

---

# Consumers

Future consumers include:

- Leave
- Approval
- Timesheet
- Overtime
- Reconciliation
- Attendance
- Payroll

Each capability integrates Authorization Foundation independently.

---

# Alternatives Considered

## Business-Service Authorization

Rejected.

Reason:

Creates duplicated authorization logic.

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

## Permission-Based Foundation

Rejected.

Reason:

Repository currently contains no permission model.

Introducing permissions now would unnecessarily constrain future architecture.

Authorization evaluation remains permission-agnostic.

---

# Consequences

Positive:

- reusable authorization capability
- consistent authorization model
- platform independence
- simplified business services
- clear capability boundaries

Negative:

- introduces an additional platform dependency
- requires future capability integration

---

# Risks

Business capabilities remain unauthorised until integrated.

This ADR introduces only the reusable platform.

Integration is intentionally deferred.

---

# Future Evolution

Future capabilities may introduce:

- manager authorization
- delegated authority
- organization hierarchy
- permission persistence
- policy composition
- policy caching
- audit integration

Each requires a separate architecture decision.

---

# Related Documents

- ADR-004 — HrEmployee User Identity Link
- ADR-005 — Request Context Architecture
- ADR-006 — Employee Context Resolution Model
- Authorization Foundation Discovery
- Authorization Foundation Decision
- Master Architecture Blueprint
- Master Architecture Roadmap

---

# Status History

| Date       | Status   | Notes            |
| ---------- | -------- | ---------------- |
| YYYY-MM-DD | Accepted | Initial approval |

---

# Decision Summary

Authentication authenticates.

Identity Context resolves identity.

Authorization Foundation evaluates authorization.

Business capabilities execute business workflow.

Each capability owns exactly one responsibility.

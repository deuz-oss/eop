# Authorization Foundation — Implementation Plan

**Status:** Approved

**Capability:** Authorization Foundation

**Owner:** EOP Architecture Governance

---

# Purpose

This document defines the implementation plan for the Authorization Foundation capability.

It translates the approved architecture into executable implementation work.

This document introduces no architectural decisions.

Architecture is defined by:

- Authorization Foundation Discovery
- Authorization Foundation Decision
- ADR-007

---

# Objective

Implement a reusable authorization platform.

The platform evaluates authorization.

The platform does not implement business authorization.

The platform introduces no workflow behavior.

The platform introduces no transport behavior.

---

# Implementation Principles

Implementation must:

- follow ADR-007
- preserve existing architecture
- preserve repository layering
- introduce no endpoint behavior changes
- introduce no business authorization
- introduce no persistence

---

# Scope

The implementation introduces the reusable platform only.

Platform components:

- AuthorizationService
- AuthorizationEvaluator
- AuthorizationDecision
- OwnershipResolver
- RoleResolver

Unit tests are included.

No business integration is included.

---

# Out of Scope

This implementation intentionally excludes:

- Leave authorization
- Approval authorization
- Overtime authorization
- Timesheet authorization
- Reconciliation authorization
- Attendance authorization
- Payroll authorization
- Manager authorization
- Organization authorization
- Permission persistence
- Policy engine
- ABAC
- RBAC redesign
- API exception mapping
- FastAPI dependencies

These belong to future capabilities.

---

# Existing Dependencies

Authorization Foundation consumes existing platform capabilities.

Authentication

```
CurrentUser
```

Identity Context

```
EmployeeContext

RequestContext
```

Role Infrastructure

```
Role

UserRole
```

Authorization Foundation must not depend on business capabilities.

---

# Layer Responsibilities

## API

Responsibilities:

- dependency injection
- request validation
- exception translation

API performs no authorization.

---

## Authorization Foundation

Responsibilities:

- authorization orchestration
- authorization evaluation
- ownership abstraction
- role abstraction
- authorization decision

No workflow.

No persistence.

No transport behavior.

---

## Business Services

Responsibilities:

- business validation
- workflow
- repository orchestration

Business services consume Authorization Foundation.

---

## Repository

Persistence only.

Repositories perform no authorization.

---

# Execution Flow

Target execution flow:

```
Authentication

↓

Identity Context

↓

RequestContext

↓

AuthorizationService

↓

AuthorizationEvaluator

↓

AuthorizationDecision

↓

Business Service

↓

Repository
```

---

# Component Responsibilities

## AuthorizationService

AuthorizationService coordinates authorization.

Responsibilities:

- receive RequestContext
- coordinate authorization
- invoke OwnershipResolver
- invoke RoleResolver
- invoke AuthorizationEvaluator
- return AuthorizationDecision

AuthorizationService owns no workflow.

AuthorizationService owns no persistence.

AuthorizationService owns no transport behavior.

---

## AuthorizationEvaluator

AuthorizationEvaluator performs authorization evaluation.

Responsibilities:

- evaluate authorization
- produce AuthorizationDecision

AuthorizationEvaluator performs no:

- persistence
- workflow
- transport logic

AuthorizationEvaluator remains replaceable.

---

## AuthorizationDecision

AuthorizationDecision is an immutable value object.

Responsibilities:

- represent authorization outcome
- expose authorization result
- expose optional denial reason

AuthorizationDecision contains:

- no workflow
- no persistence
- no transport behavior

AuthorizationDecision is not an exception.

---

## OwnershipResolver

OwnershipResolver is an abstraction.

Responsibilities:

- determine ownership

OwnershipResolver performs no business workflow.

OwnershipResolver contains no concrete ownership implementation.

Business capabilities provide implementations during future integration.

---

## RoleResolver

RoleResolver is an abstraction.

Responsibilities:

- determine role membership

RoleResolver contains no business authorization.

RoleResolver remains replaceable.

---

# Exception Strategy

Authorization Foundation introduces no authorization exceptions.

Authorization returns AuthorizationDecision.

Future business capabilities determine whether denied authorization becomes:

- HTTP exception
- domain exception
- workflow outcome

Authorization Foundation remains transport-independent.

---

# API Impact

None.

No endpoint changes.

No router modifications.

No dependency injection changes.

No behavior changes.

---

# Database Impact

None.

No migration.

No schema modification.

No model modification.

---

# Repository Impact

Expected production files:

```
services/api/src/eop_api/services/authorization.py

services/api/src/eop_api/services/authorization_evaluator.py

services/api/src/eop_api/services/authorization_decision.py

services/api/src/eop_api/services/ownership_resolver.py

services/api/src/eop_api/services/role_resolver.py
```

Additional implementation files may be introduced if they remain inside the Authorization Foundation boundary.

Existing repository structure should not be refactored.

---

# Testing Strategy

Unit tests:

- AuthorizationService
- AuthorizationEvaluator
- AuthorizationDecision
- OwnershipResolver abstraction
- RoleResolver abstraction

No endpoint tests.

No workflow tests.

No integration tests with business capabilities.

---

# Acceptance Criteria

Implementation is complete when:

- Authorization Foundation compiles successfully.
- Repository architecture remains unchanged.
- No endpoint behavior changes.
- No persistence changes.
- No migration.
- Authorization Foundation has no dependency on business capabilities.
- All tests pass.

---

# Validation

Execute:

```bash
ruff check .

mypy src

pytest
```

Alembic validation is not required.

---

# Deliverables

Implementation must provide:

1. Summary

2. Files Added

3. Files Modified

4. Validation

5. Remaining Risks

Following:

```
docs/architecture/CLAUDE_IMPLEMENTATION_GUIDE.md
```

---

# Future Integration

Future capabilities consume Authorization Foundation.

Planned order:

1. Approval Authorization

2. Leave Authorization

3. Timesheet Authorization

4. Overtime Authorization

5. Reconciliation Authorization

Each integration remains an independent capability implementation.

---

# Completion Criteria

Authorization Foundation is complete when:

- reusable authorization platform exists
- business capabilities remain unchanged
- authorization remains transport-independent
- authorization remains business-independent
- future capabilities can consume Authorization Foundation without architectural modification

---

# Summary

Authorization Foundation provides a reusable application-layer authorization platform.

It evaluates authorization.

It does not execute business workflow.

It does not persist data.

It does not perform transport behavior.

Future business capabilities integrate this platform incrementally.

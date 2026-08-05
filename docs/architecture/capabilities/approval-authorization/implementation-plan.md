# Approval Authorization — Implementation Plan

**Capability:** Approval Authorization

**Status:** Approved

**Version:** 2

**Depends On**

- ADR-004 — Identity Context
- ADR-005 — Authorization Context Model
- ADR-006 — Employee Context Resolution
- ADR-007 — Authorization Foundation
- ADR-008 — Approval Authorization Policy Model
- Approval Authorization Discovery
- Approval Authorization Policy Discovery
- Approval Authorization Decision

---

# Objective

Implement Approval Authorization using the existing Authorization Foundation.

Implementation shall consume the Approval Authorization Policy defined by the Capability Decision.

No architectural redesign is permitted.

---

# Scope

Implement only:

- ApprovalAuthorizationEvaluator
- ApprovalAuthorizationDeniedError
- Approval authorization integration
- API exception mapping
- Unit tests
- Integration tests
- API tests

No additional capability may be introduced.

---

# Out of Scope

Do not implement:

- delegated approval
- indirect manager approval
- recursive hierarchy traversal
- approval roles
- ownership authorization
- workflow assignment
- workflow engine
- permission model
- RBAC redesign
- Authorization Foundation redesign
- Employee Context redesign
- ApprovalService redesign
- repository redesign
- database schema changes

---

# Business Rule

Approval Authorization Policy is defined by the Capability Decision.

Implementation shall evaluate exactly one rule.

```
request.employee.manager_id
==
approver.employee.id
```

No additional authorization predicates shall be introduced.

---

# Authorization Flow

Approval authorization shall execute in the following sequence.

```
CurrentUser

↓

CurrentEmployeeContext

↓

RequestContext

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

Every approval operation shall pass through AuthorizationService.

No component may bypass this flow.

---

# ApprovalAuthorizationEvaluator

## Responsibilities

Owns:

- manager authorization evaluation

Consumes:

- AuthorizationRequest

Produces:

- AuthorizationDecision

Must remain:

- deterministic
- stateless
- side-effect free

Must not:

- access repositories
- execute workflow
- perform persistence
- translate HTTP
- mutate domain objects
- infer business policy

---

# AuthorizationService

## Responsibilities

Owns:

- evaluator orchestration

Consumes:

- AuthorizationRequest

Produces:

- AuthorizationDecision

Must not:

- evaluate manager hierarchy
- execute workflow
- access repositories
- introduce approval policy

---

# ApprovalService

ApprovalService remains the workflow orchestrator.

Before approving:

1. Build AuthorizationRequest.
2. Invoke AuthorizationService.
3. Receive AuthorizationDecision.
4. Throw ApprovalAuthorizationDeniedError when denied.
5. Continue workflow when allowed.

ApprovalService must never evaluate authorization directly.

---

# Exception

Create:

```
ApprovalAuthorizationDeniedError
```

Thrown only when:

```
AuthorizationDecision.allowed == false
```

No other component may throw this exception.

---

# API

Approval endpoints translate:

```
ApprovalAuthorizationDeniedError
```

into:

```
HTTP 403 Forbidden
```

API remains responsible only for:

- authentication
- validation
- HTTP translation

API must not contain authorization logic.

---

# Dependencies

Reuse existing platform components.

- CurrentUser
- CurrentEmployeeContext
- RequestContext
- EmployeeContext
- AuthorizationRequest
- AuthorizationService
- AuthorizationDecision

No new platform abstraction shall be introduced.

---

# Testing Strategy

## Unit Tests

ApprovalAuthorizationEvaluator

- direct manager → allow
- non-manager → deny
- requester without manager
- missing employee context
- requester attempting self approval

AuthorizationService

- evaluator delegation
- allow propagation
- deny propagation

---

## Integration Tests

ApprovalService

- approve allowed
- approve denied
- reject allowed
- reject denied

Verify ApprovalService performs no authorization evaluation.

---

## API Tests

Approval endpoints

- approval success
- approval forbidden
- rejection success
- rejection forbidden
- authentication required
- workflow unchanged

---

# Validation

Execute:

```
ruff check .

mypy src

pytest
```

Run capability-specific regression for:

- approval
- authorization
- employee context

---

# Success Criteria

Implementation is complete when:

- only direct managers may approve
- non-managers receive AuthorizationDecision(deny)
- API returns HTTP 403
- ApprovalService contains no authorization logic
- Authorization Foundation remains unchanged
- repository layer remains unchanged
- database schema remains unchanged
- architectural layering remains unchanged

---

# Deliverables

Implementation shall modify only components required for Approval Authorization.

No unrelated refactoring.

No architectural redesign.

No capability expansion.

---

# Architecture Contract

The following documents collectively define the implementation contract.

- ADR-004
- ADR-005
- ADR-006
- ADR-007
- ADR-008
- Approval Authorization Discovery
- Approval Authorization Policy Discovery
- Approval Authorization Decision

Implementation shall conform to these documents.

If repository evidence contradicts any approved architectural document:

Implementation must stop immediately.

Implementation must not reinterpret:

- approval policy
- manager hierarchy
- authorization rules
- workflow
- approval behavior

Architecture Governance is required before implementation may continue.

No architectural decision may be made during implementation.

---

# Escalation Matrix

Implementation must stop immediately under the following conditions.

## Business Policy Ambiguity

Examples:

- approval rule cannot be evaluated
- manager relationship is ambiguous
- approval behavior is undefined

Action:

Stop implementation.

Escalate to Architecture Governance.

---

## Repository Contradiction

Examples:

- repository behavior contradicts ADR
- repository evidence contradicts Capability Decision

Action:

Stop implementation.

Escalate.

---

## Missing Capability

Examples:

Implementation requires:

- workflow engine
- delegated approval
- approval assignment
- approval roles
- recursive hierarchy

Action:

Stop.

Do not expand capability scope.

---

## Architecture Conflict

Examples:

Implementation requires changes to:

- ADR
- Capability Decision
- Implementation Plan

Action:

Stop immediately.

Architecture must be revised before implementation resumes.

---

# Architecture Review Checklist

Before merge, verify:

- [ ] Authorization Foundation unchanged
- [ ] ApprovalService remains workflow-only
- [ ] ApprovalAuthorizationEvaluator owns manager evaluation
- [ ] AuthorizationService orchestrates evaluation only
- [ ] API performs HTTP translation only
- [ ] Repository contains no authorization logic
- [ ] No recursive hierarchy
- [ ] No delegated approval
- [ ] No approval roles introduced
- [ ] No ownership authorization introduced
- [ ] No workflow engine introduced
- [ ] Layering preserved
- [ ] No database schema changes
- [ ] All ADR constraints satisfied

---

# References

- ADR-004
- ADR-005
- ADR-006
- ADR-007
- ADR-008
- Approval Authorization Discovery
- Approval Authorization Policy Discovery
- Approval Authorization Decision
- MASTER_ARCHITECTURE_BLUEPRINT.md
- ARCHITECTURE_PRINCIPLES.md

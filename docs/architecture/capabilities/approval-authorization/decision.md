# Approval Authorization — Capability Decision

**Capability:** Approval Authorization

**Status:** Approved

**Version:** 2

**Owner:** Architecture

---

# Purpose

This capability defines the initial Approval Authorization Policy for the platform.

It selects the first business authorization policy that consumes the Authorization Foundation introduced by ADR-007.

This decision intentionally defines **business policy** only.

It does **not** modify:

- Authorization Foundation
- Authentication
- Identity Context
- Employee Context
- Approval workflow

---

# Background

The platform currently provides:

- Authentication
- Identity Context
- Employee Context
- Authorization Foundation
- Approval workflow orchestration

Repository Discovery established:

- Approval endpoints require authentication only.
- ApprovalService performs workflow orchestration.
- Authorization Foundation has no business consumers.
- No approval authorization currently exists.

Policy Discovery evaluated the following candidate policies:

- Assigned Approver
- Manager Approval
- Role-Based Approval
- Workflow Assignment
- Hybrid

Repository evidence shows that **Manager Approval** provides the strongest alignment with the current domain model while requiring no new business entities.

---

# Decision

The platform adopts **Manager Approval** as the initial Approval Authorization Policy.

Approval is granted only to the direct manager of the requesting employee.

No other authorization rule participates in approval.

This policy becomes the initial business policy consumed by Approval Authorization.

Authorization Foundation remains unchanged.

---

# Approval Rule

Approval is granted only when **all** of the following conditions are true.

1. The requester is associated with an HrEmployee.
2. The approver is associated with an HrEmployee.
3. The approver is the direct manager of the requester.

Formally:

```
request.employee.manager_id
==
approver.employee.id
```

No additional authorization rule shall be evaluated.

---

# Direct Manager Definition

The platform recognizes exactly one direct manager relationship.

The direct manager is defined exclusively by:

```
HrEmployee.manager_id
```

No:

- recursive traversal
- hierarchy inference
- organizational lookup
- reporting chain expansion

is performed.

Only this relationship participates in Approval Authorization.

---

# Architecture

```
CurrentUser
        │
        ▼
EmployeeContext
        │
        ▼
RequestContext
        │
        ▼
AuthorizationRequest
        │
        ▼
AuthorizationService
        │
        ▼
ApprovalAuthorizationEvaluator
        │
        ▼
Manager Approval Policy
        │
        ▼
AuthorizationDecision
        │
        ▼
ApprovalService
        │
        ▼
Business Workflow
```

Responsibilities remain clearly separated.

---

# Responsibilities

## Authorization Foundation

Owns:

- AuthorizationRequest
- AuthorizationDecision
- AuthorizationEvaluator
- AuthorizationService

Responsibilities:

- authorization mechanism
- authorization evaluation flow

Does **not** own:

- business policy
- approval rules
- workflow

---

## ApprovalAuthorizationEvaluator

Owns:

- manager authorization evaluation

Consumes:

- AuthorizationRequest

Produces:

- AuthorizationDecision

Must remain:

- deterministic
- stateless
- policy-focused

Must not:

- execute workflow
- access HTTP
- perform persistence
- perform repository orchestration

---

## ApprovalService

Owns:

- approval workflow
- approval state transition
- repository coordination

Consumes:

- AuthorizationDecision

Must never:

- evaluate authorization
- infer manager hierarchy
- contain authorization rules

---

## API

Owns:

- authentication
- request validation
- HTTP mapping

Must never:

- evaluate authorization
- determine approvers

---

# Repository Evidence

Current repository already contains:

- HrEmployee.manager_id
- EmployeeContext
- RequestContext
- Authorization Foundation
- ApprovalService

No new business relationship is required.

No database redesign is required.

---

# Explicit Constraints

Implementation shall:

- evaluate only the direct manager relationship
- consume EmployeeContext
- produce AuthorizationDecision
- integrate through AuthorizationService
- preserve existing layering

Implementation shall not:

- traverse manager hierarchy
- infer organizational hierarchy
- introduce approval roles
- introduce ownership rules
- introduce delegated approval
- redesign ApprovalService
- redesign Authorization Foundation

---

# Explicit Exclusions

The following are explicitly outside the scope of this policy.

- indirect managers
- delegated approvers
- organizational hierarchy
- approval roles
- ownership inference
- workflow assignment
- recursive manager traversal
- HR override
- approval delegation
- multiple approvers

A requester cannot approve their own request because the approval rule requires the approver to be the requester's direct manager.

No explicit self-approval rule exists beyond the approval policy itself.

---

# Deferred Capabilities

Future capabilities may extend Approval Authorization with:

- delegated approval
- recursive hierarchy
- organizational approval
- workflow assignment
- role-based approval
- hybrid approval
- HR override
- approval delegation

Such capabilities extend this policy.

They do not replace the Authorization Foundation.

---

# Alternatives Considered

## Assigned Approver

Rejected.

Repository contains no assignment capability.

Introducing assignment would require a workflow capability that does not currently exist.

---

## Role-Based Approval

Rejected.

Repository contains RBAC infrastructure but no approval role vocabulary.

Selecting approval roles would require an architectural decision beyond this capability.

---

## Workflow Assignment

Rejected.

Repository contains no workflow engine or assignment mechanism.

---

## Hybrid Policy

Rejected.

Hybrid authorization depends on capabilities that are intentionally deferred.

---

# Consequences

Approval Authorization now has an explicit business policy.

Authorization Foundation remains policy-agnostic.

ApprovalService remains workflow-only.

Business authorization becomes deterministic.

Future capabilities extend the approval policy without requiring changes to the Authorization Foundation.

---

# Risks

Current policy supports only direct manager approval.

Organizations requiring:

- delegated approval
- matrix organizations
- multiple managers
- temporary approvers

will require future capability extensions.

This limitation is intentional.

---

# Success Criteria

The capability is considered successful when:

- only direct managers can approve
- non-managers are denied
- Authorization Foundation remains unchanged
- ApprovalService contains no authorization logic
- layering remains preserved
- no database schema changes are required

---

# References

- ADR-004 — Identity Context
- ADR-005 — Authorization Context Model
- ADR-006 — Employee Context Resolution
- ADR-007 — Authorization Foundation
- ADR-008 — Approval Authorization Policy Model
- Approval Authorization Discovery
- Approval Authorization Policy Discovery
- MASTER_ARCHITECTURE_BLUEPRINT.md
- ARCHITECTURE_PRINCIPLES.md

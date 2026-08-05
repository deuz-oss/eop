# Approval Authorization — Policy Discovery

**Capability:** Approval Authorization

**Status:** Discovery

---

# Purpose

This document evaluates candidate approval authorization policies using repository evidence.

It does not define architecture.

It does not choose implementation.

Its purpose is to determine which policy models are technically feasible within the current platform and which require future architectural work.

This document serves as the repository evidence supporting the subsequent Capability Decision.

---

# Background

Repository discovery established the following facts.

Existing platform capabilities:

- Authentication exists.
- Identity Context exists.
- Employee Context exists.
- Authorization Foundation exists.
- Approval workflow exists.

Missing capabilities:

- Approval authorization.
- Ownership authorization.
- Manager authorization.
- Permission model.
- Workflow assignment.
- Approval policy.

The remaining architectural question is:

> Who is allowed to approve a business request?

---

# Candidate Policy Models

The following policy models were evaluated.

---

# Policy A — Assigned Approver

## Description

Approval is granted only to the user explicitly assigned as the approver.

Conceptually:

```
current_user.id == approver_id
```

---

## Repository Evidence

Current repository contains:

- `approved_by`
- `approved_at`

These fields record approval history only.

Repository does **not** contain:

- approver assignment
- approval queue
- approval routing
- assigned approver relationship

ApprovalService receives:

```
current_user.id
```

but no assigned approver information.

---

## Repository Support

**Low**

Repository has approval audit fields but no approval assignment model.

---

## Advantages

- Explicit authorization.
- Deterministic.
- Easy to audit.
- Independent of HR hierarchy.

---

## Disadvantages

Requires introducing an assignment model.

---

## Missing Repository Support

- approver assignment
- assignment lifecycle
- assignment persistence

---

## Future Compatibility

Excellent.

Supports workflow engines naturally.

---

# Policy B — Manager Approval

## Description

Approval is granted to the requester's manager.

---

## Repository Evidence

Repository contains:

```
HrEmployee.manager_id
```

Current usage:

- existence validation
- self-manager validation

Repository does **not** use manager_id for:

- authorization
- approval
- ownership
- hierarchy traversal

No service traverses management hierarchy.

---

## Repository Support

Partial.

The relationship exists.

Authorization logic does not.

---

## Advantages

Natural HR workflow.

Simple business model.

---

## Disadvantages

Hierarchy assumptions become business policy.

Indirect managers unsupported.

Delegation unsupported.

---

## Missing Repository Support

- manager authorization
- hierarchy traversal
- delegation
- escalation

---

## Future Compatibility

Good.

Requires additional hierarchy capabilities.

---

# Policy C — Role-Based Approval

## Description

Approval is granted according to RBAC.

---

## Repository Evidence

Repository contains:

- Role
- UserRole
- RequireRole

Current usage:

```
admin
```

only.

Repository does **not** define:

- APPROVER
- HR_ADMIN
- SUPERVISOR
- approval permissions

Authorization Foundation is permission-agnostic.

---

## Repository Support

Partial.

RBAC infrastructure exists.

Approval vocabulary does not.

---

## Advantages

Well understood.

Easy to audit.

Centralized authorization.

---

## Disadvantages

Business role vocabulary required.

Policy maintenance required.

---

## Missing Repository Support

- approval roles
- permission model
- approval policy

---

## Future Compatibility

Excellent.

---

# Policy D — Workflow Assignment

## Description

Approval is determined by workflow assignment.

---

## Repository Evidence

Repository contains no:

- workflow engine
- approval queue
- workflow assignment
- workflow routing
- assignment persistence

ApprovalService performs workflow orchestration only.

---

## Repository Support

None.

---

## Advantages

Most flexible.

Supports complex organizations.

---

## Disadvantages

Requires a workflow platform.

High implementation cost.

---

## Missing Repository Support

Everything required.

---

## Future Compatibility

Excellent.

---

# Policy E — Hybrid

## Description

Combination of multiple policies.

Examples:

- Role + Manager
- Manager + Assignment
- Role + Assignment

---

## Repository Evidence

Hybrid depends on multiple capabilities that are individually incomplete.

Repository currently lacks:

- approval roles
- assignment
- ownership
- hierarchy authorization

---

## Repository Support

Very Low.

---

## Advantages

Maximum flexibility.

---

## Disadvantages

Highest complexity.

Requires several future capabilities.

---

## Future Compatibility

Excellent.

---

# Comparison Matrix

| Policy              | Repository Support | Complexity | Extensibility | Current Recommendation |
| ------------------- | ------------------ | ---------- | ------------- | ---------------------- |
| Assigned Approver   | Low                | Low        | Excellent     | Future                 |
| Manager Approval    | Partial            | Medium     | Good          | Candidate              |
| Role Approval       | Partial            | Medium     | Excellent     | Candidate              |
| Workflow Assignment | None               | High       | Excellent     | Future                 |
| Hybrid              | Very Low           | Very High  | Excellent     | Future                 |

---

# Repository Constraints

Current repository does not provide:

- approval assignment
- approval routing
- ownership framework
- permission model
- approval role vocabulary
- workflow engine

Manager hierarchy exists only as a structural relationship.

No authorization capability consumes it.

---

# Architecture Constraints

Relevant architectural constraints:

**ADR-005**

Implementation must not invent approval policy.

Implementation must not infer manager authorization.

Implementation must not introduce role vocabulary.

---

**ADR-007**

Authorization Foundation remains policy-agnostic.

---

**ADR-008**

Approval policy belongs to architecture.

Implementation consumes policy.

Implementation does not define policy.

---

# Risks

## Assigned Approver

Cannot be implemented without assignment capability.

---

## Manager Approval

May introduce hidden organizational assumptions.

---

## Role Approval

Requires business role vocabulary.

---

## Workflow Assignment

Requires an entirely new platform capability.

---

## Hybrid

Combines the risks of multiple policies.

---

# Open Questions

Business questions remaining:

- Who assigns approvers?
- Can approvers be delegated?
- Can multiple approvers exist?
- Is approval hierarchical?
- Is approval organizational?
- Are approval roles permanent?
- Can external approvers exist?

These are business decisions rather than repository questions.

---

# Recommendation

Repository discovery is complete.

No additional repository investigation is required.

The remaining work is an architectural decision.

The next artifact should be:

**Capability Decision — Approval Authorization Policy**

That decision must select exactly one initial approval policy.

Implementation should not begin until that decision has been approved.

---

# References

- ADR-004
- ADR-005
- ADR-006
- ADR-007
- ADR-008
- Approval Authorization Discovery
- MASTER_ARCHITECTURE_BLUEPRINT.md
